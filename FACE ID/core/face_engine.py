"""
Face ID Authentication Engine
Minimal self-contained engine used by server.py
Owner: Eric
"""

import os
import json
import time
import uuid
import base64
import pickle
import logging
import hashlib
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# optional heavy deps used by runtime features
try:
    import cv2
    import face_recognition  # type: ignore
except Exception:
    cv2 = None
    face_recognition = None

BASE_DIR        = Path(__file__).resolve().parent.parent
DATA_DIR        = BASE_DIR / "data"
LOG_DIR         = BASE_DIR / "logs"
KEY_FILE        = DATA_DIR / ".keystore"
FACES_FILE      = DATA_DIR / "faces.enc"
AUDIT_LOG       = LOG_DIR  / "audit.log"
SESSION_LOG     = LOG_DIR  / "sessions.jsonl"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

OWNER_NAME             = "Eric"
SYSTEM_VERSION         = "2.0.0"
MAX_LOGIN_ATTEMPTS     = 3
LIVENESS_BLINK_THRESH  = 0.25
LIVENESS_EAR_FRAMES    = 2
FACE_MATCH_TOLERANCE   = 0.45


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("FaceID")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    if not logger.handlers:
        fh = logging.FileHandler(AUDIT_LOG)
        fh.setFormatter(fmt)
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger

logger = _setup_logger()


class EncryptionManager:
    def __init__(self, passphrase: Optional[str] = None):
        self._key    = self._load_or_create_key(passphrase)
        self._fernet = Fernet(self._key)

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt,
            iterations=390_000, backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

    def _load_or_create_key(self, passphrase: Optional[str]) -> bytes:
        if KEY_FILE.exists():
            payload = json.loads(KEY_FILE.read_text())
            salt    = base64.b64decode(payload["salt"])
            if passphrase:
                return self._derive_key(passphrase, salt)
            key_b64 = payload.get("key")
            if not key_b64:
                raise RuntimeError("Keystore requires a passphrase or has no stored key.")
            return key_b64.encode()

        salt = os.urandom(16)
        if passphrase:
            key     = self._derive_key(passphrase, salt)
            payload: Dict[str, Any] = {"salt": base64.b64encode(salt).decode(), "key": None,
                       "created": datetime.now(timezone.utc).isoformat(), "owner": OWNER_NAME}
        else:
            key     = Fernet.generate_key()
            payload = {"salt": base64.b64encode(salt).decode(),
                       "key": key.decode(),
                       "created": datetime.now(timezone.utc).isoformat(), "owner": OWNER_NAME}

        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(json.dumps(payload))
        logger.info(f"Keystore created for owner: {OWNER_NAME}")
        return key

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        return self._fernet.decrypt(token)


class AuditLogger:
    def log(self, event: str, user: str, success: bool, metadata: Optional[Dict[str, Any]] = None) -> None:
        entry: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "event": event, "user": user,
            "success": success, "metadata": metadata or {},
        }
        with open(SESSION_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
        status = "SUCCESS" if success else "FAILURE"
        logger.info(f"[AUDIT] {status} | event={event} user={user}")

    def read_log(self, last_n: int = 20) -> List[Dict[str, Any]]:
        if not SESSION_LOG.exists():
            return []
        lines = SESSION_LOG.read_text().strip().split("\n")
        return [json.loads(l) for l in lines[-last_n:] if l]


audit = AuditLogger()


class FaceDatabase:
    def __init__(self, encryption: EncryptionManager):
        self._enc = encryption
        self._db: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if FACES_FILE.exists():
            try:
                return pickle.loads(self._enc.decrypt(FACES_FILE.read_bytes()))
            except Exception:
                logger.exception("Failed to decrypt or load face database.")
                return {}
        return {}

    def _save(self):
        FACES_FILE.write_bytes(self._enc.encrypt(pickle.dumps(self._db)))

    def register(self, name: str, encoding: np.ndarray, meta: Optional[Dict[str, Any]] = None) -> str:
        fp = hashlib.sha256(encoding.tobytes()).hexdigest()[:12]
        self._db[name] = {
            "encoding": encoding, "fingerprint": fp,
            "registered": datetime.now(timezone.utc).isoformat(), "meta": meta or {},
        }
        self._save()
        logger.info(f"Registered '{name}' [fp={fp}]")
        return fp

    def get_all(self) -> Dict[str, Any]:
        return self._db

    def remove(self, name: str) -> bool:
        if name in self._db:
            del self._db[name]
            self._save()
            return True
        return False

    def list_users(self) -> List[str]:
        return list(self._db.keys())


class LivenessDetector:
    LEFT_EYE  = list(range(36, 42))
    RIGHT_EYE = list(range(42, 48))

    def __init__(self):
        self.blink_count = 0
        self._ear_below  = 0
        self._predictor  = None
        self._detector   = None
        self._init_dlib()

    def _init_dlib(self):
        try:
            import dlib  # type: ignore
            model_path = DATA_DIR / "shape_predictor_68_face_landmarks.dat"
            if model_path.exists():
                self._detector  = dlib.get_frontal_face_detector()  # type: ignore
                self._predictor = dlib.shape_predictor(str(model_path))  # type: ignore
                logger.info("Liveness: dlib predictor loaded.")
            else:
                logger.warning("Landmark model not found — using motion fallback.")
        except ImportError:
            logger.warning("dlib not available — using motion fallback.")

    def _ear(self, pts: np.ndarray) -> float:
        A = np.linalg.norm(pts[1] - pts[5])
        B = np.linalg.norm(pts[2] - pts[4])
        C = np.linalg.norm(pts[0] - pts[3])
        return float((A + B) / (2.0 * C) if C > 0 else 0.0)

    def check_frame(self, gray: np.ndarray) -> Dict[str, Any]:
        result: Dict[str, Any] = {"ear": None, "blink_detected": False, "blinks": self.blink_count}
        if self._predictor is None:  # type: ignore
            variance = float(np.var(gray))
            result.update({"variance": variance, "live_signal": variance > 200})
            return result
        import dlib  # type: ignore
        for face in self._detector(gray, 0):  # type: ignore
            shape = self._predictor(gray, face)  # type: ignore
            pts   = np.array([[shape.part(i).x, shape.part(i).y] for i in range(68)])  # type: ignore
            ear   = (self._ear(pts[self.LEFT_EYE]) + self._ear(pts[self.RIGHT_EYE])) / 2.0
            result["ear"] = ear
            if ear < LIVENESS_BLINK_THRESH:
                self._ear_below += 1
            else:
                if self._ear_below >= LIVENESS_EAR_FRAMES:
                    self.blink_count += 1
                    result["blink_detected"] = True
                self._ear_below = 0
            result["blinks"] = self.blink_count
        return result

    def reset(self):
        self.blink_count = 0
        self._ear_below  = 0


class FaceIDEngine:
    def __init__(self, passphrase: Optional[str] = None):
        logger.info(f"FaceID Engine v{SYSTEM_VERSION} — owner: {OWNER_NAME}")
        self._enc      = EncryptionManager(passphrase)
        self._db       = FaceDatabase(self._enc)
        self._liveness = LivenessDetector()

    def register_from_webcam(self, name: str = OWNER_NAME, num_samples: int = 5) -> bool:
        if cv2 is None or face_recognition is None:
            raise RuntimeError("cv2 and face_recognition not installed.")
        logger.info(f"Registration: '{name}' ({num_samples} samples)")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Cannot open webcam.")
            return False

        encodings, collected = [], 0
        print(f"\n>>> Look at the camera. Collecting samples for {name}...\n")

        while collected < num_samples:
            ret, frame = cap.read()
            if not ret:
                continue
            rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locs = face_recognition.face_locations(rgb, model="hog")  # type: ignore
            encs = face_recognition.face_encodings(rgb, locs)  # type: ignore
            cv2.putText(frame, f"Registering {name} [{collected}/{num_samples}]",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 200, 100), 2)
            for (top, right, bottom, left) in locs:  # type: ignore
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 100), 2)  # type: ignore
            cv2.imshow(f"Face Registration — {name}", frame)
            if encs:
                encodings.append(encs[0])  # type: ignore
                collected += 1
                time.sleep(0.4)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

        if not encodings:
            logger.error("No face samples captured.")
            return False

        fp = self._db.register(name, np.mean(encodings, axis=0), {"samples": num_samples})  # type: ignore
        audit.log("REGISTER", name, True, {"fingerprint": fp, "samples": num_samples})
        print(f"\n✅ {name} registered. Fingerprint: {fp}\n")
        return True

    def authenticate(self, require_liveness: bool = True, timeout_sec: int = 30) -> Dict[str, Any]:
        if cv2 is None or face_recognition is None:
            raise RuntimeError("cv2 and face_recognition not installed.")
        db = self._db.get_all()
        if not db:
            return {"success": False, "reason": "No registered faces."}

        known_encodings = [v["encoding"] for v in db.values()]
        known_names     = list(db.keys())

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return {"success": False, "reason": "Webcam unavailable."}

        self._liveness.reset()
        attempts        = 0
        start           = time.time()
        BLINKS_REQUIRED = 2 if require_liveness else 0

        print("\n>>> Look at the camera to authenticate...\n")
        logger.info(f"Auth session — liveness={'on' if require_liveness else 'off'}")

        while True:
            elapsed = time.time() - start
            if elapsed > timeout_sec:
                audit.log("AUTH_TIMEOUT", "unknown", False, {"elapsed": round(elapsed, 1)})
                break

            ret, frame = cap.read()
            if not ret:
                continue

            rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            locs = face_recognition.face_locations(rgb, model="hog")  # type: ignore
            encs = face_recognition.face_encodings(rgb, locs)  # type: ignore

            blinks = self._liveness.check_frame(gray).get("blinks", 0)

            for (top, right, bottom, left), enc in zip(locs, encs):  # type: ignore
                distances = face_recognition.face_distance(known_encodings, enc)  # type: ignore
                best_idx  = int(np.argmin(distances))
                best_dist = float(distances[best_idx])
                matched   = best_dist < FACE_MATCH_TOLERANCE
                color     = (0, 230, 100) if matched else (0, 60, 255)

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)  # type: ignore

                if matched:
                    confidence = round((1 - best_dist) * 100, 1)
                    matched_name = known_names[best_idx]
                    cv2.putText(frame, f"{matched_name} ({confidence}%)", (left, top - 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                    if blinks >= BLINKS_REQUIRED:
                        result: Dict[str, Any] = {
                            "success": True, "user": matched_name,
                            "confidence": confidence, "blinks": blinks,
                            "duration_ms": round((time.time() - start) * 1000),
                        }
                        cap.release()
                        cv2.destroyAllWindows()
                        audit.log("AUTH_SUCCESS", matched_name, True, result)
                        logger.info(f"✅ Authenticated: {matched_name} [{confidence}%]")
                        return result
                    else:
                        cv2.putText(frame, f"Blink to verify ({blinks}/{BLINKS_REQUIRED})",
                                    (left, bottom + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)  # type: ignore
                else:
                    cv2.putText(frame, "Unknown", (left, top - 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                    attempts += 1
                    if attempts >= MAX_LOGIN_ATTEMPTS * 10:
                        cap.release()
                        cv2.destroyAllWindows()
                        audit.log("AUTH_FAIL", "unknown", False, {"attempts": attempts})
                        return {"success": False, "reason": "Max attempts exceeded."}

            hud = [f"Blinks: {blinks}/{BLINKS_REQUIRED}",
                   f"Time left: {int(timeout_sec - elapsed)}s", "Q = cancel"]
            for i, line in enumerate(hud):
                cv2.putText(frame, line, (10, 28 + i * 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 1)

            cv2.imshow("Face ID Authentication", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                audit.log("AUTH_CANCELLED", "unknown", False)
                break

        cap.release()
        cv2.destroyAllWindows()
        return {"success": False, "reason": "Authentication failed."}

    def register_from_image(self, image_path: str, name: str = OWNER_NAME) -> bool:
        if face_recognition is None:
            raise RuntimeError("face_recognition not installed.")
        img  = face_recognition.load_image_file(image_path)  # type: ignore
        encs = face_recognition.face_encodings(img)  # type: ignore
        if not encs:
            logger.error(f"No face in image: {image_path}")
            audit.log("REGISTER", name, False, {"reason": "no_face_in_image"})
            return False
        fp = self._db.register(name, encs[0], {"source": str(image_path)})  # type: ignore
        audit.log("REGISTER", name, True, {"fingerprint": fp})
        return True

    def list_users(self) -> List[str]:
        return self._db.list_users()

    def remove_user(self, name: str) -> bool:
        ok = self._db.remove(name)
        audit.log("REMOVE_USER", name, ok)
        return ok

    def audit_log(self, last_n: int = 20) -> List[Dict[str, Any]]:
        return audit.read_log(last_n)
