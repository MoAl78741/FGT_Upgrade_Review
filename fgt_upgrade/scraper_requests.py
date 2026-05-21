"""
Requests-mode scraper (default) — no browser required.

Uses requests + BeautifulSoup with a ThreadPoolExecutor for parallel fetches.
All public scrape functions mirror the interface of the Selenium equivalents
so main() can call either without special-casing beyond the initial branch.
"""

import re
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests as req_lib
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .constants import PAGE_IDS, MODEL_CATEGORIES
from .utils import build_url, parse_version, version_in_range, deduplicate


# ── SESSION ──────────────────────────────────────────────────────────────────

def make_session() -> "req_lib.Session":
    session = req_lib.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; FortiGateDashboard/1.0)"})
    return session


# ── INTERNAL HELPERS ─────────────────────────────────────────────────────────

def _soup_content(soup):
    """Return .document-content if present, else body."""
    return soup.select_one(".document-content") or soup.body


def _check_title(soup, expected_title):
    """Return False if expected_title is set but the page <h1> doesn't contain it."""
    if not expected_title:
        return True
    h1 = soup.find("h1")
    return h1 and expected_title.lower() in h1.get_text().lower()


# ── VERSION DISCOVERY ─────────────────────────────────────────────────────────

def discover_versions(session, from_ver: str, to_ver: str) -> list:
    """Fetch the target version's known-issues page and regex-scan for version strings."""
    url = build_url(to_ver, "known_issues")
    print(f"  Loading: {url}")
    resp = session.get(url, timeout=30)
    all_found = list(set(re.findall(r'\b(\d+\.\d+\.\d+)\b', resp.text)))
    valid = [v for v in all_found if re.match(r'^\d+\.\d+\.\d+$', v)]
    in_range = sorted([v for v in valid if version_in_range(v, from_ver, to_ver)], key=parse_version)
    if to_ver not in in_range:
        in_range.append(to_ver)
        in_range.sort(key=parse_version)
    print(f"  Found {len(in_range)} versions: {in_range}")
    return in_range


# ── SECTION SCRAPERS ─────────────────────────────────────────────────────────

def scrape_table(session, url: str, expected_title: str = None) -> list:
    """Scrape a two-column table page (CLI / Default Behavior / Table Size)."""
    soup = BeautifulSoup(session.get(url, timeout=30).text, "html.parser")
    if not _check_title(soup, expected_title):
        return []
    content = _soup_content(soup)
    items, seen = [], set()
    for row in content.select("table tr"):
        cells = row.select("td")
        if len(cells) >= 2:
            id_ = cells[0].get_text(strip=True)
            desc = cells[1].get_text(strip=True)
            if id_ and desc and len(desc) > 5 and id_ not in seen:
                seen.add(id_)
                items.append({"Bug ID": id_, "Description": desc[:600]})
    return items


def scrape_features(session, url: str, expected_title: str = None) -> list:
    """Scrape new-features pages, tracking category headings."""
    soup = BeautifulSoup(session.get(url, timeout=30).text, "html.parser")
    if not _check_title(soup, expected_title):
        return []
    content = _soup_content(soup)
    items, seen, cat = [], set(), "General"
    for el in content.find_all(["h2", "h3", "h4", "table"]):
        if el.name in ("h2", "h3", "h4"):
            t = el.get_text(strip=True)
            if t and len(t) < 120 and not re.search(r"new features|table of contents", t, re.I):
                cat = t
        elif el.name == "table":
            for row in el.select("tr"):
                cells = row.select("td")
                if len(cells) >= 2:
                    fid = cells[0].get_text(strip=True)
                    desc = cells[1].get_text(strip=True)
                    if fid and desc and len(desc) > 5 and fid not in seen:
                        seen.add(fid)
                        items.append({"category": cat, "Feature ID": fid, "Description": desc[:600]})
    return items


def scrape_known_issues(session, url: str, expected_title: str = None) -> list:
    """Scrape known-issues pages, tracking category headings."""
    soup = BeautifulSoup(session.get(url, timeout=30).text, "html.parser")
    if not _check_title(soup, expected_title):
        return []
    content = _soup_content(soup)
    items, seen, cat = [], set(), "General"
    for el in content.find_all(["h2", "h3", "h4", "table"]):
        if el.name in ("h2", "h3", "h4"):
            t = el.get_text(strip=True)
            if t and len(t) < 120 and not re.search(r"known issues", t, re.I):
                cat = t
        elif el.name == "table":
            for row in el.select("tr"):
                cells = row.select("td")
                if len(cells) >= 2:
                    bug_id = cells[0].get_text(strip=True)
                    desc = cells[1].get_text(strip=True)
                    if bug_id and desc and len(desc) > 5 and bug_id not in seen:
                        seen.add(bug_id)
                        items.append({"category": cat, "Bug ID": bug_id, "Description": desc[:600]})
    return items


def scrape_special_notices(session, url: str) -> list:
    """
    Scrape the special-notices page.

    Handles two layouts:
    - Sub-page links: follows each link and extracts heading + body text.
    - Inline: parses h2/h3/h4 headings and paragraph text directly.
    """
    soup = BeautifulSoup(session.get(url, timeout=30).text, "html.parser")
    content = _soup_content(soup)
    links = []
    for a in content.select("a[href]"):
        abs_href = urljoin(url, a.get("href", ""))
        if ("fortios-release-notes" in abs_href
                and abs_href.startswith("https://docs.fortinet.com")
                and not abs_href.startswith(url)):
            links.append(abs_href)

    notices = []
    if links:
        for link in links:
            sub = BeautifulSoup(session.get(link, timeout=30).text, "html.parser")
            heading = (sub.find("h1") or sub.find("h2") or sub.new_tag("x")).get_text(strip=True) or "Notice"
            sub_content = _soup_content(sub)
            body = " ".join(
                el.get_text(strip=True) for el in sub_content.select("p,li")
                if len(el.get_text(strip=True)) > 20
            )[:800]
            if body:
                notices.append({"title": heading, "content": body})
    else:
        title, body = "", []
        for el in content.find_all(["h2", "h3", "h4", "p", "ul"]):
            if el.name in ("h2", "h3", "h4"):
                if title and body:
                    notices.append({"title": title, "content": " ".join(body)[:800]})
                title, body = el.get_text(strip=True), []
            else:
                t = el.get_text(strip=True)
                if len(t) > 10:
                    body.append(t)
        if title and body:
            notices.append({"title": title, "content": " ".join(body)[:800]})
    return notices


# ── ORCHESTRATION ─────────────────────────────────────────────────────────────

def _scrape_section_parallel(session, versions: list, section_key: str, scrape_fn, label: str) -> dict:
    """Fan out a scrape function over all versions in parallel (10 workers)."""
    entry = PAGE_IDS[section_key]
    expected_title = entry[2] if len(entry) > 2 else None
    print(f"\n  Scraping {label}...")
    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(scrape_fn, session, build_url(v, section_key), expected_title): v
            for v in versions
        }
        for future in as_completed(futures):
            v = futures[future]
            try:
                results[v] = future.result()
            except Exception as e:
                print(f"    Error scraping {v}: {e}")
                results[v] = []
    return results


def scrape_all(session, versions: list, to_ver: str) -> dict:
    """
    Scrape all sections (CLI, Default, Table Size, Features, Known Issues)
    for every version in parallel.  Returns all_data keyed by version.
    """
    all_data = {v: {} for v in versions}

    for section_key, scrape_fn, label in [
        ("changes_cli",       scrape_table,        "CLI changes"),
        ("changes_default",   scrape_table,        "Default behavior changes"),
        ("changes_tablesize", scrape_table,        "Table size changes"),
    ]:
        results = _scrape_section_parallel(session, versions, section_key, scrape_fn, label)
        for v, items in results.items():
            all_data[v][section_key] = deduplicate(items, "Bug ID")

    feat_results = _scrape_section_parallel(session, versions, "new_features", scrape_features, "New features")
    for v, items in feat_results.items():
        filtered = [i for i in items if i.get("category") not in MODEL_CATEGORIES]
        all_data[v]["new_features"] = deduplicate(filtered, "Feature ID")

    ki_results = _scrape_section_parallel(session, versions, "known_issues", scrape_known_issues, "Known issues")
    for v, items in ki_results.items():
        all_data[v]["known_issues"] = deduplicate(items, "Bug ID")

    return all_data


def scrape_target_extras(session, to_ver: str) -> list:
    """Scrape special notices for the target version only."""
    print(f"\n  Scraping special notices for {to_ver}...")
    notices = scrape_special_notices(session, build_url(to_ver, "special_notices"))
    print(f"    {len(notices)} notices found")
    return notices
