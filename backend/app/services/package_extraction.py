"""Reading a tender package: a ZIP archive the tender was downloaded as.

Tenders are usually published as a ZIP holding the notice, the BOQ, the forms
and the drawings. This module inspects such an archive and decides, for every
member, whether it may be stored and read.

Everything here is deterministic and defensive. An archive is untrusted input,
so the rules are fixed limits, not heuristics:

* a member may never write outside the extraction folder (path traversal);
* the total expanded size, the size of one member, the number of members and
  the compression ratio are all capped, so a small archive cannot expand into
  an enormous one;
* nested archives are not opened;
* executables and scripts are never stored;
* nothing here is ever executed.

A member that is not allowed is returned with the reason, so the user can see
that the package contained something we did not read.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import PurePosixPath

# Members we can read into pages and cite.
PARSEABLE_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
# Members we keep as files but cannot turn into pages.
STORED_ONLY_SUFFIXES = {
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".rtf",
    ".dwg", ".dxf", ".zip", ".7z", ".rar", ".tar", ".gz",
}
# Never stored, never executed.
BLOCKED_SUFFIXES = {
    ".exe", ".dll", ".so", ".dylib", ".com", ".msi", ".scr", ".bat", ".cmd",
    ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta", ".jar",
    ".py", ".pyc", ".sh", ".bash", ".zsh", ".reg", ".lnk", ".app", ".msc",
    ".cpl", ".inf", ".pif", ".scpt",
}
ARCHIVE_SUFFIXES = {".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz"}

# Deterministic kind hints, from the file name only.
KIND_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("corrigendum", ("corrigendum", "addendum", "amendment", "clarification", "grievance", "revision")),
    ("boq", ("boq", "bill of quantity", "bill-of-quantity", "schedule of items", "soq")),
    ("form", ("form", "annexure", "annex", "undertaking", "affidavit", "declaration", "proforma", "pro-forma")),
    ("main", ("nit", "e-tender", "etender", "tender notice", "ifb", "rfp", "invitation", "nib", "tender document")),
)

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9 _.\-()\[\]]+")


@dataclass(slots=True)
class PackageLimits:
    """Fixed limits applied to one archive."""

    max_members: int = 200
    max_member_bytes: int = 25 * 1024 * 1024
    max_expanded_bytes: int = 500 * 1024 * 1024
    max_ratio: int = 200
    max_nesting: int = 1

    @classmethod
    def from_settings(cls, settings) -> "PackageLimits":
        return cls(
            max_members=settings.package_max_members,
            max_member_bytes=settings.package_max_member_mb * 1024 * 1024,
            max_expanded_bytes=settings.package_max_expanded_mb * 1024 * 1024,
            max_ratio=settings.package_max_ratio,
            max_nesting=settings.package_max_nesting,
        )


@dataclass(slots=True)
class PackageMember:
    """One file inside the archive."""

    path: str
    size: int
    compressed_size: int
    suffix: str
    category: str  # pdf | image | document | other
    kind: str  # main | corrigendum | boq | form | other
    title: str
    accepted: bool = True
    reason: str | None = None

    @property
    def ratio(self) -> float:
        if self.compressed_size <= 0:
            return float(self.size)
        return self.size / self.compressed_size


@dataclass(slots=True)
class PackageInspection:
    """The result of reading an archive's directory."""

    members: list[PackageMember] = field(default_factory=list)
    skipped: list[PackageMember] = field(default_factory=list)
    total_uncompressed: int = 0
    total_compressed: int = 0
    error: str | None = None

    @property
    def accepted(self) -> list[PackageMember]:
        """The members that may be stored."""
        return [member for member in self.members if member.accepted]

    def summary(self) -> dict:
        return {
            "total": len(self.members) + len(self.skipped),
            "stored": len(self.accepted),
            "skipped": len(self.skipped),
            "total_uncompressed": self.total_uncompressed,
            "total_compressed": self.total_compressed,
            "error": self.error,
        }


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _safe_path(raw: str) -> str | None:
    """Return a normalised relative path, or None when it escapes the archive."""
    if not raw:
        return None
    cleaned = raw.replace("\\", "/").strip()
    if not cleaned or cleaned.endswith("/"):
        return None
    if cleaned.startswith("/") or re.match(r"^[A-Za-z]:", cleaned):
        return None
    parts = [part for part in PurePosixPath(cleaned).parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _classify(suffix: str) -> str:
    if suffix in PARSEABLE_SUFFIXES:
        return "pdf"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in STORED_ONLY_SUFFIXES:
        return "document"
    return "other"


def _kind_for(path: str) -> str:
    name = PurePosixPath(path).name.lower()
    for kind, needles in KIND_PATTERNS:
        if any(needle in name for needle in needles):
            return kind
    return "other"


def _title_for(path: str) -> str:
    name = PurePosixPath(path).name
    stem = name.rsplit(".", 1)[0] if "." in name else name
    cleaned = _SAFE_NAME_RE.sub(" ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or name)[:200]


def inspect_archive(content: bytes, *, limits: PackageLimits | None = None) -> PackageInspection:
    """Read an archive's directory and decide what may be stored."""
    limits = limits or PackageLimits()
    inspection = PackageInspection()
    if not content:
        inspection.error = "The archive is empty."
        return inspection
    try:
        archive = zipfile.ZipFile(BytesIO(content))
    except zipfile.BadZipFile:
        inspection.error = "The file is not a readable ZIP archive."
        return inspection

    with archive:
        infos = archive.infolist()
        if len(infos) > limits.max_members:
            inspection.error = (
                f"The archive holds {len(infos)} entries; only the first "
                f"{limits.max_members} were read."
            )
            infos = infos[: limits.max_members]

        expanded = 0
        for info in infos:
            path = _safe_path(info.filename)
            suffix = PurePosixPath(info.filename).suffix.lower()
            size = int(info.file_size)
            compressed = int(info.compress_size)
            inspection.total_compressed += compressed

            if path is None:
                member = PackageMember(
                    path=info.filename[:200],
                    size=size,
                    compressed_size=compressed,
                    suffix=suffix,
                    category="other",
                    kind="other",
                    title=info.filename[:200],
                    accepted=False,
                    reason="Unsafe path in the archive.",
                )
                inspection.skipped.append(member)
                continue

            if info.flag_bits & 0x1:
                member = PackageMember(
                    path=path,
                    size=size,
                    compressed_size=compressed,
                    suffix=suffix,
                    category="other",
                    kind="other",
                    title=_title_for(path),
                    accepted=False,
                    reason="The file is password protected.",
                )
                inspection.skipped.append(member)
                continue

            if _is_symlink(info):
                member = PackageMember(
                    path=path,
                    size=size,
                    compressed_size=compressed,
                    suffix=suffix,
                    category="other",
                    kind="other",
                    title=_title_for(path),
                    accepted=False,
                    reason="Symbolic links are not read.",
                )
                inspection.skipped.append(member)
                continue

            if suffix in ARCHIVE_SUFFIXES:
                member = PackageMember(
                    path=path,
                    size=size,
                    compressed_size=compressed,
                    suffix=suffix,
                    category="other",
                    kind="other",
                    title=_title_for(path),
                    accepted=False,
                    reason="Nested archives are not opened.",
                )
                inspection.skipped.append(member)
                continue

            if suffix in BLOCKED_SUFFIXES:
                member = PackageMember(
                    path=path,
                    size=size,
                    compressed_size=compressed,
                    suffix=suffix,
                    category="other",
                    kind="other",
                    title=_title_for(path),
                    accepted=False,
                    reason="Executables and scripts are never stored.",
                )
                inspection.skipped.append(member)
                continue

            if size > limits.max_member_bytes:
                member = PackageMember(
                    path=path,
                    size=size,
                    compressed_size=compressed,
                    suffix=suffix,
                    category=_classify(suffix),
                    kind=_kind_for(path),
                    title=_title_for(path),
                    accepted=False,
                    reason=(
                        f"The file is larger than "
                        f"{limits.max_member_bytes // (1024 * 1024)} MB."
                    ),
                )
                inspection.skipped.append(member)
                continue

            if compressed > 0 and size / max(compressed, 1) > limits.max_ratio:
                member = PackageMember(
                    path=path,
                    size=size,
                    compressed_size=compressed,
                    suffix=suffix,
                    category=_classify(suffix),
                    kind=_kind_for(path),
                    title=_title_for(path),
                    accepted=False,
                    reason="The file expands far beyond its compressed size.",
                )
                inspection.skipped.append(member)
                continue

            if expanded + size > limits.max_expanded_bytes:
                member = PackageMember(
                    path=path,
                    size=size,
                    compressed_size=compressed,
                    suffix=suffix,
                    category=_classify(suffix),
                    kind=_kind_for(path),
                    title=_title_for(path),
                    accepted=False,
                    reason="The archive expands beyond the allowed total size.",
                )
                inspection.skipped.append(member)
                continue

            expanded += size
            inspection.total_uncompressed += size
            member = PackageMember(
                path=path,
                size=size,
                compressed_size=compressed,
                suffix=suffix,
                category=_classify(suffix),
                kind=_kind_for(path),
                title=_title_for(path),
            )
            inspection.members.append(member)

    return inspection


def read_member(content: bytes, member: PackageMember, *, limits: PackageLimits | None = None) -> bytes:
    """Read one member's bytes, refusing anything over the limit."""
    limits = limits or PackageLimits()
    if member.size > limits.max_member_bytes:
        raise ValueError("The file is larger than the allowed size.")
    with zipfile.ZipFile(BytesIO(content)) as archive:
        try:
            data = archive.read(member.path)
        except KeyError as exc:  # pragma: no cover - the directory was just read
            raise ValueError("The file is no longer in the archive.") from exc
        except (RuntimeError, zipfile.BadZipFile) as exc:
            raise ValueError("The file could not be read from the archive.") from exc
    if len(data) > limits.max_member_bytes:
        raise ValueError("The file is larger than the allowed size.")
    return data
