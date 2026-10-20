#!/usr/bin/env python
"""Send due BidKaro in-app/email reminders through the existing Gmail SMTP setup.

This is a cron-able job, not a background scheduler. It only sends reminders for
companies that explicitly enabled email reminders in Settings, only for reminders
that are due, and it records every attempt/error in MongoDB.

Examples (run from the repository root, using the backend venv):

    python scripts/send-reminders.py            # dry run, lists what is due
    python scripts/send-reminders.py --apply    # send and record results
    python scripts/send-reminders.py --apply --limit 50

If SMTP_APP_PASSWORD is missing, --apply exits with code 2 and sends nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover - optional convenience only
    pass

from app.core.config import get_settings  # noqa: E402
from app.core.database import Database  # noqa: E402
from app.services.email import EmailService  # noqa: E402
from app.services.reminders import ReminderService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually send email. Without this flag the job only reports what is due.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum reminders to claim per company (default: 100).",
    )
    args = parser.parse_args()

    settings = get_settings()
    database = Database(
        settings.mongodb_uri,
        settings.mongodb_db,
        app_name=f"{settings.mongodb_app_name}-send-reminders",
        max_pool_size=5,
        connect_timeout_ms=settings.mongodb_connect_timeout_ms,
        server_selection_timeout_ms=settings.mongodb_server_selection_timeout_ms,
        retry_writes=settings.mongodb_retry_writes,
    )
    try:
        database.ping()
    except Exception as exc:  # noqa: BLE001 - CLI should fail clearly
        print(f"MongoDB is not reachable: {exc}", file=sys.stderr)
        return 2

    email = EmailService(settings)
    if args.apply and not email.configured:
        print(
            "SMTP_APP_PASSWORD (or SMTP_USERNAME) is not configured. "
            "No reminder emails were sent.",
            file=sys.stderr,
        )
        return 2

    result = ReminderService(database, email=email).send_due(
        dry_run=not args.apply,
        limit=max(args.limit, 1),
        email=email,
    )
    mode = "SEND" if args.apply else "DRY RUN"
    print(
        f"[{mode}] sent={result['sent']} failed={result['failed']} "
        f"companies_skipped={result['companies_skipped']} "
        f"due={len(result['due'])}"
    )
    for item in result["due"]:
        print(
            f"  due {item['due_at'].isoformat()} -> {item['recipient']}: "
            f"{item['title']} ({item['href']})"
        )
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
