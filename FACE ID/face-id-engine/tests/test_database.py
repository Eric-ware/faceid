import pytest
import numpy as np
from src.database import FaceDatabase
from src.encryption import EncryptionManager

@pytest.fixture
def encryption_manager():
    return EncryptionManager(passphrase="test_passphrase")

@pytest.fixture
def face_database(encryption_manager):
    return FaceDatabase(encryption=encryption_manager)

def test_register_and_retrieve(face_database):
    name = "Test User"
    encoding = np.random.rand(128)  # Simulated face encoding
    fingerprint = face_database.register(name, encoding)

    assert fingerprint is not None
    assert name in face_database.get_all()
    assert np.array_equal(face_database.get_all()[name]["encoding"], encoding)

def test_remove_user(face_database):
    name = "User to Remove"
    encoding = np.random.rand(128)
    face_database.register(name, encoding)

    assert face_database.remove(name) is True
    assert name not in face_database.get_all()

def test_list_users(face_database):
    users = ["User1", "User2", "User3"]
    for user in users:
        face_database.register(user, np.random.rand(128))

    assert set(face_database.list_users()) == set(users)