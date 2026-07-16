"""Shared helpers for face normalization, cropping, and quality checks."""

import cv2

from config import (
    FACE_BLUR_THRESHOLD,
    FACE_CROP_PADDING,
    FACE_IMAGE_SIZE,
    FACE_MIN_BRIGHTNESS,
)


def normalize_face(face_img):
    """Normalize grayscale face data for brightness and size checks."""

    if face_img is None or face_img.size == 0:
        return None

    normalized = cv2.resize(face_img, FACE_IMAGE_SIZE, interpolation=cv2.INTER_AREA)
    normalized = cv2.equalizeHist(normalized)
    return normalized


def prepare_face_for_embedding(face_img):
    """Convert a face crop into the expected size and channel format."""

    if face_img is None or face_img.size == 0:
        return None

    if len(face_img.shape) == 2:
        prepared = cv2.cvtColor(face_img, cv2.COLOR_GRAY2BGR)
    else:
        prepared = face_img.copy()

    interpolation = cv2.INTER_AREA
    if prepared.shape[0] < FACE_IMAGE_SIZE[1] or prepared.shape[1] < FACE_IMAGE_SIZE[0]:
        interpolation = cv2.INTER_LINEAR

    return cv2.resize(prepared, FACE_IMAGE_SIZE, interpolation=interpolation)


def extract_face_sample(frame, x, y, w, h, padding_ratio=FACE_CROP_PADDING):
    """Crop a face region, pad it to square, and resize it for storage."""

    if frame is None or frame.size == 0:
        return None

    frame_h, frame_w = frame.shape[:2]
    pad_w = int(w * padding_ratio)
    pad_h = int(h * padding_ratio)

    x1 = max(0, x - pad_w)
    y1 = max(0, y - pad_h)
    x2 = min(frame_w, x + w + pad_w)
    y2 = min(frame_h, y + h + pad_h)

    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    crop_h, crop_w = crop.shape[:2]
    side = max(crop_h, crop_w)
    top = (side - crop_h) // 2
    bottom = side - crop_h - top
    left = (side - crop_w) // 2
    right = side - crop_w - left

    border_value = 0 if len(crop.shape) == 2 else [0, 0, 0]
    squared = cv2.copyMakeBorder(
        crop,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=border_value,
    )

    interpolation = cv2.INTER_AREA
    if squared.shape[0] < FACE_IMAGE_SIZE[1] or squared.shape[1] < FACE_IMAGE_SIZE[0]:
        interpolation = cv2.INTER_LINEAR

    return cv2.resize(squared, FACE_IMAGE_SIZE, interpolation=interpolation)


def measure_face_quality(face_img):
    """Check brightness and sharpness before saving or matching a sample."""

    normalized = normalize_face(face_img)

    if normalized is None:
        return {
            "ok": False,
            "reason": "empty",
            "brightness": 0.0,
            "sharpness": 0.0,
            "image": None,
        }

    brightness = float(normalized.mean())
    sharpness = float(cv2.Laplacian(normalized, cv2.CV_64F).var())

    if brightness < FACE_MIN_BRIGHTNESS:
        return {
            "ok": False,
            "reason": "too_dark",
            "brightness": brightness,
            "sharpness": sharpness,
            "image": normalized,
        }

    if sharpness < FACE_BLUR_THRESHOLD:
        return {
            "ok": False,
            "reason": "too_blurry",
            "brightness": brightness,
            "sharpness": sharpness,
            "image": normalized,
        }

    return {
        "ok": True,
        "reason": "ok",
        "brightness": brightness,
        "sharpness": sharpness,
        "image": normalized,
    }
