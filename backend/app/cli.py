"""Owner CLI: `python -m app.cli hash-password` and `python -m app.cli seed-accounts`."""

import argparse
import getpass
import sys

from sqlmodel import Session, select

from app.core.db import get_engine
from app.core.security import hash_password
from app.models import Account, Platform, Route

SEED_ACCOUNTS = [
    ("IG #1", Platform.ig, Route.ig_direct, None),
    ("IG #2", Platform.ig, Route.ig_direct, None),
    ("YT #1", Platform.youtube, Route.buffer, "28"),  # AI apps: Science & Technology
    ("YT #2", Platform.youtube, Route.buffer, "22"),  # personal vlog: People & Blogs
    ("TikTok", Platform.tiktok, Route.buffer, None),
]


def cmd_hash_password() -> int:
    password = getpass.getpass("Password dashboard baru: ")
    if len(password) < 8:
        print("Password minimal 8 karakter.", file=sys.stderr)
        return 1
    if getpass.getpass("Ulangi password: ") != password:
        print("Password nggak sama.", file=sys.stderr)
        return 1
    # Single quotes keep the `$` characters in the hash literal in .env.
    print(f"ADMIN_PASSWORD_HASH='{hash_password(password)}'")
    return 0


def seed_accounts(session: Session) -> list[str]:
    """Create the five target accounts (without tokens) if missing. Returns created labels."""
    existing = set(session.exec(select(Account.label)).all())
    created = []
    for label, platform, route, category in SEED_ACCOUNTS:
        if label not in existing:
            session.add(
                Account(label=label, platform=platform, route=route, yt_category_id=category)
            )
            created.append(label)
    session.commit()
    return created


def cmd_seed_accounts() -> int:
    with Session(get_engine()) as session:
        created = seed_accounts(session)
    print(f"Akun dibuat: {', '.join(created)}" if created else "Semua akun sudah ada.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hash-password", help="buat ADMIN_PASSWORD_HASH untuk .env")
    sub.add_parser("seed-accounts", help="buat 5 akun tujuan (tanpa token) kalau belum ada")
    args = parser.parse_args()
    return {"hash-password": cmd_hash_password, "seed-accounts": cmd_seed_accounts}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
