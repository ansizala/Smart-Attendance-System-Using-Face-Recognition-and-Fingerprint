"""Lightweight live preview for testing face detection and recognition output."""

import cv2

from services.camera_service import CameraService


WINDOW_TITLE = "Live Face Detection"


def _draw_status_banner(frame, frame_state):
    """Render a quick status banner for the live detection preview."""

    if frame_state["recognized"]:
        names = ", ".join(student["name"] for student in frame_state["recognized"])
        text = f"Recognized: {names}"
        color = (0, 180, 0)
    elif frame_state["has_unknown_face"]:
        text = "Unknown face detected"
        color = (0, 0, 255)
    elif frame_state["has_face"]:
        text = "Face detected. Hold steady..."
        color = (0, 165, 255)
    else:
        text = "Position your face in front of the camera"
        color = (255, 200, 0)

    help_text = "Press ESC to close"

    cv2.rectangle(frame, (10, 10), (frame.shape[1] - 10, 55), color, -1)
    cv2.putText(
        frame,
        text,
        (20, 33),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
    )
    cv2.putText(
        frame,
        help_text,
        (20, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 0, 0),
        1,
    )


def main():
    """Run the live preview window until the operator closes it."""

    camera = None

    try:
        camera = CameraService()
        print("[INFO] Live detection started")

        while True:
            data = camera.read_frame()
            if data is None:
                continue

            frame, frame_state = data
            _draw_status_banner(frame, frame_state)

            cv2.imshow(WINDOW_TITLE, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break

    except Exception as exc:
        print(f"[ERROR] Live detection failed: {exc}")

    finally:
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()
        print("[INFO] Live detection stopped")


if __name__ == "__main__":
    main()
