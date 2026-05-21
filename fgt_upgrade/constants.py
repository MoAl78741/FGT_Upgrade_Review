"""
Shared constants used across the scraping and report-generation modules.
"""

FORTINET_BASE = "https://docs.fortinet.com"

# Page IDs are consistent across FortiOS versions.
# Each entry is a 3-tuple: (page_id, url-slug, expected_h1_title)
# The expected_h1_title is used to detect Fortinet's redirect-to-default behaviour:
# when a section doesn't exist for a given version the URL resolves to a generic
# "Introduction and Supported Models" page instead.  Before scraping we confirm
# the actual page <h1> contains the expected title (case-insensitive substring
# match).  If it doesn't match we return [] for that version/section combination.
PAGE_IDS = {
    "changes_cli":       ("517622",  "changes-in-cli",                 "Changes in CLI"),
    "changes_default":   ("230510",  "changes-in-default-behavior",    "Changes in Default Behavior"),
    "changes_tablesize": ("626946",  "changes-in-table-size",          "Changes in Table Size"),
    "new_features":      ("743723",  "new-features-and-enhancements",  "New features or Enhancements"),
    "special_notices":   ("708555",  "special-notices",                "Special notices"),
    "known_issues":      ("236526",  "known-issues",                   "Known Issues"),
}

# Default severity color assignments for known-issue categories.
# Users can override these in the dashboard UI and changes are saved to localStorage.
DEFAULT_PRIORITY_CATEGORIES = {
    "System":    "red",
    "Firewall":  "red",
    "HA":        "red",
    "IPsec VPN": "red",
    "Routing":   "red",
    "Upgrade":   "red",
    "REST API":  "yellow",
    "Proxy":     "yellow",
}

# Categories that are just hardware model lists — skip them in features.
MODEL_CATEGORIES = {
    "Supported models",
    "Special branch supported models",
    "FortiGate 6000 and 7000 support",
}

BATCH_SIZE = 5   # versions to fetch in parallel (Selenium mode)
LOAD_WAIT  = 6   # seconds to wait after initial page load (bumped for Grid latency)
