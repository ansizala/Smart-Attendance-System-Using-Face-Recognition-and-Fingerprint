"""Project-wide configuration values and lazy ESP32 discovery helpers."""

import threading
import time

from services.esp32_discovery import find_esp32_ip

# Filesystem paths
DATASET_PATH = "dataset"
TRAINER_PATH = "trainer/face_embeddings.pkl"
STUDENT_CSV = "student_info.csv"

# Google Sheets integration
SHEET_NAME = "Smart_Attendance_2026"

# Face recognition pipeline
FACE_IMAGE_SIZE = (160, 160)
FACE_MIN_BRIGHTNESS = 45
FACE_BLUR_THRESHOLD = 55.0
FACE_STABLE_FRAMES = 1
FACE_MODEL_REFRESH_INTERVAL_SECONDS = 20.0
FACE_RECOGNITION_CONFIRM_FRAMES = 2
FACE_RECOGNITION_RECHECK_SECONDS = 0.35
FACE_PREDICTION_MIN_INTERVAL_SECONDS = 0.18
UNKNOWN_STABLE_SECONDS = 1.0
UNKNOWN_ALERT_COOLDOWN = 10
RECOGNIZED_GRACE_SECONDS = 1.0
FACE_MATCH_DISTANCE_THRESHOLD = 0.46
FACE_CENTROID_DISTANCE_THRESHOLD = 0.40
FACE_MATCH_MARGIN = 0.01
FACE_RECENT_MATCH_DISTANCE_THRESHOLD = 0.58
FACE_TEMPORAL_HOLD_SECONDS = 1.6
FACE_ENCODING_JITTERS = 1
FACE_SAMPLE_RETENTION_RATIO = 0.6
FACE_MIN_SAMPLES_PER_STUDENT = 10
FACE_CROP_PADDING = 0.2
FACE_DETECTION_PRIMARY_SCALE = 0.7
FACE_DETECTION_PRIMARY_UPSAMPLE = 0
FACE_DETECTION_SECONDARY_SCALE = 1.0
FACE_DETECTION_SECONDARY_UPSAMPLE = 1
FACE_DETECTION_MIN_SIZE = 52
FACE_DETECTION_INTERVAL = 3
FACE_FALLBACK_DETECTION_INTERVAL = 9
FACE_CASCADE_SCALE = 0.75
FACE_TRACK_MAX_MISSES = 8
FACE_TRACK_IOU_THRESHOLD = 0.08
FACE_TRACK_MAX_CENTER_DISTANCE = 1.35
FACE_UNKNOWN_FRAME_TOLERANCE = 3
FACE_MAX_RECOGNITION_TRACKS = 2

# Camera capture
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_BUFFER_SIZE = 1
FRAME_SKIP = 3
CAMERA_THREAD_WAIT_SECONDS = 0.01

# Student registration
FACE_SAMPLES = 50
REGISTRATION_CASCADE_MIN_FACE_SIZE = 80
REGISTRATION_DETECTION_INTERVAL = 2
REGISTRATION_FALLBACK_INTERVAL = 6
REGISTRATION_TRACK_HOLD_FRAMES = 6
REGISTRATION_SAMPLE_COOLDOWN_SECONDS = 0.12

# Network and Google Sheets
GOOGLE_SHEET_BATCH_SIZE = 6
GOOGLE_SHEET_BATCH_FLUSH_SECONDS = 0.75
GOOGLE_SHEET_CACHE_TTL_SECONDS = 10.0
NETWORK_EXECUTOR_WORKERS = 4

_cached_esp32_ip = None
_esp32_lookup_done = False
_esp32_lookup_at = 0.0
_esp32_lock = threading.Lock()
ESP32_DISCOVERY_RETRY_SECONDS = 8.0


def get_esp32_ip(force_refresh=False):
    """Resolve the ESP32 base URL and retry failed lookups after a short cooldown."""

    global _cached_esp32_ip, _esp32_lookup_done, _esp32_lookup_at

    now = time.monotonic()
    with _esp32_lock:
        should_lookup = force_refresh or not _esp32_lookup_done
        if not should_lookup and _cached_esp32_ip is None:
            should_lookup = (now - _esp32_lookup_at) >= ESP32_DISCOVERY_RETRY_SECONDS

        if not should_lookup:
            return _cached_esp32_ip

        _esp32_lookup_done = True
        _esp32_lookup_at = now
        _cached_esp32_ip = find_esp32_ip()

        if _cached_esp32_ip:
            print(f"[INFO] ESP32 connected at {_cached_esp32_ip}")
        else:
            print("[WARNING] ESP32 not found")

        return _cached_esp32_ip
