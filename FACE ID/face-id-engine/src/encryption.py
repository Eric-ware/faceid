class EncryptionManager:
    def __init__(self, passphrase: str = None):
        self._key = self._load_or_create_key(passphrase)
        self._fernet = Fernet(self._key)

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt,
            iterations=390_000, backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

    def _load_or_create_key(self, passphrase: str) -> bytes:
        if KEY_FILE.exists():
            payload = json.loads(KEY_FILE.read_text())
            salt = base64.b64decode(payload["salt"])
            if passphrase:
                return self._derive_key(passphrase, salt)
            key_b64 = payload.get("key")
            if not key_b64:
                raise RuntimeError("Keystore requires a passphrase or has no stored key.")
            return key_b64.encode()

        salt = os.urandom(16)
        if passphrase:
            key = self._derive_key(passphrase, salt)
            payload = {"salt": base64.b64encode(salt).decode(), "key": None,
                       "created": datetime.utcnow().isoformat(), "owner": OWNER_NAME}
        else:
            key = Fernet.generate_key()
            payload = {"salt": base64.b64encode(salt).decode(),
                       "key": key.decode(),
                       "created": datetime.utcnow().isoformat(), "owner": OWNER_NAME}

        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(json.dumps(payload))
        logger.info(f"Keystore created for owner: {OWNER_NAME}")
        return key

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        return self._fernet.decrypt(token)