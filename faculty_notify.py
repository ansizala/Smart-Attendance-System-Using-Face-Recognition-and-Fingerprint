"""Email notification helper for sending the session summary to faculty."""

import smtplib
from email.mime.text import MIMEText

EMAIL = "ictgpga2025@gmail.com"
PASSWORD = "dnmj agqk ojwi whbu"

FACULTY_EMAILS = [
    "riyakunvarba.gpga.ict@gmail.com",
    "mansidzala@gmail.com"
]

SHEET_LINK = "https://docs.google.com/spreadsheets/d/1Df4nILk3uGv9M2b6JzgjeSbV7mxudx0F-15tshhonNU/edit?usp=sharing"


def send_faculty_report():
    """Send the attendance sheet link to every configured faculty recipient."""

    subject = "Attendance Report (Auto Generated)"

    body = f"""
Dear Sir/Madam,

Attendance session has been completed.

You can view the updated attendance here:
{SHEET_LINK}

Regards,
Smart Attendance System
"""

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL, PASSWORD)

        # Create a fresh message per recipient so the headers stay accurate.
        for faculty in FACULTY_EMAILS:

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = EMAIL
            msg["To"] = faculty

            server.sendmail(EMAIL, faculty, msg.as_string())

        server.quit()

        print("[INFO] Faculty notified successfully")

    except Exception as exc:
        print("[ERROR] Email failed:", exc)
