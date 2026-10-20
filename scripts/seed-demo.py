#!/usr/bin/env python
"""Seed deterministic, clearly labelled demo data for the BidKaro walkthrough.

This script never invents an official tender. It works on the synthetic sample
created by ``scripts/make-sample-tender.py`` and replaces only that tender's
requirements, evidence decisions, checklist tasks, obligations, snapshots and
reminders. Company evidence documents are marked as synthetic demo evidence.

Run from the repository root with the backend virtualenv:

    python scripts/seed-demo.py --email asha.phase1@example.com

By default it uses the MongoDB settings from the environment / .env. Set
``MONGODB_URI`` and ``MONGODB_DB`` to target a local database.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover - optional convenience only
    pass

import pymupdf  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import Database, redact_mongodb_uri, utcnow  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.repositories.assessment import EvidenceRepository  # noqa: E402
from app.repositories.companies import CompanyRepository  # noqa: E402
from app.repositories.tender_documents import (  # noqa: E402
    RequirementRepository,
    TenderDocumentRepository,
)
from app.repositories.tenders import ChecklistRepository, TenderRepository  # noqa: E402
from app.repositories.users import UserRepository  # noqa: E402
from app.repositories.workflow import (  # noqa: E402
    ChangeRepository,
    SnapshotRepository,
    ReminderRepository,
)
from app.services.assessment import AssessmentService  # noqa: E402
from app.services.requirement_service import normalize_for_match  # noqa: E402
from app.services.storage import StorageService  # noqa: E402
from app.services.workflow import WorkflowService  # noqa: E402

SEED_TIME = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
SAMPLE_REFERENCE = "DSIA/RFP/2026/ROAD-014"

# Fallback company profile. It is only used to fill fields that are still
# empty, so a profile the user edited is never overwritten.
DEMO_PROFILE = {
    "legal_name": "Asha Infrastructure Private Limited",
    "business_type": "private_limited",
    "description": "Roads, bridges and municipal civil works across western India.",
    "products_services": ["Road construction"],
    "sectors": ["Infrastructure"],
    "regions": ["Maharashtra"],
    "annual_turnover": 125000000.0,
    "employee_count": 240,
    "established_year": 2011,
    "onboarding_completed": True,
}
DEMO_PREFERENCES = {
    "sectors": ["Infrastructure"],
    "regions": ["Maharashtra"],
    "keywords": ["highway maintenance"],
    "min_value": 1000000.0,
    "max_value": 500000000.0,
}


def _profile_patch(company: dict) -> dict:
    patch = {
        key: value
        for key, value in DEMO_PROFILE.items()
        if not company.get(key)
    }
    preferences = dict(company.get("preferences") or {})
    for key, value in DEMO_PREFERENCES.items():
        if not preferences.get(key):
            preferences[key] = value
    if preferences != (company.get("preferences") or {}):
        patch["preferences"] = preferences
    return patch

REQUIREMENTS = [
    {
        "key": "turnover",
        "title": "Minimum average annual turnover",
        "category": "financial",
        "mandatory": "yes",
        "page_index": 3,
        "clause_reference": "3.1",
        "excerpt": (
            "The bidder shall have an average annual turnover of at least INR 5 crore "
            "during the last three financial years ending 31 March 2026."
        ),
        "deadline_text": "Before the bid due date (15 November 2026, 17:00 IST)",
    },
    {
        "key": "similar_work",
        "title": "One similar completed work of at least INR 4 crore",
        "category": "technical",
        "mandatory": "yes",
        "page_index": 3,
        "clause_reference": "3.2",
        "excerpt": (
            "The bidder shall have completed at least one similar work of value not less "
            "than INR 4 crore in the last five years. A completion certificate from the "
            "client must be enclosed."
        ),
        "deadline_text": "Before the bid due date (15 November 2026, 17:00 IST)",
    },
    {
        "key": "iso",
        "title": "Valid ISO 9001:2015 certification",
        "category": "eligibility",
        "mandatory": "yes",
        "page_index": 3,
        "clause_reference": "3.3",
        "excerpt": (
            "The bidder shall hold a valid ISO 9001:2015 quality management "
            "certification on the bid due date."
        ),
        "deadline_text": "On the bid due date (15 November 2026)",
    },
    {
        "key": "gst_pan",
        "title": "GST registration and valid PAN",
        "category": "eligibility",
        "mandatory": "yes",
        "page_index": 3,
        "clause_reference": "3.4",
        "excerpt": (
            "The bidder shall be registered under the Goods and Services Tax Act and "
            "shall possess a valid Permanent Account Number."
        ),
        "deadline_text": "Before the bid due date",
    },
    {
        "key": "non_blacklisting",
        "title": "Non-blacklisting self-declaration",
        "category": "compliance",
        "mandatory": "yes",
        "page_index": 3,
        "clause_reference": "3.5",
        "excerpt": (
            "The bidder shall not be blacklisted or debarred by any government authority "
            "as on the bid due date. A self-declaration on company letterhead is required."
        ),
        "deadline_text": "Before the bid due date",
    },
    {
        "key": "bid_security",
        "title": "Bid security of INR 2,00,000",
        "category": "financial",
        "mandatory": "yes",
        "page_index": 3,
        "clause_reference": "3.6",
        "excerpt": (
            "A bid security of INR 2,00,000 shall be furnished in favour of the Demo "
            "State Infrastructure Authority, valid for 45 days beyond the bid validity "
            "period. Bids without valid bid security shall be rejected."
        ),
        "deadline_text": "With the bid, before 15 November 2026, 17:00 IST",
        "consequence_text": "Bids without valid bid security shall be rejected.",
    },
    {
        "key": "key_personnel",
        "title": "Project manager and quality assurance engineer",
        "category": "technical",
        "mandatory": "yes",
        "page_index": 4,
        "clause_reference": "4.1",
        "excerpt": (
            "The bidder shall deploy a project manager with at least 10 years of "
            "experience in highway construction and a quality assurance engineer with at "
            "least 5 years of experience. Curriculum vitae and experience certificates "
            "shall be submitted with the bid."
        ),
        "deadline_text": "With the bid",
    },
    {
        "key": "equipment",
        "title": "Owned or leased paving equipment",
        "category": "technical",
        "mandatory": "yes",
        "page_index": 4,
        "clause_reference": "4.2",
        "excerpt": (
            "The bidder shall own or lease an asphalt paver, a vibratory roller and a "
            "mechanical broom. Equipment ownership documents or lease agreements shall "
            "be enclosed."
        ),
        "deadline_text": "With the bid",
    },
    {
        "key": "methodology",
        "title": "Methodology statement of at most 20 pages",
        "category": "submission",
        "mandatory": "yes",
        "page_index": 4,
        "clause_reference": "4.3",
        "form_reference": "Technical Bid - Annexure T1",
        "excerpt": (
            "The bidder shall submit a methodology statement, not exceeding 20 pages, "
            "describing the construction sequence, traffic management, quality control "
            "and monsoon contingency measures."
        ),
        "deadline_text": "With the bid",
    },
    {
        "key": "work_programme",
        "title": "Work programme in bar-chart form",
        "category": "submission",
        "mandatory": "yes",
        "page_index": 4,
        "clause_reference": "4.4",
        "form_reference": "Technical Bid - Annexure T2",
        "excerpt": (
            "The bidder shall submit a work programme in bar-chart form showing "
            "completion within 540 days."
        ),
        "deadline_text": "With the bid",
    },
    {
        "key": "price_validity",
        "title": "Price validity of 120 days",
        "category": "submission",
        "mandatory": "yes",
        "page_index": 5,
        "clause_reference": "5.2",
        "excerpt": "Prices shall remain valid for 120 days from the bid due date.",
        "deadline_text": "120 days from the bid due date",
    },
    {
        "key": "performance_bank_guarantee",
        "title": "Performance bank guarantee of 5 percent",
        "category": "performance",
        "mandatory": "yes",
        "page_index": 5,
        "clause_reference": "5.3",
        "excerpt": (
            "The successful bidder shall furnish a performance bank guarantee equal to "
            "5 percent of the contract value within 15 days of the award letter."
        ),
        "deadline_text": "Within 15 days of the award letter",
    },
    {
        "key": "retention",
        "title": "Five percent retention from running bills",
        "category": "performance",
        "mandatory": "no",
        "page_index": 5,
        "clause_reference": "5.4",
        "excerpt": (
            "Payments shall be made against measured work. The Authority shall deduct "
            "5 percent retention from each running bill; retention shall be released "
            "after the defect liability period."
        ),
        "deadline_text": "Released after the defect liability period",
    },
    {
        "key": "required_documents",
        "title": "Complete bid document set",
        "category": "submission",
        "mandatory": "yes",
        "page_index": 6,
        "clause_reference": "6.2",
        "form_reference": "Bid submission checklist",
        "excerpt": (
            "The bid shall contain the following documents: (a) signed bid form in the "
            "prescribed format; (b) bid security of INR 2,00,000; (c) turnover and "
            "similar-work evidence; (d) ISO 9001:2015 certificate; (e) GST registration "
            "and PAN; (f) non-blacklisting declaration; (g) key personnel and equipment "
            "details; (h) methodology statement and work programme; (i) signed integrity "
            "pact; and (j) priced Bill of Quantities."
        ),
        "deadline_text": "With the bid, before 15 November 2026, 17:00 IST",
    },
    {
        "key": "digital_signature",
        "title": "Digital signature and power of attorney",
        "category": "submission",
        "mandatory": "yes",
        "page_index": 6,
        "clause_reference": "6.5",
        "excerpt": (
            "All documents shall be digitally signed by the authorised signatory. The "
            "power of attorney authorising the signatory shall be uploaded."
        ),
        "deadline_text": "With the bid",
    },
    {
        "key": "prebid_queries",
        "title": "Pre-bid query deadline",
        "category": "submission",
        "mandatory": "no",
        "page_index": 6,
        "clause_reference": "6.3",
        "excerpt": (
            "Pre-bid queries shall be submitted in writing no later than 05 November "
            "2026, 17:00 IST. Replies will be published as a corrigendum on the portal."
        ),
        "deadline_text": "05 November 2026, 17:00 IST",
    },
    {
        "key": "liquidated_damages",
        "title": "Liquidated damages for delay",
        "category": "performance",
        "mandatory": "no",
        "page_index": 8,
        "clause_reference": "8.1",
        "excerpt": (
            "Liquidated damages of 0.5 percent of the contract value per week of delay "
            "shall apply, subject to a maximum of 10 percent of the contract value."
        ),
        "consequence_text": (
            "Liquidated damages of 0.5 percent of the contract value per week of delay, "
            "subject to a maximum of 10 percent of the contract value."
        ),
        "deadline_text": "Per week of delay",
    },
    {
        "key": "commencement",
        "title": "Commence work within 30 days",
        "category": "performance",
        "mandatory": "no",
        "page_index": 8,
        "clause_reference": "8.2",
        "excerpt": (
            "If the contractor fails to commence work within 30 days of the commencement "
            "letter, the Authority may terminate the contract and forfeit the performance "
            "bank guarantee."
        ),
        "deadline_text": "Within 30 days of the commencement letter",
        "consequence_text": (
            "The Authority may terminate the contract and forfeit the performance bank guarantee."
        ),
    },
    {
        "key": "defect_repair",
        "title": "Maintain the road for 24 months and repair defects",
        "category": "performance",
        "mandatory": "no",
        "page_index": 8,
        "clause_reference": "8.3",
        "excerpt": (
            "The contractor shall maintain the completed road for 24 months and shall "
            "repair any defect notified by the Authority within 15 days."
        ),
        "deadline_text": "24 months from completion; repair within 15 days of notice",
    },
    {
        "key": "arbitration",
        "title": "Conciliation and arbitration of disputes",
        "category": "other",
        "mandatory": "no",
        "page_index": 8,
        "clause_reference": "8.4",
        "excerpt": (
            "Disputes shall first be referred to the Engineer-in-Charge for conciliation. "
            "Unresolved disputes shall be referred to arbitration under the Arbitration and "
            "Conciliation Act, 1996. The seat of arbitration shall be Demo Nagar."
        ),
    },
    {
        "key": "labour_safety",
        "title": "Labour, safety and environmental compliance",
        "category": "compliance",
        "mandatory": "yes",
        "page_index": 8,
        "clause_reference": "8.5",
        "excerpt": (
            "The contractor shall comply with all applicable labour, safety and "
            "environmental laws. The Authority may stop work for unsafe practices without "
            "compensating the contractor for the resulting delay."
        ),
        "consequence_text": (
            "The Authority may stop work for unsafe practices without compensating the "
            "contractor for the resulting delay."
        ),
    },
]

DEMO_DOCUMENTS = [
    {
        "key": "financials",
        "title": "Audited financial statements FY2023-24 to FY2025-26",
        "document_type": "financial_statement",
        "issuer": "Rao & Associates, Chartered Accountants",
        "financial_year": "FY2025-26",
        "issue_date": date(2026, 6, 30),
        "expiry_date": date(2027, 3, 31),
        "verification_status": "verified",
    },
    {
        "key": "completion",
        "title": "Completion certificate - State Highway 9 widening",
        "document_type": "completion_certificate",
        "issuer": "Maharashtra Public Works Department",
        "project_value": 62_000_000,
        "issue_date": date(2024, 6, 30),
        "verification_status": "verified",
    },
    {
        "key": "gst",
        "title": "GST registration certificate",
        "document_type": "gst_registration",
        "issuer": "Goods and Services Tax Network",
        "issue_date": date(2021, 7, 1),
        "verification_status": "verified",
    },
    {
        "key": "pan",
        "title": "Permanent Account Number card",
        "document_type": "pan_card",
        "issuer": "Income Tax Department",
        "verification_status": "verified",
    },
    {
        "key": "non_blacklisting",
        "title": "Non-blacklisting self-declaration",
        "document_type": "declaration",
        "issuer": "Asha Infrastructure Private Limited",
        "signatory": "Asha Rao, Director",
        "issue_date": date(2026, 10, 1),
        "expiry_date": date(2027, 3, 31),
        "verification_status": "self_declared",
    },
    {
        "key": "personnel",
        "title": "Key personnel CVs and experience certificates",
        "document_type": "personnel",
        "issuer": "Asha Infrastructure Private Limited",
        "issue_date": date(2026, 9, 30),
        "verification_status": "self_declared",
    },
    {
        "key": "equipment",
        "title": "Equipment ownership documents",
        "document_type": "equipment",
        "issuer": "Asha Infrastructure Private Limited",
        "issue_date": date(2026, 9, 30),
        "verification_status": "self_declared",
    },
]

EVIDENCE_FOR = {
    "turnover": "financials",
    "similar_work": "completion",
    "iso": "iso_existing",
    "gst_pan": "gst",
    "non_blacklisting": "non_blacklisting",
    "key_personnel": "personnel",
    "equipment": "equipment",
}


def _demo_id(kind: str, *parts: str) -> str:
    return uuid5(NAMESPACE_URL, "bidkaro-demo:" + kind + ":" + ":".join(parts)).hex


def _as_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _pdf_bytes(title: str, lines: list[str]) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((64, 72), title, fontsize=15)
    page.insert_text(
        (64, 100),
        "SYNTHETIC DEMO EVIDENCE - created for the BidKaro walkthrough",
        fontsize=9,
    )
    y = 130
    for line in lines:
        page.insert_text((64, y), line, fontsize=10)
        y += 18
    content = document.tobytes()
    document.close()
    return content


def _reset_sample(db: Database, company_id: str, tender_id: str) -> None:
    requirements, _ = RequirementRepository(db).list_for_tender(
        company_id, tender_id, limit=300
    )
    requirement_ids = [item["id"] for item in requirements]
    db.evidence_matches.delete_many({"tender_id": tender_id, "company_id": company_id})
    db.requirements.delete_many({"tender_id": tender_id, "company_id": company_id})
    db.checklist_tasks.delete_many({"tender_id": tender_id, "company_id": company_id})
    db.tender_snapshots.delete_many({"tender_id": tender_id, "company_id": company_id})
    db.changes.delete_many({"tender_id": tender_id, "company_id": company_id})
    db.fit_assessments.delete_many({"tender_id": tender_id, "company_id": company_id})
    db.reminders.delete_many({"tender_id": tender_id, "company_id": company_id})
    if requirement_ids:
        db.reminders.delete_many({"requirement_id": {"$in": requirement_ids}})
    print(f"reset sample tender: {len(requirement_ids)} old requirements removed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--email",
        default="asha.phase1@example.com",
        help="Email of the demo account that owns the sample tender.",
    )
    parser.add_argument(
        "--create-user",
        action="store_true",
        help=(
            "Create the demo account and its company when they do not exist. "
            "Local demo use only."
        ),
    )
    parser.add_argument(
        "--password",
        default="BidKaro123",
        help="Password used with --create-user. Local demo use only.",
    )
    parser.add_argument("--full-name", default="Asha Rao")
    parser.add_argument("--company-name", default="Asha Infra Demo")
    args = parser.parse_args()

    settings = get_settings()
    db = Database(
        settings.mongodb_uri,
        settings.mongodb_db,
        app_name=f"{settings.mongodb_app_name}-seed-demo",
        max_pool_size=5,
        connect_timeout_ms=settings.mongodb_connect_timeout_ms,
        server_selection_timeout_ms=settings.mongodb_server_selection_timeout_ms,
        retry_writes=settings.mongodb_retry_writes,
    )
    try:
        db.ping()
    except Exception as exc:  # noqa: BLE001 - CLI should fail clearly
        print(f"MongoDB is not reachable at {redact_mongodb_uri(settings.mongodb_uri)}: {exc}", file=sys.stderr)
        return 2

    user = UserRepository(db).find_by_email(args.email)
    if not user:
        if not args.create_user:
            print(f"No demo user found for {args.email}.", file=sys.stderr)
            print(
                "Register the account in the app, or re-run with --create-user "
                "to create a local demo account.",
                file=sys.stderr,
            )
            return 2
        if settings.is_production:
            print(
                "Refusing to create a demo account with a known password in production.",
                file=sys.stderr,
            )
            return 2
        company = CompanyRepository(db).create(name=args.company_name)
        user = UserRepository(db).create(
            email=args.email,
            password_hash=hash_password(args.password),
            full_name=args.full_name,
            company_id=company["id"],
            email_verified=True,
            otp_login_enabled=False,
        )
        print(f"created demo account {args.email} for {company['name']}")
    company_id = user["company_id"]
    company = CompanyRepository(db).find_by_id(company_id)
    if not company:
        print("The demo user has no company profile.", file=sys.stderr)
        return 2

    tender = db.tenders.find_one(
        {"company_id": company_id, "reference_number": SAMPLE_REFERENCE}
    )
    if not tender:
        print(
            "Synthetic sample tender not found. Run:\n"
            f"  python scripts/make-sample-tender.py --seed --email {args.email}",
            file=sys.stderr,
        )
        return 2
    tender_id = tender["_id"]
    document = TenderDocumentRepository(db).list_for_tender(company_id, tender_id)
    document = document[0] if document else None
    if not document:
        print("The sample tender has no uploaded RFP document.", file=sys.stderr)
        return 2
    pages, _ = db.tender_pages.find({"document_id": document["id"]}).sort("page_index", 1), None
    pages_by_index = {int(page["page_index"]): page for page in pages}
    if not pages_by_index:
        print("The sample tender has no extracted pages.", file=sys.stderr)
        return 2

    _reset_sample(db, company_id, tender_id)

    storage = StorageService(settings.storage_dir, settings.max_upload_mb)
    documents = {item["_id"]: item for item in db.company_documents.find({"company_id": company_id})}
    iso = next(
        (item for item in documents.values() if "ISO 9001" in (item.get("title") or "")),
        None,
    )
    if iso:
        db.company_documents.update_one(
            {"_id": iso["_id"]},
            {"$set": {"verification_status": "verified", "updated_at": utcnow()}},
        )
    else:
        print("Warning: the existing ISO 9001 evidence is missing.", file=sys.stderr)

    demo_docs: dict[str, dict] = {}
    for spec in DEMO_DOCUMENTS:
        document_id = _demo_id("document", company_id, spec["key"])
        old = db.company_documents.find_one({"_id": document_id})
        if old:
            storage.delete(company_id, old.get("stored_filename"))
            db.company_documents.delete_one({"_id": document_id})
        db.reminders.delete_many({"document_id": document_id, "company_id": company_id})

        content = _pdf_bytes(
            spec["title"],
            [
                f"Issuer: {spec.get('issuer') or 'Synthetic demo issuer'}",
                f"Demo document key: {spec['key']}",
                "Values in this file are deterministic sample data, not an official record.",
            ],
        )
        stored_filename, _ = storage.save_company_document(company_id, ".pdf", content)
        now = utcnow()
        company_document = {
            "_id": document_id,
            "company_id": company_id,
            "original_filename": f"demo-{spec['key']}.pdf",
            "stored_filename": stored_filename,
            "title": spec["title"],
            "document_type": spec["document_type"],
            "issuer": spec.get("issuer"),
            "signatory": spec.get("signatory"),
            "financial_year": spec.get("financial_year"),
            "issue_date": _as_datetime(spec.get("issue_date")),
            "expiry_date": _as_datetime(spec.get("expiry_date")),
            "project_value": spec.get("project_value"),
            "notes": "Synthetic demo evidence for the BidKaro walkthrough.",
            "mime_type": "application/pdf",
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "verification_status": spec["verification_status"],
            "created_at": SEED_TIME,
            "updated_at": now,
        }
        db.company_documents.insert_one(company_document)
        demo_docs[spec["key"]] = company_document
        print(f"evidence: {spec['title']}")

    requirements = RequirementRepository(db)
    requirements_by_key: dict[str, dict] = {}
    for spec in REQUIREMENTS:
        page = pages_by_index.get(spec["page_index"])
        if not page:
            print(f"Missing page {spec['page_index']} for {spec['key']}.", file=sys.stderr)
            return 2
        if normalize_for_match(spec["excerpt"]) not in normalize_for_match(page.get("text") or ""):
            print(f"Excerpt for {spec['key']} is not on page {spec['page_index']}.", file=sys.stderr)
            return 2
        requirement_id = _demo_id("requirement", company_id, tender_id, spec["key"])
        created = requirements.create(
            {
                "_id": requirement_id,
                "company_id": company_id,
                "tender_id": tender_id,
                "document_id": document["id"],
                "category": spec["category"],
                "title": spec["title"],
                "obligation": spec["excerpt"],
                "excerpt": spec["excerpt"],
                "excerpt_key": normalize_for_match(spec["excerpt"])[:400],
                "page_index": spec["page_index"],
                "printed_page": page.get("printed_label"),
                "text_source": "text_layer",
                "clause_reference": spec.get("clause_reference"),
                "form_reference": spec.get("form_reference"),
                "mandatory": spec["mandatory"],
                "deadline_text": spec.get("deadline_text"),
                "consequence_text": spec.get("consequence_text"),
                "verification_status": "verified",
                "verification_notes": None,
                "document_title": document.get("title"),
                "document_retrieved_at": document.get("retrieved_at"),
                "source_url": document.get("source_url"),
                "origin": "manual",
                "model": "deterministic-demo-seed",
                "prompt_version": "demo-v1",
                "created_at": SEED_TIME,
                "updated_at": SEED_TIME,
            }
        )
        requirements_by_key[spec["key"]] = created
    print(f"requirements: {len(requirements_by_key)}")

    evidence = EvidenceRepository(db)
    for key, doc_key in EVIDENCE_FOR.items():
        requirement = requirements_by_key.get(key)
        document = iso if doc_key == "iso_existing" else demo_docs.get(doc_key)
        if not requirement or not document:
            print(f"Warning: could not confirm evidence for {key}.", file=sys.stderr)
            continue
        evidence.upsert_decision(
            company_id=company_id,
            tender_id=tender_id,
            requirement_id=requirement["id"],
            document_id=document["_id"],
            status="confirmed",
            note="Synthetic demo evidence confirmed for the walkthrough.",
            user_id=user["id"],
        )

    profile_patch = _profile_patch(company)
    if profile_patch:
        print(f"company profile: filled {sorted(profile_patch)}")
    company = CompanyRepository(db).update(
        company_id,
        {
            "reminder_email_enabled": True,
            "reminder_lead_days": [7, 3, 1],
            "certifications": ["ISO 9001:2015", "ISO 14001:2015"],
            **profile_patch,
        },
    )
    assessor = AssessmentService(db)
    created, skipped, total = assessor.generate_checklist(
        tender_id=tender_id, company=company, user_id=user["id"]
    )
    print(f"checklist: {len(created)} created, {skipped} existing, {total} total")
    obligations, obligation_skipped, obligation_total = assessor.generate_obligations(
        tender_id=tender_id, company=company, user_id=user["id"]
    )
    print(
        f"obligations: {len(obligations)} created, {obligation_skipped} existing, "
        f"{obligation_total} total"
    )

    # Leave a small, realistic open workload instead of dozens of open tasks.
    pre_award, _ = ChecklistRepository(db).list_for_tender(
        company_id, tender_id, limit=300, phase="pre_award"
    )
    for index, task in enumerate(pre_award):
        if index < 2:
            status, owner = "in_progress", "Asha Rao"
        elif index < 3:
            status, owner = "needs_verification", "Priya Deshmukh"
        else:
            status, owner = "complete", "Asha Rao"
        db.checklist_tasks.update_one(
            {"_id": task["id"]},
            {
                "$set": {
                    "status": status,
                    "owner": owner,
                    "updated_at": utcnow(),
                }
            },
        )

    WorkflowService(db).capture_snapshot(
        tender_id=tender_id, company_id=company_id, user_id=user["id"]
    )
    print("snapshot: baseline captured")

    from app.services.reminders import ReminderService  # local import avoids cycle

    ReminderService(db).sync(company)
    reminders = db.reminders.count_documents(
        {"company_id": company_id, "tender_id": tender_id, "active": True}
    )
    print(f"reminders: {reminders} active for the sample tender")

    assessed = assessor.assess(tender_id=tender_id, company=company)
    print(
        f"assessment: score {assessed.score.value} / {assessed.score.band}; "
        f"eligibility {assessed.eligibility.status} "
        f"({assessed.eligibility.pass_count} pass, "
        f"{assessed.eligibility.unknown_count} unknown, "
        f"{assessed.eligibility.fail_count} fail)"
    )
    print("\nDemo workspace ready:")
    print(f"  tender id: {tender_id}")
    print(f"  review:    http://localhost:5173/app/tenders/{tender_id}?tab=overview")
    print("  reminders: http://localhost:5173/app/reminders")
    print("  changes:   http://localhost:5173/app/changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
