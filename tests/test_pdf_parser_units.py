"""
Unit tests for pure functions in backend/pdf_parser.py and backend/pdf_worker.py.

No PDF file, no pdfplumber, no network — all functions under test are
pure input/output transformations.

Run:
    python -m pytest tests/test_pdf_parser_units.py -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from backend.pdf_parser import (
    detect_version_from_filename,
    detect_version_from_text,
    _match_section,
    _is_skippable,
    _is_category_like,
    _looks_like_id,
    _split_id_from_text,
    _clean,
    _title_to_slug,
    _words_to_lines,
    _fix_pipe_lists,
    _parse_id_desc_table,
)
from backend.pdf_worker import _ver_tuple


# ── detect_version_from_filename ─────────────────────────────────────────────

class TestDetectVersionFromFilename:
    def test_standard_with_v_prefix(self):
        assert detect_version_from_filename("fortios-v7.4.11-release-notes.pdf") == "7.4.11"

    def test_without_v_prefix(self):
        assert detect_version_from_filename("fortios-7.2.8-release-notes.pdf") == "7.2.8"

    def test_version_in_middle(self):
        assert detect_version_from_filename("release-notes-v7.0.0-something.pdf") == "7.0.0"

    def test_uppercase_v(self):
        assert detect_version_from_filename("FortiOS-V7.4.5-notes.pdf") == "7.4.5"

    def test_no_version_returns_none(self):
        assert detect_version_from_filename("release-notes.pdf") is None

    def test_empty_string_returns_none(self):
        assert detect_version_from_filename("") is None

    def test_double_digit_parts(self):
        assert detect_version_from_filename("fortios-v7.12.11.pdf") == "7.12.11"


# ── detect_version_from_text ──────────────────────────────────────────────────

class TestDetectVersionFromText:
    def test_fortios_pattern(self):
        assert detect_version_from_text("FortiOS 7.4.11 Release Notes") == "7.4.11"

    def test_fortigate_pattern(self):
        assert detect_version_from_text("FortiGate devices running 7.2.8") == "7.2.8"

    def test_release_notes_pattern(self):
        assert detect_version_from_text("Release Notes for 7.0.3 systems") == "7.0.3"

    def test_version_prefix_pattern(self):
        assert detect_version_from_text("Version 7.6.1 of FortiOS") == "7.6.1"

    def test_no_version_returns_none(self):
        assert detect_version_from_text("No version info here") is None

    def test_empty_string_returns_none(self):
        assert detect_version_from_text("") is None


# ── _match_section ────────────────────────────────────────────────────────────

class TestMatchSection:
    @pytest.mark.parametrize("line,expected", [
        ("New Features",                        "new_features"),
        ("New Feature",                         "new_features"),
        ("What's New",                          "new_features"),
        ("Known Issues",                        "known_issues"),
        ("Known Issue",                         "known_issues"),
        ("Resolved Issues",                     "resolved-issues"),
        ("Changes in CLI",                      "changes_cli"),
        ("Changes to CLI",                      "changes_cli"),
        ("Changes in Default Behavior",         "changes_default"),
        ("Changes in Default Behaviour",        "changes_default"),
        ("Changes in Default Settings",         "changes_default"),
        ("Changes in Table Size",               "changes_tablesize"),
        ("Special Notices",                     "special_notices"),
        ("Special Notice",                      "special_notices"),
        ("Upgrade Information",                 "upgrade-information"),
        ("Product Integration and Support",     "product-integration-and-support"),
        ("Change Log",                          "change-log"),
    ])
    def test_known_sections(self, line, expected):
        assert _match_section(line) == expected

    def test_case_insensitive(self):
        assert _match_section("KNOWN ISSUES") == "known_issues"
        assert _match_section("new features") == "new_features"

    def test_non_heading_returns_none(self):
        assert _match_section("Some random paragraph text") is None
        assert _match_section("") is None
        assert _match_section("Bug 890776 crashes the device") is None


# ── _is_skippable ─────────────────────────────────────────────────────────────

class TestIsSkippable:
    @pytest.mark.parametrize("line", [
        "Introduction",
        "introduction",
        "INTRODUCTION",
        "Table of Contents",
        "Table of Content",
        "Appendix",
        "Limitations",
        "Limitation",
        "Downgrade Information",
    ])
    def test_skippable_lines(self, line):
        assert _is_skippable(line) is True

    @pytest.mark.parametrize("line", [
        "Known Issues",
        "New Features",
        "Upgrade Information",
        "Special Notices",
        "",
        "Some normal text",
    ])
    def test_non_skippable_lines(self, line):
        assert _is_skippable(line) is False


# ── _is_category_like ────────────────────────────────────────────────────────

class TestIsCategoryLike:
    def test_simple_category(self):
        assert _is_category_like("Firewall") is True

    def test_hyphenated_category(self):
        assert _is_category_like("SD-WAN") is True

    def test_multi_word_category(self):
        assert _is_category_like("Security Fabric") is True

    def test_starts_with_digit(self):
        assert _is_category_like("1234 something") is False

    def test_too_long(self):
        assert _is_category_like("A" * 81) is False

    def test_exactly_80_chars_ok(self):
        assert _is_category_like("A" * 80) is True

    def test_ends_with_period(self):
        assert _is_category_like("Firewall.") is False

    def test_ends_with_colon(self):
        assert _is_category_like("Firewall:") is False

    def test_contains_pipe(self):
        assert _is_category_like("Firewall | SD-WAN") is False

    def test_contains_long_number(self):
        assert _is_category_like("Bug 890776") is False

    def test_empty_string(self):
        assert _is_category_like("") is False


# ── _looks_like_id ───────────────────────────────────────────────────────────

class TestLooksLikeId:
    def test_7_digit_id(self):
        assert _looks_like_id("1234567") is True

    def test_minimum_4_digits(self):
        assert _looks_like_id("1234") is True

    def test_maximum_10_digits(self):
        assert _looks_like_id("1234567890") is True

    def test_3_digits_too_short(self):
        assert _looks_like_id("123") is False

    def test_11_digits_too_long(self):
        assert _looks_like_id("12345678901") is False

    def test_letters_rejected(self):
        assert _looks_like_id("abc123") is False

    def test_whitespace_stripped(self):
        assert _looks_like_id("  890123  ") is True

    def test_empty_string(self):
        assert _looks_like_id("") is False


# ── _split_id_from_text ───────────────────────────────────────────────────────

class TestSplitIdFromText:
    def test_id_and_description(self):
        assert _split_id_from_text("890776 Router crashes under load") == ("890776", "Router crashes under load")

    def test_no_id(self):
        assert _split_id_from_text("No ID here at all") == ("", "No ID here at all")

    def test_id_alone_no_description(self):
        # Requires whitespace after ID — bare ID with no trailing text doesn't match
        assert _split_id_from_text("890776") == ("", "890776")

    def test_leading_whitespace_stripped(self):
        result = _split_id_from_text("  890776 Some description")
        assert result == ("890776", "Some description")

    def test_multiline_description(self):
        text = "123456 First line\nsecond line"
        id_, desc = _split_id_from_text(text)
        assert id_ == "123456"
        assert "First line" in desc


# ── _clean ────────────────────────────────────────────────────────────────────

class TestClean:
    def test_none_returns_empty(self):
        assert _clean(None) == ""

    def test_strips_whitespace(self):
        assert _clean("  foo  ") == "foo"

    def test_collapses_internal_whitespace(self):
        assert _clean("foo  bar   baz") == "foo bar baz"

    def test_converts_int_to_string(self):
        assert _clean(123) == "123"

    def test_collapses_newlines(self):
        assert _clean("foo\n\nbar") == "foo bar"

    def test_already_clean(self):
        assert _clean("clean text") == "clean text"


# ── _title_to_slug ────────────────────────────────────────────────────────────

class TestTitleToSlug:
    def test_basic(self):
        assert _title_to_slug("Upgrade Information") == "upgrade-information"

    def test_ampersand_removed(self):
        slug = _title_to_slug("Product Integration & Support")
        assert "integration" in slug
        assert "support" in slug
        assert "&" not in slug

    def test_spaces_become_hyphens(self):
        assert "-" in _title_to_slug("Known Issues")

    def test_lowercase(self):
        assert _title_to_slug("CLI Changes") == _title_to_slug("cli changes")

    def test_special_chars_removed(self):
        slug = _title_to_slug("Changes (New) / Updates!")
        assert "(" not in slug
        assert "!" not in slug


# ── _words_to_lines ───────────────────────────────────────────────────────────

class TestWordsToLines:
    def _word(self, text, top, x0):
        return {"text": text, "top": top, "x0": x0, "x1": x0 + 10}

    def test_empty_input(self):
        assert _words_to_lines([]) == []

    def test_single_word(self):
        lines = _words_to_lines([self._word("hello", 10, 50)])
        assert len(lines) == 1
        assert lines[0][1][0]["text"] == "hello"

    def test_two_words_same_line(self):
        words = [self._word("foo", 10, 50), self._word("bar", 10, 80)]
        lines = _words_to_lines(words)
        assert len(lines) == 1
        texts = [w["text"] for w in lines[0][1]]
        assert texts == ["foo", "bar"]  # sorted by x0

    def test_two_distinct_lines(self):
        words = [self._word("line1", 10, 50), self._word("line2", 100, 50)]
        lines = _words_to_lines(words)
        assert len(lines) == 2
        assert lines[0][1][0]["text"] == "line1"
        assert lines[1][1][0]["text"] == "line2"

    def test_words_sorted_by_x0_within_line(self):
        words = [self._word("second", 10, 100), self._word("first", 10, 20)]
        lines = _words_to_lines(words)
        texts = [w["text"] for w in lines[0][1]]
        assert texts == ["first", "second"]

    def test_lines_sorted_by_y_position(self):
        words = [self._word("bottom", 200, 50), self._word("top", 10, 50)]
        lines = _words_to_lines(words)
        assert lines[0][1][0]["text"] == "top"
        assert lines[1][1][0]["text"] == "bottom"

    def test_tolerance_groups_nearby_words(self):
        # round(0/3.0)=0 and round(1/3.0)=0 → same bucket
        words = [self._word("a", 0, 50), self._word("b", 1, 80)]
        lines = _words_to_lines(words, tolerance=3.0)
        assert len(lines) == 1


# ── _fix_pipe_lists ───────────────────────────────────────────────────────────

class TestFixPipeLists:
    def test_pipe_paragraph_becomes_list(self):
        blocks = [{"type": "paragraph", "text": "| item1 | item2 | item3"}]
        result = _fix_pipe_lists(blocks)
        assert result == [{"type": "list", "items": ["item1", "item2", "item3"]}]

    def test_non_pipe_paragraph_unchanged(self):
        blocks = [{"type": "paragraph", "text": "Normal text here"}]
        assert _fix_pipe_lists(blocks) == blocks

    def test_other_block_types_unchanged(self):
        blocks = [
            {"type": "heading", "level": 2, "text": "| heading"},
            {"type": "list", "items": ["| keep me"]},
        ]
        result = _fix_pipe_lists(blocks)
        assert result == blocks  # only paragraphs are converted

    def test_empty_pipe_parts_filtered(self):
        blocks = [{"type": "paragraph", "text": "| item1 |  | item2 |"}]
        result = _fix_pipe_lists(blocks)
        assert result[0]["items"] == ["item1", "item2"]

    def test_mixed_blocks(self):
        blocks = [
            {"type": "paragraph", "text": "Normal"},
            {"type": "paragraph", "text": "| link1 | link2"},
            {"type": "code", "text": "config system"},
        ]
        result = _fix_pipe_lists(blocks)
        assert result[0]["type"] == "paragraph"
        assert result[1]["type"] == "list"
        assert result[2]["type"] == "code"


# ── _parse_id_desc_table ──────────────────────────────────────────────────────

class TestParseIdDescTable:
    def test_normal_rows(self):
        # Header row (contains "bug id") is skipped; data row is returned
        rows = [["Bug ID", "Description"], ["890776", "Router crash on upgrade"]]
        result = _parse_id_desc_table(rows, "Bug ID")
        assert len(result) == 1
        assert result[0]["Bug ID"] == "890776"
        assert result[0]["Description"] == "Router crash on upgrade"

    def test_header_row_skipped(self):
        rows = [["Bug ID", "Description"], ["123456", "System process terminated"]]
        result = _parse_id_desc_table(rows)
        assert len(result) == 1  # header not included

    def test_no_header_row(self):
        # Neither row contains header keywords → both treated as data
        rows = [["123456", "First system crash"], ["789012", "Second route failure"]]
        result = _parse_id_desc_table(rows)
        assert len(result) == 2

    def test_continuation_rows_joined(self):
        # Second row has empty first cell → continuation of previous entry
        rows = [
            ["890776", "Router crash on upgrade"],
            ["",       "with memory corruption"],
        ]
        result = _parse_id_desc_table(rows)
        assert len(result) == 1
        assert "Router crash" in result[0]["Description"]
        assert "memory corruption" in result[0]["Description"]

    def test_merged_cell_id_extracted(self):
        # ID and text merged into first cell — split ID from text
        rows = [["890776 Router crashes under load", ""]]
        result = _parse_id_desc_table(rows)
        assert len(result) == 1
        assert result[0]["Bug ID"] == "890776"
        assert "Router crashes" in result[0]["Description"]

    def test_description_only_table(self):
        # No numeric ID column — pure text rows; id_key value is empty string
        rows = [["This is a standalone notice about FortiOS upgrade behavior"]]
        result = _parse_id_desc_table(rows)
        assert len(result) == 1
        assert result[0]["Bug ID"] == ""

    def test_empty_rows_ignored(self):
        rows = [["890776", "Router crash on upgrade"], [], ["", ""]]
        result = _parse_id_desc_table(rows)
        assert len(result) == 1

    def test_multiple_ids(self):
        rows = [
            ["111111", "First system crash event"],
            ["222222", "Second memory allocation fault"],
            ["333333", "Third route lookup failure"],
        ]
        result = _parse_id_desc_table(rows)
        assert len(result) == 3
        assert [r["Bug ID"] for r in result] == ["111111", "222222", "333333"]

    def test_feature_id_key(self):
        rows = [["1234567", "New routing algorithm for improved throughput"]]
        result = _parse_id_desc_table(rows, "Feature ID")
        assert result[0]["Feature ID"] == "1234567"

    def test_empty_input(self):
        assert _parse_id_desc_table([]) == []


# ── _ver_tuple (from pdf_worker) ──────────────────────────────────────────────

class TestVerTuple:
    def test_standard_version(self):
        assert _ver_tuple("7.4.11") == (7, 4, 11)

    def test_small_version(self):
        assert _ver_tuple("7.2.8") == (7, 2, 8)

    def test_zero_parts(self):
        assert _ver_tuple("7.0.0") == (7, 0, 0)

    def test_invalid_returns_fallback(self):
        assert _ver_tuple("not-a-version") == (0, 0, 0)

    def test_sortable(self):
        versions = ["7.4.11", "7.2.8", "7.4.2", "7.6.0"]
        assert sorted(versions, key=_ver_tuple) == ["7.2.8", "7.4.2", "7.4.11", "7.6.0"]
