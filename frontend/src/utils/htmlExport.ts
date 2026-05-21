import type { JobDetail, TableItem, Feature, KnownIssue, Notice } from "../types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function esc(s: unknown): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Safe JSON for embedding inside <script> tags — escapes < and > */
function safeJson(v: unknown): string {
  return JSON.stringify(v)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e");
}

function count(job: JobDetail, key: string): number {
  return (job.versions ?? []).reduce(
    (s, v) => s + ((job.all_data?.[v] as Record<string, unknown[]>)?.[key]?.length ?? 0),
    0
  );
}

// ── Extended-section discovery ─────────────────────────────────────────────────

const LEGACY_KEYS = new Set([
  "changes_cli",
  "changes_default",
  "changes_tablesize",
  "new_features",
  "known_issues",
  "resolved-issues",
  "resolved-issue",
  "new-features-and-enhancements",
  "new-features-or-enhancements",
]);

function getExtendedSlugs(
  job: JobDetail
): { slug: string; label: string; isIssues: boolean; count: number }[] {
  const seen = new Map<string, { label: string; isIssues: boolean; count: number }>();
  for (const ver of job.versions ?? []) {
    const verData = job.all_data?.[ver] as Record<string, unknown> | undefined;
    if (!verData) continue;
    for (const [key, value] of Object.entries(verData)) {
      if (LEGACY_KEYS.has(key) || key.startsWith("_") || value == null) continue;

      const isArr = Array.isArray(value);
      const first = isArr ? (value as unknown[])[0] : null;
      const isIssues =
        isArr && first != null && typeof first === "object" && "Bug ID" in (first as object);

      // Determine whether there is real content to show
      const hasContent = isArr
        ? (value as unknown[]).length > 0
        : typeof value === "object" && ((value as any)?.blocks?.length ?? 0) > 0;
      if (!hasContent) continue;

      const existing = seen.get(key);
      if (existing) {
        if (isArr) existing.count = existing.count === -1 ? -1 : existing.count + (value as unknown[]).length;
      } else {
        const label = key.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        // -1 = rich/prose section (no item count); positive = issue rows
        const cnt = isArr ? (value as unknown[]).length : -1;
        seen.set(key, { label, isIssues, count: cnt });
      }
    }
  }
  return [...seen.entries()].map(([slug, meta]) => ({ slug, ...meta }));
}

function resolvedKey(job: JobDetail): string {
  return count(job, "resolved-issues") > 0 ? "resolved-issues" : "resolved-issue";
}

function docsUrlsFor(job: JobDetail, sectionKey: string): Record<string, string> {
  const urls: Record<string, string> = {};
  for (const ver of job.versions ?? []) {
    const u = (job.all_data?.[ver] as any)?._section_urls?.[sectionKey];
    if (u) urls[ver] = u;
  }
  return urls;
}

function docsLinkTag(
  tabId: string,
  urls: Record<string, string>,
  versions: string[]
): string {
  let href = "";
  for (const ver of versions) {
    if (urls[ver]) href = urls[ver];
  }
  const hidden = href ? "" : ` style="display:none"`;
  return (
    `<a id="${esc(tabId)}-docs-link" class="docs-link" href="${esc(href)}" target="_blank" rel="noopener"${hidden}>` +
    `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">` +
    `<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>` +
    `<polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>` +
    `</svg>View in Docs</a>`
  );
}

// ── Section definitions ───────────────────────────────────────────────────────

export interface ExportSection {
  id: string;
  label: string;
  count: number;
}

export function getAvailableSections(job: JobDetail): ExportSection[] {
  const sections: ExportSection[] = [
    { id: "overview",  label: "Overview",         count: -1 },
    { id: "notices",   label: "Special Notices",  count: job.special_notices?.length ?? 0 },
    { id: "cli",       label: "CLI Changes",       count: count(job, "changes_cli") },
    { id: "default",   label: "Default Behavior", count: count(job, "changes_default") },
    { id: "tablesize", label: "Table Size",        count: count(job, "changes_tablesize") },
    { id: "features",  label: "New Features",      count: count(job, "new_features") },
    { id: "issues",    label: "Known Issues",      count: count(job, "known_issues") },
  ];

  const resolvedCount = count(job, "resolved-issues") + count(job, "resolved-issue");
  if (resolvedCount > 0)
    sections.push({ id: "resolved", label: "Resolved Issues", count: resolvedCount });

  for (const { slug, label, count: c } of getExtendedSlugs(job))
    sections.push({ id: `ext:${slug}`, label, count: c });

  return sections.filter((s) => s.count !== 0);
}

// ── Row builders ──────────────────────────────────────────────────────────────

function simpleRows(
  job: JobDetail,
  key: string,
  tabId: string,
  sectionLabel: string
): string {
  const rows: string[] = [];
  for (const ver of job.versions ?? []) {
    for (const item of ((job.all_data?.[ver] as Record<string, TableItem[]>)?.[key] ?? [])) {
      const id   = String(item["Bug ID"]    ?? "");
      const desc = String(item.Description  ?? "");
      const srch = `${ver} ${id} ${desc}`.toLowerCase();
      rows.push(
        `<tr data-version="${esc(ver)}" data-search="${esc(srch)}" ` +
        `data-composite-id="${esc(tabId)}|${esc(ver)}|${esc(id)}" ` +
        `data-section-label="${esc(sectionLabel)}" ` +
        `data-id="${esc(id)}" data-desc="${esc(desc)}" data-category="">` +
        `<td class="cb-cell"><input type="checkbox" onchange="toggleRow(this)"></td>` +
        `<td class="mono ver">${esc(ver)}</td>` +
        `<td class="mono id">${esc(id)}</td>` +
        `<td class="desc">${esc(desc)}</td></tr>`
      );
    }
  }
  return rows.join("\n");
}

function featuresRows(job: JobDetail, tabId: string, sectionLabel: string): string {
  const rows: string[] = [];
  for (const ver of job.versions ?? []) {
    for (const item of ((job.all_data?.[ver] as Record<string, Feature[]>)?.new_features ?? [])) {
      const id   = String(item["Feature ID"] ?? "");
      const desc = String(item.Description   ?? "");
      const cat  = String(item.category      ?? "");
      const srch = `${ver} ${cat} ${id} ${desc}`.toLowerCase();
      rows.push(
        `<tr data-version="${esc(ver)}" data-category="${esc(cat)}" data-search="${esc(srch)}" ` +
        `data-composite-id="${esc(tabId)}|${esc(ver)}|${esc(id)}" ` +
        `data-section-label="${esc(sectionLabel)}" ` +
        `data-id="${esc(id)}" data-desc="${esc(desc)}">` +
        `<td class="cb-cell"><input type="checkbox" onchange="toggleRow(this)"></td>` +
        `<td class="mono ver">${esc(ver)}</td>` +
        `<td class="cat">${esc(cat)}</td>` +
        `<td class="mono id feat-id">${esc(id)}</td>` +
        `<td class="desc">${esc(desc)}</td></tr>`
      );
    }
  }
  return rows.join("\n");
}

function issueRowsFor(
  job: JobDetail,
  key: string,
  tabId: string,
  sectionLabel: string
): string {
  const rows: string[] = [];
  for (const ver of job.versions ?? []) {
    for (const item of ((job.all_data?.[ver] as Record<string, KnownIssue[]>)?.[key] ?? [])) {
      const id   = String(item["Bug ID"]   ?? "");
      const desc = String(item.Description ?? "");
      const cat  = String(item.category    ?? "");
      const srch = `${ver} ${cat} ${id} ${desc}`.toLowerCase();
      rows.push(
        `<tr data-version="${esc(ver)}" data-category="${esc(cat)}" data-search="${esc(srch)}" ` +
        `data-composite-id="${esc(tabId)}|${esc(ver)}|${esc(id)}" ` +
        `data-section-label="${esc(sectionLabel)}" ` +
        `data-id="${esc(id)}" data-desc="${esc(desc)}">` +
        `<td class="cb-cell"><input type="checkbox" onchange="toggleRow(this)"></td>` +
        `<td class="mono ver">${esc(ver)}</td>` +
        `<td class="cat">${esc(cat)}</td>` +
        `<td class="mono id bug-id">${esc(id)}</td>` +
        `<td class="desc">${esc(desc)}</td></tr>`
      );
    }
  }
  return rows.join("\n");
}

function categoryOptions(job: JobDetail, key: string): string {
  const cats = new Set<string>();
  for (const ver of job.versions ?? []) {
    for (const item of ((job.all_data?.[ver] as Record<string, Array<{ category: string }>>)?.[key] ?? [])) {
      if (item.category) cats.add(item.category);
    }
  }
  return [...cats]
    .sort()
    .map((c) => `<option value="${esc(c)}">${esc(c)}</option>`)
    .join("\n");
}

function versionOptions(job: JobDetail): string {
  return (job.versions ?? [])
    .map((v) => `<option value="${esc(v)}">${esc(v)}</option>`)
    .join("\n");
}

// ── Panel builders ────────────────────────────────────────────────────────────

function overviewPanel(job: JobDetail): string {
  const versions = job.versions ?? [];
  const allData  = job.all_data ?? {};

  const SECTIONS = [
    { key: "changes_cli",       label: "CLI Changes",       color: "#0369a1" },
    { key: "changes_default",   label: "Default Behavior",  color: "#92400e" },
    { key: "changes_tablesize", label: "Table Size",        color: "#5b21b6" },
    { key: "new_features",      label: "New Features",      color: "#047857" },
    { key: "known_issues",      label: "Known Issues",      color: "#b91c1c" },
  ];

  const totals = SECTIONS.map(({ key }) =>
    versions.reduce(
      (s, v) => s + ((allData[v] as Record<string, unknown[]>)?.[key]?.length ?? 0),
      0
    )
  );

  const cards = SECTIONS.map(
    ({ label, color }, i) => `
    <div class="card" style="border-top:2px solid ${color}">
      <div class="card-num" style="color:${color}">${totals[i]}</div>
      <div class="card-label">${label}</div>
    </div>`
  ).join("");

  const headerCols = SECTIONS.map(
    ({ label, color }) =>
      `<th><span class="dot" style="background:${color}"></span>${label}</th>`
  ).join("");

  const bodyRows = versions
    .map((ver) => {
      const cells = SECTIONS.map(({ key, color }) => {
        const n = (allData[ver] as Record<string, unknown[]>)?.[key]?.length ?? 0;
        return n > 0
          ? `<td style="color:${color};font-weight:600">${n}</td>`
          : `<td class="zero">–</td>`;
      }).join("");
      return `<tr><td class="mono ver">${esc(ver)}</td>${cells}</tr>`;
    })
    .join("\n");

  return `
  <div class="cards-grid">${cards}</div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Version</th>${headerCols}</tr></thead>
      <tbody>${bodyRows}</tbody>
    </table>
  </div>`;
}

function noticesPanel(job: JobDetail): string {
  const notices: Notice[] = job.special_notices ?? [];
  if (notices.length === 0) return `<p class="empty">No special notices found.</p>`;
  return notices
    .map(
      (n) => `
  <div class="notice-card">
    <div class="notice-icon">⚠</div>
    <div>
      <div class="notice-title">${esc(n.title)}</div>
      <div class="notice-body">${esc(n.content)}</div>
    </div>
  </div>`
    )
    .join("\n");
}

function simpleTablePanel(
  job: JobDetail,
  key: string,
  idLabel: string,
  tabId: string,
  docsUrls: Record<string, string>,
  sectionLabel: string
): string {
  const rows    = simpleRows(job, key, tabId, sectionLabel);
  const verOpts = versionOptions(job);
  const versions = job.versions ?? [];
  return `
  <div class="toolbar">
    <input class="search-input" type="text" placeholder="Search…" oninput="filterTable('${tabId}', this.value)">
    <select class="ver-select" onchange="filterVersion('${tabId}', this.value)">
      <option value="">All versions</option>${verOpts}
    </select>
    <span class="row-count" id="${tabId}-count"></span>
    ${docsLinkTag(tabId, docsUrls, versions)}
  </div>
  <div class="table-wrap">
    <table id="${tabId}-table">
      <thead><tr>
        <th class="cb-cell"><input type="checkbox" title="Select all" onchange="toggleAll('${tabId}', this)"></th>
        <th>Version</th><th>${esc(idLabel)}</th><th>Description</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

function featuresPanel(job: JobDetail): string {
  const rows     = featuresRows(job, "features", "New Features");
  const verOpts  = versionOptions(job);
  const catOpts  = categoryOptions(job, "new_features");
  const docsUrls = docsUrlsFor(job, "new_features");
  const versions = job.versions ?? [];
  return `
  <div class="toolbar">
    <input class="search-input" type="text" placeholder="Search features…" oninput="filterTable('features', this.value)">
    <select class="ver-select" onchange="filterVersion('features', this.value)">
      <option value="">All versions</option>${verOpts}
    </select>
    <select class="cat-select" onchange="filterCategory('features', this.value)">
      <option value="">All categories</option>${catOpts}
    </select>
    <span class="row-count" id="features-count"></span>
    ${docsLinkTag("features", docsUrls, versions)}
  </div>
  <div class="table-wrap">
    <table id="features-table">
      <thead><tr>
        <th class="cb-cell"><input type="checkbox" title="Select all" onchange="toggleAll('features', this)"></th>
        <th>Version</th><th>Category</th><th>Feature ID</th><th>Description</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

function issuesPanel(job: JobDetail): string {
  const rows     = issueRowsFor(job, "known_issues", "issues", "Known Issues");
  const verOpts  = versionOptions(job);
  const catOpts  = categoryOptions(job, "known_issues");
  const docsUrls = docsUrlsFor(job, "known_issues");
  const versions = job.versions ?? [];
  return `
  <div class="toolbar">
    <input class="search-input" type="text" placeholder="Search issues…" oninput="filterTable('issues', this.value)">
    <select class="ver-select" onchange="filterVersion('issues', this.value)">
      <option value="">All versions</option>${verOpts}
    </select>
    <select class="cat-select" onchange="filterCategory('issues', this.value)">
      <option value="">All categories</option>${catOpts}
    </select>
    <span class="row-count" id="issues-count"></span>
    ${docsLinkTag("issues", docsUrls, versions)}
  </div>
  <div class="table-wrap">
    <table id="issues-table">
      <thead><tr>
        <th class="cb-cell"><input type="checkbox" title="Select all" onchange="toggleAll('issues', this)"></th>
        <th>Version</th><th>Category</th><th>Bug ID</th><th>Description</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

function resolvedPanel(job: JobDetail): string {
  const key      = resolvedKey(job);
  const rows     = issueRowsFor(job, key, "resolved", "Resolved Issues");
  const verOpts  = versionOptions(job);
  const catOpts  = categoryOptions(job, key);
  const docsUrls = docsUrlsFor(job, key);
  const versions = job.versions ?? [];
  return `
  <div class="toolbar">
    <input class="search-input" type="text" placeholder="Search resolved issues…" oninput="filterTable('resolved', this.value)">
    <select class="ver-select" onchange="filterVersion('resolved', this.value)">
      <option value="">All versions</option>${verOpts}
    </select>
    <select class="cat-select" onchange="filterCategory('resolved', this.value)">
      <option value="">All categories</option>${catOpts}
    </select>
    <span class="row-count" id="resolved-count"></span>
    ${docsLinkTag("resolved", docsUrls, versions)}
  </div>
  <div class="table-wrap">
    <table id="resolved-table">
      <thead><tr>
        <th class="cb-cell"><input type="checkbox" title="Select all" onchange="toggleAll('resolved', this)"></th>
        <th>Version</th><th>Category</th><th>Bug ID</th><th>Description</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

/** Render a RichSection {title, blocks[]} as HTML */
function richSectionHtml(section: { title?: string; blocks?: Array<{ type: string; level?: number; text?: string; items?: string[]; headers?: string[]; rows?: string[][] }> }): string {
  const parts: string[] = [];
  for (const block of section.blocks ?? []) {
    if (block.type === "heading") {
      const lvl = Math.min(Math.max(block.level ?? 2, 2), 5);
      const cls = lvl === 2 ? "rich-h2" : lvl === 3 ? "rich-h3" : "rich-h4";
      parts.push(`<div class="${cls}">${esc(block.text ?? "")}</div>`);
    } else if (block.type === "paragraph") {
      parts.push(`<p class="rich-p">${esc(block.text ?? "")}</p>`);
    } else if (block.type === "list") {
      const lis = (block.items ?? []).map((i) => `<li class="rich-li">${esc(i)}</li>`).join("");
      parts.push(`<ul class="rich-ul">${lis}</ul>`);
    } else if (block.type === "table") {
      const thead = block.headers?.length
        ? `<thead><tr>${block.headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>`
        : "";
      const tbody = (block.rows ?? [])
        .map((row) => `<tr>${row.map((cell) => `<td class="desc">${esc(cell)}</td>`).join("")}</tr>`)
        .join("");
      parts.push(`<div class="table-wrap" style="margin:8px 0">${
        `<table><${thead ? "" : ""}${thead}<tbody>${tbody}</tbody></table>`
      }</div>`);
    }
  }
  return parts.join("\n");
}

function extendedPanel(
  job: JobDetail,
  slug: string,
  isIssues: boolean,
  tabId: string,
  sectionLabel: string
): string {
  const versions = job.versions ?? [];
  const docsUrls = docsUrlsFor(job, slug);

  if (isIssues) {
    const rows    = issueRowsFor(job, slug, tabId, sectionLabel);
    const verOpts = versionOptions(job);
    const catOpts = categoryOptions(job, slug);
    return `
  <div class="toolbar">
    <input class="search-input" type="text" placeholder="Search…" oninput="filterTable('${tabId}', this.value)">
    <select class="ver-select" onchange="filterVersion('${tabId}', this.value)">
      <option value="">All versions</option>${verOpts}
    </select>
    <select class="cat-select" onchange="filterCategory('${tabId}', this.value)">
      <option value="">All categories</option>${catOpts}
    </select>
    <span class="row-count" id="${esc(tabId)}-count"></span>
    ${docsLinkTag(tabId, docsUrls, versions)}
  </div>
  <div class="table-wrap">
    <table id="${esc(tabId)}-table">
      <thead><tr>
        <th class="cb-cell"><input type="checkbox" title="Select all" onchange="toggleAll('${tabId}', this)"></th>
        <th>Version</th><th>Category</th><th>Bug ID</th><th>Description</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
  }

  // Non-issues: render with a version-selector UI (one version visible at a time)
  const hasUrls = Object.keys(docsUrls).length > 0;

  // Collect versions that actually have content for this slug
  const richVersions: string[] = [];
  const richInners: Record<string, string> = {};

  for (const ver of versions) {
    const raw = (job.all_data?.[ver] as any)?.[slug];
    if (!raw) continue;

    let inner = "";
    if (Array.isArray(raw) && raw.length > 0) {
      inner = raw
        .map((item: any) => {
          const desc = String(item.Description ?? item.content ?? item.text ?? "");
          return desc ? `<p class="ext-item">${esc(desc)}</p>` : "";
        })
        .filter(Boolean)
        .join("\n");
    } else if (!Array.isArray(raw) && typeof raw === "object" && raw.blocks?.length) {
      inner = richSectionHtml(raw);
    }

    if (inner) {
      richVersions.push(ver);
      richInners[ver] = inner;
    }
  }

  if (richVersions.length === 0) {
    return `<p class="empty">No data found.</p>`;
  }

  const safeId = esc(tabId);

  // Version selector buttons
  const verBtns = richVersions.length > 1
    ? richVersions.map((ver, i) =>
        `<button class="ext-ver-btn${i === 0 ? " active" : ""}" ` +
        `data-tab="${safeId}" data-ver="${esc(ver)}" ` +
        `onclick="showRichVer('${tabId}','${esc(ver)}')">${esc(ver)}</button>`
      ).join("")
    : "";

  // Version content divs
  const verDivs = richVersions.map((ver, i) =>
    `<div class="ext-rich-ver" data-tab="${safeId}" data-ver="${esc(ver)}"` +
    `${i === 0 ? "" : ' style="display:none"'}>${richInners[ver]}</div>`
  ).join("\n");

  return `
  <div class="ext-ver-selector">
    ${verBtns}
    ${hasUrls ? docsLinkTag(tabId, docsUrls, richVersions) : ""}
  </div>
  ${verDivs}`;
}

// ── Main export ───────────────────────────────────────────────────────────────

export function generateHtml(job: JobDetail, selectedIds: Set<string>): string {
  const versions  = job.versions ?? [];
  const generated = job.completed_at
    ? new Date(job.completed_at).toLocaleString()
    : new Date().toLocaleString();

  const rKey         = resolvedKey(job);
  const resolvedCount = count(job, "resolved-issues") + count(job, "resolved-issue");
  const extSlugs     = getExtendedSlugs(job);

  // ── Build docs-URLs map (tabId → {version → url}) ─────────────────────────
  const docsUrlsMap: Record<string, Record<string, string>> = {};

  const fixedSources: { id: string; key: string }[] = [
    { id: "cli",       key: "changes_cli" },
    { id: "default",   key: "changes_default" },
    { id: "tablesize", key: "changes_tablesize" },
    { id: "features",  key: "new_features" },
    { id: "issues",    key: "known_issues" },
    { id: "resolved",  key: rKey },
  ];
  for (const { id, key } of fixedSources) {
    if (selectedIds.has(id)) {
      const urls = docsUrlsFor(job, key);
      if (Object.keys(urls).length > 0) docsUrlsMap[id] = urls;
    }
  }
  for (const { slug } of extSlugs) {
    const extId = `ext:${slug}`;
    if (selectedIds.has(extId)) {
      const urls = docsUrlsFor(job, slug);
      if (Object.keys(urls).length > 0) docsUrlsMap[extId] = urls;
    }
  }

  // ── Build search index ─────────────────────────────────────────────────────
  type SearchItem = {
    compositeId: string;
    tabId: string;
    tabLabel: string;
    sectionLabel: string;
    version: string;
    id: string;
    category: string;
    desc: string;
    searchStr: string;
  };
  const searchIndex: SearchItem[] = [];

  function addItems(tabId: string, label: string, key: string, idField: string) {
    for (const ver of versions) {
      const items = (job.all_data?.[ver] as any)?.[key];
      if (!Array.isArray(items)) continue;
      for (const item of items) {
        const id   = String((item as any)[idField]     ?? "");
        const desc = String((item as any).Description  ?? "");
        const cat  = String((item as any).category     ?? "");
        searchIndex.push({
          compositeId: `${tabId}|${ver}|${id}`,
          tabId,
          tabLabel: label,
          sectionLabel: label,
          version: ver,
          id,
          category: cat,
          desc,
          searchStr: `${ver} ${cat} ${id} ${desc}`.toLowerCase(),
        });
      }
    }
  }

  if (selectedIds.has("cli"))       addItems("cli",       "CLI Changes",      "changes_cli",       "Bug ID");
  if (selectedIds.has("default"))   addItems("default",   "Default Behavior", "changes_default",   "Bug ID");
  if (selectedIds.has("tablesize")) addItems("tablesize", "Table Size",       "changes_tablesize", "Bug ID");
  if (selectedIds.has("features"))  addItems("features",  "New Features",     "new_features",      "Feature ID");
  if (selectedIds.has("issues"))    addItems("issues",    "Known Issues",     "known_issues",      "Bug ID");
  if (selectedIds.has("resolved"))  addItems("resolved",  "Resolved Issues",  rKey,                "Bug ID");
  for (const { slug, label: extLabel, isIssues } of extSlugs) {
    const extId = `ext:${slug}`;
    if (selectedIds.has(extId) && isIssues) addItems(extId, extLabel, slug, "Bug ID");
  }

  // ── ALL_PANELS ─────────────────────────────────────────────────────────────
  const ALL_PANELS: { id: string; label: string; count: number | undefined; fn: () => string }[] = [
    { id: "overview",  label: "Overview",         count: undefined,                    fn: () => overviewPanel(job) },
    { id: "notices",   label: "Special Notices",  count: job.special_notices?.length,  fn: () => noticesPanel(job) },
    { id: "cli",       label: "CLI Changes",       count: count(job, "changes_cli"),   fn: () => simpleTablePanel(job, "changes_cli",       "Bug ID", "cli",       docsUrlsFor(job, "changes_cli"),       "CLI Changes") },
    { id: "default",   label: "Default Behavior", count: count(job, "changes_default"), fn: () => simpleTablePanel(job, "changes_default",   "Bug ID", "default",   docsUrlsFor(job, "changes_default"),   "Default Behavior") },
    { id: "tablesize", label: "Table Size",        count: count(job, "changes_tablesize"), fn: () => simpleTablePanel(job, "changes_tablesize", "Bug ID", "tablesize", docsUrlsFor(job, "changes_tablesize"), "Table Size") },
    { id: "features",  label: "New Features",      count: count(job, "new_features"),  fn: () => featuresPanel(job) },
    { id: "issues",    label: "Known Issues",      count: count(job, "known_issues"),  fn: () => issuesPanel(job) },
    ...(resolvedCount > 0
      ? [{ id: "resolved", label: "Resolved Issues", count: resolvedCount, fn: () => resolvedPanel(job) }]
      : []),
    ...extSlugs.map(({ slug, label: extLabel, isIssues, count: extCount }) => ({
      id: `ext:${slug}`,
      label: extLabel,
      count: extCount,
      fn: () => extendedPanel(job, slug, isIssues, `ext:${slug}`, extLabel),
    })),
  ];

  const panels = ALL_PANELS.filter((p) => selectedIds.has(p.id));
  if (panels.length === 0) return "";

  const tabButtons = panels
    .map((p, i) => {
      const badge =
        (p.count !== undefined && p.count > 0) ? `<span class="tab-badge">${p.count}</span>` : "";
      return (
        `<button class="tab-btn${i === 0 ? " active" : ""}" ` +
        `onclick="showTab('${p.id}')" id="btn-${p.id}">${esc(p.label)}${badge}</button>`
      );
    })
    .join("\n");

  const tabPanels = panels
    .map(
      (p, i) =>
        `<div class="tab-panel${i === 0 ? " active" : ""}" id="panel-${p.id}">${p.fn()}</div>`
    )
    .join("\n");

  // ── Inline JavaScript ──────────────────────────────────────────────────────

  const js = `
const _sel = new Map();
const _searchIndex = ${safeJson(searchIndex)};
const _docsUrls    = ${safeJson(docsUrlsMap)};

// ── Per-panel filter state ─────────────────────────────────────────────────
const _state = {};
function _getState(tabId) {
  if (!_state[tabId]) _state[tabId] = { search: '', version: '', category: '' };
  return _state[tabId];
}

function _applyFilter(tabId) {
  const s = _getState(tabId);
  const table = document.getElementById(tabId + '-table');
  if (!table) return;
  let visible = 0;
  table.querySelectorAll('tbody tr').forEach(function(row) {
    const matchSearch = !s.search   || (row.dataset.search   || '').includes(s.search.toLowerCase());
    const matchVer    = !s.version  || row.dataset.version   === s.version;
    const matchCat    = !s.category || row.dataset.category  === s.category;
    const show = matchSearch && matchVer && matchCat;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  const el = document.getElementById(tabId + '-count');
  if (el) el.textContent = visible + ' item' + (visible !== 1 ? 's' : '');
  _updateHeaderCb(table);
}

function filterTable(tabId, val)    { _getState(tabId).search   = val; _applyFilter(tabId); }
function filterVersion(tabId, val)  { _getState(tabId).version  = val; _applyFilter(tabId); updateDocsLink(tabId, val); }
function filterCategory(tabId, val) { _getState(tabId).category = val; _applyFilter(tabId); }

// ── Tab switching ──────────────────────────────────────────────────────────
function showTab(id) {
  document.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
  document.querySelectorAll('.tab-btn').forEach(function(b)   { b.classList.remove('active'); });
  var panel = document.getElementById('panel-' + id);
  var btn   = document.getElementById('btn-'   + id);
  if (panel) panel.classList.add('active');
  if (btn)   btn.classList.add('active');
}

// ── Docs link ──────────────────────────────────────────────────────────────
function updateDocsLink(tabId, version) {
  var link = document.getElementById(tabId + '-docs-link');
  if (!link) return;
  var urls = _docsUrls[tabId] || {};
  var url;
  if (version) {
    url = urls[version];
  } else {
    var entries = Object.entries(urls);
    url = entries.length > 0 ? entries[entries.length - 1][1] : undefined;
  }
  if (url) { link.href = url; link.style.display = ''; }
  else      { link.style.display = 'none'; }
}

// ── Selection ──────────────────────────────────────────────────────────────
function _rowMeta(row) {
  return {
    sectionLabel: row.dataset.sectionLabel || '',
    version:      row.dataset.version      || '',
    id:           row.dataset.id           || '',
    category:     row.dataset.category     || '',
    desc:         row.dataset.desc         || ''
  };
}

function toggleRow(cb) {
  var row = cb.closest('tr');
  if (!row) return;
  var cid = row.dataset.compositeId;
  if (!cid) return;
  if (cb.checked) { row.classList.add('row-selected');    _sel.set(cid, _rowMeta(row)); }
  else            { row.classList.remove('row-selected'); _sel.delete(cid); }
  _updateFooter();
  var table = row.closest('table');
  if (table) _updateHeaderCb(table);
}

function _updateHeaderCb(table) {
  var headerCb = table.querySelector('thead input[type="checkbox"]');
  if (!headerCb) return;
  var allCbs = Array.from(table.querySelectorAll('tbody tr')).filter(function(r) {
    return r.style.display !== 'none';
  }).map(function(r) { return r.querySelector('input[type="checkbox"]'); }).filter(Boolean);
  if (allCbs.length === 0) { headerCb.checked = false; headerCb.indeterminate = false; return; }
  var checkedN = allCbs.filter(function(c) { return c.checked; }).length;
  headerCb.checked       = checkedN === allCbs.length;
  headerCb.indeterminate = checkedN > 0 && checkedN < allCbs.length;
}

function toggleAll(tabId, cb) {
  var table = document.getElementById(tabId + '-table');
  if (!table) return;
  table.querySelectorAll('tbody tr').forEach(function(row) {
    if (row.style.display === 'none') return;
    var rowCb = row.querySelector('input[type="checkbox"]');
    if (!rowCb) return;
    rowCb.checked = cb.checked;
    var cid = row.dataset.compositeId;
    if (!cid) return;
    if (cb.checked) { row.classList.add('row-selected');    _sel.set(cid, _rowMeta(row)); }
    else            { row.classList.remove('row-selected'); _sel.delete(cid); }
  });
  _updateFooter();
}

function toggleAllGlobal(cb) {
  var tbody = document.getElementById('global-results-body');
  if (!tbody) return;
  tbody.querySelectorAll('tr').forEach(function(row) {
    var rowCb = row.querySelector('input[type="checkbox"]');
    if (!rowCb) return;
    rowCb.checked = cb.checked;
    var cid = row.dataset.compositeId;
    if (!cid) return;
    if (cb.checked) { row.classList.add('row-selected');    _sel.set(cid, _rowMeta(row)); }
    else            { row.classList.remove('row-selected'); _sel.delete(cid); }
  });
  _updateFooter();
}

// ── Global search ──────────────────────────────────────────────────────────
function _escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function onGlobalSearch(val) {
  var q = val.trim().toLowerCase();
  var tabNav     = document.querySelector('.tab-nav');
  var panelsWrap = document.getElementById('tab-panels-wrap');
  var resultsDiv = document.getElementById('global-results');
  if (tabNav)     tabNav.style.display     = q ? 'none' : '';
  if (panelsWrap) panelsWrap.style.display = q ? 'none' : '';
  resultsDiv.style.display = q ? '' : 'none';
  if (!q) return;
  var matches = _searchIndex.filter(function(item) { return item.searchStr.includes(q); });
  var countEl = document.getElementById('global-results-count');
  if (countEl) countEl.textContent = matches.length + ' result' + (matches.length !== 1 ? 's' : '');
  _renderGlobalResults(matches);
}

function _renderGlobalResults(items) {
  var tbody = document.getElementById('global-results-body');
  if (!tbody) return;
  tbody.innerHTML = items.map(function(item) {
    var checked = _sel.has(item.compositeId) ? ' checked' : '';
    return '<tr' +
      ' data-composite-id="'  + _escHtml(item.compositeId)  + '"' +
      ' data-section-label="' + _escHtml(item.sectionLabel) + '"' +
      ' data-version="'       + _escHtml(item.version)       + '"' +
      ' data-id="'            + _escHtml(item.id)            + '"' +
      ' data-category="'      + _escHtml(item.category)      + '"' +
      ' data-desc="'          + _escHtml(item.desc)          + '">' +
      '<td class="cb-cell"><input type="checkbox"' + checked + ' onchange="toggleRow(this)"></td>' +
      '<td><button class="section-badge" data-tab-id="' + _escHtml(item.tabId) + '" onclick="goToTab(this.dataset.tabId)">' + _escHtml(item.tabLabel) + '</button></td>' +
      '<td class="mono ver">' + _escHtml(item.version)  + '</td>' +
      '<td class="mono id">'  + _escHtml(item.id)       + '</td>' +
      '<td class="cat">'      + _escHtml(item.category) + '</td>' +
      '<td class="desc">'     + _escHtml(item.desc)     + '</td>' +
      '</tr>';
  }).join('');
}

// ── Rich-section version selector ──────────────────────────────────────────
function showRichVer(tabId, ver) {
  document.querySelectorAll('.ext-rich-ver[data-tab="' + tabId + '"]').forEach(function(div) {
    div.style.display = div.dataset.ver === ver ? '' : 'none';
  });
  document.querySelectorAll('.ext-ver-btn[data-tab="' + tabId + '"]').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.ver === ver);
  });
  updateDocsLink(tabId, ver);
}

function goToTab(tabId) {
  var si = document.getElementById('global-search');
  if (si) { si.value = ''; onGlobalSearch(''); }
  showTab(tabId);
}

function selectAllGlobalResults() {
  var tbody = document.getElementById('global-results-body');
  if (!tbody) return;
  tbody.querySelectorAll('tr').forEach(function(row) {
    var rowCb = row.querySelector('input[type="checkbox"]');
    if (!rowCb) return;
    rowCb.checked = true;
    var cid = row.dataset.compositeId;
    if (cid) { row.classList.add('row-selected'); _sel.set(cid, _rowMeta(row)); }
  });
  var headerCb = document.querySelector('#global-results-table thead input[type="checkbox"]');
  if (headerCb) headerCb.checked = true;
  _updateFooter();
}

// ── Export ─────────────────────────────────────────────────────────────────
function exportCSV() {
  var rows = [['Section','Version','ID','Category','Description']];
  _sel.forEach(function(m) { rows.push([m.sectionLabel, m.version, m.id, m.category, m.desc]); });
  var csv = rows.map(function(row) {
    return row.map(function(cell) {
      var s = String(cell || '');
      return (s.includes(',') || s.includes('"') || s.includes('\\n'))
        ? '"' + s.replace(/"/g, '""') + '"' : s;
    }).join(',');
  }).join('\\n');
  _dlFile('export.csv', 'text/csv', csv);
}

function exportTXT() {
  var items = [];
  _sel.forEach(function(m) { items.push(m); });
  var lines = items.map(function(m) {
    return '[' + m.sectionLabel + '] v' + m.version +
      (m.id       ? ' #' + m.id           : '') +
      (m.category ? ' [' + m.category + ']': '') +
      '\\n' + m.desc;
  });
  _dlFile('export.txt', 'text/plain', lines.join('\\n\\n'));
}

function _dlFile(filename, mime, content) {
  var a = document.createElement('a');
  a.href = 'data:' + mime + ';charset=utf-8,' + encodeURIComponent(content);
  a.download = filename;
  a.click();
}

// ── Footer ─────────────────────────────────────────────────────────────────
function _updateFooter() {
  var n      = _sel.size;
  var footer = document.getElementById('sticky-footer');
  if (footer) footer.style.display = n > 0 ? '' : 'none';
  var el = document.getElementById('sel-count');
  if (el) el.textContent = n + ' item' + (n !== 1 ? 's' : '') + ' selected';
}

function clearSelection() {
  _sel.clear();
  document.querySelectorAll('input[type="checkbox"]').forEach(function(cb) {
    cb.checked = false; cb.indeterminate = false;
  });
  document.querySelectorAll('.row-selected').forEach(function(r) { r.classList.remove('row-selected'); });
  _updateFooter();
}

// ── Init ───────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('table[id$="-table"]').forEach(function(table) {
    var tabId = table.id.replace(/-table$/, '');
    var n = table.querySelectorAll('tbody tr').length;
    var el = document.getElementById(tabId + '-count');
    if (el) el.textContent = n + ' item' + (n !== 1 ? 's' : '');
  });
});`;

  // ── Inline CSS ─────────────────────────────────────────────────────────────

  const css = `
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Outfit', ui-sans-serif, system-ui, sans-serif; background: #f0f4f8; color: #0f172a; font-size: 14px; line-height: 1.5; letter-spacing: -0.01em; }
a { color: #0b6cb4; }

/* Header */
.site-header { background: #1c2d3a; border-bottom: 1px solid #243a4a; padding: 0 24px; }
.site-header-inner { max-width: 1400px; margin: 0 auto; display: flex; align-items: center; gap: 10px; height: 52px; }
.site-header-logo { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px; background: rgba(11,108,180,0.2); border: 1px solid rgba(11,108,180,0.35); }
.site-header-logo svg { width: 16px; height: 16px; }
.site-header-title { color: #fff; font-weight: 600; font-size: 15px; }
.site-header-badge { color: #0b6cb4; background: rgba(11,108,180,0.12); border: 1px solid rgba(11,108,180,0.25); font-size: 11px; font-family: 'JetBrains Mono', monospace; padding: 1px 6px; border-radius: 4px; }
.site-header-divider { width: 1px; height: 16px; background: rgba(255,255,255,0.15); }
.site-header-sub { color: rgba(255,255,255,0.45); font-size: 11px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em; }
.site-header-right { margin-left: auto; color: rgba(255,255,255,0.35); font-size: 11px; }

/* Report header */
.report-header { max-width: 1400px; margin: 0 auto; padding: 20px 24px 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; }
.report-title { font-size: 20px; font-weight: 600; color: #0f172a; }
.report-title .ver { font-family: 'JetBrains Mono', monospace; color: #0b6cb4; }
.report-title .arrow { color: #94a3b8; margin: 0 8px; }
.report-meta { font-size: 12px; color: #64748b; margin-left: auto; }

/* Main layout */
.main { max-width: 1400px; margin: 0 auto; padding: 16px 24px 80px; }

/* Global search */
.global-search-wrap { margin-bottom: 14px; }
.global-search-input { width: 100%; padding: 10px 16px 10px 40px; border: 1px solid #b8cfe2; border-radius: 10px; font-family: inherit; font-size: 14px; color: #0f172a; background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' viewBox='0 0 24 24'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E%3C/svg%3E") no-repeat 12px center; background-size: 16px; transition: border-color 0.15s, box-shadow 0.15s; outline: none; }
.global-search-input:focus { border-color: #0b6cb4; box-shadow: 0 0 0 3px rgba(11,108,180,0.1); }

/* Global results */
#global-results { margin-bottom: 16px; }
.global-results-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.global-results-count { font-size: 12px; color: #64748b; font-weight: 500; }
.global-results-header button { padding: 5px 12px; border-radius: 6px; border: 1px solid #b8cfe2; background: #fff; color: #475569; font-family: inherit; font-size: 12px; font-weight: 500; cursor: pointer; transition: background 0.12s, border-color 0.12s; }
.global-results-header button:hover { background: #f1f5f9; border-color: #0b6cb4; color: #0b6cb4; }

/* Section badge */
.section-badge { display: inline-block; font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 4px; background: #eef2f7; color: #475569; border: none; cursor: pointer; font-family: inherit; transition: background 0.12s, color 0.12s; white-space: nowrap; }
.section-badge:hover { background: rgba(11,108,180,0.12); color: #0b6cb4; }

/* Tabs */
.tab-nav { border-bottom: 1px solid #d0dce8; display: flex; gap: 2px; padding: 8px 4px 0; overflow-x: auto; }
.tab-btn { background: none; border: none; cursor: pointer; padding: 8px 14px; font-size: 13px; font-family: inherit; font-weight: 500; color: #475569; border-radius: 8px 8px 0 0; white-space: nowrap; position: relative; transition: color 0.12s, background 0.12s; }
.tab-btn:hover { color: #1e293b; background: rgba(0,0,0,0.04); }
.tab-btn.active { color: #0f172a; background: #fff; box-shadow: inset 0 2px 0 #0b6cb4; }
.tab-badge { margin-left: 6px; font-size: 10px; font-family: 'JetBrains Mono', monospace; font-weight: 500; padding: 1px 5px; border-radius: 4px; background: #eef2f7; color: #475569; }
.tab-btn.active .tab-badge { background: rgba(11,108,180,0.1); color: #0b6cb4; border: 1px solid rgba(11,108,180,0.2); }

/* Tab panels */
.tab-panel { display: none; padding-top: 20px; }
.tab-panel.active { display: block; }

/* Overview — cards */
.cards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.card { background: #fff; border: 1px solid #d0dce8; border-radius: 12px; padding: 16px; position: relative; overflow: hidden; }
.card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 48px; opacity: 0.04; background: linear-gradient(180deg, currentColor, transparent); }
.card-num { font-size: 36px; font-weight: 700; line-height: 1; margin-bottom: 6px; font-variant-numeric: tabular-nums; }
.card-label { font-size: 12px; color: #64748b; font-weight: 500; }

/* Tables */
.table-wrap { overflow-x: auto; border: 1px solid #d0dce8; border-radius: 12px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead tr { background: #1c3a5c; }
thead th { color: #fff; text-align: left; padding: 10px 14px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; white-space: nowrap; }
thead th .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
thead th:not(:first-child):not(.cb-cell):not(:nth-child(2)) { text-align: right; }
tbody tr { border-bottom: 1px solid #e8eef4; transition: background 0.1s; }
tbody tr:last-child { border-bottom: none; }
tbody tr:nth-child(even) { background: #f8fafc; }
tbody tr:hover { background: rgba(11,108,180,0.04); }
tbody tr.row-selected { background: rgba(11,108,180,0.07) !important; }
td { padding: 9px 14px; vertical-align: top; }
td:not(:first-child):not(.desc):not(.cb-cell):not(.ver):not(.id):not(.cat):not(.bug-id):not(.feat-id) { text-align: right; }
td.zero { color: #cbd5e1; text-align: right; }
td.ver { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #475569; white-space: nowrap; }
td.id  { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #0369a1; white-space: nowrap; }
td.bug-id  { color: #b91c1c; }
td.feat-id { color: #0369a1; }
td.cat  { font-size: 12px; color: #92400e; }
td.desc { font-size: 12px; color: #334155; line-height: 1.6; }

/* Checkbox column */
.cb-cell { width: 36px; text-align: center !important; padding: 8px 4px !important; vertical-align: middle !important; }
.cb-cell input[type="checkbox"] { width: 14px; height: 14px; cursor: pointer; accent-color: #0b6cb4; }

/* Toolbar */
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
.search-input { flex: 1; min-width: 200px; padding: 7px 12px; border: 1px solid #b8cfe2; border-radius: 8px; font-family: inherit; font-size: 13px; color: #0f172a; background: #fff; outline: none; transition: border-color 0.15s; }
.search-input:focus { border-color: #0b6cb4; }
.ver-select, .cat-select { padding: 7px 10px; border: 1px solid #b8cfe2; border-radius: 8px; font-family: inherit; font-size: 13px; color: #0f172a; background: #fff; outline: none; cursor: pointer; }
.row-count { font-size: 12px; color: #64748b; white-space: nowrap; }

/* Docs link */
.docs-link { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 500; color: #64748b; text-decoration: none; padding: 6px 10px; border: 1px solid #d0dce8; border-radius: 6px; background: #fff; transition: color 0.12s, border-color 0.12s, background 0.12s; margin-left: auto; white-space: nowrap; }
.docs-link:hover { color: #0b6cb4; border-color: #0b6cb4; background: rgba(11,108,180,0.04); }

/* Special Notices */
.notice-card { background: #fffbeb; border: 1px solid #f59e0b; border-radius: 12px; padding: 16px 20px; display: flex; gap: 12px; margin-bottom: 12px; }
.notice-icon { font-size: 16px; flex-shrink: 0; color: #d97706; margin-top: 1px; }
.notice-title { font-weight: 600; color: #92400e; margin-bottom: 6px; font-size: 14px; }
.notice-body { color: #44403c; font-size: 13px; line-height: 1.65; white-space: pre-line; }

/* Extended sections — version selector */
.ext-ver-selector { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 16px; }
.ext-ver-btn { padding: 4px 12px; border-radius: 8px; border: 1px solid #d0dce8; background: #f8fafc; color: #475569; font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 500; cursor: pointer; transition: background 0.12s, color 0.12s, border-color 0.12s; }
.ext-ver-btn:hover { background: #eef2f7; color: #1e293b; }
.ext-ver-btn.active { background: #0b6cb4; color: #fff; border-color: #0b6cb4; }

/* Extended sections (non-issue text blocks) */
.ext-version-block { margin-bottom: 20px; }
.ext-version-label { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #475569; background: #eef2f7; border: 1px solid #d0dce8; display: inline-block; padding: 2px 8px; border-radius: 4px; margin-bottom: 10px; font-weight: 500; }
.ext-item { font-size: 13px; color: #334155; line-height: 1.65; padding: 8px 12px; border-left: 2px solid #d0dce8; margin-bottom: 6px; background: #f8fafc; border-radius: 0 6px 6px 0; }

/* Rich section blocks */
.rich-h2 { font-size: 15px; font-weight: 600; color: #0f172a; margin: 20px 0 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }
.rich-h3 { font-size: 13px; font-weight: 600; color: #1e293b; margin: 14px 0 6px; }
.rich-h4 { font-size: 12px; font-weight: 600; color: #475569; margin: 10px 0 4px; text-transform: uppercase; letter-spacing: 0.04em; }
.rich-p  { font-size: 13px; color: #334155; line-height: 1.7; margin-bottom: 8px; }
.rich-ul { font-size: 13px; color: #334155; line-height: 1.65; margin: 0 0 10px 20px; }
.rich-li { margin-bottom: 3px; }

/* Sticky footer */
#sticky-footer { position: fixed; bottom: 0; left: 0; right: 0; background: #1c2d3a; border-top: 1px solid #2d4459; padding: 10px 24px; display: flex; align-items: center; gap: 10px; z-index: 100; box-shadow: 0 -4px 20px rgba(0,0,0,0.25); }
#sel-count { color: #cbd5e1; font-size: 13px; font-weight: 500; margin-right: 4px; }
.btn-export { padding: 7px 16px; border-radius: 7px; border: none; cursor: pointer; font-family: inherit; font-size: 13px; font-weight: 500; background: #0b6cb4; color: #fff; transition: background 0.12s; }
.btn-export:hover { background: #0a5d9a; }
.btn-clear { padding: 7px 16px; border-radius: 7px; cursor: pointer; font-family: inherit; font-size: 13px; font-weight: 500; background: transparent; color: #94a3b8; border: 1px solid #334155; transition: color 0.12s, border-color 0.12s; }
.btn-clear:hover { color: #e2e8f0; border-color: #64748b; }
#sticky-footer-spacer { flex: 1; }

/* Misc */
.empty { color: #94a3b8; text-align: center; padding: 48px 0; font-size: 14px; }
@media print {
  .toolbar { display: none; }
  .tab-nav { display: none; }
  .tab-panel { display: block !important; page-break-before: always; }
  .tab-panel:first-child { page-break-before: auto; }
  #sticky-footer { display: none !important; }
  .global-search-wrap { display: none; }
}`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>FortiGate Upgrade Report: ${esc(job.from_version)} → ${esc(job.to_version)}</title>
  <style>${css}</style>
</head>
<body>

<header class="site-header">
  <div class="site-header-inner">
    <div class="site-header-logo">
      <svg viewBox="0 0 24 24" fill="none" stroke="#0b6cb4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
    </div>
    <span class="site-header-title">FortiGate Upgrade Dashboard</span>
    <span class="site-header-badge">v2</span>
    <div class="site-header-divider"></div>
    <span class="site-header-sub">Release Notes Analyzer</span>
    <span class="site-header-right">Generated ${esc(generated)}</span>
  </div>
</header>

<div class="report-header">
  <div class="report-title">
    Upgrade Report:
    <span class="ver">${esc(job.from_version)}</span>
    <span class="arrow">→</span>
    <span class="ver">${esc(job.to_version)}</span>
  </div>
  <div class="report-meta">${versions.length} version${versions.length !== 1 ? "s" : ""}</div>
</div>

<div class="main">
  <div class="global-search-wrap">
    <input id="global-search" type="text" class="global-search-input"
           placeholder="Search across all sections and versions…"
           oninput="onGlobalSearch(this.value)">
  </div>

  <div id="global-results" style="display:none">
    <div class="global-results-header">
      <span id="global-results-count" class="global-results-count"></span>
      <button onclick="selectAllGlobalResults()">Select all results</button>
    </div>
    <div class="table-wrap">
      <table id="global-results-table">
        <thead>
          <tr>
            <th class="cb-cell"><input type="checkbox" onchange="toggleAllGlobal(this)"></th>
            <th>Section</th><th>Version</th><th>ID</th><th>Category</th><th>Description</th>
          </tr>
        </thead>
        <tbody id="global-results-body"></tbody>
      </table>
    </div>
  </div>

  <nav class="tab-nav">${tabButtons}</nav>
  <div id="tab-panels-wrap">
    ${tabPanels}
  </div>
</div>

<div id="sticky-footer" style="display:none">
  <span id="sel-count"></span>
  <div id="sticky-footer-spacer"></div>
  <button class="btn-export" onclick="exportCSV()">Export CSV</button>
  <button class="btn-export" onclick="exportTXT()">Export TXT</button>
  <button class="btn-clear"  onclick="clearSelection()">Clear</button>
</div>

<script>${js}</script>
</body>
</html>`;
}

export function downloadHtml(job: JobDetail, selectedIds: Set<string>): void {
  const html = generateHtml(job, selectedIds);
  if (!html) return;
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `fortigate_${job.from_version}_to_${job.to_version}.html`;
  a.click();
  URL.revokeObjectURL(url);
}
