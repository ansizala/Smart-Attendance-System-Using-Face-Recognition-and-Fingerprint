"""Simple Tkinter camera feed preview used for quick local testing."""

import cv2
from PIL import Image, ImageTk


class CameraFeed:
    """Continuously push frames from the webcam into a Tkinter label."""

    def __init__(self, label):

        self.cap = cv2.VideoCapture(0)

        self.label = label

        self.update_frame()

    def update_frame(self):

        ret, frame = self.cap.read()

        if ret:

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            img = Image.fromarray(frame)

            imgtk = ImageTk.PhotoImage(image=img)

            self.label.imgtk = imgtk

            self.label.configure(image=imgtk)

        self.label.after(30, self.update_frame)
