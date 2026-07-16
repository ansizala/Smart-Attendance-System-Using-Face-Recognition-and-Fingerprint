"""Live attendance workflow for face recognition and fingerprint verification."""

import cv2
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from config import (
    FRAME_SKIP,
    RECOGNIZED_GRACE_SECONDS,
    UNKNOWN_ALERT_COOLDOWN,
    UNKNOWN_STABLE_SECONDS,
)
from faculty_notify import send_faculty_report
from services.absence_service import check_absentees
from services.camera_service import CameraService
from services.network_worker import NetworkWorker

camera = None
network_worker = None
verification_executor = None
marked = set()
marked_lock = threading.Lock()
state_lock = threading.Lock()

last_unknown_time = 0.0
last_recognized_time = 0.0
unknown_since = 0.0
frame_count = 0

# Runtime tuning values that keep the loop responsive without spamming retries.
RETRY_COOLDOWN_SECONDS = 5
STATUS_BANNER_SECONDS = 3

# Shared UI state for the fingerprint verification workflow.
verification_state = {
    "active": False,
    "student_id": None,
    "name": "",
    "message": "",
    "message_time": 0.0,
}

last_attempt_time = {}


def initialize_runtime():
    """Reset in-memory state before a new attendance session starts."""

    global camera, network_worker, verification_executor
    global marked, last_unknown_time, last_recognized_time
    global unknown_since, frame_count, verification_state, last_attempt_time

    print("\n=== AI SMART ATTENDANCE SYSTEM STARTED ===\n")

    camera = CameraService()
    network_worker = NetworkWorker()
    network_worker.start()
    verification_executor = ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix="attendance-verify",
    )
    marked = set()
    last_unknown_time = 0.0
    last_recognized_time = time.time()
    unknown_since = 0.0
    frame_count = 0
    verification_state = {
        "active": False,
        "student_id": None,
        "name": "",
        "message": "",
        "message_time": 0.0,
    }
    last_attempt_time = {}


def set_status(message):
    """Store the most recent banner message shown over the camera feed."""

    with state_lock:
        verification_state["message"] = message
        verification_state["message_time"] = time.time()


def is_verification_active():
    """Return whether a fingerprint verification is currently in progress."""

    with state_lock:
        return verification_state["active"]


def should_retry(student_id, current_time):
    """Avoid repeated verification attempts for the same student in a short window."""

    with state_lock:
        return current_time - last_attempt_time.get(student_id, 0) >= RETRY_COOLDOWN_SECONDS


def draw_status_banner(frame):
    """Render the current verification or result banner on the frame."""

    with state_lock:
        active = verification_state["active"]
        active_name = verification_state["name"]
        message = verification_state["message"]
        message_time = verification_state["message_time"]

    if active:
        text = f"Verify fingerprint: {active_name}"
        color = (0, 165, 255)
    elif message and time.time() - message_time < STATUS_BANNER_SECONDS:
        text = message
        if "marked" in message.lower():
            color = (0, 180, 0)
        elif any(
            token in message.lower()
            for token in ("failed", "mismatch", "offline", "not detected", "not recognized")
        ):
            color = (0, 0, 255)
        else:
            color = (255, 200, 0)
    else:
        return

    (text_width, text_height), _ = cv2.getTextSize(
        text,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        2
    )

    banner_width = min(frame.shape[1] - 20, text_width + 30)

    cv2.rectangle(frame, (10, 10), (10 + banner_width, 50), color, -1)
    cv2.putText(
        frame,
        text,
        (20, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2
    )


def draw_performance_overlay(frame, frame_state):
    """Render rolling FPS and queue metrics so regressions are easy to spot."""

    metrics = frame_state.get("metrics") or {}
    network_metrics = network_worker.metrics() if network_worker is not None else {}

    overlay_lines = [
        f"FPS {metrics.get('fps', 0):>4}",
        f"Detect {metrics.get('detect_ms', 0):>4} ms",
        f"Recognize {metrics.get('recognize_ms', 0):>4} ms",
        f"Dropped {metrics.get('dropped_frames', 0)}",
        f"Net {network_metrics.get('pending_requests', 0)} | Sheet {network_metrics.get('pending_sheet_rows', 0)}",
    ]

    left = frame.shape[1] - 250
    top = 10
    bottom = top + (len(overlay_lines) * 22) + 14

    cv2.rectangle(frame, (left, top), (frame.shape[1] - 10, bottom), (20, 20, 20), -1)

    for index, line in enumerate(overlay_lines):
        cv2.putText(
            frame,
            line,
            (left + 10, top + 22 + (index * 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 220, 220),
            1,
        )


def finish_verification(student_id):
    """Release the verification lock and start the retry cooldown for the student."""

    with state_lock:
        verification_state["active"] = False
        verification_state["student_id"] = None
        verification_state["name"] = ""
        last_attempt_time[student_id] = time.time()


def process_attendance(student):
    """Verify a student's fingerprint and write the attendance record."""

    student_id = student["id"]
    name = student["name"]
    enrollment = student["enrollment"]
    parent = student["parent"]

    try:
        print(f"\n[INFO] Face detected: {name}")

        verification_result = network_worker.verify_fingerprint_async(student_id).result()
        if verification_result != "MATCH":
            if verification_result.startswith("NO_MATCH"):
                network_worker.enqueue_security_alert()
                scanned_id = verification_result.split(":", 1)[1] if ":" in verification_result else ""
                print("[WARNING] Fingerprint mismatch")
                if scanned_id:
                    print(f"[INFO] Fingerprint matched stored ID {scanned_id}, expected ID {student_id}")
                    print(
                        f"[ACTION] Re-enroll fingerprint for {name} as sensor ID {student_id}, "
                        "or clear the sensor database if local IDs were reset."
                    )
                    set_status(
                        f"Fingerprint mismatch: {name} (sensor {scanned_id}, expected {student_id}). "
                        "Re-enroll fingerprint."
                    )
                else:
                    print(
                        f"[ACTION] Re-enroll fingerprint for {name} if the sensor database was changed."
                    )
                    set_status(f"Fingerprint mismatch: {name}. Re-enroll fingerprint.")
            elif verification_result == "NO_FINGER":
                print("[WARNING] No finger detected")
                set_status(f"Fingerprint not detected: {name}")
            elif verification_result == "NOT_FOUND":
                network_worker.enqueue_security_alert()
                print("[WARNING] Fingerprint not recognized")
                set_status(f"Fingerprint not recognized: {name}")
            elif verification_result == "ESP32_NOT_FOUND":
                print("[ERROR] Fingerprint sensor offline")
                set_status("Fingerprint sensor offline")
            else:
                print(f"[ERROR] Fingerprint verification failed: {verification_result}")
                set_status(f"Fingerprint check failed: {name}")
            return

        now = datetime.now()
        date = now.strftime("%d-%m-%Y")
        time_now = now.strftime("%H:%M:%S")

        network_worker.enqueue_sheet_row([date, enrollment, name, time_now])

        with marked_lock:
            marked.add(student_id)

        print(f"[OK] Attendance marked: {name}")
        set_status(f"Attendance marked: {name}")

        network_worker.enqueue_attendance_signal(name)

        if parent:
            network_worker.enqueue_sms(parent, name, date, time_now)

    except Exception as exc:
        print(f"[ERROR] Attendance processing failed for {name}: {exc}")
        set_status(f"Failed to mark: {name}")
    finally:
        finish_verification(student_id)


def start_verification(student):
    """Start background fingerprint verification for the recognized student."""

    with state_lock:
        verification_state["active"] = True
        verification_state["student_id"] = student["id"]
        verification_state["name"] = student["name"]
        verification_state["message"] = f"Waiting for fingerprint: {student['name']}"
        verification_state["message_time"] = time.time()
        last_attempt_time[student["id"]] = time.time()

    verification_executor.submit(process_attendance, student.copy())


def main():
    """Run the main attendance loop until the operator stops the session."""

    global frame_count, last_recognized_time, last_unknown_time, unknown_since

    initialize_runtime()
    network_worker.warm_up_async()
    last_result_id = None

    try:
        while True:
            data = camera.read_frame()
            if data is None:
                time.sleep(0.001)
                continue

            frame, frame_state = data
            result_id = frame_state.get("result_id")
            if result_id != last_result_id:
                last_result_id = result_id
                frame_count += 1

                results = frame_state["recognized"]
                should_process = frame_count % FRAME_SKIP == 0
                current_time = time.time()

                if results:
                    unknown_since = 0.0

                if should_process and results:
                    last_recognized_time = current_time

                    if not is_verification_active():
                        for student in results:
                            student_id = student["id"]

                            with marked_lock:
                                already_marked = student_id in marked

                            if already_marked or not should_retry(student_id, current_time):
                                continue

                            start_verification(student)
                            break

                elif frame_state["has_unknown_face"] and not is_verification_active():
                    if current_time - last_recognized_time > RECOGNIZED_GRACE_SECONDS:
                        if unknown_since == 0.0:
                            unknown_since = current_time

                        if current_time - unknown_since >= UNKNOWN_STABLE_SECONDS:
                            if network_worker.enqueue_unknown_alert(UNKNOWN_ALERT_COOLDOWN):
                                last_unknown_time = current_time
                                print("[WARNING] Unknown detected")

                            unknown_since = current_time
                    else:
                        unknown_since = 0.0

                else:
                    unknown_since = 0.0

            draw_status_banner(frame)
            draw_performance_overlay(frame, frame_state)
            cv2.imshow("Smart Attendance System", frame)

            if cv2.waitKey(1) == 27:
                print("\n[INFO] Stopping attendance system...")
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted manually")

    finally:
        if camera is not None:
            camera.release()
        if verification_executor is not None:
            verification_executor.shutdown(wait=True, cancel_futures=False)
        if network_worker is not None:
            network_worker.shutdown()
        cv2.destroyAllWindows()

        print("\n[INFO] Checking absentees...")
        try:
            check_absentees()
        except Exception as exc:
            print("[ERROR] Absentee check failed:", exc)

        print("\n[INFO] Sending report to faculty...")
        try:
            send_faculty_report()
        except Exception as exc:
            print("[ERROR] Faculty notification failed:", exc)

        print("\n[OK] System shutdown complete")


if __name__ == "__main__":
    main()
