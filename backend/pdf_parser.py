"""
PDF parser for FortiGate release notes.
Converts PDF content into the same data structures produced by the web scrapers.

Expected output per call to parse_pdf():
  (version: str | None, version_data: dict, special_notices: list)

version_data keys that may be populated:
  new_features      – list of {category, Feature ID, Description}
  known_issues      – list of {category, Bug ID, Description}
  resolved-issues   – list of {category, Bug ID, Description}
  changes_cli       – list of {Bug ID, Description}
  changes_default   – list of {Bug ID, Description}
  changes_tablesize – list of {Bug ID, Description}

special_notices:
  list of {title, content}
"""

import re
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pymupdf4llm as _pymupdf4llm
    PYMUPDF4LLM_AVAILABLE = True
except ImportError:
    PYMUPDF4LLM_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# Section detection
# ──────────────────────────────────────────────────────────────────────────────

# (pattern, section_key) — ordered from most-specific to least
_SECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^what['']?s new\b", re.I),                                          "new_features"),
    (re.compile(r"^new features?\b", re.I),                                            "new_features"),
    (re.compile(r"^changes?\s+(?:in|to)\s+cli\b", re.I),                              "changes_cli"),
    (re.compile(r"^changes?\s+in\s+gui\b", re.I),                                     "changes-in-gui-behavior"),
    (re.compile(r"^changes?\s+(?:in|to)\s+default\s+(?:behavior|behaviour|settings?)$", re.I),
                                                                                       "changes_default"),
    (re.compile(r"^changes?\s+(?:in|to)\s+table\s+size$", re.I),                      "changes_tablesize"),
    (re.compile(r"^special\s+notices?$", re.I),                                        "special_notices"),
    (re.compile(r"^known\s+issues?$", re.I),                                           "known_issues"),
    (re.compile(r"^resolved\s+issues?$", re.I),                                        "resolved-issues"),
    (re.compile(r"^change\s*log$", re.I),                                              "change-log"),
    # Rich prose sections → stored as RichSection dicts under slug keys
    (re.compile(r"^upgrade\s+information$", re.I),                                     "upgrade-information"),
    (re.compile(r"^product\s+integration\s+and\s+support$", re.I),                     "product-integration-and-support"),
]

# Sections we don't want to capture at all
_SKIP_RE = re.compile(
    r"^(introduction|"
    r"downgrade\s+information|limitations?|appendix|table\s+of\s+contents?|"
    r"fortios[^\n]{0,40}release\s+notes|contents?)$",
    re.I,
)

# Section keys that produce RichSection prose content (not table-based)
_RICH_KEYS: frozenset = frozenset({
    "upgrade-information",
    "product-integration-and-support",
    "change-log",
    "changes-in-gui-behavior",
})


def _match_section(line: str) -> Optional[str]:
    """Return section key if line is a recognized section heading, else None."""
    line = line.strip()
    for pat, key in _SECTION_PATTERNS:
        if pat.match(line):
            return key
    return None


def _is_skippable(line: str) -> bool:
    return bool(_SKIP_RE.match(line.strip()))


# Monospace / code fonts used by Fortinet in PDF code blocks
_CODE_FONT_RE = re.compile(r'consolas|courier|mono(?:space)?|source.?code|lucida.?console', re.I)
# Bold (non-code) fonts used for in-text bold phrases
_BOLD_FONT_RE = re.compile(r'bold', re.I)

# Bullet characters used by Fortinet PDFs (including Symbol/Wingdings private-use glyphs)
_BULLET_CHAR_RE = re.compile(
    r'^[\u2022\u2023\u25E6\u2043\u2219\u00B7\u25CF\u25AA\u2714\u2713'
    r'\uf0b7\uf0a7\uf0d8\uf0fc\uf0cf\u00b7•·●○◆▪▫►▶◦‣⁃]\s*',
    re.UNICODE,
)

# Numbered list items: "1.", "2.", "(1)", etc.
_NUMBERED_ITEM_RE = re.compile(r'^(\d+[\.\)]|\(\d+\))\s+')

# Page-footer lines that appear on every page of FortiGate PDFs
_PDF_FOOTER_RE = re.compile(
    r'^(FortiOS\s+[\d\.]+\s+Release\s+Notes|Fortinet\s+Inc\.?\s*$)',
    re.I,
)


def _fix_pipe_lists(blocks: list[dict]) -> list[dict]:
    """
    Convert pipe-prefixed paragraph blocks into list blocks.

    Fortinet PDFs render hyperlink lists as text items prefixed with '|'
    (e.g. "| FortiGate 6000 ... | FortiGate 7000E ... | FortiGate 7000F ...").
    These may appear as individual lines or pre-merged into a single paragraph.
    """
    result = []
    for block in blocks:
        if block.get("type") == "paragraph":
            text = block["text"]
            if text.startswith("|"):
                parts = [p.strip() for p in text.split("|") if p.strip()]
                if parts:
                    result.append({"type": "list", "items": parts})
                    continue
        result.append(block)
    return result


def _is_category_like(line: str) -> bool:
    """
    Heuristic: is this line a category heading within a section?
    (e.g. "Firewall", "SD-WAN", "Security Fabric")
    """
    line = line.strip()
    if not line or len(line) > 80:
        return False
    if line[0].isdigit():
        return False
    if "|" in line or re.search(r"\d{5,}", line):
        return False
    # Don't treat lines that are probably part of sentences
    if line.endswith((".",":",",",";")):
        return False
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Version detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_version_from_filename(filename: str) -> Optional[str]:
    """Extract '7.4.11' from 'fortios-v7.4.11-release-notes.pdf'."""
    m = re.search(r"v?(\d+\.\d+\.\d+)", filename, re.I)
    return m.group(1) if m else None


def detect_version_from_text(text: str) -> Optional[str]:
    """Extract FortiOS version from the first page text."""
    for pat in [
        r"FortiOS\s+v?(\d+\.\d+\.\d+)",
        r"FortiGate[^\n]{0,40}?(\d+\.\d+\.\d+)",
        r"Release\s+Notes[^\n]{0,40}?(\d+\.\d+\.\d+)",
        r"[Vv]ersion\s+(\d+\.\d+\.\d+)",
    ]:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Table row parsing
# ──────────────────────────────────────────────────────────────────────────────

def _clean(v) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def _title_to_slug(title: str) -> str:
    """Convert a section title to a URL-style slug (lowercase, hyphens)."""
    slug = re.sub(r"[^a-z0-9\s]", " ", title.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug


def _looks_like_id(text: str) -> bool:
    """Return True if text looks like a standalone Bug/Feature ID (4-10 digit number)."""
    return bool(re.match(r'^\d{4,10}$', text.strip()))


# Matches a standalone numeric ID as it appears alone in the left-column text stream
# (Bug IDs and Feature IDs in FortiGate PDFs are 5-10 digit numbers).
_STANDALONE_ID_RE = re.compile(r'^\d{5,10}$')


def _split_id_from_text(text: str) -> tuple[str, str]:
    """
    If text begins with a numeric ID followed by whitespace, split it.
    Returns (id, rest_of_description). If no leading numeric ID, returns ("", text).
    """
    m = re.match(r'^(\d{4,10})\s+(.*)', text.strip(), re.DOTALL)
    if m:
        return m.group(1), m.group(2).strip()
    return "", text.strip()


def _parse_id_desc_table(
    rows: "list[list] | list[tuple[float, list]]",
    id_key: str = "Bug ID",
) -> list[dict]:
    """
    Convert raw pdfplumber table rows → list of {id_key: ..., Description: ..., _first_y: float}.

    Accepts two row formats:
      • list[list]                 — plain cells (tests, fallback path)
      • list[tuple[float, list]]   — (row_y, cells) from _extract_table_rows

    Handles:
      - Header row detection and skip
      - Multi-line rows (empty id cell = continuation)
      - Merged first-column cells (e.g. "890776 Description text" in one cell)
      - Description-only tables (no numeric IDs — id_key set to "")
    """
    if not rows:
        return []

    # Detect rows_with_y format: list of (float, list) tuples
    has_y = isinstance(rows[0], tuple)

    def _cells(item):
        return item[1] if has_y else item

    def _y(item) -> float:
        return float(item[0]) if has_y else 0.0

    # Detect and skip header row
    start = 0
    first = [_clean(c).lower() for c in (_cells(rows[0]) or [])]
    header_kws = {"bug id", "feature id", "description", "id", "number"}
    if any(kw in " ".join(first) for kw in header_kws):
        start = 1

    results: list[dict] = []
    cur_id: Optional[str] = None
    cur_desc_parts: list[str] = []
    cur_first_y: float = 0.0

    def _flush():
        if cur_id is None:
            return
        # Skip rows that are just leftover header text
        if cur_id.lower() in ("bug id", "feature id", "id", "number"):
            return
        # Allow empty-ID rows (description-only sections) as long as there's content
        desc = " ".join(cur_desc_parts)
        if cur_id == "" and not desc:
            return
        results.append({
            id_key: cur_id,
            "Description": desc,
            "_first_y": cur_first_y,
        })

    for item in rows[start:]:
        row = _cells(item)
        row_y = _y(item)
        if not row:
            continue
        # Pad to at least 2 cells
        row = list(row) + [""] * max(0, 2 - len(row))

        c0 = _clean(row[0])
        c1 = " ".join(_clean(c) for c in row[1:] if _clean(c))

        if not c0 and not c1:
            continue

        if not c0:
            # Continuation line — description text in remaining columns
            cur_desc_parts.append(c1)
        elif _looks_like_id(c0):
            # Clean numeric ID in column 0 — normal case
            _flush()
            cur_id = c0
            cur_desc_parts = [c1] if c1 else []
            cur_first_y = row_y
        else:
            # Column 0 is NOT a plain numeric ID.
            # Two sub-cases:
            #   (a) Merged cell: "890776 Description text" — split leading ID off
            #   (b) No ID at all: pure description text
            extracted_id, rest = _split_id_from_text(c0)
            if extracted_id:
                # Case (a): numeric ID was merged with description
                _flush()
                cur_id = extracted_id
                # Combine the rest of the merged cell with any additional columns
                full_desc = (rest + " " + c1).strip() if c1 else rest
                cur_desc_parts = [full_desc] if full_desc else []
                cur_first_y = row_y
            else:
                # Case (b): no ID — treat entire row as a description-only entry
                _flush()
                cur_id = ""
                full_desc = (c0 + " " + c1).strip() if c1 else c0
                cur_desc_parts = [full_desc] if full_desc else []
                cur_first_y = row_y

    _flush()
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Word → line grouping
# ──────────────────────────────────────────────────────────────────────────────


def _extract_table_rows(page, tbl_obj) -> list[tuple[float, list]]:
    """
    Extract table rows using per-cell word extraction so that spaces are
    correctly inserted between words.  Falls back to the raw cell text when
    cropping fails.

    Returns a list of (row_y, cells) tuples where row_y is the top-edge
    y-coordinate of the row — used later to pair text-column IDs with
    table-column descriptions by proximity.
    """
    rows_with_y: list[tuple[float, list]] = []
    try:
        for row in tbl_obj.rows:
            row_y = 0.0
            for cell in row.cells:
                if cell is not None:
                    row_y = float(cell[1])
                    break
            cells: list = []
            for cell in row.cells:
                if cell is None:
                    cells.append(None)
                    continue
                try:
                    x0, top, x1, bottom = cell
                    # Small inset to avoid picking up border lines
                    cropped = page.crop((x0 + 1, top + 1, x1 - 1, bottom - 1))
                    words = cropped.extract_words(x_tolerance=1, y_tolerance=3)
                    cells.append(" ".join(w["text"] for w in words) if words else "")
                except Exception:
                    cells.append("")
            rows_with_y.append((row_y, cells))
    except Exception:
        raw = tbl_obj.extract()
        rows_with_y = [(float(i), row or []) for i, row in enumerate(raw or [])]
    return rows_with_y

def _words_to_lines(
    words: list[dict],
    tolerance: float = 3.0,
) -> list[tuple[float, list[dict]]]:
    """Group words by y-coordinate into sorted lines."""
    buckets: dict[int, list[dict]] = {}
    for w in words:
        key = round(w["top"] / tolerance)
        buckets.setdefault(key, []).append(w)
    return sorted(
        ((k * tolerance, sorted(ws, key=lambda x: x["x0"])) for k, ws in buckets.items()),
        key=lambda t: t[0],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

def parse_pdf(pdf_path) -> tuple[Optional[str], dict, list, dict, dict]:
    """
    Parse a FortiGate release notes PDF.

    Returns
    -------
    version : str | None
    version_data : dict  (same shape as scraper output for one version)
    special_notices : list of {title, content}
    section_pages : dict[slug, list[int]]  — page indices used by each rich section
    notice_pages : dict[title, list[int]]  — page indices used by each special notice
    """
    if not PDF_AVAILABLE:
        raise RuntimeError("pdfplumber not installed — run: pip install pdfplumber")

    pdf_path = Path(pdf_path)
    version: Optional[str] = detect_version_from_filename(pdf_path.name)

    # State machine
    current_section: Optional[str] = None
    current_category: Optional[str] = None
    current_skip: bool = False

    # Accumulate (page_idx, category, rows_with_y) per section key
    section_tables: dict[str, list[tuple[int, Optional[str], list]]] = {}
    # Rich prose sections: slug → {title, blocks}
    rich_sections: dict[str, dict] = {}
    current_rich_slug: Optional[str] = None   # active sub-section slug
    pending_rich_heading: Optional[str] = None  # accumulates multi-line headings
    # Formatting state for rich sections
    rich_base_x0: float = 57.0   # left margin of body text (calibrated per section)
    last_rich_y: Optional[float] = None   # y of previous body-text event
    last_list_item_x0: float = 57.0  # x0 of the line that started the current list item
    # Standalone numeric IDs (Bug ID / Feature ID) found in the left text column,
    # in order of appearance: section → [(page_idx, y, category, id_str)]
    section_text_ids: dict[str, list[tuple[int, float, Optional[str], str]]] = {}
    # Special notices: title → [text lines]
    notice_buckets: dict[str, list[str]] = {}
    current_notice_title: Optional[str] = None
    # Page tracking for image rendering
    current_page_num: int = -1
    section_pages: dict[str, list[int]] = {}   # slug → [page indices containing content]
    notice_pages: dict[str, list[int]] = {}    # notice title → [page indices]

    def _track_section(slug: Optional[str]) -> None:
        if slug:
            lst = section_pages.setdefault(slug, [])
            if current_page_num not in lst:
                lst.append(current_page_num)

    def _track_notice(title: Optional[str]) -> None:
        if title:
            lst = notice_pages.setdefault(title, [])
            if current_page_num not in lst:
                lst.append(current_page_num)

    with pdfplumber.open(str(pdf_path)) as pdf:
        if not version and pdf.pages:
            version = detect_version_from_text(pdf.pages[0].extract_text() or "")

        for page_idx, page in enumerate(pdf.pages):
            current_page_num = page_idx
            # Record continuation pages for already-active sections/notices
            if current_section == "special_notices":
                _track_notice(current_notice_title)
                _track_section(current_rich_slug)
            elif current_section in _RICH_KEYS:
                _track_section(current_rich_slug)
            # ── Locate tables on this page ────────────────────────────────────
            try:
                tbl_objs = page.find_tables()
                tables_with_pos: list[tuple[Optional[tuple], list]] = [
                    (t.bbox, _extract_table_rows(page, t)) for t in tbl_objs
                ]
            except Exception:
                # Fallback: no positional info — synthesise fake y-positions
                tables_with_pos = [
                    (None, [(float(i), row or []) for i, row in enumerate(raw or [])])
                    for raw in (page.extract_tables() or [])
                ]

            table_bboxes = [b for b, _ in tables_with_pos if b is not None]

            # ── Extract words outside table areas ─────────────────────────────
            # Use x_tolerance=1 so that narrow inter-word gaps (common in
            # Fortinet PDFs) are treated as word boundaries rather than merged.
            try:
                words = page.extract_words(extra_attrs=["size", "fontname"], x_tolerance=1)
            except Exception:
                words = page.extract_words(x_tolerance=1)

            if table_bboxes:
                def _in_any_table(w, bboxes=table_bboxes):
                    wx0, wx1 = w.get("x0", 0), w.get("x1", 0)
                    wt, wb = w.get("top", 0), w.get("bottom", 0)
                    for bx0, by0, bx1, by1 in bboxes:
                        if wx0 >= bx0 - 2 and wt >= by0 - 2 and wx1 <= bx1 + 2 and wb <= by1 + 2:
                            return True
                    return False
                words = [w for w in words if not _in_any_table(w)]

            # ── Build an ordered event list (text + tables sorted by y) ───────
            sizes = [w.get("size", 10) for w in words if w.get("size")]
            median_sz = sorted(sizes)[len(sizes) // 2] if sizes else 10

            events: list[dict] = []

            for y_pos, lwords in _words_to_lines(words):
                text = " ".join(w["text"] for w in lwords).strip()
                if not text:
                    continue
                max_sz = max((w.get("size", 0) for w in lwords), default=0)
                # Filter tiny single-character bullet markers (Symbol/Wingdings fonts).
                # These appear as a separate sub-5pt glyph ('l', 'n', etc.) alongside
                # the actual list-item text; the text line itself carries all the content.
                if max_sz < 5 and len(text) <= 3:
                    continue
                x0 = min(w["x0"] for w in lwords)

                # Classify line by font: code (Consolas etc.) or bold (Inter-Bold etc.)
                n = len(lwords)
                code_n = sum(1 for w in lwords if _CODE_FONT_RE.search(w.get("fontname", "")))
                bold_n = sum(
                    1 for w in lwords
                    if _BOLD_FONT_RE.search(w.get("fontname", ""))
                    and not _CODE_FONT_RE.search(w.get("fontname", ""))
                )
                is_code_line = n > 0 and code_n / n >= 0.8
                is_bold_line = n > 0 and bold_n / n >= 0.8 and not is_code_line

                events.append({
                    "y": y_pos,
                    "kind": "text",
                    "text": text,
                    "large": max_sz > median_sz * 1.08,
                    "x0": x0,
                    "is_code": is_code_line,
                    "is_bold": is_bold_line,
                })

            for bbox, rwy in tables_with_pos:
                if rwy:
                    events.append({
                        "y": bbox[1] if bbox else 9999,
                        "kind": "table",
                        "rows_with_y": rwy,
                        "rows": [cells for _, cells in rwy],
                    })

            events.sort(key=lambda e: e["y"])

            # ── Process events in vertical order ─────────────────────────────
            for ev in events:
                if ev["kind"] == "text":
                    line = ev["text"]

                    # ── Special-notices title continuation check ───────────────
                    # Must happen BEFORE _match_section / _is_skippable so that
                    # words like "limitations" or "addresses" — which would
                    # otherwise match skip patterns — are correctly appended to
                    # an in-progress multi-line title.
                    if (current_section == "special_notices"
                            and current_notice_title is not None
                            and not notice_buckets.get(current_notice_title)
                            and ev["large"] and len(line) < 120
                            and not _match_section(line)):
                        new_title = current_notice_title + " " + line
                        notice_buckets[new_title] = notice_buckets.pop(
                            current_notice_title, []
                        )
                        current_notice_title = new_title
                        # Also rename the in-progress rich section
                        if current_rich_slug and current_rich_slug in rich_sections:
                            old = rich_sections.pop(current_rich_slug)
                            new_slug = _title_to_slug(new_title)
                            old["title"] = new_title
                            if old["blocks"] and old["blocks"][0].get("type") == "heading":
                                old["blocks"][0]["text"] = new_title
                            rich_sections[new_slug] = old
                            current_rich_slug = new_slug
                        continue

                    sec = _match_section(line)
                    if sec is not None:
                        if sec == "_skip":
                            # Known sections we intentionally ignore (e.g. GUI behavior)
                            current_skip = True
                            current_section = None
                            current_notice_title = None
                            pending_rich_heading = None
                        elif sec == current_section:
                            # Same heading as the active section — this is a repeated
                            # page-continuation header (Fortinet prints the chapter name
                            # at the top of every page).  Ignore it so that content on
                            # subsequent pages flows into the correct sub-section.
                            pass
                        else:
                            current_section = sec
                            current_category = None
                            current_skip = False
                            current_notice_title = None
                            section_tables.setdefault(sec, [])
                            if sec in _RICH_KEYS:
                                # Initialise a default slug for section intro content
                                current_rich_slug = sec
                                pending_rich_heading = None
                                last_rich_y = None
                                rich_base_x0 = 57.0
                                last_list_item_x0 = 57.0
                                rich_sections.setdefault(sec, {
                                    "title": sec.replace("-", " ").title(),
                                    "blocks": [],
                                })
                            elif sec == "special_notices":
                                # Reset rich state — special_notices uses dual-mode parsing
                                current_rich_slug = None
                                pending_rich_heading = None
                                last_rich_y = None
                                rich_base_x0 = 57.0
                                last_list_item_x0 = 57.0
                            else:
                                pending_rich_heading = None
                        continue

                    if _is_skippable(line):
                        current_skip = True
                        current_section = None
                        current_notice_title = None
                        continue

                    if current_skip or current_section is None:
                        continue

                    if current_section == "special_notices":
                        # Skip page-footer lines
                        if _PDF_FOOTER_RE.match(line):
                            continue
                        # Larger-than-body text = sub-notice title.
                        # (Multi-line title continuation is handled before this block.)
                        if ev["large"] and len(line) < 120:
                            current_notice_title = line
                            notice_buckets.setdefault(line, [])
                            _track_notice(line)
                            # Also start a rich section so notice appears in More Sections
                            slug = _title_to_slug(line)
                            current_rich_slug = slug
                            _track_section(slug)
                            rich_sections[slug] = {
                                "title": line,
                                "blocks": [{"type": "heading", "level": 2, "text": line}],
                            }
                            last_rich_y = None
                            rich_base_x0 = 57.0
                            last_list_item_x0 = 57.0
                        elif current_notice_title is not None:
                            notice_buckets.setdefault(current_notice_title, []).append(line)
                            # Also classify as a rich block for More Sections
                            if current_rich_slug and current_rich_slug in rich_sections:
                                blocks = rich_sections[current_rich_slug]["blocks"]
                                x0 = ev.get("x0", rich_base_x0)
                                y = ev["y"]
                                if last_rich_y is not None and y > last_rich_y:
                                    y_gap = y - last_rich_y
                                else:
                                    y_gap = 999
                                last_rich_y = y
                                is_code = ev.get("is_code", False)
                                is_bold = ev.get("is_bold", False)
                                bullet_m = _BULLET_CHAR_RE.match(line)
                                numbered_m = _NUMBERED_ITEM_RE.match(line)
                                is_indented = x0 > rich_base_x0 + 10
                                if is_code:
                                    if blocks and blocks[-1]["type"] == "code":
                                        blocks[-1]["text"] += "\n" + line
                                    else:
                                        blocks.append({"type": "code", "text": line})
                                elif bullet_m:
                                    clean = _BULLET_CHAR_RE.sub("", line).strip()
                                    if blocks and blocks[-1]["type"] == "list":
                                        blocks[-1]["items"].append(clean)
                                    else:
                                        blocks.append({"type": "list", "items": [clean]})
                                elif numbered_m:
                                    clean = _NUMBERED_ITEM_RE.sub("", line).strip()
                                    last_list_item_x0 = x0
                                    if blocks and blocks[-1]["type"] == "list":
                                        blocks[-1]["items"].append(clean)
                                    else:
                                        blocks.append({"type": "list", "items": [clean]})
                                elif is_indented:
                                    is_continuation = (
                                        blocks and blocks[-1]["type"] == "list"
                                        and blocks[-1]["items"]
                                        and y_gap < 20
                                        and x0 > last_list_item_x0 + 8
                                    )
                                    if is_continuation:
                                        blocks[-1]["items"][-1] += " " + line
                                    elif blocks and blocks[-1]["type"] == "list":
                                        last_list_item_x0 = x0
                                        blocks[-1]["items"].append(line)
                                    else:
                                        last_list_item_x0 = x0
                                        blocks.append({"type": "list", "items": [line]})
                                elif line.startswith("|"):
                                    # Pipe-prefixed link item (Fortinet hyperlink lists)
                                    clean = line.lstrip("|").strip()
                                    if clean:
                                        if blocks and blocks[-1]["type"] == "list":
                                            blocks[-1]["items"].append(clean)
                                        else:
                                            blocks.append({"type": "list", "items": [clean]})
                                elif is_bold:
                                    if (blocks and blocks[-1]["type"] == "paragraph"
                                            and blocks[-1].get("bold") and y_gap < 20):
                                        blocks[-1]["text"] += " " + line
                                    else:
                                        blocks.append({"type": "paragraph", "text": line, "bold": True})
                                else:
                                    last_para_text = blocks[-1]["text"] if blocks and blocks[-1]["type"] == "paragraph" else ""
                                    sentence_break = (
                                        last_para_text.endswith((".", "!", "?"))
                                        and line and line[0].isupper()
                                        and y_gap > 13
                                    )
                                    if y_gap > 20 or not blocks or blocks[-1]["type"] != "paragraph" or sentence_break:
                                        blocks.append({"type": "paragraph", "text": line})
                                    else:
                                        blocks[-1]["text"] += " " + line
                        else:
                            # No title yet — use a placeholder
                            notice_buckets.setdefault("__default__", []).append(line)
                    elif current_section in _RICH_KEYS:
                        # ── Rich prose section ───────────────────────────────
                        # Skip page-footer lines that appear on every PDF page
                        if _PDF_FOOTER_RE.match(line):
                            continue

                        if ev["large"]:
                            # Sub-section heading (may span multiple lines)
                            if pending_rich_heading is not None:
                                pending_rich_heading += " " + line
                            else:
                                pending_rich_heading = line
                            last_rich_y = None  # reset paragraph tracking
                        else:
                            # Body text
                            if pending_rich_heading is not None:
                                # Commit the accumulated heading as a new sub-section
                                slug = _title_to_slug(pending_rich_heading)
                                current_rich_slug = slug
                                _track_section(slug)
                                rich_sections[slug] = {
                                    "title": pending_rich_heading,
                                    "blocks": [{
                                        "type": "heading",
                                        "level": 2,
                                        "text": pending_rich_heading,
                                    }],
                                }
                                pending_rich_heading = None
                                # Calibrate base indentation from first body line
                                rich_base_x0 = ev.get("x0", 57.0)
                                last_rich_y = None
                                last_list_item_x0 = rich_base_x0

                            if current_rich_slug:
                                blocks = rich_sections[current_rich_slug]["blocks"]
                                x0 = ev.get("x0", rich_base_x0)
                                y = ev["y"]
                                # Negative gap means we crossed a page boundary
                                # (y resets to the top of the new page); treat
                                # it the same as a large gap → new block.
                                if last_rich_y is not None and y > last_rich_y:
                                    y_gap = y - last_rich_y
                                else:
                                    y_gap = 999
                                last_rich_y = y

                                # ── Classify the line ──────────────────────
                                is_code = ev.get("is_code", False)
                                is_bold = ev.get("is_bold", False)
                                bullet_m = _BULLET_CHAR_RE.match(line)
                                numbered_m = _NUMBERED_ITEM_RE.match(line)
                                # Indented beyond normal left margin →
                                # bullet-list item or wrapped numbered-item text
                                is_indented = x0 > rich_base_x0 + 10

                                if is_code:
                                    # Code block — merge consecutive code lines with newline
                                    if blocks and blocks[-1]["type"] == "code":
                                        blocks[-1]["text"] += "\n" + line
                                    else:
                                        blocks.append({"type": "code", "text": line})

                                elif bullet_m:
                                    # Explicit bullet character — strip it
                                    clean = _BULLET_CHAR_RE.sub("", line).strip()
                                    if blocks and blocks[-1]["type"] == "list":
                                        blocks[-1]["items"].append(clean)
                                    else:
                                        blocks.append({"type": "list", "items": [clean]})

                                elif numbered_m:
                                    # "1. text", "2. text", etc.
                                    clean = _NUMBERED_ITEM_RE.sub("", line).strip()
                                    last_list_item_x0 = x0  # record start x0 for wrap detection
                                    if blocks and blocks[-1]["type"] == "list":
                                        blocks[-1]["items"].append(clean)
                                    else:
                                        blocks.append({"type": "list", "items": [clean]})

                                elif is_indented:
                                    # A line is a wrapped CONTINUATION of the previous item
                                    # only when it is indented DEEPER than the line that
                                    # started that item (e.g. "below." after "1. If …").
                                    # When it is at the SAME x0 as the previous item starter
                                    # it is always a new item — this correctly handles
                                    # bullet lists where every item starts at the same indent.
                                    is_continuation = (
                                        blocks and blocks[-1]["type"] == "list"
                                        and blocks[-1]["items"]
                                        and y_gap < 20
                                        and x0 > last_list_item_x0 + 8
                                    )
                                    if is_continuation:
                                        blocks[-1]["items"][-1] += " " + line
                                    elif blocks and blocks[-1]["type"] == "list":
                                        last_list_item_x0 = x0
                                        blocks[-1]["items"].append(line)
                                    else:
                                        last_list_item_x0 = x0
                                        blocks.append({"type": "list", "items": [line]})

                                elif line.startswith("|"):
                                    # Pipe-prefixed link item (Fortinet hyperlink lists)
                                    clean = line.lstrip("|").strip()
                                    if clean:
                                        if blocks and blocks[-1]["type"] == "list":
                                            blocks[-1]["items"].append(clean)
                                        else:
                                            blocks.append({"type": "list", "items": [clean]})

                                elif is_bold:
                                    # Bold callout / inline heading paragraph.
                                    # Merge wrapped bold lines (y_gap < 20) into one block.
                                    if (blocks and blocks[-1]["type"] == "paragraph"
                                            and blocks[-1].get("bold") and y_gap < 20):
                                        blocks[-1]["text"] += " " + line
                                    else:
                                        blocks.append({"type": "paragraph", "text": line, "bold": True})

                                else:
                                    # Regular paragraph text.
                                    # New paragraph when y-gap is large enough,
                                    # otherwise concatenate (PDF line-wrap).
                                    last_para_text = blocks[-1]["text"] if blocks and blocks[-1]["type"] == "paragraph" else ""
                                    sentence_break = (
                                        last_para_text.endswith((".", "!", "?"))
                                        and line and line[0].isupper()
                                        and y_gap > 13
                                    )
                                    if y_gap > 20 or not blocks or blocks[-1]["type"] != "paragraph" or sentence_break:
                                        blocks.append({"type": "paragraph", "text": line})
                                    else:
                                        blocks[-1]["text"] += " " + line
                    else:
                        # Category heading detection: large text within a section
                        if ev["large"] and _is_category_like(line):
                            current_category = line
                        # Standalone numeric ID in the left column — collect for pairing
                        # with description rows from the right-column table.
                        elif _STANDALONE_ID_RE.match(line):
                            section_text_ids.setdefault(current_section, []).append(
                                (current_page_num, ev["y"], current_category, line.strip())
                            )

                elif ev["kind"] == "table":
                    if current_section and not current_skip:
                        if current_section in _RICH_KEYS or (
                            current_section == "special_notices" and current_rich_slug
                        ):
                            # Rich section table → add as table block
                            rwy = ev.get("rows_with_y", [])
                            if current_rich_slug and rwy and current_rich_slug in rich_sections:
                                rows = [cells for _, cells in rwy]
                                hdrs = [_clean(c) for c in (rows[0] or [])]
                                data = [
                                    [_clean(c) for c in (row or [])]
                                    for row in rows[1:]
                                    if any(_clean(c) for c in (row or []))
                                ]
                                if hdrs or data:
                                    rich_sections[current_rich_slug]["blocks"].append({
                                        "type": "table",
                                        "headers": hdrs,
                                        "rows": data,
                                    })
                        else:
                            section_tables.setdefault(current_section, []).append(
                                (current_page_num, current_category, ev.get("rows_with_y") or
                                 [(float(i), row) for i, row in enumerate(ev.get("rows", []))])
                            )

    # ── Build final data structures ───────────────────────────────────────────
    version_data: dict = {}

    # ── Helper: extract flat description list from section tables ────────────────
    def _flat_descs(sec_key: str, id_key: str) -> list[tuple[int, float, Optional[str], str]]:
        """Return [(page_idx, first_y, table_category, description)] for all parsed rows."""
        out: list[tuple[int, float, Optional[str], str]] = []
        for page_idx, cat, rows_with_y in section_tables.get(sec_key, []):
            for item in _parse_id_desc_table(rows_with_y, id_key):
                out.append((page_idx, item["_first_y"], cat, item["Description"]))
        return out

    def _y_match_descs(
        ids: list[tuple[int, float, Optional[str], str]],
        descs: list[tuple[int, float, Optional[str], str]],
    ) -> list[tuple[Optional[str], str, Optional[str]]]:
        """
        Pair each (page, y, cat, id) with the closest description row on the same
        page by y-distance.  Returns [(id_cat, desc, tbl_cat)] in the same order
        as `ids`.  Consumed description rows are removed so they cannot be reused.
        """
        desc_pool = list(descs)
        result = []
        for id_page, id_y, id_cat, _id in ids:
            best_i, best_dist = -1, float("inf")
            for i, (d_page, d_y, _d_cat, _desc) in enumerate(desc_pool):
                if d_page == id_page:
                    dist = abs(d_y - id_y)
                    if dist < best_dist:
                        best_dist, best_i = dist, i
            if best_i >= 0:
                _, _, tbl_cat, desc = desc_pool.pop(best_i)
            else:
                tbl_cat, desc = id_cat, ""
            result.append((id_cat, desc, tbl_cat))
        return result

    # ── New features ──────────────────────────────────────────────────────────
    if "new_features" in section_tables:
        feat_ids = section_text_ids.get("new_features", [])
        all_descs = _flat_descs("new_features", "Feature ID")
        feats: list[dict] = []
        if feat_ids:
            for (id_cat, desc, tbl_cat), (_, _, _, fid) in zip(
                _y_match_descs(feat_ids, all_descs), feat_ids
            ):
                feats.append({
                    "category": id_cat or tbl_cat or "General",
                    "Feature ID": fid,
                    "Description": desc,
                })
        else:
            # Fallback: no IDs collected (unusual PDF layout)
            for _pg, cat, rows_with_y in section_tables["new_features"]:
                for item in _parse_id_desc_table(rows_with_y, "Feature ID"):
                    feats.append({
                        "category": cat or "General",
                        "Feature ID": item["Feature ID"],
                        "Description": item["Description"],
                    })
        if feats:
            version_data["new_features"] = feats

    # ── Issues sections (known / resolved) ────────────────────────────────────
    for sec_key in ("known_issues", "resolved-issues"):
        if sec_key not in section_tables:
            continue
        bug_ids = section_text_ids.get(sec_key, [])
        all_descs = _flat_descs(sec_key, "Bug ID")
        issues: list[dict] = []
        if bug_ids:
            for (id_cat, desc, tbl_cat), (_, _, _, bid) in zip(
                _y_match_descs(bug_ids, all_descs), bug_ids
            ):
                issues.append({
                    "category": id_cat or tbl_cat or "General",
                    "Bug ID": bid,
                    "Description": desc,
                })
        else:
            # Fallback
            for _pg, cat, rows_with_y in section_tables[sec_key]:
                for item in _parse_id_desc_table(rows_with_y, "Bug ID"):
                    issues.append({
                        "category": cat or "General",
                        "Bug ID": item["Bug ID"],
                        "Description": item["Description"],
                    })
        if issues:
            version_data[sec_key] = issues

    # ── Simple changes sections ───────────────────────────────────────────────
    for sec_key in ("changes_cli", "changes_default", "changes_tablesize"):
        if sec_key not in section_tables:
            continue
        bug_ids = section_text_ids.get(sec_key, [])
        all_descs = _flat_descs(sec_key, "Bug ID")
        items: list[dict] = []
        if bug_ids:
            for (_id_cat, desc, _tbl_cat), (_, _, _, bid) in zip(
                _y_match_descs(bug_ids, all_descs), bug_ids
            ):
                items.append({"Bug ID": bid, "Description": desc})
        else:
            # Fallback
            for _pg, _, rows_with_y in section_tables[sec_key]:
                for item in _parse_id_desc_table(rows_with_y, "Bug ID"):
                    items.append({"Bug ID": item["Bug ID"], "Description": item["Description"]})
        if items:
            version_data[sec_key] = items

    # ── Rich prose sections (More Sections) ──────────────────────────────────
    # Safety-net: skip slugs whose title ends with a bare page number —
    # these were created from TOC entries (e.g. "Resolved issues 34")
    # that slipped past the section-pattern guard.
    _trailing_num_re = re.compile(r'\s+\d+\s*$')
    for slug, section in rich_sections.items():
        if section.get("blocks") and not _trailing_num_re.search(section.get("title", "")):
            section["blocks"] = _fix_pipe_lists(section["blocks"])
            version_data[slug] = section

    # Special notices
    # Drop __default__ — it collects pre-title text (typically a TOC list) that
    # should not be rendered as a notice entry.
    notice_buckets.pop("__default__", None)
    special_notices: list[dict] = []
    for title, lines in notice_buckets.items():
        content = " ".join(lines).strip()
        if title or content:
            special_notices.append({"title": title, "content": content})

    # ── Upgrade rich sections and notices to markdown via pymupdf4llm ─────────
    # pymupdf4llm extracts proper GFM markdown (headings, tables, code blocks,
    # lists) from specific page ranges — far more accurate than the pdfplumber
    # block extraction above, and searchable unlike the old PNG image approach.
    if PYMUPDF4LLM_AVAILABLE:
        for slug, section in list(version_data.items()):
            if isinstance(section, dict) and "blocks" in section:
                pages = section_pages.get(slug, [])
                if pages:
                    try:
                        md = _pymupdf4llm.to_markdown(str(pdf_path), pages=pages)
                        if md.strip():
                            section["markdown"] = md
                    except Exception:
                        pass

        for notice in special_notices:
            title = notice.get("title", "")
            pages = notice_pages.get(title, [])
            if pages:
                try:
                    md = _pymupdf4llm.to_markdown(str(pdf_path), pages=pages)
                    if md.strip():
                        notice["markdown"] = md
                except Exception:
                    pass

    return version, version_data, special_notices, section_pages, notice_pages
