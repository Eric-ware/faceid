import unittest
from src.encryption import EncryptionManager

class TestEncryptionManager(unittest.TestCase):

    def setUp(self):
        self.passphrase = "test_passphrase"
        self.encryption_manager = EncryptionManager(self.passphrase)

    def test_encrypt_decrypt(self):
        original_data = b"Sensitive data"
        encrypted_data = self.encryption_manager.encrypt(original_data)
        decrypted_data = self.encryption_manager.decrypt(encrypted_data)
        self.assertEqual(original_data, decrypted_data)

    def test_key_generation(self):
        key1 = self.encryption_manager._key
        new_encryption_manager = EncryptionManager(self.passphrase)
        key2 = new_encryption_manager._key
        self.assertEqual(key1, key2)

    def test_invalid_decryption(self):
        with self.assertRaises(Exception):
            self.encryption_manager.decrypt(b"invalid_token")

if __name__ == "__main__":
    unittest.main()