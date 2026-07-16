"""Network discovery helpers for locating the ESP32 controller on the LAN."""

import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


def check_ip(ip):
    """Probe a candidate IP address and return the ESP32 base URL when found."""

    try:
        base_url = f"http://{ip}"
        for path in ("/health", "/verify", "/notify"):
            res = requests.get(f"{base_url}{path}", timeout=0.45)
            if path == "/verify" and res.status_code == 400:
                print(f"ESP32 found at {ip}")
                return base_url
            if res.status_code in (200, 204):
                print(f"ESP32 found at {ip}")
                return base_url

    except Exception:
        return None


def _get_local_ipv4():
    """Return the most useful LAN IPv4 instead of relying on hostname resolution."""

    try:
        probe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe_socket.connect(("8.8.8.8", 80))
            local_ip = probe_socket.getsockname()[0]
            if local_ip and not local_ip.startswith("127."):
                return local_ip
        finally:
            probe_socket.close()
    except Exception:
        pass

    try:
        for _, _, _, _, sockaddr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            local_ip = sockaddr[0]
            if local_ip and not local_ip.startswith("127."):
                return local_ip
    except Exception:
        pass

    return None


def find_esp32_ip():
    """Scan the local subnet and return the first reachable ESP32 URL."""

    local_ip = _get_local_ipv4()
    if not local_ip:
        return None

    base_ip = ".".join(local_ip.split(".")[:-1])
    ips = [f"{base_ip}.{i}" for i in range(1, 255)]

    print("[INFO] Scanning network for ESP32...")

    with ThreadPoolExecutor(max_workers=50) as executor:
        future_map = {
            executor.submit(check_ip, ip): ip
            for ip in ips
        }
        for future in as_completed(future_map):
            result = future.result()
            if result:
                for pending_future in future_map:
                    if pending_future is not future:
                        pending_future.cancel()
                return result

    return None

