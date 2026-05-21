"""
HTML parsing tests for fgt_upgrade scraper functions.

Uses pre-canned HTML strings and a mock session — no network required.

Run:
    python -m pytest tests/test_scraper_html.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock
import pytest
from bs4 import BeautifulSoup

from fgt_upgrade.scraper_requests import (
    _soup_content,
    _check_title,
    scrape_table,
    scrape_features,
    scrape_known_issues,
    scrape_special_notices,
)
from fgt_upgrade.scraper_full import scrape_rich_section, scrape_issues_section


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_session(html: str) -> MagicMock:
    """Return a mock requests.Session whose .get() returns the given HTML."""
    session = MagicMock()
    response = MagicMock()
    response.text = html
    session.get.return_value = response
    return session


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ── _soup_content ─────────────────────────────────────────────────────────────

class TestSoupContent:
    def test_returns_document_content_when_present(self):
        soup = _soup('<body><div class="document-content"><p>Main</p></div></body>')
        result = _soup_content(soup)
        assert result is not None
        assert "Main" in result.get_text()

    def test_falls_back_to_body(self):
        soup = _soup("<body><p>Body text</p></body>")
        result = _soup_content(soup)
        assert result.name == "body"

    def test_document_content_preferred_over_body(self):
        html = '<body><p>Outside</p><div class="document-content"><p>Inside</p></div></body>'
        soup = _soup(html)
        result = _soup_content(soup)
        assert "Inside" in result.get_text()
        assert "Outside" not in result.get_text()


# ── _check_title ──────────────────────────────────────────────────────────────

class TestCheckTitle:
    def test_none_expected_always_true(self):
        soup = _soup("<body><h1>Anything</h1></body>")
        assert _check_title(soup, None) is True

    def test_matching_title(self):
        soup = _soup("<body><h1>Known Issues</h1></body>")
        assert _check_title(soup, "Known Issues") is True

    def test_case_insensitive_match(self):
        soup = _soup("<body><h1>KNOWN ISSUES</h1></body>")
        assert _check_title(soup, "known issues") is True

    def test_partial_match(self):
        soup = _soup("<body><h1>Known Issues for FortiOS 7.4</h1></body>")
        assert _check_title(soup, "Known Issues") is True

    def test_no_match(self):
        soup = _soup("<body><h1>New Features</h1></body>")
        assert _check_title(soup, "Known Issues") is False

    def test_no_h1_returns_false(self):
        soup = _soup("<body><p>No heading here</p></body>")
        assert not _check_title(soup, "Known Issues")


# ── scrape_table ──────────────────────────────────────────────────────────────

class TestScrapeTable:
    _HTML = """
    <html><body>
      <h1>Changes in CLI</h1>
      <table>
        <tr><th>Bug ID</th><th>Description</th></tr>
        <tr><td>890776</td><td>New CLI command for interface monitoring</td></tr>
        <tr><td>123456</td><td>Modified output format for diagnose commands</td></tr>
        <tr><td>999999</td><td>ok</td></tr>
      </table>
    </body></html>
    """

    def test_returns_correct_number_of_items(self):
        result = scrape_table(_mock_session(self._HTML), "http://example.com")
        # Row with short desc "ok" should be filtered
        assert len(result) == 2

    def test_bug_id_and_description_fields(self):
        result = scrape_table(_mock_session(self._HTML), "http://example.com")
        assert result[0]["Bug ID"] == "890776"
        assert "interface monitoring" in result[0]["Description"]

    def test_header_row_not_included(self):
        result = scrape_table(_mock_session(self._HTML), "http://example.com")
        ids = [r["Bug ID"] for r in result]
        assert "Bug ID" not in ids

    def test_title_mismatch_returns_empty(self):
        result = scrape_table(_mock_session(self._HTML), "http://example.com", expected_title="Known Issues")
        assert result == []

    def test_title_match_accepted(self):
        result = scrape_table(_mock_session(self._HTML), "http://example.com", expected_title="Changes in CLI")
        assert len(result) == 2

    def test_deduplicates_same_id(self):
        html = """<html><body><h1>X</h1>
        <table>
          <tr><td>111111</td><td>First description entry is fine</td></tr>
          <tr><td>111111</td><td>Duplicate should be dropped here</td></tr>
        </table></body></html>"""
        result = scrape_table(_mock_session(html), "http://example.com")
        assert len(result) == 1


# ── scrape_features ───────────────────────────────────────────────────────────

class TestScrapeFeatures:
    _HTML = """
    <html><body>
      <h1>New Features or Enhancements</h1>
      <h2>Firewall</h2>
      <table>
        <tr><th>Feature ID</th><th>Description</th></tr>
        <tr><td>1234567</td><td>New policy lookup table for improved throughput</td></tr>
      </table>
      <h2>SD-WAN</h2>
      <table>
        <tr><td>7654321</td><td>Health check improvements for SD-WAN members</td></tr>
      </table>
    </body></html>
    """

    def test_category_assigned(self):
        result = scrape_features(_mock_session(self._HTML), "http://example.com")
        firewall_feats = [r for r in result if r["category"] == "Firewall"]
        assert len(firewall_feats) == 1

    def test_second_category_assigned(self):
        result = scrape_features(_mock_session(self._HTML), "http://example.com")
        sdwan_feats = [r for r in result if r["category"] == "SD-WAN"]
        assert len(sdwan_feats) == 1

    def test_feature_id_field(self):
        result = scrape_features(_mock_session(self._HTML), "http://example.com")
        assert result[0]["Feature ID"] == "1234567"

    def test_page_heading_not_a_category(self):
        # The "New Features" page heading itself is never assigned as a category
        result = scrape_features(_mock_session(self._HTML), "http://example.com")
        categories = [r["category"] for r in result]
        assert "New Features or Enhancements" not in categories

    def test_title_mismatch_returns_empty(self):
        result = scrape_features(_mock_session(self._HTML), "http://example.com", expected_title="Known Issues")
        assert result == []


# ── scrape_known_issues ───────────────────────────────────────────────────────

class TestScrapeKnownIssues:
    _HTML = """
    <html><body>
      <h1>Known Issues</h1>
      <h2>Firewall</h2>
      <table>
        <tr><th>Bug ID</th><th>Description</th></tr>
        <tr><td>890776</td><td>Firewall policy not applied after upgrade</td></tr>
      </table>
      <h3>IPsec VPN</h3>
      <table>
        <tr><td>555555</td><td>IKE negotiation fails under high load conditions</td></tr>
      </table>
    </body></html>
    """

    def test_correct_bug_ids(self):
        result = scrape_known_issues(_mock_session(self._HTML), "http://example.com")
        ids = [r["Bug ID"] for r in result]
        assert "890776" in ids
        assert "555555" in ids

    def test_categories_tracked(self):
        result = scrape_known_issues(_mock_session(self._HTML), "http://example.com")
        cats = {r["Bug ID"]: r["category"] for r in result}
        assert cats["890776"] == "Firewall"
        assert cats["555555"] == "IPsec VPN"

    def test_title_mismatch_returns_empty(self):
        result = scrape_known_issues(_mock_session(self._HTML), "http://example.com", expected_title="New Features")
        assert result == []


# ── scrape_special_notices (inline layout) ────────────────────────────────────

class TestScrapeSpecialNoticesInline:
    """Test the inline layout (no sub-page links)."""

    _HTML = """
    <html><body>
      <h1>Special Notices</h1>
      <h2>Critical upgrade warning</h2>
      <p>You must perform a factory reset before upgrading from 7.2 to 7.4 in HA mode.</p>
      <h2>IPv6 deprecation notice</h2>
      <p>IPv6 tunnel-mode support will be removed in a future release of FortiOS firmware.</p>
      <h3>Short notice</h3>
      <p>Too short</p>
    </body></html>
    """

    def test_returns_notices_list(self):
        result = scrape_special_notices(_mock_session(self._HTML), "http://example.com")
        assert isinstance(result, list)

    def test_notice_titles_extracted(self):
        result = scrape_special_notices(_mock_session(self._HTML), "http://example.com")
        titles = [n["title"] for n in result]
        assert "Critical upgrade warning" in titles

    def test_notice_content_extracted(self):
        result = scrape_special_notices(_mock_session(self._HTML), "http://example.com")
        notices = {n["title"]: n["content"] for n in result}
        assert "factory reset" in notices.get("Critical upgrade warning", "")

    def test_short_content_filtered(self):
        result = scrape_special_notices(_mock_session(self._HTML), "http://example.com")
        titles = [n["title"] for n in result]
        assert "Short notice" not in titles


# ── scrape_rich_section (scraper_full) ────────────────────────────────────────

class TestScrapeRichSection:
    _HTML = """
    <html><body>
      <h1>Upgrade Information</h1>
      <div class="document-content">
        <h2>Upgrade Paths</h2>
        <p>Follow the supported upgrade path when upgrading FortiOS firmware versions.</p>
        <h3>Direct Upgrade</h3>
        <p>You can upgrade directly from 7.2.x to 7.4.x without an intermediate step.</p>
        <ul>
          <li>Step 1: Back up configuration</li>
          <li>Step 2: Download firmware</li>
          <li>Step 3: Apply firmware</li>
        </ul>
        <pre>config system global
    set hostname FGT-test
end</pre>
        <table>
          <tr><th>From</th><th>To</th><th>Notes</th></tr>
          <tr><td>7.2.8</td><td>7.4.11</td><td>Supported direct path</td></tr>
        </table>
      </div>
    </body></html>
    """

    def _result(self):
        return scrape_rich_section(_mock_session(self._HTML), "http://example.com")

    def test_returns_dict_with_title_and_blocks(self):
        result = self._result()
        assert isinstance(result, dict)
        assert "title" in result
        assert "blocks" in result

    def test_title_extracted(self):
        result = self._result()
        assert result["title"] == "Upgrade Information"

    def test_heading_blocks(self):
        blocks = self._result()["blocks"]
        headings = [b for b in blocks if b["type"] == "heading"]
        texts = [h["text"] for h in headings]
        assert any("Upgrade Paths" in t for t in texts)

    def test_heading_level(self):
        blocks = self._result()["blocks"]
        h2 = next(b for b in blocks if b["type"] == "heading" and "Upgrade Paths" in b["text"])
        assert h2["level"] == 2

    def test_paragraph_blocks(self):
        blocks = self._result()["blocks"]
        paras = [b for b in blocks if b["type"] == "paragraph"]
        assert len(paras) > 0
        assert any("upgrade" in p["text"].lower() for p in paras)

    def test_list_blocks(self):
        blocks = self._result()["blocks"]
        lists = [b for b in blocks if b["type"] == "list"]
        assert len(lists) > 0
        items = lists[0]["items"]
        assert any("Back up" in item for item in items)

    def test_code_blocks(self):
        blocks = self._result()["blocks"]
        code = [b for b in blocks if b["type"] == "code"]
        assert len(code) > 0
        assert "config system global" in code[0]["text"]

    def test_table_blocks(self):
        blocks = self._result()["blocks"]
        tables = [b for b in blocks if b["type"] == "table"]
        assert len(tables) > 0
        assert "From" in tables[0]["headers"]

    def test_title_mismatch_returns_none(self):
        result = scrape_rich_section(
            _mock_session(self._HTML), "http://example.com",
            expected_title="Known Issues"
        )
        assert result is None


# ── scrape_issues_section (scraper_full) ─────────────────────────────────────

class TestScrapeIssuesSection:
    _HTML = """
    <html><body>
      <h1>Resolved Issues</h1>
      <div class="document-content">
        <h2>Firewall</h2>
        <table>
          <tr><th>Bug ID</th><th>Description</th></tr>
          <tr><td>890776</td><td>Fixed crash when applying complex policy sets</td></tr>
          <tr><td>123456</td><td>Resolved interface flap on HA failover event</td></tr>
        </table>
        <h2>SD-WAN</h2>
        <table>
          <tr><td>555555</td><td>Fixed health check false positive under load</td></tr>
        </table>
      </div>
    </body></html>
    """

    def test_returns_list(self):
        result = scrape_issues_section(_mock_session(self._HTML), "http://example.com")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_bug_id_extracted(self):
        result = scrape_issues_section(_mock_session(self._HTML), "http://example.com")
        ids = [r["Bug ID"] for r in result]
        assert "890776" in ids

    def test_category_tracked(self):
        result = scrape_issues_section(_mock_session(self._HTML), "http://example.com")
        by_id = {r["Bug ID"]: r for r in result}
        assert by_id["890776"]["category"] == "Firewall"
        assert by_id["555555"]["category"] == "SD-WAN"

    def test_title_mismatch_returns_empty(self):
        result = scrape_issues_section(
            _mock_session(self._HTML), "http://example.com",
            expected_title="Known Issues"
        )
        assert result == []
