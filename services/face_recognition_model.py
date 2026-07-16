"""Face detection, encoding, training, and matching utilities."""

import hashlib
import math
import os
import pickle
import tempfile
from collections import defaultdict
from datetime import datetime

import cv2
import face_recognition
import numpy as np

from config import (
    DATASET_PATH,
    FACE_CENTROID_DISTANCE_THRESHOLD,
    FACE_DETECTION_MIN_SIZE,
    FACE_DETECTION_PRIMARY_SCALE,
    FACE_DETECTION_PRIMARY_UPSAMPLE,
    FACE_DETECTION_SECONDARY_SCALE,
    FACE_DETECTION_SECONDARY_UPSAMPLE,
    FACE_ENCODING_JITTERS,
    FACE_MATCH_DISTANCE_THRESHOLD,
    FACE_MATCH_MARGIN,
    FACE_MIN_SAMPLES_PER_STUDENT,
    FACE_SAMPLE_RETENTION_RATIO,
    TRAINER_PATH,
)
from services.face_utils import prepare_face_for_embedding


MODEL_VERSION = 3


def build_dataset_signature(dataset_path=DATASET_PATH):
    """Return a stable fingerprint for the current dataset tree.

    The attendance path only needs to detect dataset changes caused by
    registration and retraining, so hashing the student folders and file names
    is fast enough while avoiding a full per-file stat walk on every refresh.
    """

    digest = hashlib.sha1()

    if not os.path.isdir(dataset_path):
        digest.update(b"missing-dataset")
        return digest.hexdigest()

    for folder_name in sorted(os.listdir(dataset_path)):
        folder_path = os.path.join(dataset_path, folder_name)
        if not os.path.isdir(folder_path):
            continue

        try:
            folder_stats = os.stat(folder_path)
        except OSError:
            digest.update(f"DIR:{folder_name}:missing\n".encode("utf-8"))
            continue

        digest.update(
            f"DIR:{folder_name}:{int(folder_stats.st_mtime_ns)}\n".encode("utf-8")
        )

        file_names = sorted(
            file_name
            for file_name in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, file_name))
        )
        digest.update(f"COUNT:{len(file_names)}\n".encode("utf-8"))

        for file_name in file_names:
            digest.update(f"FILE:{folder_name}/{file_name}\n".encode("utf-8"))

    return digest.hexdigest()


def read_model_metadata(model_path=TRAINER_PATH):
    """Load the persisted model metadata without normalizing the full payload."""

    with open(model_path, "rb") as model_file:
        payload = pickle.load(model_file)

    return {
        "version": payload.get("version"),
        "created_at": payload.get("created_at"),
        "dataset_signature": payload.get("dataset_signature"),
    }


def _student_id_from_folder(folder_name):
    try:
        return int(folder_name.rsplit("_", 1)[-1])
    except (ValueError, IndexError):
        return None


def _box_overlap(first_box, second_box):
    x1, y1, w1, h1 = first_box
    x2, y2, w2, h2 = second_box

    left = max(x1, x2)
    top = max(y1, y2)
    right = min(x1 + w1, x2 + w2)
    bottom = min(y1 + h1, y2 + h2)

    intersection = max(0, right - left) * max(0, bottom - top)
    union = (w1 * h1) + (w2 * h2) - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def _deduplicate_boxes(boxes, overlap_threshold=0.35):
    """Remove highly overlapping detections and keep the strongest boxes."""

    unique_boxes = []

    for box in sorted(boxes, key=lambda item: item[2] * item[3], reverse=True):
        if any(_box_overlap(box, existing_box) >= overlap_threshold for existing_box in unique_boxes):
            continue
        unique_boxes.append(box)

    return unique_boxes


def detect_face_boxes(
    frame,
    detection_scales=None,
    detection_upsamples=None,
    min_face_size=FACE_DETECTION_MIN_SIZE,
):
    """Detect faces at multiple scales and return boxes sorted by size."""

    if frame is None or frame.size == 0:
        return []

    if detection_scales is None:
        detection_scales = (
            FACE_DETECTION_PRIMARY_SCALE,
            FACE_DETECTION_SECONDARY_SCALE,
        )
    if detection_upsamples is None:
        detection_upsamples = (
            FACE_DETECTION_PRIMARY_UPSAMPLE,
            FACE_DETECTION_SECONDARY_UPSAMPLE,
        )

    all_boxes = []

    for index, detection_scale in enumerate(detection_scales):
        upsample_times = detection_upsamples[min(index, len(detection_upsamples) - 1)]

        resized = cv2.resize(
            frame,
            None,
            fx=detection_scale,
            fy=detection_scale,
            interpolation=cv2.INTER_AREA if detection_scale < 1.0 else cv2.INTER_LINEAR,
        )
        rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        for top, right, bottom, left in face_recognition.face_locations(
            rgb_frame,
            number_of_times_to_upsample=upsample_times,
            model="hog",
        ):
            x = max(0, int(left / detection_scale))
            y = max(0, int(top / detection_scale))
            w = max(1, int((right - left) / detection_scale))
            h = max(1, int((bottom - top) / detection_scale))

            if min(w, h) < min_face_size:
                continue

            all_boxes.append((x, y, w, h))

        if len(_deduplicate_boxes(all_boxes)) >= 4:
            break

    boxes = _deduplicate_boxes(all_boxes)
    boxes.sort(key=lambda item: item[2] * item[3], reverse=True)
    return boxes


def encode_face_image(face_img):
    """Convert a cropped face image into a face-recognition embedding."""

    prepared = prepare_face_for_embedding(face_img)
    if prepared is None:
        return None

    rgb_face = cv2.cvtColor(prepared, cv2.COLOR_BGR2RGB)
    rgb_face = np.ascontiguousarray(rgb_face)
    height, width = rgb_face.shape[:2]

    if height == 0 or width == 0:
        return None

    encodings = face_recognition.face_encodings(
        rgb_face,
        known_face_locations=[(0, width, height, 0)],
        num_jitters=FACE_ENCODING_JITTERS,
        model="small",
    )
    if encodings:
        return np.asarray(encodings[0], dtype=np.float32)

    detected_locations = face_recognition.face_locations(
        rgb_face,
        number_of_times_to_upsample=0,
        model="hog",
    )
    if detected_locations:
        detected_locations.sort(
            key=lambda item: (item[2] - item[0]) * (item[1] - item[3]),
            reverse=True,
        )
        detected_encodings = face_recognition.face_encodings(
            rgb_face,
            known_face_locations=[detected_locations[0]],
            num_jitters=FACE_ENCODING_JITTERS,
            model="small",
        )
        if detected_encodings:
            return np.asarray(detected_encodings[0], dtype=np.float32)

    return None


def _filter_consistent_encodings(encodings):
    """Keep the most consistent samples for each student and drop outliers."""

    encoding_array = np.asarray(encodings, dtype=np.float32)
    if len(encoding_array) <= FACE_MIN_SAMPLES_PER_STUDENT:
        return encoding_array

    centroid = encoding_array.mean(axis=0)
    distances = np.linalg.norm(encoding_array - centroid, axis=1)
    keep_count = max(
        FACE_MIN_SAMPLES_PER_STUDENT,
        int(math.ceil(len(encoding_array) * FACE_SAMPLE_RETENTION_RATIO)),
    )
    keep_indices = np.argsort(distances)[:keep_count]
    return encoding_array[keep_indices]


def train_embedding_model(dataset_path=DATASET_PATH, model_path=TRAINER_PATH):
    """Build and persist the face embedding database from the dataset folders."""

    student_encodings = defaultdict(list)
    total_images = 0
    encoded_images = 0
    dataset_signature = build_dataset_signature(dataset_path)

    if not os.path.isdir(dataset_path):
        return None, {
            "total_images": 0,
            "encoded_images": 0,
            "skipped_images": 0,
        }

    for folder_name in sorted(os.listdir(dataset_path)):
        folder_path = os.path.join(dataset_path, folder_name)
        if not os.path.isdir(folder_path):
            continue

        student_id = _student_id_from_folder(folder_name)
        if student_id is None:
            continue

        for image_name in sorted(os.listdir(folder_path)):
            image_path = os.path.join(folder_path, image_name)
            image = cv2.imread(image_path)
            total_images += 1

            if image is None:
                continue

            encoding = encode_face_image(image)
            if encoding is None:
                continue

            student_encodings[student_id].append(encoding)
            encoded_images += 1

    if not student_encodings:
        return None, {
            "total_images": total_images,
            "encoded_images": 0,
            "skipped_images": total_images,
        }

    all_encodings = []
    labels = []
    centroids = {}
    sample_counts = {}
    raw_sample_counts = {}

    for student_id in sorted(student_encodings):
        filtered = _filter_consistent_encodings(student_encodings[student_id])
        if len(filtered) == 0:
            continue

        centroids[student_id] = filtered.mean(axis=0).astype(np.float32)
        sample_counts[student_id] = int(len(filtered))
        raw_sample_counts[student_id] = int(len(student_encodings[student_id]))

        for encoding in filtered:
            all_encodings.append(encoding.astype(np.float32))
            labels.append(student_id)

    if not all_encodings:
        return None, {
            "total_images": total_images,
            "encoded_images": 0,
            "skipped_images": total_images,
        }

    payload = {
        "version": MODEL_VERSION,
        "algorithm": "dlib_face_embeddings",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_signature": dataset_signature,
        "encodings": np.stack(all_encodings).astype(np.float32),
        "labels": np.asarray(labels, dtype=np.int32),
        "centroids": centroids,
        "sample_counts": sample_counts,
        "raw_sample_counts": raw_sample_counts,
    }

    model_dir = os.path.dirname(model_path) or "."
    os.makedirs(model_dir, exist_ok=True)

    temp_fd, temp_path = tempfile.mkstemp(
        prefix="face_embeddings_",
        suffix=".tmp",
        dir=model_dir,
    )
    try:
        with os.fdopen(temp_fd, "wb") as model_file:
            pickle.dump(payload, model_file)
        os.replace(temp_path, model_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return payload, {
        "total_images": total_images,
        "encoded_images": encoded_images,
        "skipped_images": total_images - encoded_images,
    }


def load_face_database(model_path=TRAINER_PATH):
    """Load the trained embedding payload from disk and normalize its types."""

    with open(model_path, "rb") as model_file:
        payload = pickle.load(model_file)

    if payload.get("version") != MODEL_VERSION:
        raise ValueError("Unsupported face model version")

    payload["encodings"] = np.asarray(payload.get("encodings", []), dtype=np.float32)
    payload["labels"] = np.asarray(payload.get("labels", []), dtype=np.int32)
    payload["centroids"] = {
        int(student_id): np.asarray(centroid, dtype=np.float32)
        for student_id, centroid in payload.get("centroids", {}).items()
    }
    payload["sample_counts"] = {
        int(student_id): int(count)
        for student_id, count in payload.get("sample_counts", {}).items()
    }
    payload["dataset_signature"] = payload.get("dataset_signature")

    if payload["encodings"].size == 0 or payload["labels"].size == 0:
        raise ValueError("Face database is empty")

    return payload


class FaceEmbeddingMatcher:
    """Match an incoming face crop against the trained student database."""

    def __init__(self, model_path=TRAINER_PATH):
        payload = load_face_database(model_path)
        self.encodings = payload["encodings"]
        self.labels = payload["labels"]
        self.centroids = payload["centroids"]
        self.sample_counts = payload["sample_counts"]
        sort_order = np.argsort(self.labels, kind="stable")
        self.sorted_encodings = self.encodings[sort_order]
        self.sorted_labels = self.labels[sort_order]
        self.unique_labels, self.group_start_indices = np.unique(
            self.sorted_labels,
            return_index=True,
        )
        self.centroid_ids = np.asarray(sorted(self.centroids), dtype=np.int32)
        self.centroid_matrix = np.stack(
            [self.centroids[int(student_id)] for student_id in self.centroid_ids]
        ).astype(np.float32)

    def predict(self, face_img):
        """Return the best recognition match and associated confidence metadata."""

        encoding = encode_face_image(face_img)
        if encoding is None:
            return {
                "matched": False,
                "student_id": None,
                "distance": None,
                "centroid_distance": None,
                "margin": None,
                "confidence": 0.0,
            }

        distances = np.linalg.norm(self.sorted_encodings - encoding, axis=1)
        grouped_distances = np.minimum.reduceat(distances, self.group_start_indices)

        if grouped_distances.size == 0:
            return {
                "matched": False,
                "student_id": None,
                "distance": None,
                "centroid_distance": None,
                "margin": None,
                "confidence": 0.0,
            }

        best_index = int(np.argmin(grouped_distances))
        best_student_id = int(self.unique_labels[best_index])
        best_distance = float(grouped_distances[best_index])
        if grouped_distances.size > 1:
            second_best_distance = float(np.partition(grouped_distances, 1)[1])
        else:
            second_best_distance = float("inf")
        margin = second_best_distance - best_distance

        centroid_distances = np.linalg.norm(self.centroid_matrix - encoding, axis=1)
        centroid_index = int(np.argmin(centroid_distances))
        centroid_student_id = int(self.centroid_ids[centroid_index])
        centroid_distance = float(centroid_distances[centroid_index])

        matched = (
            best_distance <= FACE_MATCH_DISTANCE_THRESHOLD
            and centroid_distance <= FACE_CENTROID_DISTANCE_THRESHOLD
            and best_student_id == centroid_student_id
            and margin >= FACE_MATCH_MARGIN
        )

        confidence = max(
            0.0,
            min(
                1.0,
                1.0 - (best_distance / max(FACE_MATCH_DISTANCE_THRESHOLD, 1e-6)),
            ),
        )

        return {
            "matched": matched,
            "student_id": best_student_id,
            "distance": best_distance,
            "centroid_distance": centroid_distance,
            "margin": margin,
            "confidence": confidence,
        }
