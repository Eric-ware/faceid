import argparse
from src.engine import FaceIDEngine

def main():
    parser = argparse.ArgumentParser(description="Face ID Authentication CLI")
    parser.add_argument("command", choices=["register", "authenticate", "list", "remove"],
                        help="Command to execute")
    parser.add_argument("--name", type=str, help="Name of the user")
    parser.add_argument("--image", type=str, help="Path to the image for registration")
    parser.add_argument("--passphrase", type=str, help="Passphrase for encryption")

    args = parser.parse_args()
    engine = FaceIDEngine(args.passphrase)

    if args.command == "register":
        if args.image:
            success = engine.register_from_image(args.image, args.name)
            if success:
                print(f"User '{args.name}' registered successfully.")
            else:
                print(f"Failed to register user '{args.name}'.")
        else:
            print("Image path is required for registration.")
    
    elif args.command == "authenticate":
        result = engine.authenticate()
        if result["success"]:
            print(f"Authenticated: {result['user']} with confidence {result['confidence']}%.")
        else:
            print(f"Authentication failed: {result['reason']}.")

    elif args.command == "list":
        users = engine.list_users()
        print("Registered users:", ", ".join(users) if users else "No users registered.")

    elif args.command == "remove":
        if args.name:
            success = engine.remove_user(args.name)
            if success:
                print(f"User '{args.name}' removed successfully.")
            else:
                print(f"User '{args.name}' not found.")

if __name__ == "__main__":
    main()