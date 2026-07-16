"""Asynchronous network helpers for ESP32 calls and batched Google Sheets writes."""

import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from config import (
    GOOGLE_SHEET_BATCH_FLUSH_SECONDS,
    GOOGLE_SHEET_BATCH_SIZE,
    NETWORK_EXECUTOR_WORKERS,
)
from services.esp32_service import notify_attendance, notify_unknown, verify_fingerprint
from services.esp32_sms_service import send_sms
from services.google_service import append_rows, connect_sheet


class NetworkWorker:
    """Keep slow network operations off the real-time recognition path."""

    def __init__(self):
        self.sheet_queue = queue.Queue(maxsize=256)
        self.stop_event = threading.Event()
        self.sheet_thread = None
        self.request_executor = ThreadPoolExecutor(
            max_workers=NETWORK_EXECUTOR_WORKERS,
            thread_name_prefix="attendance-net",
        )
        self._start_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self._pending_requests = 0
        self._last_unknown_alert = 0.0

    def start(self):
        """Start the background sheet writer once."""

        with self._start_lock:
            if self.sheet_thread and self.sheet_thread.is_alive():
                return

            self.stop_event.clear()
            self.sheet_thread = threading.Thread(
                target=self._sheet_loop,
                daemon=True,
                name="attendance-sheet-writer",
            )
            self.sheet_thread.start()

    def warm_up(self):
        """Warm the Google Sheets connection so the first write is not a cold start."""

        self.start()
        try:
            connect_sheet()
            print("[INFO] Google Sheets ready")
        except Exception as exc:
            print("[WARNING] Google Sheets warm-up failed:", exc)

    def warm_up_async(self):
        """Warm slow network dependencies without blocking the caller."""

        return self._submit_request(self.warm_up)

    def _submit_request(self, func, *args, **kwargs):
        self.start()

        with self._metrics_lock:
            self._pending_requests += 1

        future = self.request_executor.submit(func, *args, **kwargs)

        def _complete(_future):
            with self._metrics_lock:
                self._pending_requests = max(0, self._pending_requests - 1)

        future.add_done_callback(_complete)
        return future

    def verify_fingerprint_async(self, student_id):
        """Run fingerprint verification in the shared request pool."""

        return self._submit_request(verify_fingerprint, student_id)

    def enqueue_sheet_row(self, row):
        """Queue a row for batched Google Sheets writes."""

        self.start()
        try:
            self.sheet_queue.put_nowait(list(row))
        except queue.Full:
            self._submit_request(append_rows, [list(row)])

    def enqueue_attendance_signal(self, name):
        """Trigger the success signal without blocking the caller."""

        self._submit_request(notify_attendance, name)

    def enqueue_sms(self, phone, name, date, time_now, status="present"):
        """Send SMS notifications without blocking the recognition path."""

        self._submit_request(send_sms, phone, name, date, time_now, status)

    def enqueue_unknown_alert(self, cooldown_seconds):
        """Debounce noisy unknown-person alarms before sending them."""

        now = time.monotonic()
        with self._metrics_lock:
            if now - self._last_unknown_alert < cooldown_seconds:
                return False
            self._last_unknown_alert = now

        self._submit_request(notify_unknown)
        return True

    def enqueue_security_alert(self):
        """Trigger the red LED and buzzer immediately for security events."""

        self._submit_request(notify_unknown)
        return True

    def _sheet_loop(self):
        batch = []
        last_flush = time.monotonic()

        while not self.stop_event.is_set() or not self.sheet_queue.empty() or batch:
            timeout = max(
                0.05,
                GOOGLE_SHEET_BATCH_FLUSH_SECONDS - (time.monotonic() - last_flush),
            )

            try:
                row = self.sheet_queue.get(timeout=timeout)
                batch.append(row)
            except queue.Empty:
                row = None

            if batch and (
                len(batch) >= GOOGLE_SHEET_BATCH_SIZE
                or time.monotonic() - last_flush >= GOOGLE_SHEET_BATCH_FLUSH_SECONDS
                or (self.stop_event.is_set() and self.sheet_queue.empty())
            ):
                self._flush_batch(batch)
                batch = []
                last_flush = time.monotonic()

            if row is not None:
                self.sheet_queue.task_done()

    def _flush_batch(self, rows):
        try:
            append_rows(rows)
        except Exception as exc:
            print("[ERROR] Failed to flush attendance rows:", exc)

    def metrics(self):
        """Return lightweight queue metrics for the on-screen performance overlay."""

        with self._metrics_lock:
            return {
                "pending_requests": self._pending_requests,
                "pending_sheet_rows": self.sheet_queue.qsize(),
            }

    def shutdown(self):
        """Flush pending rows and stop background workers cleanly."""

        self.stop_event.set()
        if self.sheet_thread and self.sheet_thread.is_alive():
            self.sheet_thread.join(timeout=2.0)
        self.request_executor.shutdown(wait=True, cancel_futures=False)
