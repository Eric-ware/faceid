"""
╔══════════════════════════════════════════════════════════════╗
║         FACE ID — DESKTOP / CLI LAUNCHER                    ║
║         Authenticated Identity: Eric                        ║
╚══════════════════════════════════════════════════════════════╝

Usage:
  python3 main.py register         — Register Eric's face via webcam
  python3 main.py register-image   — Register from an image file
  python3 main.py login            — Authenticate with liveness check
  python3 main.py login --no-live  — Authenticate without liveness
  python3 main.py users            — List registered identities
  python3 main.py remove --name X  — Remove a registered user
  python3 main.py audit            — Print recent audit log
  python3 main.py server           — Launch web API server
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from typing import Any, Dict
from core.face_engine import FaceIDEngine, SYSTEM_VERSION

BANNER = f"""
╔══════════════════════════════════════════════════════════════╗
║   FACE ID SYSTEM  v{SYSTEM_VERSION}                                  ║
║   Authenticated Identity: Eric                              ║
║   Platforms: Desktop · Web · Embedded                       ║
╚══════════════════════════════════════════════════════════════╝
"""


def cmd_register(engine: Any, args: Any) -> None:
    name = args.name or "Eric"
    ok = engine.register_from_webcam(name=name, num_samples=args.samples)
    sys.exit(0 if ok else 1)


def cmd_register_image(engine: Any, args: Any) -> None:
    if not args.path:
        print("Provide --path <image_file>")
        sys.exit(1)
    name = args.name or "Eric"
    ok = engine.register_from_image(args.path, name=name)
    sys.exit(0 if ok else 1)


def cmd_login(engine: Any, args: Any) -> None:
    result = engine.authenticate(
        require_liveness=not args.no_live,
        timeout_sec=args.timeout
    )
    if result.get("success"):
        print(f"\n✅ ACCESS GRANTED")
        print(f"   User:       Eric")
        print(f"   Confidence: {result['confidence']}%")
        print(f"   Blinks:     {result['blinks']}")
        print(f"   Duration:   {result['duration_ms']}ms\n")
        sys.exit(0)
    else:
        print(f"\n❌ ACCESS DENIED — {result.get('reason', 'Authentication failed.')}\n")
        sys.exit(1)


def cmd_users(engine: Any, _: Any) -> None:
    users = engine.list_users()
    if not users:
        print("No registered users.")
    else:
        print(f"\nRegistered identities ({len(users)}):")
        for u in users:
            print(f"  • {u}")
        print()


def cmd_remove(engine: Any, args: Any) -> None:
    if not args.name:
        print("Provide --name <username>")
        sys.exit(1)
    ok = engine.remove_user(args.name)
    print(f"{'✅ Removed' if ok else '❌ Not found'}: {args.name}")
    sys.exit(0 if ok else 1)


def cmd_audit(engine: Any, args: Any) -> None:
    entries = engine.audit_log(args.n)
    if not entries:
        print("No audit entries found.")
        return
    print(f"\n{'─' * 66}")
    print(f"  AUDIT LOG — Last {len(entries)} entries  (Owner: Eric)")
    print(f"{'─' * 66}")
    for e in entries:
        status = "✅" if e["success"] else "❌"
        ts = e["timestamp"][:19].replace("T", " ")
        print(f"  {status}  {ts}  [{e['event']:<16}]  user={e['user']}")
        for k, v in (e.get("metadata") or {}).items():  # type: ignore
            print(f"        {k}: {v}")
    print(f"{'─' * 66}\n")


def cmd_server(_: Any, args: Any) -> None:
    print("Starting Face ID web server — owner: Eric")
    os.execlp(
        sys.executable, sys.executable,
        os.path.join(os.path.dirname(__file__), "server.py")
    )


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(prog="faceid",
                                     description="Face ID — Authenticated to Eric")
    parser.add_argument("--passphrase", default=None, help="Encryption passphrase")
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="Register face via webcam")
    p_reg.add_argument("--name", default="Eric")
    p_reg.add_argument("--samples", type=int, default=5)

    p_img = sub.add_parser("register-image", help="Register from image file")
    p_img.add_argument("--path", required=True)
    p_img.add_argument("--name", default="Eric")

    p_log = sub.add_parser("login", help="Authenticate via webcam")
    p_log.add_argument("--no-live", action="store_true", help="Skip liveness check")
    p_log.add_argument("--timeout", type=int, default=30)

    sub.add_parser("users", help="List registered identities")

    p_rem = sub.add_parser("remove", help="Remove a user")
    p_rem.add_argument("--name", required=True)

    p_aud = sub.add_parser("audit", help="Show audit log")
    p_aud.add_argument("--n", type=int, default=20)

    sub.add_parser("server", help="Launch web API server")

    args   = parser.parse_args()
    engine = FaceIDEngine(passphrase=args.passphrase)

    commands: Dict[str, Any] = {
        "register":       cmd_register,
        "register-image": cmd_register_image,
        "login":          cmd_login,
        "users":          cmd_users,
        "remove":         cmd_remove,
        "audit":          cmd_audit,
        "server":         cmd_server,
    }
    commands[args.command](engine, args)


if __name__ == "__main__":
    main()