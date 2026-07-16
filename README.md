# Smart Attendance System using Face Recognition and Fingerprint Authentication

An AI-powered Smart Attendance System that combines **Face Recognition**, **Fingerprint Authentication**, **ESP32**, **IoT**, and **Cloud Integration** to provide a secure, automated, and real-time attendance management solution.

This project was developed to eliminate manual attendance, prevent proxy attendance, and provide real-time attendance monitoring with cloud storage and automated notifications.

---

# Features

- Face Recognition using Python and OpenCV
- Fingerprint Authentication using ESP32
- Dual Biometric Authentication
- Student Registration System
- Automated Attendance Marking
- Google Sheets Cloud Integration
- Parent SMS Notification using SIM800L GSM Module
- Faculty Email Notification
- Attendance Dashboard
- Student Management System
- Attendance Analytics
- Real-time Attendance Logs
- LED Status Indicators
- Professional Desktop GUI

---

# Project Overview

The Smart Attendance System verifies the identity of a student using two levels of authentication:

1. Face Recognition
2. Fingerprint Verification

Attendance is recorded only when both authentications are successful.

The attendance data is automatically uploaded to Google Sheets, while SMS notifications are sent to parents and attendance reports are emailed to faculty members.

---

# Hardware Components

| Component | Quantity |
|------------|----------|
| ESP32 Development Board | 1 |
| Fingerprint Sensor | 1 |
| Laptop / PC | 1 |
| Webcam | 1 |
| SIM800L GSM Module | 1 |
| Green LED | 1 |
| Red LED | 1 |
| Blue LED | 1 |
| Breadboard | 1 |
| Jumper Wires | As Required |
| USB Cable | 1 |

---

# Software & Technologies

- Python
- OpenCV
- Face Recognition Library
- Tkinter
- ESP32
- Arduino IDE
- Google Sheets API
- gspread
- SMTP Email Service
- CSV
- NumPy
- Pandas

---

# Project Architecture

```
                   Student

                      │

                      ▼

             Webcam (Face Capture)

                      │

                      ▼

        Face Recognition (Python + OpenCV)

                      │

           Face Verified ?

                Yes

                      │

                      ▼

        ESP32 Fingerprint Verification

                      │

       Fingerprint Verified ?

                Yes

                      │

                      ▼

          Attendance Recorded

                      │

        ┌─────────────┼─────────────┐

        ▼             ▼             ▼

 Google Sheets     SMS Alert     Email Report

        │

        ▼

 Dashboard & Analytics
```

---

# Project Structure

```
Smart_Attendance_Project/
│
├── main.py
├── attendance.py
├── register.py
├── register_professional.py
├── live_detection.py
├── train_model.py
├── config.py
├── faculty_notify.py
├── calculate_percentage.py
├── camera_test.py
│
├── services/
│   ├── absence_service.py
│   ├── camera_service.py
│   ├── esp32_discovery.py
│   ├── esp32_service.py
│   ├── esp32_sms_service.py
│   ├── face_recognition_model.py
│   ├── face_utils.py
│   ├── google_service.py
│   └── thread_service.py
│
├── ui/
│   ├── dashboard.py
│   ├── students.py
│   ├── logs.py
│   ├── charts_professional.py
│   ├── sidebar.py
│   └── theme.py
│
├── trainer/
│
├── dataset/
│
├── ESP32_CODE/
│
└── README.md
```

---

# Working Flow

### Student Registration

- Enter Student Details
- Capture Face Images
- Enroll Fingerprint
- Save Student Information

### Attendance Process

- Capture Face
- Verify Face
- Verify Fingerprint
- Record Attendance
- Upload to Google Sheets
- Send SMS Notification
- Send Faculty Email
- Update Dashboard

---

# Hardware Setup

The hardware section includes:

- ESP32 Development Board
- Fingerprint Sensor
- SIM800L GSM Module
- LED Indicators
- Webcam
- Breadboard Connections

---

# Modules

## Face Recognition Module

- Face Detection
- Face Encoding
- Face Matching
- Dataset Generation

## Fingerprint Module

- Fingerprint Enrollment
- Fingerprint Verification

## ESP32 Module

- Hardware Communication
- Sensor Control
- Wi-Fi Communication

## IoT Module

- Google Sheets Integration
- Cloud Attendance Storage

## Notification Module

- Parent SMS
- Faculty Email

## Dashboard Module

- Student Records
- Attendance Logs
- Charts
- Attendance Percentage

---

# Key Features

✔ Dual Biometric Authentication

✔ Prevents Proxy Attendance

✔ Cloud-Based Attendance Storage

✔ Real-Time Notifications

✔ Automated Attendance

✔ Desktop GUI

✔ ESP32 Integration

✔ IoT Enabled

✔ Secure Authentication

✔ Easy to Use

---

# Applications

- Schools
- Colleges
- Universities
- Coaching Institutes
- Offices
- Organizations
- Laboratories
- Training Centers

---

# Advantages

- Eliminates Manual Attendance
- Prevents Fake Attendance
- High Accuracy
- Secure Authentication
- Cloud Storage
- Real-Time Monitoring
- Automatic Notifications
- Easy Record Management

---

# Future Enhancements

- Mobile Application
- Firebase Integration
- Face Anti-Spoofing
- AI Attendance Analytics
- Web Dashboard
- RFID Integration
- QR Code Attendance
- Cloud Database
- Multi-Campus Support

---

# Author

**Mansi Zala**

Bachelor of Technology (Electronics & Communication Engineering)

Passionate about Embedded Systems, IoT, Artificial Intelligence, Computer Vision, and Smart Automation.

---

# License

This project is developed for educational and research purposes.
