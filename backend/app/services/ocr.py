"""Optional English OCR for scanned tender pages.

Tesseract is deliberately kept behind a small callable so PDF extraction stays
deterministic and testable without the system binary. OCR output is a
transcription, not a text layer: callers must label it as such.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path
from typing import Callable

OcrCallable = Callable[[bytes], str]


class OcrUnavailable(RuntimeError):
    """Raised when OCR is enabled but the local engine cannot be used."""


def _tesseract_command(explicit: str) -> str:
    if explicit.strip():
        return explicit.strip()
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return ""


def build_ocr(
    *,
    language: str = "eng",
    tesseract_cmd: str = "",
    timeout_seconds: int = 45,
) -> OcrCallable:
    """Return a PNG-bytes -> text callable, or raise OcrUnavailable."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise OcrUnavailable(
            "OCR dependencies are missing. Install pytesseract and pillow."
        ) from exc

    command = _tesseract_command(tesseract_cmd)
    if not command:
        raise OcrUnavailable(
            "Tesseract is not installed. Install it and set TESSERACT_CMD if needed."
        )
    pytesseract.pytesseract.tesseract_cmd = command

    try:
        version = pytesseract.get_tesseract_version()
    except Exception as exc:  # pragma: no cover - depends on the host install
        raise OcrUnavailable(f"Tesseract could not be started: {exc}") from exc

    if not version:
        raise OcrUnavailable("Tesseract did not report a version.")

    config = f"--oem 1 --psm 3 -l {language}"

    def run(png_bytes: bytes) -> str:
        image = Image.open(io.BytesIO(png_bytes))
        return pytesseract.image_to_string(
            image,
            lang=language,
            config=config,
            timeout=max(timeout_seconds, 1),
        )

    return run
