"""Camera capture service that handles detection, tracking, and recognition."""

import csv
import os
import threading
import time

import cv2

from config import (
    CAMERA_BUFFER_SIZE,
    CAMERA_HEIGHT,
    CAMERA_THREAD_WAIT_SECONDS,
    CAMERA_WIDTH,
    DATASET_PATH,
    FACE_CASCADE_SCALE,
    FACE_DETECTION_INTERVAL,
    FACE_DETECTION_MIN_SIZE,
    FACE_FALLBACK_DETECTION_INTERVAL,
    FACE_MAX_RECOGNITION_TRACKS,
    FACE_MODEL_REFRESH_INTERVAL_SECONDS,
    FACE_PREDICTION_MIN_INTERVAL_SECONDS,
    FACE_RECENT_MATCH_DISTANCE_THRESHOLD,
    FACE_RECOGNITION_CONFIRM_FRAMES,
    FACE_RECOGNITION_RECHECK_SECONDS,
    FACE_STABLE_FRAMES,
    FACE_TEMPORAL_HOLD_SECONDS,
    FACE_TRACK_IOU_THRESHOLD,
    FACE_TRACK_MAX_CENTER_DISTANCE,
    FACE_TRACK_MAX_MISSES,
    FACE_UNKNOWN_FRAME_TOLERANCE,
    STUDENT_CSV,
    TRAINER_PATH,
)
from services.face_recognition_model import (
    FaceEmbeddingMatcher,
    MODEL_VERSION,
    build_dataset_signature,
    detect_face_boxes,
    read_model_metadata,
    train_embedding_model,
)
from services.face_utils import extract_face_sample, measure_face_quality


CASCADE_MIN_FACE_SIZE = 48
NO_FACE_RESET_SECONDS = 0.8


class CameraService:
    """Read camera frames and attach face recognition state for the UI."""

    def __init__(self):
        self.students = {}
        self.matcher = None
        self._students_state = None
        self._loaded_model_state = None
        self._loaded_dataset_signature = None
        self._last_failed_dataset_signature = None
        self._last_refresh_check = 0.0
        self._pending_model_reload = False
        self._refresh_lock = threading.Lock()
        self._refresh_thread = None

        model_exists = os.path.exists(TRAINER_PATH)
        if self._model_needs_refresh():
            if not model_exists:
                print("[INFO] Face model not found. Training from saved samples...")
                payload, _ = train_embedding_model()
                if payload is None:
                    raise RuntimeError("No trained face model found. Register students first.")
            else:
                print("[INFO] Face model is outdated. Loading current model and refreshing in background...")

        try:
            self._load_matcher_from_disk(force=True)
        except Exception as exc:
            print(f"[WARNING] Face model reload failed ({exc}). Rebuilding model...")
            payload, _ = train_embedding_model()
            if payload is None:
                raise RuntimeError("Unable to build face model from the saved dataset.")
            self._load_matcher_from_disk(force=True)

        if model_exists:
            dataset_signature = build_dataset_signature(DATASET_PATH)
            metadata = self._read_model_metadata()
            if self._model_needs_refresh(dataset_signature=dataset_signature, metadata=metadata):
                self._start_background_refresh(dataset_signature)

        self.detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        self._reload_students(force=True)

        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)

        self.face_detect_counter = 0
        self.last_face_time = 0.0
        self.face_tracks = {}
        self.next_track_id = 1
        self.frame_index = 0
        self._last_fallback_frame_index = 0

        self._frame_condition = threading.Condition()
        self._result_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._latest_frame = None
        self._latest_frame_id = 0
        self._latest_result = None

        self._smoothed_fps = 0.0
        self._smoothed_detect_ms = 0.0
        self._smoothed_recognize_ms = 0.0
        self._smoothed_total_ms = 0.0
        self._dropped_frames = 0
        self._last_metrics_time = None

        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
            name="camera-capture",
        )
        self._recognition_thread = threading.Thread(
            target=self._recognition_loop,
            daemon=True,
            name="camera-recognition",
        )
        self._capture_thread.start()
        self._recognition_thread.start()

    def _path_state(self, path):
        try:
            stats = os.stat(path)
        except OSError:
            return None

        return int(stats.st_mtime_ns), int(stats.st_size)

    def _load_students_from_disk(self):
        students = {}

        if not os.path.exists(STUDENT_CSV):
            return students

        with open(STUDENT_CSV, newline="", encoding="utf-8") as file_obj:
            reader = csv.DictReader(file_obj)
            for row in reader:
                students[int(row["ID"])] = {
                    "name": row["Name"],
                    "enrollment": row["Enrollment"],
                    "parent": row.get("ParentPhone", ""),
                }

        return students

    def _reload_students(self, force=False):
        students_state = self._path_state(STUDENT_CSV)
        if not force and students_state == self._students_state:
            return False

        self.students = self._load_students_from_disk()
        self._students_state = students_state
        return True

    def _read_model_metadata(self):
        if not os.path.exists(TRAINER_PATH):
            return None

        try:
            return read_model_metadata(TRAINER_PATH)
        except Exception:
            return None

    def _load_matcher_from_disk(self, force=False):
        model_state = self._path_state(TRAINER_PATH)
        if not force and model_state == self._loaded_model_state:
            return False

        metadata = self._read_model_metadata()
        self.matcher = FaceEmbeddingMatcher(TRAINER_PATH)
        self._loaded_model_state = model_state
        self._loaded_dataset_signature = metadata.get("dataset_signature") if metadata else None
        return True

    def _reset_tracking_state(self):
        self.face_detect_counter = 0
        self.last_face_time = 0.0
        self.face_tracks.clear()
        self.next_track_id = 1
        self._last_fallback_frame_index = 0

    def _model_needs_refresh(self, dataset_signature=None, metadata=None):
        current_signature = dataset_signature
        if current_signature is None:
            current_signature = build_dataset_signature(DATASET_PATH)

        if metadata is None:
            metadata = self._read_model_metadata()

        if metadata is None:
            return True

        if metadata.get("version") != MODEL_VERSION:
            return True

        return metadata.get("dataset_signature") != current_signature

    def _start_background_refresh(self, dataset_signature):
        with self._refresh_lock:
            if self._refresh_thread and self._refresh_thread.is_alive():
                return False

            self._pending_model_reload = False
            self._refresh_thread = threading.Thread(
                target=self._train_model_in_background,
                args=(dataset_signature,),
                daemon=True,
            )
            self._refresh_thread.start()
            return True

    def _train_model_in_background(self, dataset_signature):
        try:
            payload, _ = train_embedding_model()
            if payload is None:
                print("[WARNING] Automatic model refresh could not build a usable face model.")
                with self._refresh_lock:
                    self._last_failed_dataset_signature = dataset_signature
                    self._pending_model_reload = False
                return

            with self._refresh_lock:
                self._last_failed_dataset_signature = None
                self._pending_model_reload = True
        except Exception as exc:
            print(f"[WARNING] Automatic model refresh failed: {exc}")
            with self._refresh_lock:
                self._last_failed_dataset_signature = dataset_signature
                self._pending_model_reload = False

    def _refresh_runtime_state(self, now):
        if now - self._last_refresh_check < FACE_MODEL_REFRESH_INTERVAL_SECONDS:
            return

        self._last_refresh_check = now
        should_reset_tracking = self._reload_students()

        with self._refresh_lock:
            refresh_thread = self._refresh_thread

        if refresh_thread and refresh_thread.is_alive():
            if should_reset_tracking:
                self._reset_tracking_state()
            return

        if refresh_thread and not refresh_thread.is_alive():
            with self._refresh_lock:
                self._refresh_thread = None
                should_reload_model = self._pending_model_reload
                self._pending_model_reload = False
        else:
            should_reload_model = False

        if should_reload_model:
            try:
                if self._load_matcher_from_disk(force=True):
                    print("[INFO] Face model refreshed automatically.")
                    should_reset_tracking = True
            except Exception as exc:
                print(f"[WARNING] Face model reload after refresh failed: {exc}")

        dataset_signature = build_dataset_signature(DATASET_PATH)
        metadata = self._read_model_metadata()
        if self._model_needs_refresh(dataset_signature=dataset_signature, metadata=metadata):
            if dataset_signature != self._last_failed_dataset_signature:
                if self._start_background_refresh(dataset_signature):
                    print("[INFO] Dataset change detected. Training face model automatically...")
            if should_reset_tracking:
                self._reset_tracking_state()
            return

        try:
            if self._load_matcher_from_disk():
                print("[INFO] Loaded updated face model from disk.")
                should_reset_tracking = True
        except Exception as exc:
            print(f"[WARNING] Face model reload failed: {exc}")

        if should_reset_tracking:
            self._reset_tracking_state()

    def _capture_loop(self):
        while not self._stop_event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(CAMERA_THREAD_WAIT_SECONDS)
                continue

            with self._frame_condition:
                self._latest_frame = frame
                self._latest_frame_id += 1
                self._frame_condition.notify_all()

    def _recognition_loop(self):
        last_processed_id = 0

        while not self._stop_event.is_set():
            with self._frame_condition:
                while (
                    not self._stop_event.is_set()
                    and self._latest_frame_id == last_processed_id
                ):
                    self._frame_condition.wait(timeout=CAMERA_THREAD_WAIT_SECONDS)

                if self._stop_event.is_set():
                    return

                frame = self._latest_frame.copy()
                frame_id = self._latest_frame_id

            if frame_id > last_processed_id + 1:
                self._dropped_frames += frame_id - last_processed_id - 1
            last_processed_id = frame_id

            processed_frame, frame_state = self._process_frame(frame, frame_id)

            with self._result_lock:
                self._latest_result = (processed_frame, frame_state)

    def _detect_faces(self, frame, gray):
        scaled_gray = gray
        cascade_scale = FACE_CASCADE_SCALE
        if cascade_scale != 1.0:
            scaled_gray = cv2.resize(
                gray,
                None,
                fx=cascade_scale,
                fy=cascade_scale,
                interpolation=cv2.INTER_LINEAR,
            )

        cascade_faces = self.detector.detectMultiScale(
            cv2.equalizeHist(scaled_gray),
            scaleFactor=1.12,
            minNeighbors=4,
            minSize=(
                max(24, int(CASCADE_MIN_FACE_SIZE * cascade_scale)),
                max(24, int(CASCADE_MIN_FACE_SIZE * cascade_scale)),
            ),
        )

        face_boxes = []
        for x, y, w, h in cascade_faces:
            x = int(x / cascade_scale)
            y = int(y / cascade_scale)
            w = int(w / cascade_scale)
            h = int(h / cascade_scale)
            if min(w, h) < CASCADE_MIN_FACE_SIZE:
                continue
            face_boxes.append((x, y, w, h))

        face_boxes.sort(key=lambda item: item[2] * item[3], reverse=True)
        if face_boxes:
            return face_boxes, False

        if self.frame_index - self._last_fallback_frame_index < FACE_FALLBACK_DETECTION_INTERVAL:
            return [], False

        self._last_fallback_frame_index = self.frame_index
        fallback_boxes = detect_face_boxes(frame, min_face_size=FACE_DETECTION_MIN_SIZE)
        return fallback_boxes, bool(fallback_boxes)

    def _draw_label(self, frame, x, y, w, h, label, color):
        header_y = max(y - 25, 0)
        text_y = max(y - 8, 15)

        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.rectangle(frame, (x, header_y), (x + w, y), color, -1)
        cv2.putText(
            frame,
            label,
            (x + 5, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
        )

    def _sanitize_box(self, box, frame_shape):
        frame_h, frame_w = frame_shape[:2]
        x, y, w, h = box

        x = max(0, x)
        y = max(0, y)
        w = min(w, frame_w - x)
        h = min(h, frame_h - y)
        return x, y, w, h

    def _box_metrics(self, first_box, second_box):
        x1, y1, w1, h1 = first_box
        x2, y2, w2, h2 = second_box

        left = max(x1, x2)
        top = max(y1, y2)
        right = min(x1 + w1, x2 + w2)
        bottom = min(y1 + h1, y2 + h2)

        intersection = max(0, right - left) * max(0, bottom - top)
        union = (w1 * h1) + (w2 * h2) - intersection
        overlap = intersection / union if union > 0 else 0.0

        center_x1 = x1 + (w1 / 2.0)
        center_y1 = y1 + (h1 / 2.0)
        center_x2 = x2 + (w2 / 2.0)
        center_y2 = y2 + (h2 / 2.0)
        center_distance = ((center_x1 - center_x2) ** 2 + (center_y1 - center_y2) ** 2) ** 0.5
        scale = max(40.0, float(max(w1, h1, w2, h2)))
        normalized_distance = center_distance / scale

        return overlap, normalized_distance

    def _create_track(self, box):
        track = {
            "track_id": self.next_track_id,
            "box": box,
            "last_seen": time.time(),
            "misses": 0,
            "candidate_id": None,
            "candidate_hits": 0,
            "recognized_id": None,
            "confirmed_frames": 0,
            "unknown_hits": 0,
            "name": "",
            "enrollment": "",
            "parent": "",
            "distance": None,
            "confidence": 0.0,
            "last_identity_time": 0.0,
            "last_prediction_time": 0.0,
            "last_prediction_box": None,
        }
        self.face_tracks[track["track_id"]] = track
        self.next_track_id += 1
        return track

    def _sync_tracks(self, faces):
        """Match current detections to active tracks so identities stay stable."""

        now = time.time()
        ordered_tracks = []
        used_track_ids = set()

        active_tracks = [
            track
            for track in self.face_tracks.values()
            if now - track["last_seen"] <= FACE_TEMPORAL_HOLD_SECONDS * 2.0
        ]

        for box in faces:
            best_track = None
            best_score = float("-inf")

            for track in active_tracks:
                if track["track_id"] in used_track_ids:
                    continue

                overlap, normalized_distance = self._box_metrics(box, track["box"])
                if overlap < FACE_TRACK_IOU_THRESHOLD and normalized_distance > FACE_TRACK_MAX_CENTER_DISTANCE:
                    continue

                score = (overlap * 2.0) - normalized_distance
                if score > best_score:
                    best_score = score
                    best_track = track

            if best_track is None:
                track = self._create_track(box)
            else:
                track = best_track

            track["box"] = box
            track["last_seen"] = now
            track["misses"] = 0
            used_track_ids.add(track["track_id"])
            ordered_tracks.append(track)

        expired_track_ids = []
        for track_id, track in self.face_tracks.items():
            if track_id in used_track_ids:
                continue

            track["misses"] += 1
            if track["misses"] > FACE_TRACK_MAX_MISSES:
                expired_track_ids.append(track_id)

        for track_id in expired_track_ids:
            self.face_tracks.pop(track_id, None)

        return ordered_tracks

    def _get_active_tracks(self, max_age=FACE_TEMPORAL_HOLD_SECONDS):
        now = time.time()
        active_tracks = []
        expired_track_ids = []

        for track_id, track in self.face_tracks.items():
            age = now - track["last_seen"]
            if age <= max_age:
                active_tracks.append(track)
            elif age > FACE_TEMPORAL_HOLD_SECONDS * 2.0 or track["misses"] > FACE_TRACK_MAX_MISSES:
                expired_track_ids.append(track_id)

        for track_id in expired_track_ids:
            self.face_tracks.pop(track_id, None)

        active_tracks.sort(key=lambda item: item["box"][2] * item["box"][3], reverse=True)
        return active_tracks

    def _store_best_match(self, best_matches, track, distance_override=None):
        """Keep the strongest recognition candidate for each student in a frame."""

        student_id = track["recognized_id"]
        if student_id is None:
            return

        distance = track["distance"] if distance_override is None else distance_override
        current_match = best_matches.get(student_id)

        should_replace = current_match is None
        if not should_replace and distance is not None:
            existing_distance = current_match.get("distance")
            should_replace = existing_distance is None or distance < existing_distance

        if should_replace:
            best_matches[student_id] = {
                "id": student_id,
                "name": track["name"],
                "enrollment": track["enrollment"],
                "parent": track["parent"],
                "confidence": track["confidence"],
                "distance": distance,
            }

    def _can_hold_identity(self, track, match=None):
        """Allow a recent identity to persist through brief low-confidence frames."""

        if track["recognized_id"] is None:
            return False

        if time.time() - track["last_identity_time"] > FACE_TEMPORAL_HOLD_SECONDS:
            return False

        if match is None:
            return True

        if match["student_id"] not in (None, track["recognized_id"]):
            return False

        if match["distance"] is None:
            return True

        return match["distance"] <= FACE_RECENT_MATCH_DISTANCE_THRESHOLD

    def _promote_identity(self, track, student_id, student, match):
        """Promote a candidate identity to a confirmed recognition."""

        now = time.time()

        if track["candidate_id"] == student_id:
            track["candidate_hits"] += 1
        else:
            track["candidate_id"] = student_id
            track["candidate_hits"] = 1

        track["name"] = student["name"]
        track["enrollment"] = student["enrollment"]
        track["parent"] = student["parent"]
        track["distance"] = match["distance"]
        track["confidence"] = round(match["confidence"] * 100.0, 2)
        track["unknown_hits"] = 0

        if track["recognized_id"] == student_id:
            track["confirmed_frames"] = min(
                track["confirmed_frames"] + 1,
                FACE_RECOGNITION_CONFIRM_FRAMES + 3,
            )
            track["last_identity_time"] = now
            return "recognized"

        if track["candidate_hits"] >= FACE_RECOGNITION_CONFIRM_FRAMES:
            track["recognized_id"] = student_id
            track["confirmed_frames"] = track["candidate_hits"]
            track["last_identity_time"] = now
            return "recognized"

        return "confirming"

    def _clear_track_identity(self, track):
        """Reset recognition state when a track is no longer trustworthy."""

        track["candidate_id"] = None
        track["candidate_hits"] = 0
        track["recognized_id"] = None
        track["confirmed_frames"] = 0
        track["unknown_hits"] = 0
        track["name"] = ""
        track["enrollment"] = ""
        track["parent"] = ""
        track["distance"] = None
        track["confidence"] = 0.0
        track["last_identity_time"] = 0.0
        track["last_prediction_time"] = 0.0
        track["last_prediction_box"] = None

    def _render_cached_tracks(self, frame, tracks, frame_state):
        """Draw the most recent stable track state without re-running recognition."""

        best_matches = {}

        for track in tracks:
            x, y, w, h = self._sanitize_box(track["box"], frame.shape)
            if w <= 0 or h <= 0:
                continue

            track["box"] = (x, y, w, h)
            label = "Scanning..."
            color = (0, 165, 255)

            if track["recognized_id"] is not None and self._can_hold_identity(track):
                label = track["name"]
                color = (0, 220, 120)
                self._store_best_match(best_matches, track)
            elif track["candidate_id"] is not None and track["name"]:
                label = f"Confirming {track['name']}"
                color = (0, 200, 255)
            elif track["unknown_hits"] >= FACE_UNKNOWN_FRAME_TOLERANCE:
                label = "Unknown"
                color = (0, 0, 255)
                frame_state["has_unknown_face"] = True

            self._draw_label(frame, x, y, w, h, label, color)

        frame_state["recognized"] = list(best_matches.values())
        return frame_state

    def _should_predict_track(self, track, now):
        if track["last_prediction_box"] is None:
            return True

        if now - track["last_prediction_time"] >= FACE_PREDICTION_MIN_INTERVAL_SECONDS:
            return True

        overlap, normalized_distance = self._box_metrics(
            track["box"],
            track["last_prediction_box"],
        )
        return not (overlap >= 0.18 or normalized_distance <= 0.35)

    def _update_ema(self, current_value, new_value, alpha=0.2):
        if current_value == 0.0:
            return new_value
        return (current_value * (1.0 - alpha)) + (new_value * alpha)

    def _build_metrics(self, frame_id, detect_ms, recognize_ms, total_ms, fallback_used):
        now = time.perf_counter()
        if self._last_metrics_time is not None:
            instantaneous_fps = 1.0 / max(now - self._last_metrics_time, 1e-6)
            self._smoothed_fps = self._update_ema(self._smoothed_fps, instantaneous_fps, alpha=0.12)
        self._last_metrics_time = now

        self._smoothed_detect_ms = self._update_ema(self._smoothed_detect_ms, detect_ms)
        self._smoothed_recognize_ms = self._update_ema(self._smoothed_recognize_ms, recognize_ms)
        self._smoothed_total_ms = self._update_ema(self._smoothed_total_ms, total_ms)

        return {
            "result_id": frame_id,
            "fps": round(self._smoothed_fps, 1),
            "detect_ms": round(self._smoothed_detect_ms, 1),
            "recognize_ms": round(self._smoothed_recognize_ms, 1),
            "total_ms": round(self._smoothed_total_ms, 1),
            "dropped_frames": int(self._dropped_frames),
            "fallback_used": fallback_used,
        }

    def _process_frame(self, frame, frame_id):
        start_time = time.perf_counter()
        now = time.time()
        self._refresh_runtime_state(now)

        self.frame_index += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        detect_start = time.perf_counter()
        should_detect = (
            len(self.face_tracks) == 0
            or self.frame_index % FACE_DETECTION_INTERVAL == 0
        )

        fallback_used = False
        if should_detect:
            faces, fallback_used = self._detect_faces(frame, gray)
            if faces:
                self.last_face_time = now
                self.face_detect_counter += 1
                tracks = self._sync_tracks(faces)
            elif now - self.last_face_time > NO_FACE_RESET_SECONDS:
                self.face_detect_counter = 0
                self.face_tracks.clear()
                tracks = []
            else:
                tracks = self._get_active_tracks()
        else:
            tracks = self._get_active_tracks()

        detect_ms = (time.perf_counter() - detect_start) * 1000.0
        frame_state = {
            "recognized": [],
            "has_face": len(tracks) > 0,
            "has_unknown_face": False,
            "result_id": frame_id,
        }

        if len(tracks) == 0:
            frame_state["metrics"] = self._build_metrics(
                frame_id,
                detect_ms,
                0.0,
                (time.perf_counter() - start_time) * 1000.0,
                fallback_used,
            )
            return frame, frame_state

        if not should_detect:
            frame_state = self._render_cached_tracks(frame, tracks, frame_state)
            frame_state["metrics"] = self._build_metrics(
                frame_id,
                detect_ms,
                0.0,
                (time.perf_counter() - start_time) * 1000.0,
                fallback_used,
            )
            return frame, frame_state

        if self.face_detect_counter < FACE_STABLE_FRAMES:
            for track in tracks:
                x, y, w, h = track["box"]
                self._draw_label(frame, x, y, w, h, "Scanning...", (0, 165, 255))

            frame_state["metrics"] = self._build_metrics(
                frame_id,
                detect_ms,
                0.0,
                (time.perf_counter() - start_time) * 1000.0,
                fallback_used,
            )
            return frame, frame_state

        best_matches = {}
        recognition_start = time.perf_counter()
        active_track_ids = {
            track["track_id"]
            for track in tracks[:FACE_MAX_RECOGNITION_TRACKS]
        }

        for track in tracks:
            x, y, w, h = self._sanitize_box(track["box"], frame.shape)
            if w <= 0 or h <= 0:
                continue

            track["box"] = (x, y, w, h)

            if track["track_id"] not in active_track_ids:
                self._render_cached_tracks(frame, [track], frame_state)
                continue

            face_img = gray[y:y + h, x:x + w]
            color_face = extract_face_sample(frame, x, y, w, h)

            if face_img.size == 0 or color_face is None:
                continue

            quality = measure_face_quality(face_img)
            label = "Hold steady"
            color = (0, 165, 255)

            if not quality["ok"]:
                if quality["reason"] == "too_dark":
                    label = "Need more light"
                elif self._can_hold_identity(track):
                    label = track["name"]
                    color = (0, 200, 255)
                    self._store_best_match(best_matches, track)
                self._draw_label(frame, x, y, w, h, label, color)
                continue

            if (
                track["recognized_id"] is not None
                and now - track["last_identity_time"] < FACE_RECOGNITION_RECHECK_SECONDS
            ):
                label = track["name"]
                color = (0, 220, 120)
                self._store_best_match(best_matches, track)
                self._draw_label(frame, x, y, w, h, label, color)
                continue

            if not self._should_predict_track(track, now):
                if track["recognized_id"] is not None and self._can_hold_identity(track):
                    label = track["name"]
                    color = (0, 220, 120)
                    self._store_best_match(best_matches, track)
                elif track["candidate_id"] is not None and track["name"]:
                    label = f"Confirming {track['name']}"
                    color = (0, 200, 255)
                elif track["unknown_hits"] >= FACE_UNKNOWN_FRAME_TOLERANCE:
                    label = "Unknown"
                    color = (0, 0, 255)
                    frame_state["has_unknown_face"] = True
                self._draw_label(frame, x, y, w, h, label, color)
                continue

            match = self.matcher.predict(color_face)
            track["last_prediction_time"] = now
            track["last_prediction_box"] = track["box"]
            student_id = match["student_id"]
            student = self.students.get(student_id) if student_id is not None else None

            if student and match["matched"]:
                status = self._promote_identity(track, student_id, student, match)

                if status == "recognized":
                    label = student["name"]
                    color = (0, 255, 0)
                    self._store_best_match(best_matches, track)
                else:
                    label = f"Confirming {student['name']}"
                    color = (0, 200, 255)

            elif self._can_hold_identity(track, match):
                track["unknown_hits"] = 0
                if (
                    match["distance"] is not None
                    and match["student_id"] in (None, track["recognized_id"])
                ):
                    track["distance"] = match["distance"]
                    track["confidence"] = round(match["confidence"] * 100.0, 2)
                track["last_identity_time"] = now
                label = track["name"]
                color = (0, 220, 120)
                self._store_best_match(best_matches, track, match.get("distance"))

            else:
                track["unknown_hits"] += 1
                track["candidate_id"] = None
                track["candidate_hits"] = 0

                if track["unknown_hits"] < FACE_UNKNOWN_FRAME_TOLERANCE:
                    label = "Scanning..."
                    color = (0, 165, 255)
                else:
                    label = "Unknown"
                    color = (0, 0, 255)
                    frame_state["has_unknown_face"] = True

                if (
                    track["unknown_hits"]
                    >= FACE_UNKNOWN_FRAME_TOLERANCE + FACE_RECOGNITION_CONFIRM_FRAMES
                ):
                    self._clear_track_identity(track)

            self._draw_label(frame, x, y, w, h, label, color)

        frame_state["recognized"] = list(best_matches.values())
        frame_state["metrics"] = self._build_metrics(
            frame_id,
            detect_ms,
            (time.perf_counter() - recognition_start) * 1000.0,
            (time.perf_counter() - start_time) * 1000.0,
            fallback_used,
        )
        return frame, frame_state

    def read_frame(self):
        """Return the latest processed frame without blocking on camera I/O."""

        with self._result_lock:
            if self._latest_result is None:
                return None

            frame, frame_state = self._latest_result
            copied_state = dict(frame_state)
            copied_state["recognized"] = [
                dict(student)
                for student in frame_state.get("recognized", [])
            ]
            copied_state["metrics"] = dict(frame_state.get("metrics", {}))
            return frame.copy(), copied_state

    def release(self):
        self._stop_event.set()
        with self._frame_condition:
            self._frame_condition.notify_all()

        if self.cap.isOpened():
            self.cap.release()
        if self._capture_thread.is_alive():
            self._capture_thread.join(timeout=1.0)
        if self._recognition_thread.is_alive():
            self._recognition_thread.join(timeout=1.0)
