"""ESP32 integration helpers for LEDs, alarms, enrollment, and verification."""

import threading

import requests
from requests.adapters import HTTPAdapter

from config import get_esp32_ip


_thread_local = threading.local()


def _get_session():
    session = getattr(_thread_local, "session", None)
    if session is not None:
        return session

    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
    session.mount("http://", adapter)
    session.headers.update({"Connection": "keep-alive"})
    _thread_local.session = session
    return session


def _request(path, params=None, timeout=5):
    esp32_ip = get_esp32_ip()
    if not esp32_ip:
        esp32_ip = get_esp32_ip(force_refresh=True)
    if not esp32_ip:
        return None, "ESP32_NOT_FOUND"

    try:
        response = _get_session().get(
            f"{esp32_ip}{path}",
            params=params,
            timeout=timeout,
        )
        return response, None
    except Exception as exc:
        return None, exc


def notify_attendance(name):
    """Trigger the success signal on the ESP32 after attendance is marked."""

    response, error = _request("/attendance", params={"name": name}, timeout=3)
    if error == "ESP32_NOT_FOUND":
        print("ESP32 not found")
        return False

    if error is None:
        print("[INFO] Green LED + Buzzer")
        return True

    print("ESP32 error:", error)
    return False


def notify_unknown():
    """Trigger the unknown-person alert on the ESP32."""

    response, error = _request("/unknown", timeout=5)
    if error == "ESP32_NOT_FOUND":
        print("ESP32 not found")
        return False

    try:
        if error is not None:
            raise error
        response.raise_for_status()
        print("[INFO] Red LED + Alarm")
        return True

    except Exception as exc:
        print("ESP32 unknown alert error:", exc)
        return False


def send_sms(phone, name, date, time):
    """Ask the ESP32 service to send a present-status SMS to a parent."""

    response, error = _request(
        "/notify",
        params={
            "phone": phone,
            "name": name,
            "date": date,
            "time": time,
        },
        timeout=5,
    )
    if error == "ESP32_NOT_FOUND":
        print("ESP32 not found")
        return False

    try:
        if error is not None:
            raise error
        print("[INFO] SMS:", response.text)
        return True

    except Exception as exc:
        print("SMS failed:", exc)
        return False


def notify_fingerprint_register(student_id):
    """Start fingerprint enrollment for the given student ID."""

    response, error = _request(
        "/enroll",
        params={"id": student_id},
        timeout=15,
    )
    if error == "ESP32_NOT_FOUND":
        print("ESP32 not found")
        return False

    try:
        print(f"[INFO] Place finger to register (ID: {student_id})")
        if error is not None:
            raise error

        result = response.text.strip()
        print("FP Enroll Response:", result)

        if response.status_code == 200 and result == "ENROLL_SUCCESS":
            print("[OK] Fingerprint enroll success")
            return True
        else:
            print("[ERROR] Enroll failed:", response.text)
            return False

    except Exception as exc:
        print("ESP32 error:", exc)
        return False


def clear_fingerprint_database():
    """Remove all enrolled fingerprint templates from the ESP32 sensor."""

    response, error = _request("/clear-fingerprints", timeout=10)
    if error == "ESP32_NOT_FOUND":
        print("ESP32 not found")
        return False

    try:
        if error is not None:
            raise error
        response.raise_for_status()
        result = response.text.strip()
        print("FP Clear Response:", result)
        return result == "CLEAR_SUCCESS"
    except Exception as exc:
        print("ESP32 error:", exc)
        return False


def verify_fingerprint(student_id):
    """Verify that the presented fingerprint matches the recognized student.

    Returns a status string instead of a boolean so the UI can distinguish
    a real mismatch from timeouts, missing fingers, or sensor errors.
    """

    try:
        print("\n[INFO] Place finger on sensor...")
        response, error = _request(
            "/verify",
            params={"id": student_id},
            timeout=8,
        )
        if error == "ESP32_NOT_FOUND":
            print("ESP32 not found")
            return "ESP32_NOT_FOUND"
        if error is not None:
            raise error

        response.raise_for_status()
        result = response.text.strip()

        print("FP Response:", result)

        if result == "MATCH":
            print("[OK] Fingerprint verified")
        elif result.startswith("NO_MATCH"):
            print("[ERROR] Fingerprint mismatch")
        elif result == "NO_FINGER":
            print("[WARNING] No finger detected on sensor")
        elif result == "NOT_FOUND":
            print("[WARNING] Fingerprint not recognized by sensor")
        elif result == "SENSOR_ERROR":
            print("[ERROR] Sensor reported a verification error")
        else:
            print("[WARNING] Unknown response:", result)
            return "UNKNOWN_RESPONSE"

        return result

    except Exception as exc:
        print("ESP32 error:", exc)
        return "REQUEST_ERROR"
