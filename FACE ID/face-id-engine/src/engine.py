"""
Main Face ID engine — owner: Eric
Handles registration, authentication, liveness, and audit trail.
"""

import cv2
import face_recognition
import numpy as np
import time
import uuid
from datetime import datetime
from .encryption import EncryptionManager
from .database import FaceDatabase
from .liveness import LivenessDetector
from .audit import AuditLogger

OWNER_NAME = "Eric"
SYSTEM_VERSION = "2.0.0"
MAX_LOGIN_ATTEMPTS = 3
FACE_MATCH_TOLERANCE = 0.45


class FaceIDEngine:
    def __init__(self, passphrase: str = None):
        self._enc = EncryptionManager(passphrase)
        self._db = FaceDatabase(self._enc)
        self._liveness = LivenessDetector()
        print(f"FaceID Engine v{SYSTEM_VERSION} — owner: {OWNER_NAME}")

    def register_from_webcam(self, name: str = OWNER_NAME, num_samples: int = 5) -> bool:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Cannot open webcam.")
            return False

        encodings, collected = [], 0
        print(f"\n>>> Look at the camera. Collecting samples for {name}...\n")

        while collected < num_samples:
            ret, frame = cap.read()
            if not ret:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locs = face_recognition.face_locations(rgb, model="hog")
            encs = face_recognition.face_encodings(rgb, locs)
            cv2.putText(frame, f"Registering {name} [{collected}/{num_samples}]",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 200, 100), 2)
            for (top, right, bottom, left) in locs:
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 100), 2)
            cv2.imshow("Face Registration", frame)
            if encs:
                encodings.append(encs[0])
                collected += 1
                time.sleep(0.4)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        if not encodings:
            print("No face samples captured.")
            return False

        fp = self._db.register(name, np.mean(encodings, axis=0))
        print(f"\n✅ {name} registered. Fingerprint: {fp}\n")
        return True

    def authenticate(self, require_liveness: bool = True, timeout_sec: int = 30) -> dict:
        db = self._db.get_all()
        if not db:
            return {"success": False, "reason": "No registered faces."}

        known_encodings = [v["encoding"] for v in db.values()]
        known_names = list(db.keys())

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return {"success": False, "reason": "Webcam unavailable."}

        self._liveness.reset()
        attempts = 0
        start = time.time()
        BLINKS_REQUIRED = 2 if require_liveness else 0

        print("\n>>> Look at the camera to authenticate...\n")

        while True:
            elapsed = time.time() - start
            if elapsed > timeout_sec:
                break

            ret, frame = cap.read()
            if not ret:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locs = face_recognition.face_locations(rgb, model="hog")
            encs = face_recognition.face_encodings(rgb, locs)

            for (top, right, bottom, left), enc in zip(locs, encs):
                distances = face_recognition.face_distance(known_encodings, enc)
                best_idx = int(np.argmin(distances))
                best_dist = float(distances[best_idx])
                matched = best_dist < FACE_MATCH_TOLERANCE
                color = (0, 230, 100) if matched else (0, 60, 255)

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

                if matched:
                    confidence = round((1 - best_dist) * 100, 1)
                    cv2.putText(frame, f"{known_names[best_idx]} ({confidence}%)", (left, top - 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                    if self._liveness.check_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))['blinks'] >= BLINKS_REQUIRED:
                        cap.release()
                        cv2.destroyAllWindows()
                        return {"success": True, "user": known_names[best_idx], "confidence": confidence}
                else:
                    attempts += 1
                    if attempts >= MAX_LOGIN_ATTEMPTS:
                        cap.release()
                        cv2.destroyAllWindows()
                        return {"success": False, "reason": "Max attempts exceeded."}

            cv2.imshow("Face ID", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        return {"success": False, "reason": "Authentication failed."}

    def list_users(self) -> list:
        return self._db.list_users()

    def remove_user(self, name: str) -> bool:
        return self._db.remove(name)