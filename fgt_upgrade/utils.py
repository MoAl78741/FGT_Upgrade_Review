"""
Shared utility functions: version parsing, URL building, and data cleaning.
"""

import re
from .constants import FORTINET_BASE, PAGE_IDS


def parse_version(v: str) -> tuple:
    """Convert a dotted version string like '7.4.11' into a comparable int tuple."""
    return tuple(int(x) for x in v.strip().split("."))


def version_in_range(v: str, from_ver: str, to_ver: str) -> bool:
    """Return True if from_ver < v <= to_ver."""
    return parse_version(from_ver) < parse_version(v) <= parse_version(to_ver)


def build_url(version: str, section_key: str) -> str:
    """Assemble the full Fortinet docs URL for a given version and section."""
    pid, pname = PAGE_IDS[section_key][0], PAGE_IDS[section_key][1]
    return f"{FORTINET_BASE}/document/fortigate/{version}/fortios-release-notes/{pid}/{pname}"


def clean_text(s: str) -> str:
    """Normalise whitespace and truncate to 600 characters."""
    return " ".join(s.split()).strip()[:600] if s else ""


def deduplicate(items: list, id_key: str = "Bug ID") -> list:
    """
    Remove duplicate entries and entries with empty/short descriptions.
    Also cleans all string fields via clean_text.
    """
    seen, out = set(), []
    for item in items:
        desc = item.get("Description", "")
        if not desc or len(desc.strip()) < 5:
            continue
        key = item.get(id_key) or item.get("Feature ID") or item.get("Bug ID") or desc[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append({k: clean_text(v) if isinstance(v, str) else v for k, v in item.items()})
    return out
