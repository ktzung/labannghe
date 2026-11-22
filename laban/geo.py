from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import List

from .config import TAXONOMY_DIR
from .text import normalize

_WORD_START = r"(?<![a-z0-9])"
_WORD_END = r"(?![a-z0-9])"


def _pattern(alias: str) -> re.Pattern:
    alias = alias.strip()
    pre = _WORD_START if alias and alias[0].isalnum() else ""
    post = _WORD_END if alias and alias[-1].isalnum() else ""
    return re.compile(pre + re.escape(alias) + post)


@lru_cache(maxsize=1)
def _location_patterns():
    data = json.loads((TAXONOMY_DIR / "locations.json").read_text(encoding="utf-8"))
    pairs = []
    for item in data["locations"]:
        name = item["name"]
        for alias in [name] + item.get("aliases", []):
            norm = normalize(alias)
            if len(norm) >= 2:
                pairs.append((_pattern(norm), name))
    pairs.sort(key=lambda pair: len(pair[0].pattern), reverse=True)
    return tuple(pairs)


def parse_locations(text: str) -> List[str]:
    norm = normalize(text)
    if not norm:
        return []
    found: List[str] = []
    for pattern, name in _location_patterns():
        if name in found:
            continue
        if pattern.search(norm):
            found.append(name)
    return found


def location_names() -> List[str]:
    data = json.loads((TAXONOMY_DIR / "locations.json").read_text(encoding="utf-8"))
    return [item["name"] for item in data["locations"]]


__all__ = ["parse_locations", "location_names"]
