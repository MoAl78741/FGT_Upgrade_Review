"""
Unit tests for fgt_upgrade/utils.py and fgt_upgrade/constants.py.

All functions are pure input/output — no mocking required.

Run:
    python -m pytest tests/test_fgt_utils.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from fgt_upgrade.utils import parse_version, version_in_range, build_url, clean_text, deduplicate
from fgt_upgrade.constants import PAGE_IDS, MODEL_CATEGORIES, DEFAULT_PRIORITY_CATEGORIES


# ── parse_version ─────────────────────────────────────────────────────────────

class TestParseVersion:
    def test_three_part_version(self):
        assert parse_version("7.4.11") == (7, 4, 11)

    def test_small_version(self):
        assert parse_version("7.2.8") == (7, 2, 8)

    def test_zeros(self):
        assert parse_version("7.0.0") == (7, 0, 0)

    def test_strips_whitespace(self):
        assert parse_version("  7.0.3  ") == (7, 0, 3)

    def test_double_digit_minor(self):
        assert parse_version("7.12.1") == (7, 12, 1)

    def test_sortable_numerically(self):
        # "7.4.2" must sort BEFORE "7.4.11" (not lexicographically after)
        assert parse_version("7.4.2") < parse_version("7.4.11")

    def test_major_version_ordering(self):
        assert parse_version("6.4.11") < parse_version("7.0.0")

    def test_equal_versions(self):
        assert parse_version("7.4.11") == parse_version("7.4.11")


# ── version_in_range ──────────────────────────────────────────────────────────

class TestVersionInRange:
    def test_version_in_middle_of_range(self):
        assert version_in_range("7.4.5", "7.4.1", "7.4.10") is True

    def test_lower_bound_exclusive(self):
        # from_ver itself should NOT be in range
        assert version_in_range("7.4.1", "7.4.1", "7.4.10") is False

    def test_upper_bound_inclusive(self):
        # to_ver itself IS in range
        assert version_in_range("7.4.10", "7.4.1", "7.4.10") is True

    def test_below_range(self):
        assert version_in_range("7.4.0", "7.4.1", "7.4.10") is False

    def test_above_range(self):
        assert version_in_range("7.4.11", "7.4.1", "7.4.10") is False

    def test_cross_minor_range(self):
        assert version_in_range("7.4.0", "7.2.8", "7.4.11") is True

    def test_cross_major_range(self):
        assert version_in_range("7.0.0", "6.4.15", "7.2.8") is True


# ── build_url ─────────────────────────────────────────────────────────────────

class TestBuildUrl:
    def test_known_issues_url(self):
        url = build_url("7.4.11", "known_issues")
        assert "7.4.11" in url
        assert "236526" in url  # PAGE_IDS page_id for known_issues
        assert url.startswith("https://docs.fortinet.com")

    def test_changes_cli_url(self):
        url = build_url("7.2.8", "changes_cli")
        assert "7.2.8" in url
        assert "517622" in url  # PAGE_IDS page_id for changes_cli

    @pytest.mark.parametrize("key", list(PAGE_IDS.keys()))
    def test_all_keys_produce_valid_url(self, key):
        url = build_url("7.4.11", key)
        assert url.startswith("https://docs.fortinet.com")
        assert "7.4.11" in url
        assert "fortios-release-notes" in url

    def test_url_contains_slug(self):
        url = build_url("7.4.11", "changes_cli")
        assert "changes-in-cli" in url


# ── clean_text ────────────────────────────────────────────────────────────────

class TestCleanText:
    def test_strips_leading_trailing(self):
        assert clean_text("  foo  ") == "foo"

    def test_collapses_internal_spaces(self):
        assert clean_text("foo   bar") == "foo bar"

    def test_collapses_newlines(self):
        assert clean_text("foo\n\nbar") == "foo bar"

    def test_collapses_tabs(self):
        assert clean_text("foo\t\tbar") == "foo bar"

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_falsy_input(self):
        assert clean_text(None) == ""  # type: ignore[arg-type]

    def test_truncates_to_600(self):
        long_text = "a " * 400  # 800 chars
        result = clean_text(long_text)
        assert len(result) <= 600

    def test_short_text_not_truncated(self):
        text = "Short text"
        assert clean_text(text) == text


# ── deduplicate ───────────────────────────────────────────────────────────────

class TestDeduplicate:
    def _bug(self, id_, desc):
        return {"Bug ID": id_, "Description": desc}

    def _feature(self, id_, desc):
        return {"Feature ID": id_, "Description": desc}

    def test_removes_duplicate_bug_ids(self):
        items = [
            self._bug("890776", "Router crash on upgrade"),
            self._bug("890776", "Duplicate entry — should be removed"),
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert result[0]["Description"] == "Router crash on upgrade"

    def test_keeps_distinct_ids(self):
        items = [self._bug("111111", "First issue"), self._bug("222222", "Second issue")]
        assert len(deduplicate(items)) == 2

    def test_filters_short_description(self):
        items = [self._bug("111111", "ok"), self._bug("222222", "Valid description here")]
        result = deduplicate(items)
        assert len(result) == 1
        assert result[0]["Bug ID"] == "222222"

    def test_filters_empty_description(self):
        items = [self._bug("111111", ""), self._bug("222222", "Valid description here")]
        result = deduplicate(items)
        assert len(result) == 1

    def test_feature_id_key(self):
        items = [
            self._feature("1234567", "First feature description"),
            self._feature("1234567", "Duplicate feature"),
        ]
        result = deduplicate(items, id_key="Feature ID")
        assert len(result) == 1

    def test_cleans_string_fields(self):
        items = [{"Bug ID": "111111", "Description": "  extra   spaces  "}]
        result = deduplicate(items)
        assert result[0]["Description"] == "extra spaces"

    def test_empty_input(self):
        assert deduplicate([]) == []

    def test_no_duplicates_all_returned(self):
        items = [self._bug(str(i) * 6, f"Description number {i} is valid") for i in range(5)]
        assert len(deduplicate(items)) == 5


# ── constants structure ───────────────────────────────────────────────────────

class TestConstants:
    EXPECTED_PAGE_IDS_KEYS = {
        "changes_cli",
        "changes_default",
        "changes_tablesize",
        "new_features",
        "special_notices",
        "known_issues",
    }

    def test_page_ids_has_expected_keys(self):
        assert self.EXPECTED_PAGE_IDS_KEYS == set(PAGE_IDS.keys())

    @pytest.mark.parametrize("key", list(PAGE_IDS.keys()))
    def test_page_ids_values_are_3_tuples(self, key):
        entry = PAGE_IDS[key]
        assert isinstance(entry, tuple)
        assert len(entry) == 3

    @pytest.mark.parametrize("key", list(PAGE_IDS.keys()))
    def test_page_ids_page_id_is_numeric_string(self, key):
        page_id = PAGE_IDS[key][0]
        assert page_id.isdigit(), f"page_id for {key!r} is not numeric: {page_id!r}"

    @pytest.mark.parametrize("key", list(PAGE_IDS.keys()))
    def test_page_ids_slug_is_lowercase_hyphenated(self, key):
        slug = PAGE_IDS[key][1]
        assert slug == slug.lower()
        assert " " not in slug

    def test_model_categories_is_set(self):
        assert isinstance(MODEL_CATEGORIES, set)
        assert len(MODEL_CATEGORIES) > 0

    def test_default_priority_categories_is_dict(self):
        assert isinstance(DEFAULT_PRIORITY_CATEGORIES, dict)

    def test_default_priority_categories_values_are_color_strings(self):
        for k, v in DEFAULT_PRIORITY_CATEGORIES.items():
            assert isinstance(v, str), f"Value for {k!r} is not a string"
