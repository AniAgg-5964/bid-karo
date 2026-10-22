"""Indexing the documents into the retrieval store.

The store is a stand-in here, so the tests can check what would be written to
Qdrant without a server. What matters is the contract: what is written, that
re-indexing does not duplicate, that a failure is visible, and that a document
of another company is never touched.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.repositories.documents import DocumentRepository
from app.repositories.tender_documents import TenderDocumentRepository, TenderPageRepository
from app.services.document_ingestion import DocumentIngestionService
from app.services.storage import StorageService

PAGE_ONE = (
    "1. Scope of work\n\n"
    "The contractor shall supply and commission the system at the site.\n\n"
    "1.1 The contractor shall obtain every statutory approval before the work begins."
)
PAGE_TWO = (
    "2. Payments\n\n"
    "Payment shall be made within thirty days of the invoice being certified."
)


class FakeStore:
    """A stand-in for the vector store."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.points: dict[str, dict] = {}
        self.deleted: list[str] = []
        self.dimension: int | None = None

    def health(self) -> dict:
        return {"status": "unavailable"} if self.fail else {"status": "ok"}

    def ensure_collection(self, dimension: int, *, distance: str = "Cosine") -> bool:
        self.dimension = dimension
        return True

    def delete_document(self, document_id: str) -> int:
        self.deleted.append(document_id)
        for key in [k for k, v in self.points.items() if v.get("document_id") == document_id]:
            self.points.pop(key)
        return 1

    def upsert_points(self, points) -> int:
        if self.fail:
            raise RuntimeError("the store is not available")
        for point in points:
            self.points[point.id] = point.payload
        return len(points)

    def count(self, filters=None) -> int:
        return len(self.points)


class FakeEmbeddings:
    name = "fake"
    model = "fake-model"
    dimension = 8
    available = True

    def embed(self, texts):
        return [[float(len(text) % 7)] * self.dimension for text in texts]

    def embed_query(self, text):
        return [0.0] * self.dimension


def make_service(database, store, tmp_path, **settings) -> DocumentIngestionService:
    return DocumentIngestionService(
        database,
        StorageService(tmp_path / "storage", 25),
        FakeEmbeddings(),
        store,
        settings=Settings(**settings),
    )


def make_tender_document(database, tender: dict, pages: list[str]) -> dict:
    documents = TenderDocumentRepository(database)
    document = documents.create(
        {
            "company_id": tender["company_id"],
            "tender_id": tender["id"],
            "kind": "main",
            "title": "Tender document",
            "original_filename": "tender.pdf",
            "stored_filename": "abc123.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "sha256": "hash-1",
            "source": "uploaded",
            "source_url": "https://example.gov.in/tender/road-14",
            "retrieved_at": None,
            "status": "extracted",
            "page_count": len(pages),
            "text_page_count": len(pages),
        }
    )
    TenderPageRepository(database).replace_for_document(
        company_id=tender["company_id"],
        tender_id=tender["id"],
        document_id=document["id"],
        pages=[
            {
                "page_index": index + 1,
                "printed_label": str(index + 1),
                "text": text,
                "char_count": len(text),
                "has_text": True,
                "text_source": "text_layer",
            }
            for index, text in enumerate(pages)
        ],
    )
    return document


def test_a_tender_document_is_indexed_with_its_provenance(
    database, tender: dict, tmp_path
):
    store = FakeStore()
    service = make_service(database, store, tmp_path)
    document = make_tender_document(database, tender, [PAGE_ONE, PAGE_TWO])

    result = service.index_tender_document(tender["company_id"], tender["id"], document["id"])

    assert result["status"] == "indexed"
    assert result["chunks"] > 0
    assert store.dimension == 8

    payloads = list(store.points.values())
    assert payloads
    for payload in payloads:
        assert payload["company_id"] == tender["company_id"]
        assert payload["tender_id"] == tender["id"]
        assert payload["document_id"] == document["id"]
        assert payload["document_version_id"] == "hash-1"
        assert payload["embedding_model"] == "fake-model"
        assert payload["text"]
        assert payload["page_index"] in {1, 2}
        assert payload["indexed_at"]


def test_the_document_record_says_what_happened(database, tender: dict, tmp_path):
    service = make_service(database, FakeStore(), tmp_path)
    document = make_tender_document(database, tender, [PAGE_ONE])

    service.index_tender_document(tender["company_id"], tender["id"], document["id"])

    stored = TenderDocumentRepository(database).find_for_company(
        document["id"], tender["company_id"]
    )
    assert stored["index_status"] == "indexed"
    assert stored["index_chunk_count"] > 0
    assert stored["index_model"] == "fake-model"
    assert stored["index_error"] is None
    assert stored["indexed_at"] is not None


def test_indexing_the_same_content_again_does_not_duplicate(
    database, tender: dict, tmp_path
):
    store = FakeStore()
    service = make_service(database, store, tmp_path)
    document = make_tender_document(database, tender, [PAGE_ONE])

    service.index_tender_document(tender["company_id"], tender["id"], document["id"])
    count = len(store.points)
    again = service.index_tender_document(tender["company_id"], tender["id"], document["id"])

    assert again["status"] == "unchanged"
    assert len(store.points) == count


def test_a_changed_document_replaces_its_old_passages(
    database, tender: dict, tmp_path
):
    store = FakeStore()
    service = make_service(database, store, tmp_path)
    document = make_tender_document(database, tender, [PAGE_ONE])
    service.index_tender_document(tender["company_id"], tender["id"], document["id"])
    first_ids = set(store.points)

    TenderPageRepository(database).replace_for_document(
        company_id=tender["company_id"],
        tender_id=tender["id"],
        document_id=document["id"],
        pages=[
            {
                "page_index": 1,
                "printed_label": "1",
                "text": "3. Security\n\nA performance guarantee of five percent is required.",
                "char_count": 60,
                "has_text": True,
                "text_source": "text_layer",
            }
        ],
    )
    result = service.index_tender_document(tender["company_id"], tender["id"], document["id"])

    assert result["status"] == "indexed"
    assert document["id"] in store.deleted
    # The old passages are gone: no point of the first run is left.
    assert not (first_ids & set(store.points))
    texts = " ".join(payload["text"] for payload in store.points.values())
    assert "performance guarantee" in texts


def test_a_failing_store_is_recorded_not_hidden(database, tender: dict, tmp_path):
    store = FakeStore(fail=True)
    service = make_service(database, store, tmp_path)
    document = make_tender_document(database, tender, [PAGE_ONE])

    result = service.index_tender_document(tender["company_id"], tender["id"], document["id"])

    assert result["status"] == "failed"
    stored = TenderDocumentRepository(database).find_for_company(
        document["id"], tender["company_id"]
    )
    assert stored["index_status"] == "failed"
    assert stored["index_error"]
    assert stored["indexed_at"] is None


def test_a_document_without_text_is_skipped(database, tender: dict, tmp_path):
    store = FakeStore()
    service = make_service(database, store, tmp_path)
    document = make_tender_document(database, tender, ["   "])

    result = service.index_tender_document(tender["company_id"], tender["id"], document["id"])

    assert result["status"] == "skipped"
    assert store.points == {}


def test_a_document_of_another_company_is_refused(database, tender: dict, tmp_path):
    service = make_service(database, FakeStore(), tmp_path)
    document = make_tender_document(database, tender, [PAGE_ONE])

    with pytest.raises(NotFoundError):
        service.index_tender_document("another-company", tender["id"], document["id"])
    with pytest.raises(NotFoundError):
        service.index_tender_document(
            tender["company_id"], tender["id"], "a-document-that-does-not-exist"
        )


def test_the_point_ids_are_deterministic(database, tender: dict, tmp_path):
    first = FakeStore()
    second = FakeStore()
    document = make_tender_document(database, tender, [PAGE_ONE])

    make_service(database, first, tmp_path).index_tender_document(
        tender["company_id"], tender["id"], document["id"]
    )
    # Forced, so the second run writes again instead of reporting "unchanged".
    make_service(database, second, tmp_path).index_tender_document(
        tender["company_id"], tender["id"], document["id"], force=True
    )

    assert set(first.points) == set(second.points)


def test_a_company_document_is_indexed(database, company_id: str, tmp_path):
    store = FakeStore()
    service = make_service(database, store, tmp_path)
    document = DocumentRepository(database).create(
        {
            "company_id": company_id,
            "original_filename": "certificate.pdf",
            "stored_filename": "0123456789abcdef0123456789abcdef.pdf",
            "title": "ISO certificate",
            "document_type": "certificate",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "sha256": "hash-company",
            "verification_status": "self_declared",
        }
    )

    # There is no file on disk, so there is nothing to extract: the document
    # is skipped rather than indexed with nothing in it.
    result = service.index_company_document(company_id, document["id"])
    assert result["status"] == "skipped"
    assert store.points == {}
