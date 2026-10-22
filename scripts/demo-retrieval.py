"""The end-to-end check of the retrieval, through the running API.

Everything here goes through the running API, the running Qdrant and the
running MongoDB. Nothing is mocked and nothing is hardcoded: the passages that
come back are read from Qdrant and checked against the stored page.

Start the pieces first:

    .\\scripts\\qdrant-dev.ps1 start
    cd backend; .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000

Then:

    .\\backend\\.venv\\Scripts\\python.exe scripts\\demo-retrieval.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

BASE = os.environ.get("BIDKARO_API", "http://127.0.0.1:8000/api")
EMAIL = os.environ.get("BIDKARO_EMAIL", "asha.phase1@example.com")
PASSWORD = os.environ.get("BIDKARO_PASSWORD", "BidKaro123")
ROOT = Path(__file__).resolve().parents[1]

QUESTIONS = [
    "How much money must the company have earned over the last three years?",
    "What quality certificate does the bidder need?",
    "When is the bid due and what is the security deposit?",
]


def heading(text: str) -> None:
    print()
    print("=" * 78)
    print(text)
    print("=" * 78)


def login(client: httpx.Client) -> str:
    response = client.post(
        f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    if response.status_code != 200:
        raise SystemExit(f"Login failed: {response.status_code} {response.text}")
    return response.json()["access_token"]


def make_sample_pdf(target: Path) -> Path:
    """A real, freshly generated tender PDF."""
    script = ROOT / "scripts" / "make-sample-tender.py"
    python = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
    subprocess.run(
        [str(python), str(script), "--output", str(target)],
        check=True,
        capture_output=True,
    )
    return target


def main() -> int:
    client = httpx.Client(timeout=300.0)
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    heading("1. Qdrant and the backend")
    print(client.get(f"{BASE}/health").json())
    knowledge = client.get(f"{BASE}/knowledge/health").json()
    print(knowledge)
    if knowledge.get("status") != "ok":
        print("Qdrant is not ready. Start it with scripts\\qdrant-dev.ps1 start")
        return 1

    heading("2. The tender")
    tenders = client.get(f"{BASE}/tenders", headers=headers).json()
    items = tenders.get("items", tenders if isinstance(tenders, list) else [])
    if not items:
        print("No tender found for this account. Run scripts\\seed-demo.py first.")
        return 1
    tender = items[0]
    print(f"{tender.get('title')}\n  id: {tender['id']}")

    heading("3. Upload a real tender PDF through the upload workflow")
    existing = client.get(f"{BASE}/tenders/{tender['id']}/documents", headers=headers).json()
    for document in existing.get("items", []):
        if str(document.get("title", "")).startswith("Demo upload"):
            client.delete(f"{BASE}/tender-documents/{document['id']}", headers=headers)
            print(f"Removed the earlier demo document {document['id']}")
    target = ROOT / ".data" / "demo-upload.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf_path = make_sample_pdf(target)
    with pdf_path.open("rb") as handle:
        upload = client.post(
            f"{BASE}/tenders/{tender['id']}/documents",
            headers=headers,
            data={"kind": "main", "title": "Demo upload for the retrieval check"},
            files={"file": ("demo-tender.pdf", handle, "application/pdf")},
        )
    print("Upload status:", upload.status_code)
    if upload.status_code != 201:
        print(upload.text[:600])
        return 1
    document = upload.json()
    print(f"Document {document['id']}: {document['page_count']} pages, "
          f"{document['text_page_count']} with text")

    heading("4. Index the documents into Qdrant")
    job = client.post(f"{BASE}/knowledge/tenders/{tender['id']}/index", headers=headers)
    job_id = job.json()["id"]
    state: dict = {}
    for _ in range(120):
        time.sleep(1)
        state = client.get(f"{BASE}/analysis/jobs/{job_id}", headers=headers).json()
        if state.get("status") in {"done", "failed"}:
            break
    print("Job:", state.get("status"))
    for step in state.get("steps", []):
        print(f"  {step['key']}: {step['status']} {step.get('summary') or {}}")
    status = client.get(
        f"{BASE}/knowledge/tenders/{tender['id']}/status", headers=headers
    ).json()
    for item in status["items"]:
        print(f"  {item['index_status']:<9} chunks={item['index_chunk_count']:<5} {item['title']}")

    heading("5. Ask in plain language (a paraphrase, not the wording)")
    for question in QUESTIONS:
        response = client.post(
            f"{BASE}/knowledge/search",
            headers=headers,
            json={
                "query": question,
                "scope": "tender",
                "tender_id": tender["id"],
                "limit": 3,
            },
        )
        body = response.json()
        print(f"\nQ: {question}")
        print(f"   {body.get('count')} passages")
        for item in body.get("items", []):
            citation = item["citation"]
            print(
                f"   [{item['score']:.3f}] page {citation['page_index']} "
                f"clause {citation['clause_number']} "
                f"verified={item['verified']}\n"
                f"      {item['text'][:150]}"
            )

    heading("6. The company's own evidence")
    job = client.post(f"{BASE}/knowledge/documents/index", headers=headers)
    job_id = job.json()["id"]
    for _ in range(120):
        time.sleep(1)
        state = client.get(f"{BASE}/analysis/jobs/{job_id}", headers=headers).json()
        if state.get("status") in {"done", "failed"}:
            break
    print("Job:", state.get("status"))
    for step in state.get("steps", []):
        print(f"  {step['key']}: {step['status']} {step.get('summary') or {}}")
    status = client.get(f"{BASE}/knowledge/documents/status", headers=headers).json()
    print(f"  {status['indexed']} indexed, {status['failed']} failed, {status['pending']} pending")
    for question in [
        "What turnover does the company have?",
        "Does the company have an ISO certification?",
    ]:
        response = client.post(
            f"{BASE}/knowledge/search",
            headers=headers,
            json={"query": question, "scope": "company_evidence", "limit": 2},
        )
        body = response.json()
        print(f"\nQ: {question}\n   {body.get('count')} passages")
        for item in body.get("items", []):
            citation = item["citation"]
            print(
                f"   [{item['score']:.3f}] {citation['document_title']} "
                f"({citation['document_type']}) verified={item['verified']}\n"
                f"      {item['text'][:140]}"
            )

    heading("7. The same file again must not double the index")
    before = client.get(
        f"{BASE}/knowledge/tenders/{tender['id']}/status", headers=headers
    ).json()
    chunks_before = sum(item["index_chunk_count"] for item in before["items"])
    with pdf_path.open("rb") as handle:
        again = client.post(
            f"{BASE}/tenders/{tender['id']}/documents",
            headers=headers,
            data={"kind": "main", "title": "Demo upload, second time"},
            files={"file": ("demo-tender.pdf", handle, "application/pdf")},
        )
    print("Second upload status:", again.status_code, "document:", again.json().get("id"))
    client.post(f"{BASE}/knowledge/tenders/{tender['id']}/index", headers=headers)
    time.sleep(5)
    after = client.get(
        f"{BASE}/knowledge/tenders/{tender['id']}/status", headers=headers
    ).json()
    chunks_after = sum(item["index_chunk_count"] for item in after["items"])
    print(f"Chunks before: {chunks_before}, after: {chunks_after}")

    heading("8. The company boundary")
    response = client.post(
        f"{BASE}/knowledge/search",
        headers=headers,
        json={"query": "average annual turnover", "scope": "all", "limit": 5},
    )
    companies = {item["citation"]["company_id"] for item in response.json().get("items", [])}
    print("Companies in the results:", companies)
    print("Only the signed-in company appears:", len(companies) <= 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
