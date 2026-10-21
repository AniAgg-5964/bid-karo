"""Tender packages: a ZIP the tender was downloaded as.

A tender is usually published as a ZIP holding the notice, the BOQ, forms and
drawings. These tests cover the archive rules (path traversal, archives that
expand too far, nested archives, executables) and the expansion into
individual documents.
"""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from app.services.package_extraction import (
    PackageLimits,
    inspect_archive,
    read_member,
)
from tests.conftest import make_pdf, register_and_verify

PDF_BYTES = make_pdf(
    [
        "Section 3 - Eligibility Criteria. The bidder shall have an average annual "
        "turnover of at least INR 5 crore during the last three financial years."
    ]
)


def make_zip(entries: list[tuple[str, bytes]], *, compression=zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return buffer.getvalue()


def png_bytes(text: str = "Tender notice scan") -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 80), text, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def upload_package(
    client: TestClient,
    headers: dict[str, str],
    tender_id: str,
    content: bytes,
    *,
    filename: str = "tender-package.zip",
):
    return client.post(
        f"/api/tenders/{tender_id}/documents",
        headers=headers,
        data={"kind": "main", "title": "Tender package"},
        files={"file": (filename, content, "application/zip")},
    )


# ------------------------------------------------------------------- the rules


def test_path_traversal_entries_are_refused() -> None:
    archive = make_zip([("../escape.txt", b"nope"), ("/absolute.txt", b"nope")])
    inspection = inspect_archive(archive)
    assert inspection.accepted == []
    assert len(inspection.skipped) == 2
    assert all("Unsafe path" in (member.reason or "") for member in inspection.skipped)


def test_executables_and_nested_archives_are_refused() -> None:
    archive = make_zip(
        [
            ("setup.exe", b"MZ"),
            ("run.sh", b"#!/bin/sh"),
            ("inner.zip", make_zip([("a.txt", b"a")])),
        ]
    )
    inspection = inspect_archive(archive)
    reasons = {member.path: member.reason for member in inspection.skipped}
    assert "Executables" in (reasons["setup.exe"] or "")
    assert "Executables" in (reasons["run.sh"] or "")
    assert "Nested" in (reasons["inner.zip"] or "")
    assert inspection.accepted == []


def test_a_file_that_expands_too_far_is_refused() -> None:
    limits = PackageLimits(max_ratio=2, max_expanded_bytes=1024, max_member_bytes=1024)
    archive = make_zip([("big.txt", b"a" * 100_000)], compression=zipfile.ZIP_DEFLATED)
    inspection = inspect_archive(archive, limits=limits)
    assert inspection.accepted == []
    assert inspection.skipped[0].reason


def test_too_many_members_are_refused() -> None:
    limits = PackageLimits(max_members=2)
    archive = make_zip([(f"file-{index}.txt", b"x") for index in range(5)])
    inspection = inspect_archive(archive, limits=limits)
    assert len(inspection.accepted) == 2
    assert "entries" in (inspection.error or "")


def test_a_member_is_read_back_verbatim() -> None:
    archive = make_zip([("notice.txt", b"hello tender")])
    inspection = inspect_archive(archive)
    member = inspection.accepted[0]
    assert read_member(archive, member) == b"hello tender"


def test_a_broken_archive_is_reported() -> None:
    inspection = inspect_archive(b"not a zip at all")
    assert inspection.error
    assert inspection.accepted == []


# ------------------------------------------------------------------ the upload


def test_a_package_is_expanded_into_documents(
    client: TestClient, auth_headers: dict[str, str], tender: dict
) -> None:
    archive = make_zip(
        [
            ("Tender Notice.pdf", PDF_BYTES),
            ("BOQ.xlsx", b"PK\x03\x04fake spreadsheet"),
            ("Scan-001.png", png_bytes()),
            ("Layout.dwg", b"AC1027 dwg"),
            ("inner.zip", make_zip([("a.txt", b"a")])),
            ("setup.exe", b"MZ"),
        ]
    )
    response = upload_package(client, auth_headers, tender["id"], archive)
    assert response.status_code == 201, response.text
    package = response.json()

    assert package["kind"] == "package"
    assert package["is_container"] is True
    assert package["parse_status"] == "container"
    summary = package["package_summary"]
    assert summary["total"] == 6
    assert summary["stored"] == 4
    assert summary["skipped"] == 2

    skipped = {item["path"]: item["reason"] for item in summary["skipped_files"]}
    assert "Nested" in skipped["inner.zip"]
    assert "Executables" in skipped["setup.exe"]

    members = {item["path"]: item for item in summary["members"]}
    notice = members["Tender Notice.pdf"]
    assert notice["kind"] == "main"
    assert notice["status"] == "extracted"
    assert notice["page_count"] == 1

    boq = members["BOQ.xlsx"]
    assert boq["kind"] == "boq"
    assert boq["status"] == "not_parsed"

    scan = members["Scan-001.png"]
    assert scan["page_count"] == 1
    assert scan["status"] in {"extracted", "no_text_layer", "not_parsed"}

    drawing = members["Layout.dwg"]
    assert drawing["status"] == "not_parsed"

    # The children are documents of the tender, so a requirement can cite them.
    listing = client.get(f"/api/tenders/{tender['id']}/documents", headers=auth_headers)
    documents = {item["original_filename"]: item for item in listing.json()["items"]}
    assert "Tender Notice.pdf" in documents
    assert documents["Tender Notice.pdf"]["parent_document_id"] == package["id"]
    assert documents["Tender Notice.pdf"]["archive_path"] == "Tender Notice.pdf"
    assert documents["Tender Notice.pdf"]["page_count"] == 1

    pages = client.get(
        f"/api/tender-documents/{documents['Tender Notice.pdf']['id']}/pages",
        headers=auth_headers,
    )
    assert pages.status_code == 200
    assert len(pages.json()["items"]) == 1
    page_text = client.get(
        f"/api/tender-documents/{documents['Tender Notice.pdf']['id']}/pages/1",
        headers=auth_headers,
    )
    assert page_text.status_code == 200
    assert "average annual turnover" in page_text.json()["text"]


def test_uploading_the_same_package_twice_is_idempotent(
    client: TestClient, auth_headers: dict[str, str], tender: dict
) -> None:
    archive = make_zip([("Tender Notice.pdf", PDF_BYTES)])
    first = upload_package(client, auth_headers, tender["id"], archive)
    assert first.status_code == 201
    second = upload_package(client, auth_headers, tender["id"], archive)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]

    listing = client.get(f"/api/tenders/{tender['id']}/documents", headers=auth_headers)
    assert listing.json()["total"] == 2  # the package and its one child


def test_a_package_is_tenant_scoped(
    client: TestClient, auth_headers: dict[str, str], tender: dict, fake_email
) -> None:
    archive = make_zip([("Tender Notice.pdf", PDF_BYTES)])
    upload_package(client, auth_headers, tender["id"], archive)

    other = register_and_verify(
        client,
        fake_email,
        email="package-owner@example.com",
        full_name="Other Owner",
        company_name="Other Infra Pvt Ltd",
    )
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    listing = client.get(f"/api/tenders/{tender['id']}/documents", headers=other_headers)
    assert listing.status_code == 404
    assert "total" not in listing.json()
