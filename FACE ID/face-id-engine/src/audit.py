class AuditLogger:
    def log(self, event: str, user: str, success: bool, metadata: dict = None):
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event, "user": user,
            "success": success, "metadata": metadata or {},
        }
        with open(SESSION_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
        status = "SUCCESS" if success else "FAILURE"
        logger.info(f"[AUDIT] {status} | event={event} user={user}")

    def read_log(self, last_n: int = 20) -> list:
        if not SESSION_LOG.exists():
            return []
        lines = SESSION_LOG.read_text().strip().split("\n")
        return [json.loads(l) for l in lines[-last_n:] if l]