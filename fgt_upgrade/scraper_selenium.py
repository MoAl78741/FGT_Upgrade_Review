"""
Selenium-mode scraper (opt-in via --selenium flag).

Launches Chrome via WebDriver, injects browser-side JS helpers (window._fg.*),
then fans out parallel fetch() calls inside the browser for same-origin scraping.

Requires: selenium>=4.0.0, Google Chrome, and a matching ChromeDriver (or Grid).
"""

import json
import time
import re

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from .constants import PAGE_IDS, FORTINET_BASE, MODEL_CATEGORIES, BATCH_SIZE, LOAD_WAIT
from .utils import build_url, parse_version, version_in_range, deduplicate


# ── DRIVER SETUP ──────────────────────────────────────────────────────────────

def setup_driver(grid_url: str = "http://10.0.10.221:4444", headless: bool = False):
    """
    Configure Chrome WebDriver.
    Tries Selenium Grid first; falls back to a locally installed ChromeDriver.
    """
    options = Options()
    options.page_load_strategy = "eager"
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,900")

    try:
        print(f"  Connecting to Selenium Grid at {grid_url}...")
        driver = webdriver.Remote(grid_url, options=options)
        print("  ✓ Connected to Selenium Grid")
    except Exception as e:
        print(f"  Grid unavailable ({e.__class__.__name__}), falling back to local ChromeDriver")
        driver = webdriver.Chrome(options=options)
        print("  ✓ Local ChromeDriver started")

    driver.set_page_load_timeout(60)
    driver.set_script_timeout(120)
    return driver


# ── JAVASCRIPT HELPERS (injected once, reused for all fetches) ────────────────

# This block is injected into the browser page via execute_script.
# All backslash sequences are JavaScript regex/escape syntax, not Python escapes.
SCRAPING_HELPERS_JS = """
window._fg = window._fg || {};

window._fg.fetchHTML = async function(url) {
    const resp = await fetch(url);
    const html = await resp.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    return doc.querySelector('.document-content') || doc.body;
};

// Scrape a table-based section (CLI, Default Behavior, Table Size).
// expectedTitle (optional): if provided, the page <h1> must contain this string
// (case-insensitive substring match).  Returns [] when the title doesn't match —
// this catches Fortinet's redirect-to-default when a section doesn't exist for a
// given firmware version.
window._fg.scrapeTable = async function(url, expectedTitle) {
    const resp = await fetch(url);
    const html = await resp.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    // Title verification — check BEFORE diving into the content div
    if (expectedTitle) {
        const h1 = (doc.querySelector('h1') || {}).textContent || '';
        if (!h1.toLowerCase().includes(expectedTitle.toLowerCase())) {
            return [];  // Wrong page (likely redirected to Introduction / default)
        }
    }

    const content = doc.querySelector('.document-content') || doc.body;
    const items = [];
    const seen = new Set();
    content.querySelectorAll('table tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 2) {
            const id   = cells[0].textContent.trim();
            const desc = cells[1].textContent.trim();
            if (id && desc && desc.length > 5 && !seen.has(id)) {
                seen.add(id);
                items.push({'Bug ID': id, Description: desc.substring(0, 600)});
            }
        }
    });
    return items;
};

// Scrape new features WITH category headings.
// expectedTitle (optional): page <h1> must contain this string — returns [] on mismatch.
window._fg.scrapeFeatures = async function(url, expectedTitle) {
    const MODEL_CATS = new Set([
        'Supported models','Special branch supported models','FortiGate 6000 and 7000 support'
    ]);
    const resp = await fetch(url);
    const html = await resp.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    // Title verification
    if (expectedTitle) {
        const h1 = (doc.querySelector('h1') || {}).textContent || '';
        if (!h1.toLowerCase().includes(expectedTitle.toLowerCase())) {
            return [];  // Wrong page (likely redirected to Introduction / default)
        }
    }

    const content = doc.querySelector('.document-content') || doc.body;
    const items = [];
    const seen = new Set();
    let cat = 'General';
    content.querySelectorAll('h2,h3,h4,table').forEach(el => {
        if (/^H[234]$/.test(el.tagName)) {
            const t = el.textContent.trim();
            if (t && t.length < 120 && !/^(New features|Table of Contents)/i.test(t)) cat = t;
        } else if (el.tagName === 'TABLE' && !MODEL_CATS.has(cat)) {
            el.querySelectorAll('tr').forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 2) {
                    const fid  = cells[0].textContent.trim();
                    const desc = cells[1].textContent.trim();
                    if (fid && desc && desc.length > 5 && !seen.has(fid)) {
                        seen.add(fid);
                        items.push({category: cat, 'Feature ID': fid, Description: desc.substring(0, 600)});
                    }
                }
            });
        }
    });
    return items;
};

// Scrape known issues with category headings
window._fg.scrapeKnownIssues = async function(url, expectedTitle) {
    const resp = await fetch(url);
    const html = await resp.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    if (expectedTitle) {
        const h1 = (doc.querySelector('h1') || {}).textContent || '';
        if (!h1.toLowerCase().includes(expectedTitle.toLowerCase())) {
            return [];  // Wrong page (redirected to default — section absent for this version)
        }
    }
    const content = doc.querySelector('.document-content') || doc.body;
    const items = [];
    const seen = new Set();
    let cat = 'General';
    content.querySelectorAll('h2,h3,h4,table').forEach(el => {
        if (/^H[234]$/.test(el.tagName)) {
            const t = el.textContent.trim();
            if (t && t.length < 120 && !/known issues/i.test(t)) cat = t;
        } else if (el.tagName === 'TABLE') {
            el.querySelectorAll('tr').forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 2) {
                    const bugId = cells[0].textContent.trim();
                    const desc  = cells[1].textContent.trim();
                    if (bugId && desc && desc.length > 5 && !seen.has(bugId)) {
                        seen.add(bugId);
                        items.push({category: cat, 'Bug ID': bugId, Description: desc.substring(0, 600)});
                    }
                }
            });
        }
    });
    return items;
};

// Scrape special notices — handles both inline and sub-page link formats
window._fg.scrapeSpecialNotices = async function(mainUrl) {
    const content = await window._fg.fetchHTML(mainUrl);
    const links = [...content.querySelectorAll('a[href]')]
        .map(a => a.href)
        .filter(h => !h.startsWith(mainUrl) && /fortios-release-notes/.test(h) && h.startsWith('https://docs.fortinet.com'));

    const notices = [];

    if (links.length > 0) {
        const subPages = await Promise.all(links.map(u => window._fg.fetchHTML(u)));
        subPages.forEach((sub, i) => {
            const heading = sub.querySelector('h1,h2')?.textContent?.trim() || 'Notice ' + (i+1);
            const body = [...sub.querySelectorAll('p,li')]
                .map(el => el.textContent.trim()).filter(t => t.length > 20)
                .join(' ').substring(0, 800);
            if (body) notices.push({title: heading, content: body});
        });
    } else {
        let title = '', body = [];
        content.querySelectorAll('h2,h3,h4,p,ul').forEach(el => {
            if (/^H[234]$/.test(el.tagName)) {
                if (title && body.length) notices.push({title, content: body.join(' ').substring(0, 800)});
                title = el.textContent.trim(); body = [];
            } else {
                const t = el.textContent.trim();
                if (t.length > 10) body.push(t);
            }
        });
        if (title && body.length) notices.push({title, content: body.join(' ').substring(0, 800)});
    }
    return notices;
};

// Sentinel — must be the final statement so Chrome's execute_script returns it
window._fg._loaded = true;
return 'helpers_loaded';
"""


def inject_helpers(driver):
    """
    Inject the _fg helper functions into the current page.

    Chrome's execute_script only returns a value when the script contains an
    explicit `return` statement (unlike Firefox which returns the last
    expression).  We also set window._fg._loaded as a belt-and-suspenders
    sentinel that we can verify independently.
    """
    for _ in range(10):
        ready = driver.execute_script("return document.readyState;")
        if ready in ("complete", "interactive"):
            break
        time.sleep(1)

    for attempt in range(5):
        result = driver.execute_script(SCRAPING_HELPERS_JS)
        if result == "helpers_loaded":
            return
        sentinel = driver.execute_script("return !!(window._fg && window._fg._loaded);")
        if sentinel:
            return
        print(f"    Helper injection attempt {attempt + 1} returned {result!r}, retrying...")
        time.sleep(2)
    raise AssertionError(
        f"Helper injection failed after 5 attempts. "
        f"Last execute_script return: {result!r}. "
        f"window._fg present: {driver.execute_script('return typeof window._fg')}"
    )


# ── VERSION DISCOVERY ─────────────────────────────────────────────────────────

def discover_versions(driver, from_ver: str, to_ver: str) -> list:
    """
    Navigate to the Fortinet docs page for to_ver and extract all versions
    that fall between from_ver (exclusive) and to_ver (inclusive).
    Uses four JS extraction strategies plus a page-source regex fallback.
    """
    start_url = build_url(to_ver, "known_issues")
    print(f"  Loading: {start_url}")
    driver.get(start_url)
    time.sleep(LOAD_WAIT)

    js = """
    const results = new Set();

    // Strategy 1: <select> elements with semver-looking options
    document.querySelectorAll('select').forEach(sel => {
        [...sel.options].forEach(opt => {
            const v = (opt.value || opt.textContent).trim();
            if (/^\\d+\\.\\d+\\.\\d+$/.test(v)) results.add(v);
        });
    });

    // Strategy 2: version links in page nav / sidebar
    document.querySelectorAll('a[href*="/document/fortigate/"]').forEach(a => {
        const m = a.href.match(/\\/fortigate\\/(\\d+\\.\\d+\\.\\d+)\\//);
        if (m) results.add(m[1]);
    });

    // Strategy 3: button / list-item text matching version pattern
    document.querySelectorAll('button, li, span').forEach(el => {
        const t = el.textContent.trim();
        if (/^\\d+\\.\\d+\\.\\d+$/.test(t)) results.add(t);
    });

    // Strategy 4: data attributes
    document.querySelectorAll('[data-version], [value]').forEach(el => {
        const v = el.dataset.version || el.getAttribute('value') || '';
        if (/^\\d+\\.\\d+\\.\\d+$/.test(v.trim())) results.add(v.trim());
    });

    return JSON.stringify([...results]);
    """

    raw = driver.execute_script(js)
    all_found = json.loads(raw)

    if not all_found:
        print("  JS strategies found nothing — scanning page source...")
        matches = re.findall(r'\b(\d+\.\d+\.\d+)\b', driver.page_source)
        all_found = list(set(matches))

    valid = [v for v in all_found if re.match(r'^\d+\.\d+\.\d+$', v)]
    in_range = [v for v in valid if version_in_range(v, from_ver, to_ver)]
    in_range.sort(key=parse_version)

    if to_ver not in in_range:
        in_range.append(to_ver)
        in_range.sort(key=parse_version)

    print(f"  Found {len(in_range)} versions: {in_range}")
    return in_range


# ── BATCH SCRAPING ────────────────────────────────────────────────────────────

def _scrape_batch(driver, urls_by_version: dict, js_func: str, expected_title: str = None) -> dict:
    """
    Fetch multiple URLs in parallel using browser fetch(), return results keyed by version.
    Uses execute_async_script so Python waits for all Promises to resolve.
    """
    script = """
    const callback = arguments[arguments.length - 1];
    const urlMap = arguments[0];
    const func = arguments[1];
    const expectedTitle = arguments[2] || null;

    (async () => {
        const results = {};
        await Promise.all(Object.entries(urlMap).map(async ([ver, url]) => {
            try {
                results[ver] = await window._fg[func](url, expectedTitle);
            } catch(e) {
                console.error('Scrape error ' + ver + ':', e);
                results[ver] = [];
            }
        }));
        callback(JSON.stringify(results));
    })();
    """
    raw = driver.execute_async_script(script, urls_by_version, js_func, expected_title)
    return json.loads(raw)


def _scrape_section(driver, versions: list, section_key: str, js_func: str, label: str) -> dict:
    """Scrape a section for all versions, processing in BATCH_SIZE chunks."""
    entry = PAGE_IDS[section_key]
    expected_title = entry[2] if len(entry) > 2 else None
    print(f"\n  Scraping {label}...")
    all_results = {}
    for i in range(0, len(versions), BATCH_SIZE):
        batch = versions[i: i + BATCH_SIZE]
        urls = {v: build_url(v, section_key) for v in batch}
        print(f"    Batch {i // BATCH_SIZE + 1}: {batch}")
        results = _scrape_batch(driver, urls, js_func, expected_title)
        all_results.update(results)
    return all_results


# ── ORCHESTRATION ─────────────────────────────────────────────────────────────

def scrape_all(driver, versions: list, target_ver: str) -> dict:
    """
    Scrape all sections for all versions via the browser.
    Loads the base page first so that same-origin fetch() works.
    """
    print(f"\n  Loading base page for same-origin fetch...")
    driver.get(f"{FORTINET_BASE}/document/fortigate/{target_ver}/fortios-release-notes")
    time.sleep(LOAD_WAIT)
    inject_helpers(driver)

    all_data = {v: {} for v in versions}

    for section_key, js_func, label in [
        ("changes_cli",       "scrapeTable",    "CLI changes"),
        ("changes_default",   "scrapeTable",    "Default behavior changes"),
        ("changes_tablesize", "scrapeTable",    "Table size changes"),
    ]:
        results = _scrape_section(driver, versions, section_key, js_func, label)
        for ver, items in results.items():
            all_data[ver][section_key] = deduplicate(items, "Bug ID")

    feat_results = _scrape_section(driver, versions, "new_features", "scrapeFeatures", "New features")
    for ver, items in feat_results.items():
        filtered = [i for i in items if i.get("category") not in MODEL_CATEGORIES]
        all_data[ver]["new_features"] = deduplicate(filtered, "Feature ID")

    ki_results = _scrape_section(driver, versions, "known_issues", "scrapeKnownIssues", "Known issues")
    for ver, items in ki_results.items():
        all_data[ver]["known_issues"] = deduplicate(items, "Bug ID")

    return all_data


def scrape_target_extras(driver, target_ver: str) -> list:
    """Scrape special notices for the target version only."""
    print(f"\n  Scraping special notices for {target_ver}...")
    driver.get(build_url(target_ver, "special_notices"))
    time.sleep(LOAD_WAIT)
    inject_helpers(driver)
    raw_notices = driver.execute_async_script("""
        const callback = arguments[arguments.length - 1];
        (async () => {
            try { callback(JSON.stringify(await window._fg.scrapeSpecialNotices(arguments[0]))); }
            catch(e) { callback(JSON.stringify([])); }
        })();
    """, build_url(target_ver, "special_notices"))
    special_notices = json.loads(raw_notices)
    print(f"    {len(special_notices)} notices found")
    return special_notices
