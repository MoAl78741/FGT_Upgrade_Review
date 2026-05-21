"""
Live integration test for scrape_issues_section() in fgt_upgrade/scraper_full.py.

Hits the real Fortinet docs site — requires internet access.

Run:
    python test_scrape_issues.py                  # tests 7.4.9 (default)
    python test_scrape_issues.py 7.2.8            # test a specific version
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import requests
from fgt_upgrade.scraper_full import discover_toc, scrape_issues_section

VERSION = sys.argv[1] if len(sys.argv) > 1 else "7.4.9"


class TestLiveScrapeIssuesSection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.session = requests.Session()
        cls.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )

        print(f"\n  Discovering TOC for v{VERSION}...")
        toc = discover_toc(cls.session, VERSION)
        print(f"  TOC slugs found: {sorted(toc.keys())}")

        slug_info = toc.get("resolved-issues") or toc.get("resolved-issue")
        if slug_info is None:
            raise unittest.SkipTest(
                f"No 'resolved-issues' slug found in TOC for v{VERSION}. "
                f"Available: {sorted(toc.keys())}"
            )

        cls.url   = slug_info["url"]
        cls.title = slug_info["title"]
        print(f"  Resolved Issues URL: {cls.url}")

        print(f"  Scraping resolved issues...")
        cls.items = scrape_issues_section(cls.session, cls.url, expected_title=None)
        print(f"  Got {len(cls.items)} items")
        cats = sorted(set(i["category"] for i in cls.items))
        print(f"  Categories: {cats}")

    def test_returns_items(self):
        """Should return at least one resolved issue."""
        self.assertGreater(len(self.items), 0, "Expected at least one resolved issue")

    def test_multiple_categories(self):
        """Should have more than one category (e.g. Firewall, System, GUI...)."""
        cats = set(i["category"] for i in self.items)
        self.assertGreater(len(cats), 1,
            f"Expected multiple categories, got: {cats}")

    def test_no_item_has_page_title_as_category(self):
        """'Resolved Issues' (the page title) must never appear as a category."""
        bad = [i for i in self.items if "resolved issues" in i["category"].lower()]
        self.assertEqual(bad, [],
            f"Page title leaked into categories: {[i['category'] for i in bad]}")

    def test_all_items_have_required_fields(self):
        """Every item must have category, Bug ID, and Description."""
        for item in self.items:
            self.assertIn("category",     item)
            self.assertIn("Bug ID",       item)
            self.assertIn("Description",  item)
            self.assertTrue(item["Bug ID"].strip(),       "Empty Bug ID")
            self.assertTrue(item["Description"].strip(),  "Empty Description")

    def test_no_duplicate_bug_ids(self):
        """Bug IDs should be unique."""
        ids = [i["Bug ID"] for i in self.items]
        dupes = [bid for bid in ids if ids.count(bid) > 1]
        self.assertEqual(dupes, [], f"Duplicate Bug IDs found: {set(dupes)}")

    def test_categories_look_real(self):
        """At least one well-known category name should appear."""
        known = {"Firewall", "System", "GUI", "HA", "SSL VPN", "IPsec VPN",
                 "Routing", "SD-WAN", "Web Filter", "Log & Report"}
        found_cats = {i["category"] for i in self.items}
        overlap = known & found_cats
        self.assertGreater(len(overlap), 0,
            f"None of the expected category names found. Got: {found_cats}")


if __name__ == "__main__":
    # Strip the version arg before unittest sees it
    sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if not a[0].isdigit()]
    unittest.main(verbosity=2)
