import unittest
from src.engine import FaceIDEngine

class TestFaceIDEngine(unittest.TestCase):

    def setUp(self):
        self.engine = FaceIDEngine(passphrase="test_passphrase")

    def test_register_from_webcam(self):
        result = self.engine.register_from_webcam(name="TestUser", num_samples=5)
        self.assertTrue(result)

    def test_register_from_image(self):
        result = self.engine.register_from_image("path/to/test/image.jpg", name="TestUser")
        self.assertTrue(result)

    def test_authenticate_success(self):
        self.engine.register_from_image("path/to/test/image.jpg", name="TestUser")
        result = self.engine.authenticate(require_liveness=False)
        self.assertTrue(result["success"])
        self.assertEqual(result["user"], "TestUser")

    def test_authenticate_failure(self):
        result = self.engine.authenticate(require_liveness=False)
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "Authentication failed.")

    def test_list_users(self):
        self.engine.register_from_image("path/to/test/image.jpg", name="TestUser")
        users = self.engine.list_users()
        self.assertIn("TestUser", users)

    def test_remove_user(self):
        self.engine.register_from_image("path/to/test/image.jpg", name="TestUser")
        result = self.engine.remove_user("TestUser")
        self.assertTrue(result)
        users = self.engine.list_users()
        self.assertNotIn("TestUser", users)

if __name__ == "__main__":
    unittest.main()