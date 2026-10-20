#!/usr/bin/env python
"""Copy BidKaro collections from a local MongoDB to MongoDB Atlas.

Examples (dry run first, then apply):

    python scripts/migrate-to-atlas.py --target "mongodb+srv://..."
    python scripts/migrate-to-atlas.py --target "mongodb+srv://..." --apply

The target URI can also come from ATLAS_MONGODB_URI. Credentials are never
printed. Uploaded files live under STORAGE_DIR and are not copied by this
script; only MongoDB metadata moves.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from pymongo import MongoClient, ReplaceOne
from pymongo.errors import PyMongoError

try:  # python-dotenv ships with the backend dependencies
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:  # pragma: no cover - optional convenience only
    pass

COLLECTIONS = [
    "users",
    "companies",
    "company_documents",
    "tenders",
    "tender_documents",
    "tender_pages",
    "requirements",
    "checklist_tasks",
    "changes",
    "audit_logs",
    "discovered_tenders",
    "discovery_runs",
]

def host_of(uri: str) -> str:
    try:
        return urlsplit(uri).hostname or "unknown-host"
    except ValueError:
        return "unknown-host"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--source",
        default=os.getenv("SOURCE_MONGODB_URI", "mongodb://localhost:27017"),
        help="Source MongoDB URI (default: local MongoDB).",
    )
    parser.add_argument(
        "--target",
        default=os.getenv("ATLAS_MONGODB_URI", ""),
        help="Target Atlas URI (default: ATLAS_MONGODB_URI).",
    )
    parser.add_argument("--source-db", default="bidkaro", help="Source database name.")
    parser.add_argument("--target-db", default="bidkaro", help="Target database name.")
    parser.add_argument("--batch-size", type=int, default=500, help="Documents per bulk write.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write to the target. Without this flag the script only reports counts.",
    )
    return parser.parse_args()


def connect(uri: str, label: str) -> MongoClient:
    client = MongoClient(
        uri,
        appname="BidKaroMigrate",
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        tz_aware=True,
    )
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        raise SystemExit(f"{label} MongoDB is unreachable at {host_of(uri)} ({type(exc).__name__}).") from exc
    return client


def main() -> int:
    args = parse_args()
    if not args.target:
        raise SystemExit("Provide --target or set ATLAS_MONGODB_URI.")

    source = connect(args.source, "Source")
    target = connect(args.target, "Target")
    source_db = source[args.source_db]
    target_db = target[args.target_db]

    source_counts = {name: source_db[name].count_documents({}) for name in COLLECTIONS}
    target_counts = {name: target_db[name].count_documents({}) for name in COLLECTIONS}

    print(f"Source: {host_of(args.source)}/{args.source_db}")
    print(f"Target: {host_of(args.target)}/{args.target_db}")
    print(f"Mode:   {'APPLY' if args.apply else 'DRY RUN'}\n")
    print(f"{'collection':<22}{'source':>8}{'target':>8}")
    for name in COLLECTIONS:
        print(f"{name:<22}{source_counts[name]:>8}{target_counts[name]:>8}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to copy the documents above.")
        return 0

    copied = 0
    for name in COLLECTIONS:
        collection = source_db[name]
        total = source_counts[name]
        if total == 0:
            continue
        pending: list[ReplaceOne] = []
        for document in collection.find({}):
            pending.append(ReplaceOne({"_id": document["_id"]}, document, upsert=True))
            if len(pending) >= max(args.batch_size, 1):
                target_db[name].bulk_write(pending, ordered=False)
                copied += len(pending)
                pending.clear()
        if pending:
            target_db[name].bulk_write(pending, ordered=False)
            copied += len(pending)
        print(f"copied {name}: {total}")

    print(f"\nCopied {copied} documents.")

    problems = []
    for name in COLLECTIONS:
        missing = [
            document_id
            for document_id in source_db[name].distinct("_id")
            if target_db[name].count_documents({"_id": document_id}, limit=1) == 0
        ]
        if missing:
            problems.append(f"{name}: {len(missing)} missing (example _id {missing[0]})")

    if problems:
        print("Verification failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Verification passed: every source _id exists on the target.")
    print("Indexes are created by the API on startup; restart the backend against the Atlas URI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
