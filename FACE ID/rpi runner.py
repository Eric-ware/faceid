"""
╔══════════════════════════════════════════════════════════════╗
║     FACE ID — RASPBERRY PI / EMBEDDED PLATFORM             ║
║     Authenticated Identity: Eric                           ║
╚══════════════════════════════════════════════════════════════╝

GPIO wiring (BCM):
  GPIO 17 → Green LED  (granted)
  GPIO 27 → Red LED    (denied)
  GPIO 22 → Door relay
  GPIO 23 → Push button
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core.face_engine import FaceIDEngine, logger

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    class _FakeGPIO:
        BCM = OUT = IN = HIGH = LOW = PUD_UP = FALLING = None
        def setmode(self, *a): pass
        def setup(self, *a, **kw): pass
        def output(self, *a): pass
        def input(self, _): return True
        def cleanup(self): pass
        def wait_for_edge(self, *a, **kw): time.sleep(0.1)
    GPIO = _FakeGPIO()

PIN_LED_GREEN = 17
PIN_LED_RED   = 27
PIN_RELAY     = 22
PIN_BUTTON    = 23
RELAY_OPEN_SEC = 3
AUTH_TIMEOUT   = 20


class EmbeddedFaceID:
    def __init__(self):
        self.engine = FaceIDEngine()
        self._setup_gpio()
        logger.info("Embedded Face ID ready — Owner: Eric")

    def _setup_gpio(self):
        if not GPIO_AVAILABLE: return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_LED_GREEN, GPIO.OUT)
        GPIO.setup(PIN_LED_RED,   GPIO.OUT)
        GPIO.setup(PIN_RELAY,     GPIO.OUT)
        GPIO.setup(PIN_BUTTON,    GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self._led()

    def _led(self, green=False, red=False):
        if GPIO_AVAILABLE:
            GPIO.output(PIN_LED_GREEN, GPIO.HIGH if green else GPIO.LOW)
            GPIO.output(PIN_LED_RED,   GPIO.HIGH if red   else GPIO.LOW)
        else:
            if green: print("  💚 GREEN LED ON")
            elif red: print("  🔴 RED LED ON")
            else:     print("  ⚫ LEDs OFF")

    def _relay_open(self):
        if GPIO_AVAILABLE:
            GPIO.output(PIN_RELAY, GPIO.HIGH)
            time.sleep(RELAY_OPEN_SEC)
            GPIO.output(PIN_RELAY, GPIO.LOW)
        else:
            print(f"  🔓 [SIM] Door open ({RELAY_OPEN_SEC}s)")
            time.sleep(RELAY_OPEN_SEC)
            print("  🔒 [SIM] Door closed")

    def _flash(self, color, times=3, interval=0.2):
        for _ in range(times):
            self._led(green=(color == "green"), red=(color == "red"))
            time.sleep(interval)
            self._led()
            time.sleep(interval)

    def run_auth_cycle(self):
        self._led(red=True)
        result = self.engine.authenticate(require_liveness=True, timeout_sec=AUTH_TIMEOUT)
        if result.get("success"):
            print(f"\n  ✅ ACCESS GRANTED — Eric ({result['confidence']}%)\n")
            self._flash("green", 2)
            self._led(green=True)
            self._relay_open()
            self._led()
        else:
            print(f"\n  ❌ ACCESS DENIED — {result.get('reason')}\n")
            self._flash("red", 4, 0.15)
            self._led()

    def wait_for_button(self):
        if GPIO_AVAILABLE:
            GPIO.wait_for_edge(PIN_BUTTON, GPIO.FALLING)
            return True
        try:
            input("  [SIM] Press ENTER to trigger auth (Ctrl+C to exit): ")
            return True
        except KeyboardInterrupt:
            return False

    def run(self):
        print(f"\n🔐 Embedded Face ID — Owner: Eric")
        print(f"   GPIO: {'enabled' if GPIO_AVAILABLE else 'simulated'}")
        print(f"   Registered users: {len(self.engine.list_users())}")
        print("   Waiting for button press...\n")
        try:
            while True:
                if not self.wait_for_button():
                    break
                time.sleep(0.05)
                self.run_auth_cycle()
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass
        finally:
            if GPIO_AVAILABLE:
                GPIO.cleanup()


if __name__ == "__main__":
    runner = EmbeddedFaceID()
    if not runner.engine.list_users():
        print("No registered faces. Registering Eric from webcam first...\n")
        runner.engine.register_from_webcam(name="Eric", num_samples=5)
    runner.run()