from __future__ import annotations

from typing import Any


def with_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    item = dict(document)
    if "_id" in item:
        item["id"] = item.pop("_id")
    return item
