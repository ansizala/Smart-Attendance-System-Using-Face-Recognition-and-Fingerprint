"""Absent-student detection and parent notification workflow."""

import csv
from datetime import datetime

from services.google_service import get_sheet_data
from services.esp32_sms_service import send_sms

CSV_FILE = "student_info.csv"


def check_absentees():
    """Notify parents for students who were not marked present today."""

    print("\n[INFO] Checking absentees...")

    today = datetime.now().strftime("%d-%m-%Y")
    students = []

    try:
        with open(CSV_FILE) as f:
            reader = csv.DictReader(f)

            for row in reader:
                students.append({
                    "name": row["Name"].strip(),
                    "enrollment": row["Enrollment"].strip(),
                    "phone": row.get("ParentPhone", "").strip()
                })

    except Exception as exc:
        print("[ERROR] Error loading student file:", exc)
        return

    print(f"[INFO] Loaded {len(students)} students")

    try:
        data = get_sheet_data(raise_on_error=True)
    except Exception as exc:
        print("[ERROR] Google Sheet error:", exc)
        return

    present_today = set()
    data_rows = []

    if not data:
        print("[WARNING] Attendance sheet is empty; treating all students as absent")
    else:
        data_rows = data[1:]
        if not data_rows:
            print("[WARNING] No attendance rows found; treating all students as absent")

    for row in data_rows:
        try:
            date = row[0].strip()
            enrollment = row[1].strip()

            if date == today:
                present_today.add(enrollment)

        except Exception as exc:
            print("Row error:", exc)
            continue

    print("[OK] Present today:", present_today)

    absent_count = 0
    notified_count = 0
    missing_phone_count = 0

    for student in students:

        name = student["name"]
        enrollment = student["enrollment"]
        phone = student["phone"]

        print(f"Checking: {name} ({enrollment})")

        if enrollment not in present_today:
            absent_count += 1

            print(f"[WARNING] Absent: {name}")

            if phone:

                phone = phone.replace(" ", "").replace("-", "")

                try:
                    print(f"[INFO] Sending SMS to {phone}")

                    send_sms(
                        phone,
                        name,
                        today,
                        "Absent",
                        "absent"
                    )
                    notified_count += 1

                except Exception as exc:
                    print(f"[ERROR] SMS failed for {name}:", exc)

            else:
                print(f"[WARNING] No phone for {name}")
                missing_phone_count += 1

    print(
        "[INFO] Absentee check complete:",
        f"{absent_count} absent,",
        f"{notified_count} SMS attempted,",
        f"{missing_phone_count} missing parent phone"
    )
