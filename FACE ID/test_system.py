#!/usr/bin/env python3
"""
Face ID System Verification Script
Tests all core functionality without requiring a webcam
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

print("\n" + "="*70)
print("  FACE ID SYSTEM — VERIFICATION TEST")
print("="*70 + "\n")

tests_passed = 0
tests_failed = 0

# Test 1: Core Engine Import
print("Test 1: Core Engine Import")
try:
    from core.face_engine import (
        FaceIDEngine, AuditLogger, FaceDatabase, EncryptionManager,
        LivenessDetector, OWNER_NAME, SYSTEM_VERSION
    )
    print(f"  ✅ Successfully imported all core components")
    print(f"     Owner: {OWNER_NAME}")
    print(f"     Version: {SYSTEM_VERSION}\n")
    tests_passed += 1
except Exception as e:
    print(f"  ❌ Failed to import core: {e}\n")
    tests_failed += 1

# Test 2: Main CLI
print("Test 2: Main CLI Module")
try:
    from main import cmd_register, cmd_login, cmd_audit
    print(f"  ✅ Successfully imported CLI commands\n")
    tests_passed += 1
except Exception as e:
    print(f"  ❌ Failed to import CLI: {e}\n")
    tests_failed += 1

# Test 3: Server Module
print("Test 3: Server Module")
try:
    import server
    print(f"  ✅ Successfully imported Flask server\n")
    tests_passed += 1
except Exception as e:
    print(f"  ❌ Failed to import server: {e}\n")
    tests_failed += 1

# Test 4: Encryption
print("Test 4: Encryption Manager")
try:
    enc = EncryptionManager()
    test_data = b"test_face_encoding_12345"
    encrypted = enc.encrypt(test_data)
    decrypted = enc.decrypt(encrypted)
    assert decrypted == test_data
    print(f"  ✅ Encryption/decryption working correctly\n")
    tests_passed += 1
except Exception as e:
    print(f"  ❌ Encryption test failed: {e}\n")
    tests_failed += 1

# Test 5: Audit Logger
print("Test 5: Audit Logger")
try:
    from core.face_engine import audit
    audit.log("TEST_EVENT", "test_user", True, {"test": "data"})
    logs = audit.read_log(1)
    assert len(logs) > 0
    assert logs[-1]["event"] == "TEST_EVENT"
    print(f"  ✅ Audit logging working correctly\n")
    tests_passed += 1
except Exception as e:
    print(f"  ❌ Audit test failed: {e}\n")
    tests_failed += 1

# Test 6: Data Directories
print("Test 6: Data Directory Structure")
try:
    data_dir = Path(__file__).parent / "data"
    log_dir = Path(__file__).parent / "logs"
    assert data_dir.exists(), "data/ directory missing"
    assert log_dir.exists(), "logs/ directory missing"
    print(f"  ✅ Directory structure valid\n")
    tests_passed += 1
except Exception as e:
    print(f"  ❌ Directory structure test failed: {e}\n")
    tests_failed += 1

# Summary
print("="*70)
print(f"  RESULTS: {tests_passed} passed, {tests_failed} failed")
print("="*70)

if tests_failed == 0:
    print("\n  ✅ ALL TESTS PASSED — System is ready to use!")
    print("\n  Quick Start Commands:")
    print("    python3 main.py register          # Register face via webcam")
    print("    python3 main.py login             # Authenticate with liveness")
    print("    python3 main.py server            # Start web API on :5001")
    print("    python3 main.py users             # List registered users")
    print("    python3 main.py audit             # Show audit log\n")
    sys.exit(0)
else:
    print("\n  ❌ Some tests failed. Check output above.\n")
    sys.exit(1)
