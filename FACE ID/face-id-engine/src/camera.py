import cv2

class Camera:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise Exception("Could not open webcam.")

    def capture_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            raise Exception("Failed to capture frame.")
        return frame

    def release(self):
        self.cap.release()
        cv2.destroyAllWindows()