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
            import dlib
            model_path = Path(__file__).resolve().parent.parent / "data" / "shape_predictor_68_face_landmarks.dat"
            if model_path.exists():
                self._detector  = dlib.get_frontal_face_detector()
                self._predictor = dlib.shape_predictor(str(model_path))
                logger.info("Liveness: dlib predictor loaded.")
            else:
                logger.warning("Landmark model not found — using motion fallback.")
        except ImportError:
            logger.warning("dlib not available — using motion fallback.")

    def _ear(self, pts) -> float:
        A = np.linalg.norm(pts[1] - pts[5])
        B = np.linalg.norm(pts[2] - pts[4])
        C = np.linalg.norm(pts[0] - pts[3])
        return (A + B) / (2.0 * C) if C > 0 else 0.0

    def check_frame(self, gray: np.ndarray) -> dict:
        result = {"ear": None, "blink_detected": False, "blinks": self.blink_count}
        if self._predictor is None:
            variance = float(np.var(gray))
            result.update({"variance": variance, "live_signal": variance > 200})
            return result
        import dlib
        for face in self._detector(gray, 0):
            shape = self._predictor(gray, face)
            pts   = np.array([[shape.part(i).x, shape.part(i).y] for i in range(68)])
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