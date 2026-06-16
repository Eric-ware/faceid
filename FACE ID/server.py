#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║           FACE ID — WEB BACKEND (Flask REST API)            ║
║           Authenticated Identity: Eric                      ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
from pathlib import Path
import base64
import numpy as np
import cv2
from datetime import datetime, timezone
from typing import Optional, Any, Tuple, Dict, List

# Ensure project root is on sys.path
proj_root = Path(__file__).resolve().parent
sys.path.insert(0, str(proj_root))

# Import core modules
try:
    from core.face_engine import FaceIDEngine, audit, FACE_MATCH_TOLERANCE, OWNER_NAME, SYSTEM_VERSION
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        f"{e}. Ensure there is a 'core' package in {proj_root} and a module named 'face_engine.py'."
    )

from flask import Flask, request, jsonify
from flask_cors import CORS
import face_recognition  # type: ignore

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize engine (lazy — don't load face_recognition yet)
engine = None

def init_engine():
    global engine
    if engine is None:
        try:
            engine = FaceIDEngine()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize FaceIDEngine: {e}")
    return engine


def _decode_image(b64: str) -> np.ndarray:
    """Decode base64 image string to numpy array (RGB)"""
    if "," in b64:
        b64 = b64.split(",")[1]
    try:
        nparr = np.frombuffer(base64.b64decode(b64), np.uint8)
        bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError("cv2.imdecode failed — invalid image data")
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    except Exception as e:
        raise ValueError(f"Failed to decode image: {e}")


def _resp(success: bool, data: Optional[Dict[str, Any]] = None, error: Optional[str] = None, status: int = 200) -> Tuple[Any, int]:
    """Build standardized JSON response"""
    payload: Dict[str, Any] = {
        "success": success,
        "owner": OWNER_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "") + "Z",
        "version": SYSTEM_VERSION,
    }
    if data:
        payload["data"] = data
    if error:
        payload["error"] = error
    return jsonify(payload), status


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    try:
        eng = init_engine()
        users = eng.list_users()
        return _resp(True, {
            "status": "healthy",
            "registered_users": len(users),
            "engine_version": SYSTEM_VERSION,
        })
    except Exception as e:
        return _resp(False, error=str(e), status=500)


@app.route("/api/register", methods=["POST"])
def register():
    """Register a new face from base64 image"""
    try:
        eng = init_engine()
        data = request.get_json()
        if not data:
            return _resp(False, error="No JSON body", status=400)

        name = data.get("name", OWNER_NAME)
        image_b64 = data.get("image")

        if not image_b64:
            return _resp(False, error="Missing 'image' field", status=400)

        # Decode image and register
        rgb = _decode_image(image_b64)
        encs = face_recognition.face_encodings(rgb)  # type: ignore

        if not encs:
            audit.log("REGISTER", name, False, {"reason": "no_face_detected"})
            return _resp(False, error="No face detected in image", status=400)

        fp = eng._db.register(name, encs[0], {"source": "web_api"})  # type: ignore
        audit.log("REGISTER", name, True, {"fingerprint": fp})

        return _resp(True, {"name": name, "fingerprint": fp, "message": f"{name} registered successfully"})

    except Exception as e:
        return _resp(False, error=str(e), status=500)


@app.route("/api/authenticate", methods=["POST"])
def authenticate():
    """Authenticate user from base64 image"""
    try:
        eng = init_engine()
        data = request.get_json()
        if not data:
            return _resp(False, error="No JSON body", status=400)

        image_b64 = data.get("image")

        if not image_b64:
            return _resp(False, error="Missing 'image' field", status=400)

        # Decode and authenticate
        rgb = _decode_image(image_b64)

        db = eng._db.get_all()  # type: ignore
        if not db:
            audit.log("AUTH", "unknown", False, {"reason": "no_registered_faces"})
            return _resp(False, error="No registered faces", status=400)

        known_names: List[str] = [name for name in db.keys()]  # type: ignore
        known_encs: List[Any] = [db[name]["encoding"] for name in known_names]  # type: ignore

        encs = face_recognition.face_encodings(rgb)  # type: ignore
        if not encs:
            audit.log("AUTH", "unknown", False, {"reason": "no_face_in_image"})
            return _resp(False, error="No face detected in image", status=400)

        enc = encs[0]  # type: ignore
        distances = face_recognition.face_distance(known_encs, enc)  # type: ignore
        best_idx = int(np.argmin(distances))
        best_dist = float(distances[best_idx])
        matched = best_dist < FACE_MATCH_TOLERANCE

        if matched:
            matched_name: str = known_names[best_idx]
            confidence = round(max(0.0, (1 - best_dist)) * 100, 1)
            audit.log("AUTH", matched_name, True, {"confidence": confidence})
            return _resp(True, {
                "user": matched_name,
                "confidence": confidence,
                "message": f"Authenticated as {matched_name}"
            })
        else:
            audit.log("AUTH", "unknown", False, {"reason": "no_match"})
            return _resp(False, error="Face not recognized", status=401)

    except Exception as e:
        return _resp(False, error=str(e), status=500)


@app.route("/api/users", methods=["GET"])
def list_users():
    """List all registered users"""
    try:
        eng = init_engine()
        users = eng.list_users()
        return _resp(True, {"users": users, "count": len(users)})
    except Exception as e:
        return _resp(False, error=str(e), status=500)


@app.route("/api/users/<name>", methods=["DELETE"])
def delete_user(name: str):
    """Remove a registered user"""
    try:
        eng = init_engine()
        ok = eng.remove_user(name)
        if ok:
            audit.log("DELETE_USER", name, True)
            return _resp(True, {"message": f"User '{name}' deleted"})
        else:
            audit.log("DELETE_USER", name, False, {"reason": "user_not_found"})
            return _resp(False, error=f"User '{name}' not found", status=404)
    except Exception as e:
        return _resp(False, error=str(e), status=500)


@app.route("/api/audit", methods=["GET"])
def get_audit():
    """Get audit log (last N entries)"""
    try:
        eng = init_engine()
        last_n = request.args.get("last_n", 20, type=int)
        logs = eng.audit_log(last_n)
        return _resp(True, {"entries": logs, "count": len(logs)})
    except Exception as e:
        return _resp(False, error=str(e), status=500)


@app.errorhandler(404)
def not_found(e: Exception) -> Tuple[Any, int]:
    return _resp(False, error="Endpoint not found", status=404)


@app.errorhandler(500)
def server_error(e: Exception) -> Tuple[Any, int]:
    return _resp(False, error="Internal server error", status=500)


if __name__ == "__main__":
    print("\n🔐 Face ID Web Server — Owner: Eric")
    print(f"   Version: {SYSTEM_VERSION}")
    print(f"   http://localhost:5001\n")
    app.run(host="0.0.0.0", port=5001, debug=False)