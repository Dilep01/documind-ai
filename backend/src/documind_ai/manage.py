import argparse
import os

from sqlalchemy import select

from documind_ai.auth import hash_password
from documind_ai.database import User, session_factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate", "seed", "process", "train"])
    parser.add_argument("id", nargs="?")
    args = parser.parse_args()
    if args.command == "migrate":
        from alembic import command
        from alembic.config import Config

        command.upgrade(Config("alembic.ini"), "head")
    elif args.command == "seed":
        username = os.environ.get("DOCUMIND_ADMIN_USERNAME", "admin")
        password = os.environ.get("DOCUMIND_ADMIN_PASSWORD", "")
        if len(password) < 12:
            raise SystemExit(
                "Set DOCUMIND_ADMIN_PASSWORD to a unique password of at least 12 characters."
            )
        with session_factory()() as db:
            if not db.scalar(select(User).where(User.username == username)):
                db.add(User(username=username, password_hash=hash_password(password), role="admin"))
                db.commit()
        print("Local administrator is ready. Existing passwords were preserved.")
    elif args.command == "process":
        if not args.id:
            raise SystemExit("A job ID is required.")
        from documind_ai.processing import process

        process(args.id)
    else:
        from documind_ai.training import train

        report = train()
        print(f"Trained synthetic text classifier: {report['counts']}")


if __name__ == "__main__":
    main()
