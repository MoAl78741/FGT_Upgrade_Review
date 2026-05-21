"""
HTML report generator.

generate_html() takes all scraped data and produces a single self-contained
HTML file with all CSS, JavaScript, and data embedded inline — no external
dependencies at runtime.
"""

import json
import datetime

from .constants import PAGE_IDS
from .utils import build_url


def generate_html(all_data: dict, special_notices: list,
                  from_ver: str, to_ver: str, priority_categories: dict) -> str:

    versions = sorted(all_data.keys(), key=lambda v: [int(x) for x in v.split(".")])
    total_cli       = sum(len(all_data[v].get("changes_cli", []))       for v in versions)
    total_default   = sum(len(all_data[v].get("changes_default", []))   for v in versions)
    total_tablesize = sum(len(all_data[v].get("changes_tablesize", [])) for v in versions)
    total_features  = sum(len(all_data[v].get("new_features", []))      for v in versions)
    total_ki        = len(all_data.get(to_ver, {}).get("known_issues", []))
    today           = datetime.date.today().isoformat()

    url_map = {v: {sk: build_url(v, sk) for sk in PAGE_IDS} for v in versions}

    js_data     = json.dumps(all_data,            ensure_ascii=False)
    js_notices  = json.dumps(special_notices,     ensure_ascii=False)
    js_priority = json.dumps(priority_categories, ensure_ascii=False)
    js_urls     = json.dumps(url_map,             ensure_ascii=False)
    js_from_ver = json.dumps(from_ver)
    js_to_ver   = json.dumps(to_ver)
    js_versions = json.dumps(versions)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FortiGate {from_ver} → {to_ver} Upgrade Dashboard</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {{
    --bg-0:#0c0f14; --bg-1:#12161e; --bg-2:#181d28; --bg-3:#1f2533; --bg-4:#272e3f;
    --border-1:#2a3244; --border-2:#353f55;
    --text-0:#f1f3f8; --text-1:#c8cdd8; --text-2:#8e95a5; --text-3:#5e6575;
    --teal:#2dd4bf; --teal-dim:rgba(45,212,191,.12);
    --sky:#38bdf8;  --sky-dim:rgba(56,189,248,.12);
    --violet:#a78bfa; --violet-dim:rgba(167,139,250,.12);
    --amber:#fbbf24; --amber-dim:rgba(251,191,36,.12);
    --rose:#fb7185;  --rose-dim:rgba(251,113,133,.12);
    --emerald:#34d399; --emerald-dim:rgba(52,211,153,.12);
    --slate:#64748b; --slate-dim:rgba(100,116,139,.15);
    --sev-red:#f87171; --sev-yellow:#fbbf24; --sev-green:#34d399; --sev-gray:#64748b;
    --r-sm:6px; --r-md:10px; --r-lg:14px; --r-xl:18px;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',-apple-system,sans-serif;background:var(--bg-0);color:var(--text-1);line-height:1.6;-webkit-font-smoothing:antialiased}}
.dashboard{{max-width:1500px;margin:0 auto;padding:28px 32px}}

/* ── HEADER ── */
.header{{background:linear-gradient(135deg,var(--bg-2) 0%,var(--bg-1) 60%,rgba(45,212,191,.04) 100%);border:1px solid var(--border-1);border-radius:var(--r-xl);padding:32px 40px 28px;margin-bottom:22px;position:relative;overflow:hidden}}
.header::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--teal),var(--sky),var(--violet))}}
.header-top{{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px}}
.header h1{{font-size:24px;font-weight:800;letter-spacing:-.5px;color:var(--text-0)}}
.header .subtitle{{color:var(--text-2);font-size:13px;margin-top:3px}}
.header-meta{{color:var(--text-3);font-size:12px;font-weight:500}}
.header-right{{display:flex;flex-direction:column;align-items:flex-end;gap:10px}}
.theme-switcher{{display:flex;gap:6px;align-items:center}}
.theme-lbl{{color:var(--text-3);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;margin-right:2px}}
.theme-dot{{width:20px;height:20px;border-radius:50%;cursor:pointer;border:2px solid transparent;transition:all .2s;padding:0;flex-shrink:0;position:relative}}
.theme-dot:hover{{transform:scale(1.15)}}
.theme-dot.active{{box-shadow:0 0 0 2px var(--bg-0),0 0 0 4px var(--text-1)}}
.theme-dot[title]:hover::after{{content:attr(title);position:absolute;bottom:-22px;left:50%;transform:translateX(-50%);background:var(--bg-3);color:var(--text-1);font-size:10px;font-weight:600;white-space:nowrap;padding:2px 6px;border-radius:4px;pointer-events:none;border:1px solid var(--border-1)}}
.version-path{{margin-top:14px;display:flex;align-items:center;gap:10px}}
.vbadge{{padding:4px 13px;border-radius:20px;font-weight:700;font-size:12px;font-family:'JetBrains Mono',monospace}}
.vbadge.from{{background:var(--violet-dim);color:var(--violet);border:1px solid rgba(167,139,250,.25)}}
.vbadge.to{{background:var(--teal-dim);color:var(--teal);border:1px solid rgba(45,212,191,.25)}}
.varrow{{color:var(--text-3);font-size:18px}}

/* ── EXPORT BAR ── */
.export-bar{{display:flex;align-items:center;gap:8px;padding:10px 14px;background:var(--bg-2);border:1px solid var(--border-1);border-radius:var(--r-md);margin-bottom:18px;flex-wrap:wrap}}
.bar-label{{color:var(--text-3);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px}}
.btn{{padding:6px 13px;border-radius:var(--r-sm);cursor:pointer;font-size:12px;font-weight:600;border:1px solid var(--border-2);background:var(--bg-3);color:var(--text-1);transition:all .15s;font-family:'Inter',sans-serif;display:inline-flex;align-items:center;gap:5px}}
.btn:hover{{background:var(--bg-4);border-color:var(--teal);color:var(--teal)}}
.btn svg{{width:13px;height:13px;flex-shrink:0}}
.sel-count{{color:var(--teal);font-size:12px;font-weight:700;font-family:'JetBrains Mono',monospace;margin-left:auto}}
.settings-btn{{margin-left:6px;border-color:var(--violet);color:var(--violet)}}
.settings-btn:hover{{background:var(--violet-dim);border-color:var(--violet);color:var(--violet)}}

/* ── STATS ── */
.stats-row{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:20px}}
.stat-card{{background:var(--bg-2);border:1px solid var(--border-1);border-radius:var(--r-lg);padding:20px 16px;text-align:center;position:relative;overflow:hidden;transition:transform .2s}}
.stat-card:hover{{transform:translateY(-2px)}}
.stat-card::after{{content:'';position:absolute;bottom:0;left:20%;right:20%;height:2px;border-radius:2px;opacity:.7}}
.stat-card:nth-child(1)::after{{background:var(--sky)}}
.stat-card:nth-child(2)::after{{background:var(--violet)}}
.stat-card:nth-child(3)::after{{background:var(--amber)}}
.stat-card:nth-child(4)::after{{background:var(--rose)}}
.stat-card:nth-child(5)::after{{background:var(--emerald)}}
.stat-card:nth-child(6)::after{{background:var(--rose)}}
.stat-num{{font-size:32px;font-weight:800;font-family:'JetBrains Mono',monospace;letter-spacing:-1px;margin-bottom:3px}}
.stat-card:nth-child(1) .stat-num{{color:var(--sky)}}
.stat-card:nth-child(2) .stat-num{{color:var(--violet)}}
.stat-card:nth-child(3) .stat-num{{color:var(--amber)}}
.stat-card:nth-child(4) .stat-num{{color:var(--rose)}}
.stat-card:nth-child(5) .stat-num{{color:var(--emerald)}}
.stat-card:nth-child(6) .stat-num{{color:var(--rose)}}
.stat-lbl{{color:var(--text-2);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.8px}}

/* ── NAV TABS ── */
.nav-tabs{{display:flex;gap:3px;margin-bottom:20px;background:var(--bg-1);border-radius:var(--r-lg);padding:4px;border:1px solid var(--border-1);overflow-x:auto}}
.nav-tab{{padding:9px 16px;border-radius:var(--r-md);cursor:pointer;font-size:13px;font-weight:600;color:var(--text-2);transition:all .15s;white-space:nowrap;border:none;background:none;font-family:'Inter',sans-serif}}
.nav-tab:hover{{color:var(--text-0);background:var(--bg-3)}}
.nav-tab.active{{background:linear-gradient(135deg,var(--teal-dim),rgba(56,189,248,.07));color:var(--teal);border:1px solid rgba(45,212,191,.2)}}

/* ── TAB PANELS ── */
.tab-panel{{display:none}}.tab-panel.active{{display:block}}

/* ── TOOLBAR ── */
.toolbar{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:16px}}
.search-box{{flex:0 0 320px;padding:8px 14px 8px 36px;border-radius:var(--r-md);border:1px solid var(--border-1);background:var(--bg-2);color:var(--text-0);font-size:13px;font-family:'Inter',sans-serif;outline:none;transition:border-color .15s;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' fill='none' stroke='%235e6575' stroke-width='2' viewBox='0 0 24 24'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:11px center}}
.search-box:focus{{border-color:var(--teal)}}
.search-box::placeholder{{color:var(--text-3)}}
.dedup-toggle{{display:flex;align-items:center;gap:7px;padding:7px 13px;border-radius:var(--r-md);border:1px solid var(--border-1);background:var(--bg-2);cursor:pointer;font-size:12px;font-weight:600;color:var(--text-2);transition:all .15s;font-family:'Inter',sans-serif;user-select:none}}
.dedup-toggle:hover{{border-color:var(--amber);color:var(--amber)}}
.dedup-toggle.on{{border-color:var(--amber);background:var(--amber-dim);color:var(--amber)}}
.toggle-pill{{width:28px;height:16px;border-radius:8px;background:var(--bg-4);position:relative;transition:background .15s;flex-shrink:0}}
.toggle-pill::after{{content:'';position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:var(--text-3);transition:all .15s}}
.dedup-toggle.on .toggle-pill{{background:var(--amber)}}
.dedup-toggle.on .toggle-pill::after{{left:14px;background:var(--bg-0)}}
.src-link{{margin-left:auto;font-size:12px;color:var(--text-3);text-decoration:none;display:flex;align-items:center;gap:4px;transition:color .15s}}
.src-link:hover{{color:var(--sky)}}
.src-link svg{{width:12px;height:12px}}

/* ── VERSION BUTTONS ── */
.version-timeline{{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}}
.vbtn{{padding:4px 11px;border-radius:var(--r-sm);cursor:pointer;font-size:11px;font-weight:600;border:1px solid var(--border-1);background:var(--bg-2);color:var(--text-2);transition:all .15s;white-space:nowrap;font-family:'JetBrains Mono',monospace}}
.vbtn:hover{{border-color:var(--teal);color:var(--text-0)}}
.vbtn.active{{background:var(--teal-dim);border-color:var(--teal);color:var(--teal)}}
.vbtn.v72{{border-left:3px solid var(--violet)}}
.vbtn.v74{{border-left:3px solid var(--teal)}}
.vbtn .cnt{{background:rgba(255,255,255,.08);padding:1px 6px;border-radius:8px;font-size:10px;margin-left:3px}}

/* ── CONTENT CARDS ── */
.content-card{{background:var(--bg-2);border:1px solid var(--border-1);border-radius:var(--r-md);margin-bottom:7px;overflow:hidden;transition:border-color .15s}}
.content-card:hover{{border-color:var(--border-2)}}
.card-row{{padding:11px 16px;display:flex;align-items:center;gap:10px;cursor:pointer;user-select:none}}
.card-cb{{appearance:none;-webkit-appearance:none;width:15px;height:15px;border:2px solid var(--border-2);border-radius:3px;cursor:pointer;flex-shrink:0;position:relative;transition:all .12s;background:var(--bg-3)}}
.card-cb:checked{{background:var(--teal);border-color:var(--teal)}}
.card-cb:checked::after{{content:'';position:absolute;top:1px;left:4px;width:4px;height:7px;border:solid var(--bg-0);border-width:0 2px 2px 0;transform:rotate(45deg)}}
.card-ver{{font-size:11px;color:var(--text-3);font-family:'JetBrains Mono',monospace;min-width:48px;font-weight:500}}
.card-id{{background:var(--sky-dim);color:var(--sky);padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;font-family:'JetBrains Mono',monospace;flex-shrink:0}}
.card-cat{{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;flex-shrink:0;background:var(--slate-dim);color:var(--slate)}}
.card-preview{{font-size:13px;color:var(--text-1);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.card-chev{{color:var(--text-3);transition:transform .15s;font-size:12px;flex-shrink:0;padding:2px 4px}}
.card-chev.open{{transform:rotate(180deg)}}
.card-body{{padding:0 16px 12px 54px;color:var(--text-2);font-size:13px;display:none;line-height:1.7}}
.card-body.open{{display:block}}

/* ── DIFF ── */
.diff-controls{{display:flex;gap:12px;align-items:center;margin-bottom:14px;flex-wrap:wrap}}
.diff-sel{{padding:8px 12px;border-radius:var(--r-sm);border:1px solid var(--border-1);background:var(--bg-2);color:var(--text-0);font-size:13px;font-family:'Inter',sans-serif;outline:none;cursor:pointer}}
.diff-sel:focus{{border-color:var(--teal)}}
.diff-lbl{{color:var(--text-2);font-size:12px;font-weight:600}}
.diff-added{{background:rgba(52,211,153,.07);border-left:3px solid var(--emerald)}}
.diff-removed{{background:rgba(251,113,133,.07);border-left:3px solid var(--rose)}}
.diff-tag{{font-size:10px;font-weight:700;padding:2px 6px;border-radius:3px;text-transform:uppercase;letter-spacing:.3px}}
.diff-tag.added{{background:var(--emerald-dim);color:var(--emerald)}}
.diff-tag.removed{{background:var(--rose-dim);color:var(--rose)}}

/* ── KNOWN ISSUES ── */
.issue-card{{background:var(--bg-2);border:1px solid var(--border-1);border-radius:var(--r-md);padding:13px 16px;margin-bottom:7px;border-left:4px solid var(--sev-gray);display:flex;align-items:flex-start;gap:10px}}
.issue-card:hover{{border-color:var(--border-2)}}
.issue-card.sev-red{{border-left-color:var(--sev-red)}}
.issue-card.sev-yellow{{border-left-color:var(--sev-yellow)}}
.issue-card.sev-green{{border-left-color:var(--sev-green)}}
.issue-card.sev-gray{{border-left-color:var(--sev-gray)}}
.sev-dot{{width:9px;height:9px;border-radius:50%;flex-shrink:0;margin-top:5px}}
.sev-dot.red{{background:var(--sev-red);box-shadow:0 0 7px rgba(248,113,113,.35)}}
.sev-dot.yellow{{background:var(--sev-yellow);box-shadow:0 0 7px rgba(251,191,36,.35)}}
.sev-dot.green{{background:var(--sev-green);box-shadow:0 0 7px rgba(52,211,153,.35)}}
.sev-dot.gray{{background:var(--sev-gray)}}
.issue-meta{{display:flex;align-items:center;gap:7px;margin-bottom:5px;flex-wrap:wrap}}
.cat-tag{{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:700;text-transform:uppercase;letter-spacing:.3px}}
.cat-tag.red{{background:rgba(248,113,113,.12);color:var(--sev-red)}}
.cat-tag.yellow{{background:rgba(251,191,36,.12);color:var(--sev-yellow)}}
.cat-tag.green{{background:rgba(52,211,153,.12);color:var(--sev-green)}}
.cat-tag.gray{{background:var(--slate-dim);color:var(--sev-gray)}}
.issue-desc{{color:var(--text-2);font-size:13px;line-height:1.55}}

/* ── SPECIAL NOTICES ── */
.notice-card{{background:var(--bg-2);border:1px solid var(--border-1);border-radius:var(--r-md);padding:16px 20px;margin-bottom:9px;border-left:4px solid var(--amber);display:flex;gap:12px}}
.notice-icon{{color:var(--amber);font-size:16px;flex-shrink:0;margin-top:2px}}
.notice-card h3{{font-size:14px;font-weight:700;margin-bottom:5px;color:var(--text-0)}}
.notice-card p{{color:var(--text-2);font-size:13px}}

/* ── FILTER BAR ── */
.filter-bar{{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap;align-items:center}}
.fbtn{{padding:4px 10px;border-radius:var(--r-sm);cursor:pointer;font-size:11px;font-weight:600;border:1px solid var(--border-1);background:var(--bg-2);color:var(--text-2);transition:all .15s;font-family:'Inter',sans-serif;display:inline-flex;align-items:center;gap:4px}}
.fbtn:hover{{border-color:var(--teal);color:var(--text-0)}}
.fbtn.active{{background:var(--teal-dim);border-color:var(--teal);color:var(--teal)}}
.flabel{{color:var(--text-3);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;margin-right:2px}}

/* ── OVERVIEW TABLE ── */
.ov-table{{width:100%;border-collapse:separate;border-spacing:0;border-radius:var(--r-lg);overflow:hidden;border:1px solid var(--border-1);margin-bottom:20px}}
.ov-table th{{background:var(--bg-3);padding:11px 14px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:var(--text-3);font-weight:700;border-bottom:1px solid var(--border-1)}}
.ov-table td{{padding:9px 14px;border-bottom:1px solid var(--border-1);font-size:13px;background:var(--bg-2)}}
.ov-table tr:last-child td{{border-bottom:none}}
.cnt{{font-weight:700;text-align:center;font-family:'JetBrains Mono',monospace;font-size:13px}}
.cnt.has{{color:var(--sky)}}.cnt.none{{color:var(--text-3)}}
.vc{{font-weight:700;font-family:'JetBrains Mono',monospace}}
.vc a{{text-decoration:none;transition:color .15s}}.vc a:hover{{text-decoration:underline}}
.tot-row td{{background:var(--bg-3);font-weight:800;border-top:2px solid var(--border-2)}}

/* ── EMPTY STATE ── */
.empty{{text-align:center;padding:40px;color:var(--text-3);font-size:14px}}

/* ═══════════════════════════════════
   SETTINGS MODAL
   ═══════════════════════════════════ */
.modal-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:none;align-items:center;justify-content:center;padding:24px;backdrop-filter:blur(4px)}}
.modal-overlay.open{{display:flex}}
.modal{{background:var(--bg-2);border:1px solid var(--border-1);border-radius:var(--r-xl);width:min(700px,100%);max-height:85vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 25px 60px rgba(0,0,0,.6)}}
.modal-header{{padding:20px 24px 16px;border-bottom:1px solid var(--border-1);display:flex;align-items:center;justify-content:space-between}}
.modal-header h2{{font-size:16px;font-weight:700;color:var(--text-0)}}
.modal-close{{background:none;border:none;cursor:pointer;color:var(--text-2);font-size:20px;padding:4px 8px;border-radius:4px;transition:color .15s;font-family:'Inter',sans-serif}}
.modal-close:hover{{color:var(--rose)}}
.modal-body{{padding:20px 24px;overflow-y:auto;flex:1}}
.modal-footer{{padding:14px 24px;border-top:1px solid var(--border-1);display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.modal-desc{{color:var(--text-2);font-size:13px;margin-bottom:16px;line-height:1.6}}
.cat-row{{display:flex;align-items:center;padding:9px 12px;border-radius:var(--r-sm);margin-bottom:6px;background:var(--bg-3);gap:12px}}
.cat-name{{flex:1;font-size:13px;font-weight:600;color:var(--text-1);font-family:'JetBrains Mono',monospace}}
.sev-picker{{display:flex;gap:6px}}
.sev-radio{{display:none}}
.sev-radio + label{{padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.3px;border:1px solid var(--border-1);background:var(--bg-4);color:var(--text-2);transition:all .15s;user-select:none}}
.sev-radio[value="red"] + label:hover,.sev-radio[value="red"]:checked + label{{background:rgba(248,113,113,.15);border-color:var(--sev-red);color:var(--sev-red)}}
.sev-radio[value="yellow"] + label:hover,.sev-radio[value="yellow"]:checked + label{{background:rgba(251,191,36,.15);border-color:var(--sev-yellow);color:var(--sev-yellow)}}
.sev-radio[value="green"] + label:hover,.sev-radio[value="green"]:checked + label{{background:rgba(52,211,153,.15);border-color:var(--sev-green);color:var(--sev-green)}}
.sev-radio[value="gray"] + label:hover,.sev-radio[value="gray"]:checked + label{{background:var(--slate-dim);border-color:var(--sev-gray);color:var(--sev-gray)}}
.section-header{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:var(--text-3);margin:16px 0 8px}}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{{width:7px;height:7px}}
::-webkit-scrollbar-track{{background:var(--bg-0)}}
::-webkit-scrollbar-thumb{{background:var(--border-1);border-radius:4px}}
::-webkit-scrollbar-thumb:hover{{background:var(--text-3)}}

@media(max-width:900px){{
    .stats-row{{grid-template-columns:repeat(3,1fr);row-gap:10px}}
    .search-box{{flex:1 1 180px}}
    .dashboard{{padding:16px}}
}}
@media print{{
    body{{background:#fff;color:#000}}
    .nav-tabs,.filter-bar,.search-box,.export-bar,.dedup-toggle,.modal-overlay{{display:none!important}}
}}
</style>
</head>
<body>
<div class="dashboard">

    <!-- Header -->
    <div class="header">
        <div class="header-top">
            <div>
                <h1>FortiGate Upgrade Dashboard</h1>
                <div class="subtitle">Release notes analysis &mdash; every change between builds</div>
            </div>
            <div class="header-right">
                <div class="header-meta">Generated {today}</div>
                <div class="theme-switcher" id="theme-switcher">
                    <span class="theme-lbl">Theme</span>
                    <button class="theme-dot active" data-theme="obsidian" title="Obsidian" style="background:linear-gradient(135deg,#0c0f14 50%,#2dd4bf)"></button>
                    <button class="theme-dot" data-theme="fortinet" title="Fortinet" style="background:linear-gradient(135deg,#1c2d3a 50%,#f5821f)"></button>
                    <button class="theme-dot" data-theme="arctic" title="Arctic" style="background:linear-gradient(135deg,#dde9f5 50%,#0ea5e9)"></button>
                    <button class="theme-dot" data-theme="midnight" title="Midnight" style="background:linear-gradient(135deg,#07071a 50%,#818cf8)"></button>
                    <button class="theme-dot" data-theme="carbon" title="Carbon" style="background:linear-gradient(135deg,#09090b 50%,#22d3ee)"></button>
                </div>
            </div>
        </div>
        <div class="version-path">
            <span class="vbadge from">{from_ver}</span>
            <span class="varrow">&#8594;</span>
            <span class="vbadge to">{to_ver}</span>
            <span style="color:var(--text-3);margin-left:12px;font-size:12px;font-weight:500">{len(versions)} versions analyzed</span>
        </div>
    </div>

    <!-- Export Bar -->
    <div class="export-bar">
        <span class="bar-label">Export</span>
        <button class="btn" onclick="exportSelected('csv')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M12 18v-6m-3 3 3 3 3-3"/></svg>
            Selected (CSV)
        </button>
        <button class="btn" onclick="exportAll('csv')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
            All (CSV)
        </button>
        <button class="btn" onclick="exportSelected('txt')">Selected (TXT)</button>
        <button class="btn" onclick="exportAll('txt')">All (TXT)</button>
        <button class="btn settings-btn" onclick="openSettings()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            Severity Settings
        </button>
        <button class="btn" onclick="resetAllSelections()">Reset All</button>
        <span class="sel-count" id="sel-count">0 selected</span>
    </div>

    <!-- Stats -->
    <div class="stats-row">
        <div class="stat-card"><div class="stat-num">{len(versions)}</div><div class="stat-lbl">Versions</div></div>
        <div class="stat-card"><div class="stat-num">{total_cli}</div><div class="stat-lbl">CLI Changes</div></div>
        <div class="stat-card"><div class="stat-num">{total_default}</div><div class="stat-lbl">Default Behavior</div></div>
        <div class="stat-card"><div class="stat-num">{total_tablesize}</div><div class="stat-lbl">Table Size</div></div>
        <div class="stat-card"><div class="stat-num">{total_features}</div><div class="stat-lbl">New Features</div></div>
        <div class="stat-card"><div class="stat-num">{total_ki}</div><div class="stat-lbl">Known Issues</div></div>
    </div>

    <!-- Navigation -->
    <div class="nav-tabs" id="main-nav">
        <button class="nav-tab active" data-tab="overview">Overview</button>
        <button class="nav-tab" data-tab="cli">CLI Changes</button>
        <button class="nav-tab" data-tab="default">Default Behavior</button>
        <button class="nav-tab" data-tab="tablesize">Table Size</button>
        <button class="nav-tab" data-tab="features">New Features</button>
        <button class="nav-tab" data-tab="diff">Feature Diff</button>
        <button class="nav-tab" data-tab="notices">Special Notices</button>
        <button class="nav-tab" data-tab="known">Known Issues ({total_ki})</button>
    </div>

    <!-- Tab: Overview -->
    <div class="tab-panel active" id="tab-overview">
        <table class="ov-table"><thead><tr>
            <th>Version</th><th style="text-align:center">CLI</th><th style="text-align:center">Default Behavior</th>
            <th style="text-align:center">Table Size</th><th style="text-align:center">Features</th><th style="text-align:center">Known Issues</th><th style="text-align:center">Total</th>
        </tr></thead><tbody id="ov-tbody"></tbody></table>
    </div>

    <!-- Tab: CLI Changes -->
    <div class="tab-panel" id="tab-cli">
        <div class="toolbar">
            <input class="search-box" placeholder="Search CLI changes…" data-sec="cli">
            <label class="dedup-toggle" data-sec="cli"><span class="toggle-pill"></span>Hide duplicates</label>
            <button class="btn" onclick="selectPageAll(true)">Select All</button>
            <button class="btn" onclick="selectPageAll(false)">Select None</button>
            <a class="src-link" id="lnk-cli" href="#" target="_blank"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>Fortinet Docs</a>
        </div>
        <div class="version-timeline" id="cli-vt"></div>
        <div id="cli-content"></div>
    </div>

    <!-- Tab: Default Behavior -->
    <div class="tab-panel" id="tab-default">
        <div class="toolbar">
            <input class="search-box" placeholder="Search default behavior changes…" data-sec="default">
            <label class="dedup-toggle" data-sec="default"><span class="toggle-pill"></span>Hide duplicates</label>
            <button class="btn" onclick="selectPageAll(true)">Select All</button>
            <button class="btn" onclick="selectPageAll(false)">Select None</button>
            <a class="src-link" id="lnk-default" href="#" target="_blank"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>Fortinet Docs</a>
        </div>
        <div class="version-timeline" id="default-vt"></div>
        <div id="default-content"></div>
    </div>

    <!-- Tab: Table Size -->
    <div class="tab-panel" id="tab-tablesize">
        <div class="toolbar">
            <input class="search-box" placeholder="Search table size changes…" data-sec="tablesize">
            <label class="dedup-toggle" data-sec="tablesize"><span class="toggle-pill"></span>Hide duplicates</label>
            <button class="btn" onclick="selectPageAll(true)">Select All</button>
            <button class="btn" onclick="selectPageAll(false)">Select None</button>
            <a class="src-link" id="lnk-tablesize" href="#" target="_blank"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>Fortinet Docs</a>
        </div>
        <div class="version-timeline" id="tablesize-vt"></div>
        <div id="tablesize-content"></div>
    </div>

    <!-- Tab: New Features -->
    <div class="tab-panel" id="tab-features">
        <div class="toolbar">
            <input class="search-box" placeholder="Search features…" data-sec="features">
            <label class="dedup-toggle" data-sec="features"><span class="toggle-pill"></span>Hide duplicates</label>
            <button class="btn" onclick="selectPageAll(true)">Select All</button>
            <button class="btn" onclick="selectPageAll(false)">Select None</button>
            <a class="src-link" id="lnk-features" href="#" target="_blank"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>Fortinet Docs</a>
        </div>
        <div class="version-timeline" id="features-vt"></div>
        <div class="filter-bar" id="feat-cat-filters"></div>
        <div id="features-content"></div>
    </div>

    <!-- Tab: Feature Diff -->
    <div class="tab-panel" id="tab-diff">
        <div class="diff-controls">
            <span class="diff-lbl">Compare:</span>
            <select class="diff-sel" id="diff-from"></select>
            <span class="diff-lbl">vs</span>
            <select class="diff-sel" id="diff-to"></select>
            <button class="btn" onclick="runDiff()" style="padding:7px 18px">Compare &#9654;</button>
        </div>
        <div id="diff-result"></div>
    </div>

    <!-- Tab: Special Notices -->
    <div class="tab-panel" id="tab-notices">
        <div class="toolbar">
            <a class="src-link" href="{build_url(to_ver, 'special_notices')}" target="_blank" style="margin-left:0"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>Fortinet Docs</a>
        </div>
        <h2 style="margin:10px 0 16px;font-size:17px;color:var(--amber);font-weight:700">Special Notices &mdash; FortiOS {to_ver}</h2>
        <div id="notices-content"></div>
    </div>

    <!-- Tab: Known Issues -->
    <div class="tab-panel" id="tab-known">
        <div class="toolbar">
            <input class="search-box" placeholder="Search known issues…" data-sec="known">
            <button class="btn" onclick="selectPageAll(true)">Select All</button>
            <button class="btn" onclick="selectPageAll(false)">Select None</button>
            <a class="src-link" id="lnk-known" href="{build_url(to_ver, 'known_issues')}" target="_blank"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>Fortinet Docs</a>
        </div>
        <div class="version-timeline" id="known-vt"></div>
        <div class="filter-bar" id="ki-sev-filters"></div>
        <div class="filter-bar" id="ki-cat-filters"></div>
        <div id="known-content"></div>
        <div id="ki-count" style="color:var(--text-3);font-size:12px;margin-top:10px;font-weight:600"></div>
    </div>
</div>

<!-- ═══════════════════════════════════
     SETTINGS MODAL
     ═══════════════════════════════════ -->
<div class="modal-overlay" id="settings-overlay" onclick="if(event.target===this)closeSettings()">
    <div class="modal">
        <div class="modal-header">
            <h2>Severity Color Settings</h2>
            <button class="modal-close" onclick="closeSettings()">&#10005;</button>
        </div>
        <div class="modal-body">
            <p class="modal-desc">
                Assign a severity color to each known-issue category. Changes apply immediately and are saved in your browser's localStorage so they persist across sessions.
            </p>
            <div id="settings-cats"></div>
        </div>
        <div class="modal-footer">
            <button class="btn" onclick="resetCategoryDefaults()">Reset to Defaults</button>
            <button class="btn" onclick="exportCategoryConfig()">Export Config (JSON)</button>
            <label class="btn" style="cursor:pointer">
                Import Config
                <input type="file" accept=".json" onchange="importCategoryConfig(event)" style="display:none">
            </label>
            <button class="btn" onclick="closeSettings()" style="margin-left:auto;border-color:var(--teal);color:var(--teal)">Done</button>
        </div>
    </div>
</div>

<script>
// ═══════════════════════ EMBEDDED DATA ═══════════════════════
const DATA         = {js_data};
const SPECIAL_NOTICES = {js_notices};
const DEFAULT_PRIORITY = {js_priority};
const URLS         = {js_urls};
const FROM_VER     = {js_from_ver};
const TO_VER       = {js_to_ver};
const VERSIONS     = {js_versions};
const KNOWN_ISSUES = VERSIONS.flatMap(v => DATA[v]?.known_issues || []);

const SECTION_MAP = {{
    cli: 'changes_cli', default: 'changes_default',
    tablesize: 'changes_tablesize', features: 'new_features', known: 'known_issues'
}};
const SEC_URL_KEY = {{
    cli: 'changes_cli', default: 'changes_default',
    tablesize: 'changes_tablesize', features: 'new_features', known: 'known_issues'
}};

// ═══════════════════════ CATEGORY COLOR STATE ═══════════════════════
const LS_KEY = 'fg_severity_config';

function loadPriorityCategories() {{
    try {{
        const saved = localStorage.getItem(LS_KEY);
        if (saved) return JSON.parse(saved);
    }} catch(e) {{}}
    return {{...DEFAULT_PRIORITY}};
}}

function savePriorityCategories(cats) {{
    try {{ localStorage.setItem(LS_KEY, JSON.stringify(cats)); }} catch(e) {{}}
}}

let PRIORITY_CATS = loadPriorityCategories();

function getSeverity(cat) {{
    return PRIORITY_CATS[cat] || 'gray';
}}

// ═══════════════════════ STATE ═══════════════════════
const S = {{
    verFilter: {{}}, search: {{}}, dedup: {{}},
    sevFilter: 'all', catFilter: 'all', featCat: 'all',
    selected: new Set()
}};

// ═══════════════════════ TAB SWITCHING ═══════════════════════
document.getElementById('main-nav').addEventListener('click', e => {{
    const btn = e.target.closest('.nav-tab');
    if (!btn) return;
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    btn.classList.add('active');
}});

// ═══════════════════════ OVERVIEW ═══════════════════════
function buildOverview() {{
    const tbody = document.getElementById('ov-tbody');
    let html = '', tots = [0,0,0,0,0,0];
    VERSIONS.forEach(v => {{
        const cli = (DATA[v].changes_cli||[]).length,
              def = (DATA[v].changes_default||[]).length,
              ts  = (DATA[v].changes_tablesize||[]).length,
              ft  = (DATA[v].new_features||[]).length,
              ki  = (DATA[v].known_issues||[]).length,
              tot = cli+def+ts+ft;
        tots[0]+=cli; tots[1]+=def; tots[2]+=ts; tots[3]+=ft; tots[4]+=ki; tots[5]+=tot;
        const col = v.startsWith('7.2') ? 'var(--violet)' : 'var(--teal)';
        const rn  = `https://docs.fortinet.com/document/fortigate/${{v}}/fortios-release-notes`;
        html += `<tr>
            <td class="vc"><a href="${{rn}}" target="_blank" style="color:${{col}}">${{v}}</a></td>
            <td class="cnt ${{cli?'has':'none'}}">${{cli||'—'}}</td>
            <td class="cnt ${{def?'has':'none'}}">${{def||'—'}}</td>
            <td class="cnt ${{ts?'has':'none'}}">${{ts||'—'}}</td>
            <td class="cnt ${{ft?'has':'none'}}">${{ft||'—'}}</td>
            <td class="cnt ${{ki?'has':'none'}}" style="${{ki?'color:var(--rose)':''}}">${{ki||'—'}}</td>
            <td class="cnt has" style="color:var(--teal)">${{tot}}</td>
        </tr>`;
    }});
    html += `<tr class="tot-row">
        <td class="vc" style="color:var(--teal)">TOTAL</td>
        ${{tots.slice(0,4).map(n=>`<td class="cnt has">${{n}}</td>`).join('')}}
        <td class="cnt has" style="color:var(--rose)">${{tots[4]}}</td>
        <td class="cnt has" style="color:var(--teal);font-size:15px">${{tots[5]}}</td>
    </tr>`;
    tbody.innerHTML = html;
}}

// ═══════════════════════ VERSION TIMELINES ═══════════════════════
function buildTimeline(sec, containerId, onSelect) {{
    const el = document.getElementById(containerId);
    const dk = SECTION_MAP[sec];
    let html = '<button class="vbtn active" data-ver="all">All</button>';
    VERSIONS.forEach(v => {{
        const n = (DATA[v][dk]||[]).length;
        const cls = v.startsWith('7.2') ? 'v72' : 'v74';
        html += `<button class="vbtn ${{cls}}" data-ver="${{v}}">${{v}}<span class="cnt">${{n}}</span></button>`;
    }});
    el.innerHTML = html;
    el.addEventListener('click', e => {{
        const btn = e.target.closest('.vbtn');
        if (!btn) return;
        el.querySelectorAll('.vbtn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        S.verFilter[sec] = btn.dataset.ver;
        updateSrcLink(sec, btn.dataset.ver);
        if (onSelect) onSelect(); else renderSection(sec);
    }});
}}

function updateSrcLink(sec, ver) {{
    const lnk = document.getElementById('lnk-' + sec);
    if (!lnk) return;
    const v = (ver && ver !== 'all') ? ver : TO_VER;
    lnk.href = URLS[v]?.[SEC_URL_KEY[sec]] || '#';
}}

// ═══════════════════════ DEDUP TOGGLES ═══════════════════════
document.querySelectorAll('.dedup-toggle').forEach(el => {{
    el.addEventListener('click', () => {{
        el.classList.toggle('on');
        S.dedup[el.dataset.sec] = el.classList.contains('on');
        renderSection(el.dataset.sec);
    }});
}});

// ═══════════════════════ SEARCH ═══════════════════════
document.querySelectorAll('.search-box').forEach(el => {{
    el.addEventListener('input', () => {{
        const sec = el.dataset.sec;
        S.search[sec] = el.value;
        sec === 'known' ? renderKnownIssues() : renderSection(sec);
    }});
}});

// ═══════════════════════ SECTION RENDERER ═══════════════════════
function renderSection(sec) {{
    const el   = document.getElementById(sec + '-content');
    const dk   = SECTION_MAP[sec];
    const vf   = S.verFilter[sec] || 'all';
    const term = (S.search[sec] || '').toLowerCase();
    const dedup= S.dedup[sec] || false;
    const catF = sec === 'features' ? S.featCat : 'all';
    const vers = vf === 'all' ? VERSIONS : [vf];

    let html = '', count = 0;
    const seenIds = new Set();

    vers.forEach(v => {{
        (DATA[v][dk] || []).forEach((item, idx) => {{
            const id   = item['Bug ID'] || item['Feature ID'] || '';
            const desc = item.Description || '';
            const cat  = item.category || '';
            if (dedup && id && seenIds.has(id)) return;
            if (dedup && id) seenIds.add(id);
            if (catF !== 'all' && cat !== catF) return;
            if (term && !id.toLowerCase().includes(term) && !desc.toLowerCase().includes(term) && !cat.toLowerCase().includes(term)) return;
            count++;
            const uid = sec + '_' + v.replace(/\\./g,'') + '_' + idx;
            const chk = S.selected.has(uid) ? 'checked' : '';
            html += `<div class="content-card">
                <div class="card-row" onclick="toggleCard('${{uid}}')">
                    <input type="checkbox" class="card-cb" data-uid="${{uid}}" data-sec="${{sec}}" data-ver="${{v}}" data-id="${{id}}" data-desc="${{desc.replace(/"/g,'&quot;')}}" data-cat="${{cat}}" ${{chk}} onclick="event.stopPropagation();toggleCheck(this)">
                    <span class="card-ver">${{v}}</span>
                    ${{id ? `<span class="card-id">${{id}}</span>` : ''}}
                    ${{cat ? `<span class="card-cat">${{cat}}</span>` : ''}}
                    <span class="card-preview">${{desc.substring(0,130)}}${{desc.length>130?'…':''}}</span>
                    <span class="card-chev" id="chev-${{uid}}">&#9660;</span>
                </div>
                <div class="card-body" id="body-${{uid}}">${{desc}}</div>
            </div>`;
        }});
    }});
    el.innerHTML = count ? html : '<div class="empty">No items match the current filters</div>';
}}

function toggleCard(uid) {{
    document.getElementById('body-'+uid)?.classList.toggle('open');
    document.getElementById('chev-'+uid)?.classList.toggle('open');
}}

function toggleCheck(cb) {{
    cb.checked ? S.selected.add(cb.dataset.uid) : S.selected.delete(cb.dataset.uid);
    document.getElementById('sel-count').textContent = S.selected.size + ' selected';
}}

function selectPageAll(check) {{
    const panel = document.querySelector('.tab-panel.active');
    if (!panel) return;
    panel.querySelectorAll('.card-cb').forEach(cb => {{
        cb.checked = check;
        check ? S.selected.add(cb.dataset.uid) : S.selected.delete(cb.dataset.uid);
    }});
    document.getElementById('sel-count').textContent = S.selected.size + ' selected';
}}

function resetAllSelections() {{
    document.querySelectorAll('.card-cb').forEach(cb => {{ cb.checked = false; }});
    S.selected.clear();
    document.getElementById('sel-count').textContent = '0 selected';
}}

// ═══════════════════════ FEATURE CATEGORY FILTER ═══════════════════════
function buildFeatCatFilters() {{
    const el = document.getElementById('feat-cat-filters');
    const cats = new Set();
    VERSIONS.forEach(v => (DATA[v].new_features||[]).forEach(i => i.category && cats.add(i.category)));
    let html = '<span class="flabel">Category:</span><button class="fbtn active" data-cat="all">All</button>';
    [...cats].sort().forEach(c => {{ html += `<button class="fbtn" data-cat="${{c}}">${{c}}</button>`; }});
    el.innerHTML = html;
    el.addEventListener('click', e => {{
        const btn = e.target.closest('.fbtn');
        if (!btn) return;
        el.querySelectorAll('.fbtn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        S.featCat = btn.dataset.cat;
        renderSection('features');
    }});
}}

// ═══════════════════════ DIFF ═══════════════════════
function buildDiff() {{
    const fromEl = document.getElementById('diff-from');
    const toEl   = document.getElementById('diff-to');
    VERSIONS.forEach((v, i) => {{
        fromEl.innerHTML += `<option value="${{v}}" ${{i===0?'selected':''}}>${{v}}</option>`;
        toEl.innerHTML   += `<option value="${{v}}" ${{i===VERSIONS.length-1?'selected':''}}>${{v}}</option>`;
    }});
}}

function runDiff() {{
    const fv = document.getElementById('diff-from').value;
    const tv = document.getElementById('diff-to').value;
    const fItems = DATA[fv]?.new_features || [];
    const tItems = DATA[tv]?.new_features || [];
    const fIds = new Set(fItems.map(f => f['Feature ID'] || f.Description?.substring(0,80)));
    const tIds = new Set(tItems.map(f => f['Feature ID'] || f.Description?.substring(0,80)));
    const added   = tItems.filter(f => !fIds.has(f['Feature ID'] || f.Description?.substring(0,80)));
    const removed = fItems.filter(f => !tIds.has(f['Feature ID'] || f.Description?.substring(0,80)));
    let html = `<div style="margin-bottom:14px;font-size:13px;color:var(--text-2)">
        <span style="color:var(--emerald);font-weight:700">+${{added.length}} new</span> in ${{tv}} &nbsp;|&nbsp;
        <span style="color:var(--rose);font-weight:700">-${{removed.length}} only in</span> ${{fv}}
    </div>`;
    if (added.length) {{
        html += `<div style="color:var(--emerald);font-size:13px;font-weight:700;margin:14px 0 8px">Added in ${{tv}}</div>`;
        added.forEach(f => {{ html += diffCard(f, 'added'); }});
    }}
    if (removed.length) {{
        html += `<div style="color:var(--rose);font-size:13px;font-weight:700;margin:14px 0 8px">Only in ${{fv}}</div>`;
        removed.forEach(f => {{ html += diffCard(f, 'removed'); }});
    }}
    if (!added.length && !removed.length) html += '<div class="empty">No differences found</div>';
    document.getElementById('diff-result').innerHTML = html;
}}

function diffCard(f, type) {{
    const id  = f['Feature ID'] || '';
    const desc= f.Description || '';
    const cat = f.category || '';
    return `<div class="content-card diff-${{type}}">
        <div class="card-row">
            <span class="diff-tag ${{type}}">${{type==='added'?'+new':'only'}}</span>
            ${{id ? `<span class="card-id">${{id}}</span>` : ''}}
            ${{cat ? `<span class="card-cat">${{cat}}</span>` : ''}}
            <span class="card-preview">${{desc.substring(0,220)}}</span>
        </div>
    </div>`;
}}

// ═══════════════════════ SPECIAL NOTICES ═══════════════════════
function buildNotices() {{
    let html = '';
    SPECIAL_NOTICES.forEach(n => {{
        html += `<div class="notice-card"><span class="notice-icon">&#9888;</span>
            <div><h3>${{n.title}}</h3><p>${{n.content}}</p></div></div>`;
    }});
    document.getElementById('notices-content').innerHTML = html || '<div class="empty">No special notices found</div>';
}}

// ═══════════════════════ KNOWN ISSUES ═══════════════════════
function getActiveKnownIssues() {{
    const ver = S.verFilter['known'] || 'all';
    return ver === 'all' ? KNOWN_ISSUES : (DATA[ver]?.known_issues || []);
}}

function buildKnownCatFilter() {{
    const catEl = document.getElementById('ki-cat-filters');
    const cats = [...new Set(getActiveKnownIssues().map(i => i.category))].sort();
    let html = '<span class="flabel">Category:</span><button class="fbtn active" data-cat="all">All</button>';
    cats.forEach(c => {{
        const col = getSeverity(c);
        html += `<button class="fbtn" data-cat="${{c}}"><span class="sev-dot ${{col}}" style="display:inline-block;width:8px;height:8px;vertical-align:middle;margin-right:3px"></span>${{c}}</button>`;
    }});
    catEl.innerHTML = html;
    catEl.addEventListener('click', e => {{
        const btn = e.target.closest('.fbtn');
        if (!btn) return;
        catEl.querySelectorAll('.fbtn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        S.catFilter = btn.dataset.cat;
        renderKnownIssues();
    }});
}}

function buildKnownIssueFilters() {{
    buildTimeline('known', 'known-vt', () => {{
        S.catFilter = 'all';
        buildKnownCatFilter();
        renderKnownIssues();
    }});

    // Severity filter
    const sevEl = document.getElementById('ki-sev-filters');
    sevEl.innerHTML = `<span class="flabel">Severity:</span>
        <button class="fbtn active" data-sev="all">All</button>
        ${{['red','yellow','green','gray'].map(s =>
            `<button class="fbtn" data-sev="${{s}}"><span class="sev-dot ${{s}}" style="display:inline-block;width:8px;height:8px;vertical-align:middle;margin-right:3px"></span>${{s.charAt(0).toUpperCase()+s.slice(1)}}</button>`
        ).join('')}}`;
    sevEl.addEventListener('click', e => {{
        const btn = e.target.closest('.fbtn');
        if (!btn) return;
        sevEl.querySelectorAll('.fbtn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        S.sevFilter = btn.dataset.sev;
        renderKnownIssues();
    }});

    buildKnownCatFilter();
    renderKnownIssues();
}}

function renderKnownIssues() {{
    const term   = (S.search['known'] || '').toLowerCase();
    const issues = getActiveKnownIssues();
    const ver    = S.verFilter['known'] || 'all';
    let html = '', count = 0;
    issues.forEach((issue, idx) => {{
        const cat   = issue.category || 'Unknown';
        const color = getSeverity(cat);
        const bugId = issue['Bug ID'] || '';
        const desc  = issue.Description || '';
        if (S.sevFilter !== 'all' && color !== S.sevFilter) return;
        if (S.catFilter !== 'all' && cat !== S.catFilter) return;
        if (term && !bugId.toLowerCase().includes(term) && !desc.toLowerCase().includes(term) && !cat.toLowerCase().includes(term)) return;
        count++;
        const issueVer = ver === 'all' ? TO_VER : ver;
        const uid = 'ki_' + (ver === 'all' ? '' : ver.replace(/\\./g,'') + '_') + idx;
        const chk = S.selected.has(uid) ? 'checked' : '';
        html += `<div class="issue-card sev-${{color}}">
            <input type="checkbox" class="card-cb" data-uid="${{uid}}" data-sec="known" data-ver="${{issueVer}}" data-id="${{bugId}}" data-desc="${{desc.replace(/"/g,'&quot;')}}" data-cat="${{cat}}" ${{chk}} onclick="toggleCheck(this)" style="margin-top:4px">
            <span class="sev-dot ${{color}}"></span>
            <div style="flex:1">
                <div class="issue-meta">
                    <span class="cat-tag ${{color}}">${{cat}}</span>
                    ${{bugId ? `<span class="card-id">${{bugId}}</span>` : ''}}
                    ${{ver === 'all' ? '' : ''}}
                </div>
                <div class="issue-desc">${{desc}}</div>
            </div>
        </div>`;
    }});
    document.getElementById('known-content').innerHTML = html || '<div class="empty">No issues match filters</div>';
    document.getElementById('ki-count').textContent = count + ' of ' + issues.length + ' issues shown';
}}

// ═══════════════════════ SETTINGS MODAL ═══════════════════════
function openSettings() {{
    buildSettingsUI();
    document.getElementById('settings-overlay').classList.add('open');
}}
function closeSettings() {{
    document.getElementById('settings-overlay').classList.remove('open');
}}

function buildSettingsUI() {{
    const cats = [...new Set(KNOWN_ISSUES.map(i => i.category))].sort();
    let html = '';
    if (cats.length === 0) {{ html = '<p style="color:var(--text-2)">No known issue categories found.</p>'; }}
    else {{
        html += '<div class="section-header">Known Issue Categories</div>';
        cats.forEach(cat => {{
            const cur = getSeverity(cat);
            const id  = 'cat_' + cat.replace(/[^a-z0-9]/gi,'_');
            html += `<div class="cat-row">
                <span class="cat-name">${{cat}}</span>
                <div class="sev-picker">
                    ${{['red','yellow','green','gray'].map(s => `
                        <input type="radio" class="sev-radio" name="${{id}}" id="${{id}}_${{s}}" value="${{s}}" ${{cur===s?'checked':''}} onchange="setCatColor('${{cat}}','${{s}}')">
                        <label for="${{id}}_${{s}}">${{s}}</label>`).join('')}}
                </div>
            </div>`;
        }});
    }}
    document.getElementById('settings-cats').innerHTML = html;
}}

function setCatColor(cat, color) {{
    PRIORITY_CATS[cat] = color;
    savePriorityCategories(PRIORITY_CATS);
    buildKnownIssueFilters();
}}

function resetCategoryDefaults() {{
    PRIORITY_CATS = {{...DEFAULT_PRIORITY}};
    savePriorityCategories(PRIORITY_CATS);
    buildSettingsUI();
    buildKnownIssueFilters();
}}

function exportCategoryConfig() {{
    const blob = new Blob([JSON.stringify(PRIORITY_CATS, null, 2)], {{type:'application/json'}});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'severity_config.json';
    a.click();
    URL.revokeObjectURL(a.href);
}}

function importCategoryConfig(e) {{
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {{
        try {{
            const imported = JSON.parse(ev.target.result);
            Object.assign(PRIORITY_CATS, imported);
            savePriorityCategories(PRIORITY_CATS);
            buildSettingsUI();
            buildKnownIssueFilters();
            alert('Config imported successfully!');
        }} catch(err) {{
            alert('Invalid JSON file: ' + err.message);
        }}
    }};
    reader.readAsText(file);
}}

// ═══════════════════════ EXPORT ═══════════════════════
function getCheckedData() {{
    return [...document.querySelectorAll('.card-cb:checked')].map(cb => ({{
        section: cb.dataset.sec, version: cb.dataset.ver,
        id: cb.dataset.id, description: cb.dataset.desc, category: cb.dataset.cat
    }}));
}}

function getVisibleData() {{
    return [...document.querySelectorAll('.tab-panel.active .card-cb')].map(cb => ({{
        section: cb.dataset.sec, version: cb.dataset.ver,
        id: cb.dataset.id, description: cb.dataset.desc, category: cb.dataset.cat
    }}));
}}

function exportSelected(fmt) {{
    const items = getCheckedData();
    if (!items.length) {{ alert('No items selected. Use checkboxes to select items first.'); return; }}
    doExport(items, fmt, 'selected');
}}

function exportAll(fmt) {{
    const items = getVisibleData();
    if (!items.length) {{ alert('No visible items on current tab.'); return; }}
    doExport(items, fmt, 'all');
}}

function doExport(items, fmt, label) {{
    let content, filename;
    if (fmt === 'csv') {{
        content = 'Section,Version,ID,Category,Description\\n' +
            items.map(i => `"${{i.section}}","${{i.version}}","${{i.id}}","${{i.category}}","${{(i.description||'').replace(/"/g,'""')}}"`).join('\\n');
        filename = `fortigate_${{FROM_VER}}_to_${{TO_VER}}_${{label}}.csv`;
    }} else {{
        content = `FortiGate Upgrade Dashboard (${{FROM_VER}} → ${{TO_VER}}) — ${{label}}\\n${'='*60}\\n\\n` +
            items.map(i => `[${{i.version}}] ${{i.section.toUpperCase()}}${{i.id ? ' | '+i.id : ''}}${{i.category ? ' | '+i.category : ''}}\\n${{i.description}}\\n`).join('\\n');
        filename = `fortigate_${{FROM_VER}}_to_${{TO_VER}}_${{label}}.txt`;
    }}
    const blob = new Blob([content], {{type:'text/plain;charset=utf-8'}});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click();
    URL.revokeObjectURL(a.href);
}}

// ═══════════════════════ KEYBOARD ═══════════════════════
document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') closeSettings();
}});

// ═══════════════════════ THEMES ═══════════════════════
const THEMES = {{
  obsidian: {{
    vars: {{'--bg-0':'#0c0f14','--bg-1':'#12161e','--bg-2':'#181d28','--bg-3':'#1f2533','--bg-4':'#272e3f',
            '--border-1':'#2a3244','--border-2':'#353f55',
            '--text-0':'#f1f3f8','--text-1':'#c8cdd8','--text-2':'#8e95a5','--text-3':'#5e6575',
            '--teal':'#2dd4bf','--teal-dim':'rgba(45,212,191,.12)',
            '--sky':'#38bdf8','--sky-dim':'rgba(56,189,248,.12)',
            '--violet':'#a78bfa','--violet-dim':'rgba(167,139,250,.12)',
            '--amber':'#fbbf24','--amber-dim':'rgba(251,191,36,.12)',
            '--rose':'#fb7185','--rose-dim':'rgba(251,113,133,.12)',
            '--emerald':'#34d399','--emerald-dim':'rgba(52,211,153,.12)',
            '--slate':'#64748b','--slate-dim':'rgba(100,116,139,.15)'}}
  }},
  fortinet: {{
    // Matches the Fortinet docs site: white content, dark navy nav, orange accents
    vars: {{'--bg-0':'#f2f4f7','--bg-1':'#ffffff','--bg-2':'#ffffff','--bg-3':'#f0f2f5','--bg-4':'#e3e8ed',
            '--border-1':'#d0d8e0','--border-2':'#a8b8c8',
            '--text-0':'#0f1d2c','--text-1':'#1e3347','--text-2':'#4a6070','--text-3':'#8090a0',
            '--teal':'#f5821f','--teal-dim':'rgba(245,130,31,.1)',
            '--sky':'#1c5fa8','--sky-dim':'rgba(28,95,168,.1)',
            '--violet':'#1c2d3a','--violet-dim':'rgba(28,45,58,.08)',
            '--amber':'#e67e22','--amber-dim':'rgba(230,126,34,.1)',
            '--rose':'#e74c3c','--rose-dim':'rgba(231,76,60,.1)',
            '--emerald':'#27ae60','--emerald-dim':'rgba(39,174,96,.1)',
            '--slate':'#6c7a89','--slate-dim':'rgba(108,122,137,.12)'}}
  }},
  arctic: {{
    // Clean light theme with blue accents
    vars: {{'--bg-0':'#eef2f7','--bg-1':'#ffffff','--bg-2':'#f5f8fc','--bg-3':'#e8edf5','--bg-4':'#dae2ee',
            '--border-1':'#c4d0df','--border-2':'#9db0c8',
            '--text-0':'#0b1929','--text-1':'#1a2e42','--text-2':'#3d5470','--text-3':'#7090a8',
            '--teal':'#0ea5e9','--teal-dim':'rgba(14,165,233,.12)',
            '--sky':'#3b82f6','--sky-dim':'rgba(59,130,246,.12)',
            '--violet':'#7c3aed','--violet-dim':'rgba(124,58,237,.1)',
            '--amber':'#d97706','--amber-dim':'rgba(217,119,6,.1)',
            '--rose':'#e11d48','--rose-dim':'rgba(225,29,72,.1)',
            '--emerald':'#059669','--emerald-dim':'rgba(5,150,105,.1)',
            '--slate':'#5a7080','--slate-dim':'rgba(90,112,128,.12)'}}
  }},
  midnight: {{
    // Deep indigo — darker and more purple than Obsidian
    vars: {{'--bg-0':'#07071a','--bg-1':'#0d0d28','--bg-2':'#111136','--bg-3':'#171744','--bg-4':'#1d1d52',
            '--border-1':'#282868','--border-2':'#383880',
            '--text-0':'#eeeeff','--text-1':'#b8b8e8','--text-2':'#7070b0','--text-3':'#484888',
            '--teal':'#818cf8','--teal-dim':'rgba(129,140,248,.15)',
            '--sky':'#38bdf8','--sky-dim':'rgba(56,189,248,.12)',
            '--violet':'#c084fc','--violet-dim':'rgba(192,132,252,.12)',
            '--amber':'#fbbf24','--amber-dim':'rgba(251,191,36,.12)',
            '--rose':'#f87171','--rose-dim':'rgba(248,113,113,.12)',
            '--emerald':'#4ade80','--emerald-dim':'rgba(74,222,128,.12)',
            '--slate':'#6366f1','--slate-dim':'rgba(99,102,241,.15)'}}
  }},
  carbon: {{
    // Near-black with cyan accent — terminal / hacker aesthetic
    vars: {{'--bg-0':'#09090b','--bg-1':'#111113','--bg-2':'#18181b','--bg-3':'#1f1f24','--bg-4':'#27272c',
            '--border-1':'#3f3f46','--border-2':'#52525b',
            '--text-0':'#fafafa','--text-1':'#d4d4d8','--text-2':'#71717a','--text-3':'#52525b',
            '--teal':'#22d3ee','--teal-dim':'rgba(34,211,238,.1)',
            '--sky':'#60a5fa','--sky-dim':'rgba(96,165,250,.1)',
            '--violet':'#e879f9','--violet-dim':'rgba(232,121,249,.1)',
            '--amber':'#fbbf24','--amber-dim':'rgba(251,191,36,.1)',
            '--rose':'#fb7185','--rose-dim':'rgba(251,113,133,.1)',
            '--emerald':'#34d399','--emerald-dim':'rgba(52,211,153,.1)',
            '--slate':'#a1a1aa','--slate-dim':'rgba(161,161,170,.1)'}}
  }}
}};

function applyTheme(name) {{
    const theme = THEMES[name];
    if (!theme) return;
    const root = document.documentElement;
    Object.entries(theme.vars).forEach(([k, v]) => root.style.setProperty(k, v));
    document.querySelectorAll('.theme-dot').forEach(d => d.classList.toggle('active', d.dataset.theme === name));
    try {{ localStorage.setItem('fg_theme', name); }} catch(e) {{}}
}}

document.getElementById('theme-switcher').addEventListener('click', e => {{
    const dot = e.target.closest('.theme-dot');
    if (dot) applyTheme(dot.dataset.theme);
}});

// ═══════════════════════ INIT ═══════════════════════
// Restore saved theme (skip obsidian — it's already the CSS default)
(function() {{
    try {{
        const saved = localStorage.getItem('fg_theme');
        if (saved && saved !== 'obsidian') applyTheme(saved);
    }} catch(e) {{}}
}})();
buildOverview();
['cli','default','tablesize','features'].forEach(sec => {{
    buildTimeline(sec, sec + '-vt');
    updateSrcLink(sec, 'all');
    renderSection(sec);
}});
buildFeatCatFilters();
buildDiff();
buildNotices();
updateSrcLink('known', 'all');
buildKnownIssueFilters();
</script>
</body>
</html>"""
