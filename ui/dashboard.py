"""Dashboard overview page for operational status and quick actions."""

import csv
import os
import subprocess
import sys
import threading
from datetime import datetime
from tkinter import messagebox

import ttkbootstrap as tb

from config import get_esp32_ip
from services.esp32_service import clear_fingerprint_database
from services.google_service import get_sheet_data
from ui.theme import COLORS, build_scrollable_page, create_card, create_key_value_row, create_metric_card

_SCRIPT_PROCESSES = {}


def _is_script_running(script_name):
    """Return whether the dashboard already has an active child process for a script."""

    process = _SCRIPT_PROCESSES.get(script_name)
    if process is None:
        return False

    if process.poll() is None:
        return True

    _SCRIPT_PROCESSES.pop(script_name, None)
    return False


def _launch_script(script_name, window_label):
    """Start a child Python script unless an existing instance is still running."""

    if _is_script_running(script_name):
        messagebox.showinfo("Already Running", f"{window_label} is already running.")
        return False

    try:
        process = subprocess.Popen([sys.executable, script_name], cwd=os.getcwd())
    except Exception as exc:
        messagebox.showerror(
            "Launch Error",
            f"Unable to start {window_label.lower()}.\n\n{exc}",
        )
        return False

    _SCRIPT_PROCESSES[script_name] = process
    return True


def show_dashboard(content):
    """Render the main operational dashboard view."""

    existing_refresh = getattr(content, "_dashboard_launch_refresh_id", None)
    if existing_refresh:
        try:
            content.after_cancel(existing_refresh)
        except Exception:
            pass
        content._dashboard_launch_refresh_id = None

    _page, body = build_scrollable_page(
        content,
        "Dashboard",
    )

    today_date = datetime.now().strftime("%d-%m-%Y")
    last_entry_text = "Loading attendance data..."

    launch_buttons = {}

    def refresh_launch_buttons():
        """Keep dashboard quick-action buttons aligned with live child process state."""

        if not content.winfo_exists():
            return

        for script_name, button in launch_buttons.items():
            if button.winfo_exists():
                button.configure(
                    state="disabled" if _is_script_running(script_name) else "normal"
                )

        content._dashboard_launch_refresh_id = content.after(1500, refresh_launch_buttons)

    def run_script(script_name, window_label):
        if _launch_script(script_name, window_label):
            button = launch_buttons.get(script_name)
            if button and button.winfo_exists():
                button.configure(state="disabled")

    def reset_fingerprints():
        confirmed = messagebox.askyesno(
            "Reset Fingerprints",
            "Clear all fingerprint templates from the ESP32 sensor?\n\n"
            "Use this when local student IDs and sensor IDs are out of sync. "
            "You will need to re-enroll fingerprints for existing students afterward.",
        )

        if not confirmed:
            return

        if clear_fingerprint_database():
            messagebox.showinfo(
                "Fingerprint Sensor Reset",
                "Fingerprint database cleared successfully.\n\n"
                "Re-enroll fingerprints from each student's profile before starting attendance again.",
            )
        else:
            messagebox.showerror(
                "Reset Failed",
                "Could not clear the fingerprint database.\n\n"
                "Make sure the ESP32 is connected and try again.",
            )

    actions_card = create_card(body, padding=18)
    actions_card.pack(fill="x", pady=(0, 18))

    actions_info = tb.Frame(actions_card, style="Card.TFrame")
    actions_info.pack(side="left", fill="x", expand=True)

    tb.Label(actions_info, text="Quick Actions", style="SectionTitle.TLabel").pack(anchor="w")
    latest_entry_label = tb.Label(
        actions_info,
        text=f"Latest entry: {last_entry_text}",
        style="Muted.TLabel",
        justify="left",
        wraplength=520,
    )
    latest_entry_label.pack(anchor="w", pady=(6, 0))

    hero_actions = tb.Frame(actions_card, style="Card.TFrame")
    hero_actions.pack(side="right", padx=(18, 0))

    register_button = tb.Button(
        hero_actions,
        text="Register Student",
        width=18,
        bootstyle="primary",
        command=lambda: run_script("register_professional.py", "Student registration"),
    )
    register_button.pack(fill="x", pady=(4, 10))

    attendance_button = tb.Button(
        hero_actions,
        text="Start Attendance",
        width=18,
        bootstyle="secondary",
        command=lambda: run_script("attendance.py", "Attendance"),
    )
    attendance_button.pack(fill="x")

    reset_button = tb.Button(
        hero_actions,
        text="Reset Fingerprints",
        width=18,
        bootstyle="danger-outline",
        command=reset_fingerprints,
    )
    reset_button.pack(fill="x", pady=(10, 0))

    launch_buttons["register_professional.py"] = register_button
    launch_buttons["attendance.py"] = attendance_button

    metrics = tb.Frame(body, style="App.TFrame")
    metrics.pack(fill="x", pady=(0, 22))

    for index in range(4):
        metrics.columnconfigure(index, weight=1)

    metric_specs = [
        ("Registered Students", "...", "Total student records available in the system.", COLORS["accent"]),
        ("Present Today", "...", "Students marked for the current date.", COLORS["success"]),
        ("Working Days", "...", "Unique attendance dates recorded so far.", COLORS["warning"]),
        ("Avg Attendance", "...", "Average attendance percentage across recorded students.", COLORS["danger"]),
    ]
    metric_cards = []

    for column, (title, value, note, accent) in enumerate(metric_specs):
        card = create_metric_card(metrics, title, value, note, accent)
        card.grid(row=0, column=column, padx=10, sticky="nsew")
        metric_cards.append(card)

    lower = tb.Frame(body, style="App.TFrame")
    lower.pack(fill="x")
    lower.columnconfigure(0, weight=1)
    lower.columnconfigure(1, weight=1)

    summary_card = create_card(lower, padding=24)
    summary_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

    tb.Label(summary_card, text="Today's Summary", style="SectionTitle.TLabel").pack(anchor="w")
    create_key_value_row(summary_card, "Current date", today_date)
    last_entry_row = create_key_value_row(summary_card, "Latest entry", last_entry_text)
    esp32_row = create_key_value_row(summary_card, "ESP32 status", "Checking...")
    source_row = create_key_value_row(summary_card, "Attendance source", "Loading...")
    create_key_value_row(summary_card, "Dashboard status", "Ready for live operations")

    workflow_card = create_card(lower, padding=24)
    workflow_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    tb.Label(workflow_card, text="Attendance Guide", style="SectionTitle.TLabel").pack(anchor="w")

    steps = [
        "1. Register or update student profiles before starting a new attendance session.",
        "2. Start attendance to begin live face recognition and presence verification.",
        "3. Review logs and analytics to track records, activity, and attendance trends.",
    ]

    for step in steps:
        tb.Label(
            workflow_card,
            text=step,
            style="Body.TLabel",
            justify="left",
            wraplength=420,
        ).pack(anchor="w", pady=4)

    refresh_launch_buttons()
    _load_dashboard_snapshot_async(
        _page,
        latest_entry_label,
        metric_cards,
        last_entry_row,
        esp32_row,
        source_row,
    )


def _build_dashboard_snapshot():
    """Collect dashboard metrics without blocking the UI thread."""

    today_date = datetime.now().strftime("%d-%m-%Y")
    registered_enrollments = _load_registered_enrollments()
    registered_student_count = len(registered_enrollments)

    snapshot = {
        "registered_students": registered_student_count,
        "present_today": 0,
        "working_days": 0,
        "avg_attendance": "0.0%",
        "last_entry_text": "No attendance marked yet",
        "esp32_status": "Unknown",
        "attendance_source": "Google Sheets sync",
    }

    try:
        data = get_sheet_data()
        rows = data[1:] if len(data) > 1 else []

        unique_dates = {row[0] for row in rows if len(row) >= 1 and row[0]}
        present_days_by_enrollment = {}

        for row in rows:
            if len(row) < 2:
                continue

            date = row[0]
            enrollment = row[1]
            present_days_by_enrollment.setdefault(enrollment, set()).add(date)

        working_days = len(unique_dates)
        today_present = len({row[1] for row in rows if len(row) >= 2 and row[0] == today_date})
        attendance_population = registered_student_count or len(present_days_by_enrollment)

        overall_percent = 0.0
        if working_days and attendance_population:
            enrollments_for_average = registered_enrollments or list(present_days_by_enrollment.keys())
            total_percent = sum(
                (len(present_days_by_enrollment.get(enrollment, set())) / working_days) * 100
                for enrollment in enrollments_for_average
            )
            overall_percent = total_percent / attendance_population

        last_entry = rows[-1] if rows else None
        if last_entry and len(last_entry) >= 4:
            last_entry_text = f"{last_entry[2]} on {last_entry[0]} at {last_entry[3]}"
        else:
            last_entry_text = "No attendance marked yet"

        snapshot.update(
            {
                "registered_students": registered_student_count,
                "present_today": today_present,
                "working_days": working_days,
                "avg_attendance": f"{overall_percent:.1f}%",
                "last_entry_text": last_entry_text,
            }
        )
    except Exception as exc:
        snapshot["attendance_source"] = f"Google Sheets unavailable ({exc})"

    snapshot["esp32_status"] = _get_esp32_status()
    return snapshot


def _load_dashboard_snapshot_async(
    page,
    latest_entry_label,
    metric_cards,
    last_entry_row,
    esp32_row,
    source_row,
):
    """Populate the dashboard after slow I/O completes in the background."""

    result = {}

    def apply_snapshot(snapshot):
        if not page.winfo_exists():
            return

        latest_entry_label.configure(text=f"Latest entry: {snapshot['last_entry_text']}")
        metric_cards[0].value_label.configure(text=str(snapshot["registered_students"]))
        metric_cards[1].value_label.configure(text=str(snapshot["present_today"]))
        metric_cards[2].value_label.configure(text=str(snapshot["working_days"]))
        metric_cards[3].value_label.configure(text=snapshot["avg_attendance"])
        last_entry_row.value_widget.configure(text=snapshot["last_entry_text"])
        esp32_row.value_widget.configure(text=snapshot["esp32_status"])
        source_row.value_widget.configure(text=snapshot["attendance_source"])

    def worker():
        result["snapshot"] = _build_dashboard_snapshot()

    load_thread = threading.Thread(target=worker, daemon=True)
    load_thread.start()

    def poll_for_result():
        if not page.winfo_exists():
            return

        if load_thread.is_alive():
            page.after(120, poll_for_result)
            return

        snapshot = result.get("snapshot")
        if snapshot is not None:
            apply_snapshot(snapshot)

    page.after(120, poll_for_result)


def _load_registered_enrollments():
    """Load all registered enrollment numbers from the local student registry."""

    if not os.path.exists("student_info.csv"):
        return []

    with open("student_info.csv", newline="") as csv_file:
        return [
            row["Enrollment"].strip()
            for row in csv.DictReader(csv_file)
            if row.get("Enrollment", "").strip()
        ]


def _get_esp32_status():
    """Return a simple connectivity label for the ESP32 controller."""

    try:
        return "Connected" if get_esp32_ip(force_refresh=True) else "Not connected"
    except Exception:
        return "Unknown"
