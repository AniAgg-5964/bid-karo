from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from app.core.exceptions import ValidationError

ALLOWED_TYPES = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
}

STORED_NAME_RE = re.compile(r"^[a-f0-9]{32}\.(pdf|png|jpg|jpeg)$")


def sanitize_original_filename(filename: str | None) -> str:
    name = Path(filename or "document").name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:200] or "document"


class StorageService:
    def __init__(self, root: Path, max_upload_mb: int = 25) -> None:
        self.root = Path(root)
        self.max_upload_mb = max_upload_mb

    @property
    def max_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def validate(
        self, filename: str | None, content_type: str | None, content: bytes
    ) -> tuple[str, str]:
        if not content:
            raise ValidationError("The uploaded file is empty.")
        if len(content) > self.max_bytes:
            raise ValidationError(f"Files must be {self.max_upload_mb} MB or smaller.")

        original = sanitize_original_filename(filename)
        suffix = Path(original).suffix.lower()
        if suffix not in ALLOWED_TYPES:
            raise ValidationError("Only PDF, PNG, JPG and JPEG files are accepted.")

        expected_mime, signatures = ALLOWED_TYPES[suffix]
        if not any(content.startswith(signature) for signature in signatures):
            raise ValidationError("The file content does not match its extension.")

        declared = (content_type or "").lower()
        if declared and declared not in {expected_mime, "application/octet-stream"}:
            raise ValidationError("The declared file type is not supported.")

        return suffix, expected_mime

    def save_company_document(
        self, company_id: str, suffix: str, content: bytes
    ) -> tuple[str, Path]:
        folder = self.root / "companies" / company_id
        folder.mkdir(parents=True, exist_ok=True)
        stored_filename = f"{uuid4().hex}{suffix}"
        path = folder / stored_filename
        path.write_bytes(content)
        return stored_filename, path

    def resolve_company_document(self, company_id: str, stored_filename: str) -> Path:
        if not STORED_NAME_RE.match(stored_filename):
            raise ValidationError("Invalid stored document reference.")
        path = (self.root / "companies" / company_id / stored_filename).resolve()
        root = (self.root / "companies" / company_id).resolve()
        if root not in path.parents:
            raise ValidationError("Invalid stored document reference.")
        return path

    def delete(self, company_id: str, stored_filename: str) -> None:
        try:
            path = self.resolve_company_document(company_id, stored_filename)
        except ValidationError:
            return
        if path.exists() and path.is_file():
            path.unlink()
