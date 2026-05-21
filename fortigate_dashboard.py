#!/usr/bin/env python3
"""
FortiGate Upgrade Dashboard Generator
======================================
Scrapes Fortinet release notes and builds a fully interactive HTML dashboard.

Usage:
    python fortigate_dashboard.py <from_version> <to_version> [options]

Examples:
    python fortigate_dashboard.py 7.2.8 7.4.11
    python fortigate_dashboard.py 7.4.5 7.4.11 --output dashboard.html
    python fortigate_dashboard.py 7.2.8 7.4.11 --selenium --grid http://10.0.10.221:4444
    python fortigate_dashboard.py 7.2.8 7.4.11 --save-data ./data/
    python fortigate_dashboard.py 7.2.8 7.4.11 --load-data ./data/scraped.json
"""

import sys
import json
import argparse
import re
from pathlib import Path

from fgt_upgrade.constants import DEFAULT_PRIORITY_CATEGORIES
from fgt_upgrade.utils import parse_version
from fgt_upgrade.report import generate_html
from fgt_upgrade.scraper_requests import (
    REQUESTS_AVAILABLE,
    make_session,
    discover_versions as discover_versions_requests,
    scrape_all as scrape_all_requests,
    scrape_target_extras as scrape_target_extras_requests,
)

try:
    from fgt_upgrade.scraper_selenium import (
        SELENIUM_AVAILABLE,
        setup_driver,
        discover_versions as discover_versions_selenium,
        scrape_all as scrape_all_selenium,
        scrape_target_extras as scrape_target_extras_selenium,
    )
except ImportError:
    SELENIUM_AVAILABLE = False
    setup_driver = discover_versions_selenium = scrape_all_selenium = scrape_target_extras_selenium = None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an interactive FortiGate upgrade dashboard from Fortinet release notes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fortigate_dashboard.py 7.2.8 7.4.11
  python fortigate_dashboard.py 7.4.5 7.4.11 --output my_dashboard.html
  python fortigate_dashboard.py 7.2.8 7.4.11 --save-data ./data/
  python fortigate_dashboard.py 7.2.8 7.4.11 --load-data ./data/scraped.json
  python fortigate_dashboard.py 7.2.8 7.4.11 --selenium --grid http://10.0.10.221:4444
        """
    )
    parser.add_argument("from_version", help="Starting version (exclusive), e.g. 7.2.8")
    parser.add_argument("to_version",   help="Target version (inclusive), e.g. 7.4.11")
    parser.add_argument("--output", "-o", default=None,
                        help="Output HTML file path (default: output/fortigate_<from>_to_<to>.html)")
    parser.add_argument("--selenium", action="store_true",
                        help="Use Selenium/Chrome instead of requests (requires Chrome + ChromeDriver)")
    parser.add_argument("--grid", default="http://10.0.10.221:4444",
                        help="Selenium Grid URL (Selenium mode only, default: http://10.0.10.221:4444)")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode (Selenium mode only)")
    parser.add_argument("--save-data", metavar="DIR",
                        help="Directory to save raw scraped JSON for later reuse")
    parser.add_argument("--load-data", metavar="FILE",
                        help="Skip scraping and load a previously saved JSON file")
    args = parser.parse_args()

    # Validate version format
    ver_re = re.compile(r"^\d+\.\d+\.\d+$")
    for v in [args.from_version, args.to_version]:
        if not ver_re.match(v):
            parser.error(f"Invalid version format: '{v}'. Expected X.Y.Z (e.g. 7.2.8)")
    if parse_version(args.from_version) >= parse_version(args.to_version):
        parser.error("from_version must be strictly less than to_version")

    default_name = f"fortigate_{args.from_version}_to_{args.to_version}.html"
    output_path = args.output or str(Path("output") / default_name)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═'*60}")
    print(f"  FortiGate Upgrade Dashboard Generator")
    print(f"  From : {args.from_version}  (exclusive)")
    print(f"  To   : {args.to_version}  (inclusive)")
    print(f"  Output: {output_path}")
    print(f"{'═'*60}\n")

    # ── LOAD MODE: skip scraping entirely ─────────────────────────
    if args.load_data:
        print(f"Loading saved data from {args.load_data}...")
        with open(args.load_data, "r") as f:
            saved = json.load(f)
        versions        = saved["versions"]
        all_data        = saved["all_data"]
        special_notices = saved.get("special_notices", [])
        # Backwards compat: migrate old flat known_issues key into all_data[to_ver]
        if "known_issues" in saved and not any("known_issues" in all_data.get(v, {}) for v in versions):
            all_data.setdefault(args.to_version, {})["known_issues"] = saved["known_issues"]
        ki_count = len(all_data.get(args.to_version, {}).get("known_issues", []))
        print(f"Loaded {len(versions)} versions, {ki_count} known issues (target version).")

    # ── SELENIUM MODE ──────────────────────────────────────────────
    elif args.selenium:
        if not SELENIUM_AVAILABLE:
            print("ERROR: --selenium requires the 'selenium' package. Install with:")
            print("  pip install selenium")
            return 1
        driver = setup_driver(grid_url=args.grid, headless=args.headless)
        try:
            print("Step 1/4: Discovering versions...")
            versions = discover_versions_selenium(driver, args.from_version, args.to_version)
            if not versions:
                print("ERROR: No versions found in range. Check version numbers and connectivity.")
                return 1

            print(f"\nStep 2/4: Scraping release note sections for {len(versions)} versions...")
            all_data = scrape_all_selenium(driver, versions, args.to_version)

            print(f"\nStep 3/4: Scraping target-version extras ({args.to_version})...")
            special_notices = scrape_target_extras_selenium(driver, args.to_version)

        finally:
            driver.quit()
            print("\nBrowser closed.")

    # ── REQUESTS MODE (default) ────────────────────────────────────
    else:
        if not REQUESTS_AVAILABLE:
            print("ERROR: requests mode requires 'requests' and 'beautifulsoup4'. Install with:")
            print("  pip install requests beautifulsoup4")
            return 1
        session = make_session()
        print("Step 1/4: Discovering versions...")
        versions = discover_versions_requests(session, args.from_version, args.to_version)
        if not versions:
            print("ERROR: No versions found in range. Check version numbers and connectivity.")
            return 1

        print(f"\nStep 2/4: Scraping release note sections for {len(versions)} versions...")
        all_data = scrape_all_requests(session, versions, args.to_version)

        print(f"\nStep 3/4: Scraping target-version extras ({args.to_version})...")
        special_notices = scrape_target_extras_requests(session, args.to_version)

    # ── SAVE RAW DATA (optional, works for both scraping modes) ────
    if not args.load_data and args.save_data:
        save_dir = Path(args.save_data)
        save_dir.mkdir(parents=True, exist_ok=True)
        save_file = save_dir / f"scraped_{args.from_version}_to_{args.to_version}.json"
        with open(save_file, "w", encoding="utf-8") as f:
            json.dump({
                "from_version": args.from_version,
                "to_version": args.to_version,
                "versions": versions,
                "all_data": all_data,
                "special_notices": special_notices,
            }, f, ensure_ascii=False, indent=2)
        print(f"\nRaw data saved to: {save_file}")

    # ── GENERATE HTML ──────────────────────────────────────────────
    print(f"\nStep 4/4: Generating dashboard HTML...")
    html = generate_html(
        all_data=all_data,
        special_notices=special_notices,
        from_ver=args.from_version,
        to_ver=args.to_version,
        priority_categories=DEFAULT_PRIORITY_CATEGORIES,
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # ── SUMMARY ────────────────────────────────────────────────────
    total_cli  = sum(len(all_data[v].get("changes_cli", []))       for v in versions)
    total_def  = sum(len(all_data[v].get("changes_default", []))   for v in versions)
    total_ts   = sum(len(all_data[v].get("changes_tablesize", [])) for v in versions)
    total_feat = sum(len(all_data[v].get("new_features", []))      for v in versions)
    total_ki   = sum(len(all_data[v].get("known_issues", []))      for v in versions)

    print(f"\n{'═'*60}")
    print(f"  ✓ Dashboard saved to: {output_path}")
    print(f"  Versions        : {len(versions)}")
    print(f"  CLI changes     : {total_cli}")
    print(f"  Default behavior: {total_def}")
    print(f"  Table size      : {total_ts}")
    print(f"  New features    : {total_feat}")
    print(f"  Known issues    : {total_ki} (across all versions)")
    print(f"  Special notices : {len(special_notices)}")
    print(f"{'═'*60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
