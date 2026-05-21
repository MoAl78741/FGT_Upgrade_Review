"""
Full-document scraper — captures every section of the Fortinet release notes,
not just the cherry-picked tables.

Strategy
--------
1. discover_toc()  — fetches the release notes index page for a version and
                     extracts every section link from the sidebar navigation.
                     Returns a dict keyed by a normalised section slug:
                       {slug: {page_id, slug, title, url}}

2. scrape_rich_section()  — generic scraper for prose/mixed pages.
                             Returns structured blocks so the frontend can
                             render them properly later:
                               [{"type": "heading"|"paragraph"|"list"|"table",
                                 ...fields...}]

3. scrape_issues_section() — reuses the known-issues table format
                              (category + Bug ID + Description).
                              Used for "Resolved Issues" and any other
                              section whose slug contains "issues".

4. scrape_version_full()  — scrapes all TOC sections for one version,
                             returns a dict keyed by slug.

5. scrape_all_extended()  — parallel wrapper over all versions; merges
                             results into the existing all_data dict so
                             the existing section keys are preserved.

All results are stored in all_data[version][slug], which goes into the
existing all_data_json column in SQLite — no schema change needed.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

from .constants import FORTINET_BASE
from .utils import clean_text, parse_version

# ── Slugs we already scrape via the legacy pipeline; skip them here ────────
_LEGACY_SLUGS = {
    "changes-in-cli",
    "changes-in-default-behavior",
    "changes-in-table-size",
    "new-features-and-enhancements",
    "new-features-or-enhancements",   # alternate phrasing in some versions
    "special-notices",
    "known-issues",
}

# Maps each legacy TOC slug → the data key used in all_data / _section_urls
# so the frontend can look up docs URLs for the standard tabs too.
_LEGACY_SLUG_TO_DATA_KEY: dict = {
    "changes-in-cli":                "changes_cli",
    "changes-in-default-behavior":   "changes_default",
    "changes-in-table-size":         "changes_tablesize",
    "new-features-and-enhancements": "new_features",
    "new-features-or-enhancements":  "new_features",
    "special-notices":               "special_notices",
    "known-issues":                  "known_issues",
}

# Slugs (substring match) that contain Bug-ID tables like Known Issues
_ISSUES_SLUGS = {"resolved-issues", "resolved-issue"}

# ── Release-notes index URL (redirects to Introduction for any version) ────
def _index_url(version: str) -> str:
    return f"{FORTINET_BASE}/document/fortigate/{version}/fortios-release-notes"


# ── 1. TOC discovery ──────────────────────────────────────────────────────

def discover_toc(session, version: str) -> dict:
    """
    Fetch the release notes sidebar for *version* and return every section as:
        {normalised_slug: {"page_id": str, "slug": str, "title": str, "url": str}}

    We use a regex search over the raw HTML because the sidebar is often
    rendered server-side inside <script> JSON or <a href=…> tags.
    """
    url = _index_url(version)
    try:
        resp = session.get(url, timeout=30)
    except Exception:
        return {}

    # Pattern: /document/fortigate/{version}/fortios-release-notes/{page_id}/{slug}
    pattern = re.compile(
        r"/document/fortigate/"
        + re.escape(version)
        + r"/fortios-release-notes/(\d+)/([a-z0-9][a-z0-9\-]*)"
    )

    toc: dict = {}
    for page_id, slug in pattern.findall(resp.text):
        if slug in toc:
            continue  # keep first occurrence
        toc[slug] = {
            "page_id": page_id,
            "slug": slug,
            "title": slug.replace("-", " ").title(),
            "url": (
                f"{FORTINET_BASE}/document/fortigate/{version}"
                f"/fortios-release-notes/{page_id}/{slug}"
            ),
        }

    # Try to enrich titles from link text in the parsed HTML
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            m = pattern.search(href)
            if m:
                slug = m.group(2)
                if slug in toc:
                    t = a.get_text(strip=True)
                    if t:
                        toc[slug]["title"] = t
    except Exception:
        pass

    return toc


# ── 2. Rich prose scraper ─────────────────────────────────────────────────

def scrape_rich_section(session, url: str, expected_title: str = None) -> dict:
    """
    Scrape a mixed prose/table page into structured blocks.

    Returns:
        {
          "title":  str,          # actual page <h1>
          "blocks": [             # ordered list of content blocks
            {"type": "heading",   "level": int, "text": str},
            {"type": "paragraph", "text": str},
            {"type": "list",      "items": [str, ...]},
            {"type": "table",     "headers": [str], "rows": [[str, ...], ...]},
          ]
        }

    Returns None if the title check fails (Fortinet redirected to default page).
    """
    try:
        from bs4 import BeautifulSoup
        resp = session.get(url, timeout=30)
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None

    # Title verification
    h1_el = soup.find("h1")
    h1_text = h1_el.get_text(strip=True) if h1_el else ""
    if expected_title and not h1_text.lower().__contains__(expected_title.lower()):
        return None

    content = soup.select_one(".document-content") or soup.body
    if not content:
        return None

    blocks = []
    _seen_texts: set = set()

    def _push(block: dict):
        # Deduplicate consecutive identical text blocks
        key = block.get("text") or str(block.get("items")) or str(block.get("headers"))
        if key and key in _seen_texts:
            return
        if key:
            _seen_texts.add(key)
        blocks.append(block)

    for el in content.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "pre"], recursive=True
    ):
        tag = el.name

        if tag == "h1":
            continue  # already captured as title

        # Skip anything nested inside a <table> — captured as cell text when the
        # table block itself is processed; emitting it again causes duplicate text.
        if tag in ("h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "pre") and el.find_parent("table"):
            continue

        # Skip nested lists — outer list already collects them via recursive=False li
        if tag in ("ul", "ol") and el.find_parent(["ul", "ol"]):
            continue

        # Skip <p> and <pre> inside <li> — the list handler already captures the
        # full text of each item; processing inner <p>/<pre> again causes duplicates.
        if tag in ("p", "pre") and el.find_parent("li"):
            continue

        if tag in ("h2", "h3", "h4", "h5", "h6"):
            text = clean_text(el.get_text())
            if text:
                _push({"type": "heading", "level": int(tag[1]), "text": text})

        elif tag == "pre":
            # Preserve internal newlines — clean_text() would collapse them.
            # Strip each line's trailing whitespace and remove leading/trailing
            # blank lines, but keep the multi-line structure intact.
            raw = el.get_text()
            lines = [ln.rstrip() for ln in raw.splitlines()]
            # Drop leading and trailing blank lines only
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            text = "\n".join(lines)
            if text:
                _push({"type": "code", "text": text})

        elif tag == "p":
            text = clean_text(el.get_text())
            if text and len(text) > 15:
                # Detect paragraphs that are predominantly bold.
                # Use ≥ 80% coverage to handle a trailing colon or space
                # that sits outside the <strong> tag.
                strong_text = clean_text(
                    "".join(s.get_text() for s in el.find_all(["strong", "b"]))
                )
                block: dict = {"type": "paragraph", "text": text}
                if strong_text and len(strong_text) >= len(text) * 0.8:
                    block["bold"] = True
                _push(block)

        elif tag in ("ul", "ol"):
            # Only direct <li> children to avoid double-counting nested lists
            items = [
                clean_text(li.get_text())
                for li in el.find_all("li", recursive=False)
                if clean_text(li.get_text())
            ]
            if items:
                _push({"type": "list", "items": items})

        elif tag == "table":
            # Extract headers from <th> or first <tr> of <thead>
            headers = []
            thead = el.find("thead")
            if thead:
                headers = [clean_text(th.get_text()) for th in thead.find_all(["th", "td"])]
            if not headers:
                first_row = el.find("tr")
                if first_row:
                    ths = first_row.find_all("th")
                    headers = [clean_text(th.get_text()) for th in ths] if ths else []

            rows = []
            tbody = el.find("tbody") or el
            for tr in tbody.find_all("tr"):
                cells = [clean_text(td.get_text()) for td in tr.find_all("td")]
                if any(cells):
                    rows.append(cells)

            if rows:
                _push({"type": "table", "headers": headers, "rows": rows})

    return {"title": h1_text, "blocks": blocks}


# ── 3. Issues-style scraper (Resolved Issues, etc.) ──────────────────────

def scrape_issues_section(session, url: str, expected_title: str = None) -> list:
    """
    Same format as known_issues: list of {category, Bug ID, Description}.
    Returns [] on title mismatch (Fortinet redirect).
    """
    try:
        from bs4 import BeautifulSoup
        resp = session.get(url, timeout=30)
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return []

    h1_el = soup.find("h1")
    h1_text = (h1_el.get_text(strip=True) if h1_el else "").lower()
    if expected_title and expected_title.lower() not in h1_text:
        return []

    content = soup.select_one(".document-content") or soup.body

    # Build a regex to skip any heading that IS the page title
    # (mirrors how scrape_known_issues filters out "known issues" headings)
    title_re = re.compile(re.escape(h1_text.strip()), re.I) if h1_text else None

    items, seen, cat = [], set(), "General"
    for el in content.find_all(["h2", "h3", "h4", "h5", "table"]):
        if el.name in ("h2", "h3", "h4", "h5"):
            t = el.get_text(strip=True)
            if t and len(t) < 120 and (title_re is None or not title_re.search(t)):
                cat = t
        elif el.name == "table":
            for row in el.select("tr"):
                cells = row.select("td")
                if len(cells) >= 2:
                    bug_id = cells[0].get_text(strip=True)
                    desc = cells[1].get_text(strip=True)
                    if bug_id and desc and len(desc) > 5 and bug_id not in seen:
                        seen.add(bug_id)
                        items.append({
                            "category": cat,
                            "Bug ID": bug_id,
                            "Description": clean_text(desc),
                        })
    return items


# ── 4. Single-version extended scrape ────────────────────────────────────

def scrape_version_full(session, version: str, toc: dict) -> dict:
    """
    Scrape every section in *toc* that is not already handled by the legacy
    pipeline.  Returns {slug: data} where data is either:
      - list of issue dicts  (for issues-style sections)
      - rich-section dict    (for everything else)

    Also stores a special "_section_urls" key mapping each scraped slug to its
    source URL so the frontend can link directly to each section.
    """
    result: dict = {}
    section_urls: dict = {}

    for slug, info in toc.items():
        if slug in _LEGACY_SLUGS:
            # Still record the URL so the frontend can show "View in Docs"
            data_key = _LEGACY_SLUG_TO_DATA_KEY.get(slug)
            if data_key:
                section_urls[data_key] = info["url"]
            continue

        url = info["url"]
        title = info["title"]
        section_urls[slug] = url

        # Choose scraper based on slug
        if any(s in slug for s in _ISSUES_SLUGS):
            data = scrape_issues_section(session, url, title)
        else:
            data = scrape_rich_section(session, url, title)

        if data:  # None / empty list → page didn't exist for this version
            result[slug] = data

    if section_urls:
        result["_section_urls"] = section_urls

    return result


# ── 5. Parallel orchestration ─────────────────────────────────────────────

def scrape_all_extended(session, versions: list, all_data: dict) -> dict:
    """
    Discover the TOC for *each* version individually (in parallel), then scrape
    every non-legacy section for each version using its own URLs and page IDs.

    Each Fortinet version has its own page IDs inside release-notes URLs, so
    reusing one version's TOC for a different version fetches the wrong page.

    Results are merged directly into *all_data* (in-place) and also returned.
    """
    if not versions:
        return all_data

    print(f"\n  Discovering TOC for {len(versions)} version(s) (parallel)...")

    # ── Step 1: Discover each version's own TOC in parallel ─────────────────
    version_tocs: dict = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        toc_futures = {
            executor.submit(discover_toc, session, ver): ver
            for ver in versions
        }
        for future in as_completed(toc_futures):
            ver = toc_futures[future]
            try:
                toc = future.result()
                version_tocs[ver] = toc
                ext = [s for s in toc if s not in _LEGACY_SLUGS]
                print(f"    v{ver}: {len(ext)} extended slug(s)")
            except Exception as e:
                print(f"    v{ver}: TOC discovery failed — {e}")
                version_tocs[ver] = {}

    all_extended = {s for t in version_tocs.values() for s in t if s not in _LEGACY_SLUGS}
    if not all_extended:
        print("  No additional sections found.")
        return all_data

    print(f"  Unique extended sections: {', '.join(sorted(all_extended))}")
    print(f"\n  Scraping extended sections for {len(versions)} version(s) (parallel)...")

    # ── Step 2: Scrape each version with its own TOC ─────────────────────────
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(scrape_version_full, session, ver, version_tocs[ver]): ver
            for ver in versions
        }
        for future in as_completed(futures):
            ver = futures[future]
            try:
                extended = future.result()
                all_data.setdefault(ver, {}).update(extended)
                section_counts = {k: (len(v) if isinstance(v, list) else len(v.get("blocks", [])))
                                  for k, v in extended.items()}
                print(f"    v{ver}: {len(extended)} sections — "
                      + ", ".join(f"{k}={n}" for k, n in section_counts.items()))
            except Exception as e:
                print(f"    Error scraping extended sections for v{ver}: {e}")

    return all_data
