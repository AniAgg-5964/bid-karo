#!/usr/bin/env python
"""Generate a clearly-labelled synthetic tender PDF for BidKaro testing.

The document is fictional. Every page carries a "SYNTHETIC SAMPLE" footer so it
can never be mistaken for an official procurement notice. Use --seed to also
create a saved tender for the demo company and attach the PDF to it.

    python scripts/make-sample-tender.py
    python scripts/make-sample-tender.py --seed --email asha.phase1@example.com
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.database import Database  # noqa: E402
from app.repositories.tenders import TenderRepository  # noqa: E402
from app.services.requirement_service import RequirementService  # noqa: E402
from app.services.storage import StorageService  # noqa: E402

REFERENCE = "DSIA/RFP/2026/ROAD-014"
TITLE = "Synthetic sample tender - four-laning of Demo State Highway 14"
FOOTER = "SYNTHETIC SAMPLE - NOT AN OFFICIAL TENDER - created for BidKaro testing"

PAGES: list[str] = [
    """DEMO STATE INFRASTRUCTURE AUTHORITY
(Government of Demo State)

SYNTHETIC SAMPLE - NOT AN OFFICIAL TENDER

REQUEST FOR PROPOSAL (RFP)

Four-Laning of Demo State Highway 14 (km 0.000 to km 18.500)
District: Demo Nagar, Demo State

RFP No.: DSIA/RFP/2026/ROAD-014
Date of issue: 01 October 2026
Bid due date and time: 15 November 2026, 17:00 IST
Bid security: INR 2,00,000
Document fee: INR 5,000 (non-refundable)

This document is a synthetic sample generated for software testing. It is not
an official tender, does not invite real bids, and must not be used for any
procurement decision. Authority names, amounts and dates are fictional.

Bids must be submitted electronically through the Demo State e-Procurement
Portal. The Authority reserves the right to reject any or all bids without
assigning reasons, subject to the conditions stated in this RFP.

Issued by:
Director (Procurement), Demo State Infrastructure Authority
""",
    """SECTION 2 - SCOPE OF WORK

2.1 The selected bidder shall widen and strengthen Demo State Highway 14 from
km 0.000 to km 18.500 to a four-lane configuration, including earthwork,
granular sub-base, wet mix macadam, bituminous base and wearing courses,
drainage, road furniture and toll-plaza approach works.

2.2 The completion period is 540 days from the date of the commencement
letter. The defect liability period is 24 months from the date of completion.

2.3 The bidder shall mobilise a site office, a laboratory and a batching plant
within 30 days of commencement. Construction drawings and a quality assurance
plan must be submitted for approval within 45 days of commencement.

2.4 All works shall conform to the specifications of the Demo State Public
Works Department and the relevant Indian Roads Congress codes.
""",
    """SECTION 3 - ELIGIBILITY CRITERIA

3.1 The bidder shall have an average annual turnover of at least INR 5 crore
during the last three financial years ending 31 March 2026.

3.2 The bidder shall have completed at least one similar work of value not less
than INR 4 crore in the last five years. A completion certificate from the
client must be enclosed.

3.3 The bidder shall hold a valid ISO 9001:2015 quality management
certification on the bid due date.

3.4 The bidder shall be registered under the Goods and Services Tax Act and
shall possess a valid Permanent Account Number.

3.5 The bidder shall not be blacklisted or debarred by any government
authority as on the bid due date. A self-declaration on company letterhead is
required.

3.6 A bid security of INR 2,00,000 shall be furnished in favour of the Demo
State Infrastructure Authority, valid for 45 days beyond the bid validity
period. Bids without valid bid security shall be rejected.

3.7 A bidder who fails any mandatory eligibility criterion shall be
disqualified; no technical or financial evaluation shall be carried out.
""",
    """SECTION 4 - TECHNICAL REQUIREMENTS

4.1 The bidder shall deploy a project manager with at least 10 years of
experience in highway construction and a quality assurance engineer with at
least 5 years of experience. Curriculum vitae and experience certificates
shall be submitted with the bid.

4.2 The bidder shall own or lease an asphalt paver, a vibratory roller and a
mechanical broom. Equipment ownership documents or lease agreements shall be
enclosed.

4.3 The bidder shall submit a methodology statement, not exceeding 20 pages,
describing the construction sequence, traffic management, quality control and
monsoon contingency measures.

4.4 The bidder shall submit a work programme in bar-chart form showing
completion within 540 days.

4.5 Technical bids shall be evaluated out of 100 marks. A bid securing less
than 70 marks shall be treated as technically non-responsive.
""",
    """SECTION 5 - FINANCIAL REQUIREMENTS

5.1 The bidder shall quote rates for all items in the Bill of Quantities.
Rates shall be inclusive of all taxes, duties, royalties, lead and lift.

5.2 Prices shall remain valid for 120 days from the bid due date.

5.3 The successful bidder shall furnish a performance bank guarantee equal to
5 percent of the contract value within 15 days of the award letter.

5.4 Payments shall be made against measured work. The Authority shall deduct
5 percent retention from each running bill; retention shall be released after
the defect liability period.

5.5 The Bill of Quantities must be uploaded in the prescribed spreadsheet
format; a conditional or incomplete price bid shall be rejected.
""",
    """SECTION 6 - SUBMISSION REQUIREMENTS

6.1 Bids must be submitted through the Demo State e-Procurement Portal before
15 November 2026 at 17:00 IST. Late bids shall be rejected by the system.

6.2 The bid shall contain the following documents:
(a) signed bid form in the prescribed format;
(b) bid security of INR 2,00,000;
(c) turnover and similar-work evidence;
(d) ISO 9001:2015 certificate;
(e) GST registration and PAN;
(f) non-blacklisting declaration;
(g) key personnel and equipment details;
(h) methodology statement and work programme;
(i) signed integrity pact; and
(j) priced Bill of Quantities.

6.3 Pre-bid queries shall be submitted in writing no later than 05 November
2026, 17:00 IST. Replies will be published as a corrigendum on the portal.

6.4 Bids shall remain valid for 120 days from the bid due date. A bidder who
withdraws a bid during this period may be debarred for two years.

6.5 All documents shall be digitally signed by the authorised signatory. The
power of attorney authorising the signatory shall be uploaded.
""",
    """SECTION 7 - EVALUATION AND AWARD

7.1 Bids shall be evaluated in two stages: technical evaluation followed by
financial evaluation of technically responsive bids.

7.2 The technical score shall carry 70 percent weight and the financial score
30 percent. The lowest evaluated financial bid shall receive the maximum
financial score.

7.3 The Authority may seek clarification on any bid. Failure to respond within
seven days may result in rejection of the bid.

7.4 The Authority may verify original documents before award. If any
document is found false or fabricated, the bid shall be rejected and the
bidder may be debarred for three years.

7.5 Award shall be made to the bidder with the highest combined score. The
Authority is not bound to accept the lowest price.
""",
    """SECTION 8 - CONTRACT CONDITIONS AND PENALTIES

8.1 Liquidated damages of 0.5 percent of the contract value per week of delay
shall apply, subject to a maximum of 10 percent of the contract value.

8.2 If the contractor fails to commence work within 30 days of the
commencement letter, the Authority may terminate the contract and forfeit the
performance bank guarantee.

8.3 The contractor shall maintain the completed road for 24 months and shall
repair any defect notified by the Authority within 15 days.

8.4 Disputes shall first be referred to the Engineer-in-Charge for
conciliation. Unresolved disputes shall be referred to arbitration under the
Arbitration and Conciliation Act, 1996. The seat of arbitration shall be
Demo Nagar.

8.5 The contractor shall comply with all applicable labour, safety and
environmental laws. The Authority may stop work for unsafe practices without
compensating the contractor for the resulting delay.
""",
]


def build_pdf() -> bytes:
    document = pymupdf.open()
    total = len(PAGES)
    for index, text in enumerate(PAGES, start=1):
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(50, 45, 545, 770),
            text,
            fontsize=10.5,
            fontname="helv",
            lineheight=1.35,
        )
        page.insert_text(
            (50, 800),
            f"{FOOTER} - page {index} of {total}",
            fontsize=7.5,
            fontname="helv",
            color=(0.45, 0.45, 0.45),
        )
    data = document.tobytes()
    document.close()
    return data


def seed(email: str, pdf_path: Path, content: bytes) -> None:
    settings = get_settings()
    database = Database(
        settings.mongodb_uri,
        settings.mongodb_db,
        app_name=settings.mongodb_app_name,
        max_pool_size=settings.mongodb_max_pool_size,
        connect_timeout_ms=settings.mongodb_connect_timeout_ms,
        server_selection_timeout_ms=settings.mongodb_server_selection_timeout_ms,
        retry_writes=settings.mongodb_retry_writes,
    )
    database.init_indexes()

    user = database.users.find_one({"email": email})
    if not user:
        raise SystemExit(f"No user found for {email}. Register first or pass --email.")
    company_id = user["company_id"]

    tender = database.tenders.find_one(
        {"company_id": company_id, "reference_number": REFERENCE}
    )
    if not tender:
        tender = TenderRepository(database).create(
            {
                "company_id": company_id,
                "title": TITLE,
                "authority": "Demo State Infrastructure Authority (fictional)",
                "reference_number": REFERENCE,
                "deadline": datetime(2026, 11, 15, 11, 30, tzinfo=timezone.utc),
                "status": "saved",
                "source_url": None,
                "source_type": "synthetic_sample",
                "source_retrieved_at": datetime.now(timezone.utc),
                "description": (
                    "Synthetic sample generated for BidKaro testing. "
                    "This is not an official tender."
                ),
                "is_sample": True,
            }
        )
        print(f"created tender {tender['id']}")
    else:
        tender = {"id": tender["_id"], **tender}
        print(f"reusing tender {tender['id']}")

    service = RequirementService(
        database,
        StorageService(settings.storage_dir, settings.max_upload_mb),
        ai=None,
        settings=settings,
    )
    document = service.upload_document(
        tender_id=tender["id"],
        company_id=company_id,
        user_id=user["_id"],
        filename=pdf_path.name,
        content_type="application/pdf",
        content=content,
        kind="main",
        title="Synthetic RFP - DSIA/RFP/2026/ROAD-014 (sample)",
        source_url=None,
        source="uploaded",
    )
    print(
        f"document {document['id']}: {document['status']}, "
        f"{document['page_count']} pages, {document['text_page_count']} with text"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="store_true", help="Create a saved tender and attach the PDF.")
    parser.add_argument("--email", default="asha.phase1@example.com", help="Company owner email for --seed.")
    parser.add_argument(
        "--output",
        default=str(ROOT / "storage" / "samples" / "synthetic-tender-road-14.pdf"),
        help="Where to write the PDF.",
    )
    args = parser.parse_args()

    content = build_pdf()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    print(f"wrote {output} ({len(content)} bytes, {len(PAGES)} pages)")

    if args.seed:
        seed(args.email, output, content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
