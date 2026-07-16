"""Dedicated helper for ESP32-powered parent SMS notifications."""

import requests

from config import get_esp32_ip


def send_sms(phone, name, date, time, status="present"):
    """Send an attendance status SMS through the ESP32 notification endpoint."""

    esp32_ip = get_esp32_ip()
    if not esp32_ip:
        esp32_ip = get_esp32_ip(force_refresh=True)

    if not esp32_ip:
        print("ESP32 not found")
        return

    try:
        response = requests.get(
            f"{esp32_ip}/notify",
            params={
                "phone": phone,
                "name": name,
                "date": date,
                "time": time,
                "status": status,
            },
            timeout=5
        )

        print(f"[INFO] SMS sent to {phone} for {name} ({status})")
        print("Response:", response.text)

    except Exception as exc:
        print("[ERROR] SMS failed:", exc)
