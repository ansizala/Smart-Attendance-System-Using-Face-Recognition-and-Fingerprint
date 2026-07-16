"""Student registration workflow for face capture and fingerprint enrollment."""

import csv
import os
import subprocess
import sys
import threading
import time
from tkinter import messagebox

import cv2
import ttkbootstrap as tb
from config import (
    CAMERA_BUFFER_SIZE,
    CAMERA_HEIGHT,
    CAMERA_WIDTH,
    DATASET_PATH,
    FACE_DETECTION_MIN_SIZE,
    FACE_SAMPLES,
    REGISTRATION_CASCADE_MIN_FACE_SIZE,
    REGISTRATION_DETECTION_INTERVAL,
    REGISTRATION_FALLBACK_INTERVAL,
    REGISTRATION_SAMPLE_COOLDOWN_SECONDS,
    REGISTRATION_TRACK_HOLD_FRAMES,
)
from services.face_utils import extract_face_sample, measure_face_quality
from services.face_recognition_model import detect_face_boxes

from services.esp32_service import notify_fingerprint_register

CSV_FILE = "student_info.csv"
_training_lock = threading.Lock()
_training_process = None
_training_pending = False


def _sanitize_box(box, frame_shape):
    """Clamp a detection box so it stays within the current frame bounds."""

    frame_h, frame_w = frame_shape[:2]
    x, y, w, h = box

    x = max(0, int(x))
    y = max(0, int(y))
    w = max(1, min(int(w), frame_w - x))
    h = max(1, min(int(h), frame_h - y))
    return x, y, w, h


def _detect_registration_faces(detector, frame, gray, frame_index):
    """Use the fast cascade first and only fall back to HOG occasionally."""

    cascade_faces = detector.detectMultiScale(
        cv2.equalizeHist(gray),
        scaleFactor=1.1,
        minNeighbors=4,
        minSize=(
            REGISTRATION_CASCADE_MIN_FACE_SIZE,
            REGISTRATION_CASCADE_MIN_FACE_SIZE,
        ),
    )
    face_boxes = [
        (int(x), int(y), int(w), int(h))
        for (x, y, w, h) in cascade_faces
        if min(w, h) >= REGISTRATION_CASCADE_MIN_FACE_SIZE
    ]
    face_boxes.sort(key=lambda item: item[2] * item[3], reverse=True)
    if face_boxes:
        return face_boxes

    if frame_index % REGISTRATION_FALLBACK_INTERVAL == 0:
        return detect_face_boxes(frame, min_face_size=FACE_DETECTION_MIN_SIZE)

    return []


def generate_new_id():
    """Return the next available numeric student ID."""

    if not os.path.exists(CSV_FILE):
        return 1

    ids = []

    with open(CSV_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.append(int(row["ID"]))

    return max(ids) + 1 if ids else 1


def save_student(student_id, name, enrollment, phone):
    """Append the student record to the local registry CSV."""

    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["ID", "Name", "Enrollment", "ParentPhone"])

        writer.writerow([student_id, name, enrollment, phone])


def _launch_training_process():
    """Start model training in a separate process so registration returns quickly."""

    popen_kwargs = {
        "cwd": os.getcwd(),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if creationflags:
        popen_kwargs["creationflags"] = creationflags

    return subprocess.Popen([sys.executable, "train_model.py"], **popen_kwargs)


def _watch_training_process(process):
    """Restart training once if another registration happened during the current run."""

    global _training_process, _training_pending

    process.wait()

    with _training_lock:
        if _training_process is process:
            _training_process = None
        should_restart = _training_pending
        _training_pending = False

    if should_restart:
        schedule_model_training()


def schedule_model_training():
    """Queue background model training and coalesce repeated registration bursts."""

    global _training_process, _training_pending

    with _training_lock:
        if _training_process is not None and _training_process.poll() is None:
            _training_pending = True
            return "queued"

        try:
            process = _launch_training_process()
        except Exception as exc:
            print(f"[WARNING] Training failed to start: {exc}")
            return f"failed:{exc}"

        _training_process = process

    threading.Thread(
        target=_watch_training_process,
        args=(process,),
        daemon=True,
        name="model-train-watch",
    ).start()
    return "started"


def register_fingerprint(student_id):
    """Request fingerprint enrollment from the ESP32 sensor."""

    messagebox.showinfo(
        "Fingerprint",
        f"Place finger on sensor\nID: {student_id}"
    )

    print(f"[ESP32] Sending enroll request: {student_id}")

    success = notify_fingerprint_register(student_id)

    if success:
        print("[OK] Fingerprint registered")
        messagebox.showinfo("Success", "Fingerprint registered successfully")
        return True
    else:
        print("[ERROR] Fingerprint failed")
        messagebox.showerror("Error", "Fingerprint registration failed")
        return False


def capture_faces(student_id, name, enrollment, phone):
    """Capture face samples and return whether the full registration completed."""

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cam.isOpened():
        messagebox.showerror("Camera Error", "Unable to access camera")
        return False

    cam.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cam.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)

    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades +
        "haarcascade_frontalface_default.xml"
    )

    sample_num = 0
    max_samples = FACE_SAMPLES
    frame_index = 0
    last_face_box = None
    tracked_face_misses = 0
    last_capture_time = 0.0

    folder = os.path.join(DATASET_PATH, f"{name}_{student_id}")
    os.makedirs(folder, exist_ok=True)

    messagebox.showinfo(
        "Face Capture",
        "Look at camera, stay steady, and slightly turn left and right for better accuracy",
    )

    while True:

        ret, img = cam.read()
        if not ret:
            break

        frame_index += 1
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        should_detect = (
            last_face_box is None
            or frame_index % REGISTRATION_DETECTION_INTERVAL == 0
        )
        if should_detect:
            faces = _detect_registration_faces(detector, img, gray, frame_index)
            if len(faces) == 1:
                last_face_box = _sanitize_box(
                    max(faces, key=lambda item: item[2] * item[3]),
                    img.shape,
                )
                tracked_face_misses = 0
                faces = [last_face_box]
            elif len(faces) > 1:
                last_face_box = None
                tracked_face_misses = 0
            else:
                tracked_face_misses += 1
                if tracked_face_misses > REGISTRATION_TRACK_HOLD_FRAMES:
                    last_face_box = None
                faces = [last_face_box] if last_face_box is not None else []
        else:
            faces = [last_face_box] if last_face_box is not None else []

        if len(faces) > 1:
            cv2.putText(
                img,
                "Only one face should be visible",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )
            for (x, y, w, h) in faces:
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
        elif len(faces) == 1:
            x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
            face = gray[y:y+h, x:x+w]
            sample_face = extract_face_sample(img, x, y, w, h)
            quality = measure_face_quality(face)
            color = (0, 165, 255)
            label = "Hold steady"

            if quality["ok"]:
                color = (0, 255, 0)
                now = time.time()
                if (
                    sample_face is not None
                    and (now - last_capture_time) >= REGISTRATION_SAMPLE_COOLDOWN_SECONDS
                ):
                    sample_num += 1
                    cv2.imwrite(os.path.join(folder, f"{sample_num}.jpg"), sample_face)
                    last_capture_time = now
                label = f"Samples: {sample_num}/{max_samples}"
            elif quality["reason"] == "too_dark":
                label = "Need more light"

            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
            cv2.rectangle(img, (x, max(y - 25, 0)), (x + w, y), color, -1)
            cv2.putText(
                img,
                label,
                (x + 5, max(y - 8, 15)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                2
            )

        cv2.imshow("Face Capture", img)

        if cv2.waitKey(1) == 27:
            break

        if sample_num >= max_samples:
            break

    cam.release()
    cv2.destroyAllWindows()

    if sample_num == 0:
        if os.path.isdir(folder):
            os.rmdir(folder)
        messagebox.showerror("Face Capture", "No face samples captured")
        return False

    success = register_fingerprint(student_id)

    if not success:
        if os.path.isdir(folder):
            for file_name in os.listdir(folder):
                os.remove(os.path.join(folder, file_name))
            os.rmdir(folder)
        return False

    save_student(student_id, name, enrollment, phone)

    training_state = schedule_model_training()
    if training_state.startswith("failed:"):
        messagebox.showwarning(
            "Training Warning",
            "Face capture was saved, but model training could not be started. "
            "Attendance may recognize this student as unknown until training runs.",
        )
    elif training_state == "queued":
        messagebox.showinfo(
            "Done",
            f"{name} registered successfully!\n\n"
            "Face model training is already running in the background. "
            "This student will be included in the next training pass.",
        )
    else:
        messagebox.showinfo(
            "Done",
            f"{name} registered successfully!\n\n"
            "Face model training has started in the background.",
        )
    return True


def open_register_window():
    """Open the classic standalone registration form."""

    app = tb.Window(themename="cosmo")
    app.title("Register Student")
    app.geometry("420x450")

    student_id = generate_new_id()

    tb.Label(
        app,
        text=f"Student ID: {student_id}",
        font=("Segoe UI", 12, "bold")
    ).pack(pady=10)

    tb.Label(app, text="Student Name").pack()
    name_entry = tb.Entry(app, width=30)
    name_entry.pack(pady=5)

    tb.Label(app, text="Enrollment Number").pack()
    enroll_entry = tb.Entry(app, width=30)
    enroll_entry.pack(pady=5)

    tb.Label(app, text="Parent Phone Number").pack()
    phone_entry = tb.Entry(app, width=30)
    phone_entry.pack(pady=5)

    def start():

        name = name_entry.get().strip()
        enrollment = enroll_entry.get().strip()
        phone = phone_entry.get().strip()

        if not name or not enrollment:
            messagebox.showerror("Error", "All fields are required")
            return

        app.destroy()
        capture_faces(student_id, name, enrollment, phone)

    tb.Button(
        app,
        text="Start Registration",
        bootstyle="primary",
        width=20,
        command=start
    ).pack(pady=25)

    app.mainloop()


if __name__ == "__main__":
    open_register_window()
