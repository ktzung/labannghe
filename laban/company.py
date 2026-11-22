from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Dict, List

from .config import TAXONOMY_DIR
from .text import normalize

_WORD_START = r"(?<![a-z0-9])"
_WORD_END = r"(?![a-z0-9])"


def _compile(phrases: List[str]) -> tuple:
    patterns = []
    for phrase in phrases:
        norm = normalize(phrase)
        if len(norm) < 2:
            continue
        pre = _WORD_START if norm[0].isalnum() else ""
        post = _WORD_END if norm[-1].isalnum() else ""
        patterns.append(re.compile(pre + re.escape(norm) + post))
    return tuple(patterns)


@lru_cache(maxsize=1)
def _data() -> Dict:
    return json.loads((TAXONOMY_DIR / "company_types.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _index():
    data = _data()
    agency = _compile(data.get("agency_markers", []))
    types = {key: _compile(values) for key, values in data.get("types", {}).items()}
    legal = _compile(data.get("legal_form_private", []))
    return agency, types, legal


def classify_company_type(company: str, region: str = "VN") -> str:
    if (region or "").upper() != "VN":
        return "unknown"
    name = normalize(company)
    if not name:
        return "unknown"
    agency, types, legal = _index()
    if any(pattern.search(name) for pattern in agency):
        return "agency"
    for key in ("state", "fdi", "private"):
        if any(pattern.search(name) for pattern in types.get(key, ())):
            return key
    if any(pattern.search(name) for pattern in legal):
        return "private"
    return "unknown"


def type_label(key: str) -> str:
    return _data().get("labels", {}).get(key, key)


def type_short_label(key: str) -> str:
    return _data().get("labels_short", {}).get(key, type_label(key))


def type_order() -> List[str]:
    return list(_data().get("order", ["state", "fdi", "private", "agency", "unknown"]))


def only_known_types() -> List[str]:
    return [key for key in type_order() if key != "unknown"]


__all__ = ["classify_company_type", "type_label", "type_short_label", "type_order", "only_known_types"]
