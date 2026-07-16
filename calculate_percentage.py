"""Utility script for printing attendance percentage from Google Sheets."""

from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

TOTAL_WORKING_DAYS = 20
SHEET_NAME = "Smart_Attendance_2026"

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
client = gspread.authorize(creds)

sheet = client.open(SHEET_NAME).sheet1

data = sheet.get_all_values()

attendance_count = defaultdict(int)

# Skip header row
for row in data[1:]:
    enrollment = row[1]  # Second column = Enrollment
    attendance_count[enrollment] += 1

print("------ Attendance Percentage Report ------\n")

for enrollment, days_present in attendance_count.items():
    percentage = (days_present / TOTAL_WORKING_DAYS) * 100

    print(f"Enrollment : {enrollment}")
    print(f"Days Present : {days_present}")
    print(f"Attendance % : {percentage:.2f}%")
    print("--------------------------------------")
