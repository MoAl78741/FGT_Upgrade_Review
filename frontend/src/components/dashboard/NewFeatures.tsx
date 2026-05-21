import { useState, useMemo, useDeferredValue } from "react";
import { ExternalLink } from "lucide-react";
import type { Feature, JobDetail } from "../../types";
import SearchBar from "./SearchBar";
import VersionFilter from "./VersionFilter";
import ExportButton from "./ExportButton";

interface Row extends Feature {
  _version: string;
}

interface Props {
  job: JobDetail;
  sourceUrls?: Record<string, string>;
}

export default function NewFeatures({ job, sourceUrls }: Props) {
  const [search, setSearch]       = useState("");
  const deferredSearch = useDeferredValue(search);
  const [verFilter, setVerFilter] = useState<string | "all">("all");
  const [catFilter, setCatFilter] = useState<string | "all">("all");
  const [selected, setSelected]   = useState<Set<number>>(new Set());

  const versions = job.versions ?? [];
  const allData  = job.all_data ?? {};

  const rows = useMemo<Row[]>(() => {
    const out: Row[] = [];
    for (const ver of versions)
      for (const item of allData[ver]?.new_features ?? [])
        out.push({ ...item, _version: ver });
    return out;
  }, [versions, allData]);

  const categories = useMemo(
    () => ["all", ...Array.from(new Set(rows.map((r) => r.category))).sort()],
    [rows]
  );

  const filtered = useMemo(() => {
    let r = rows;
    if (verFilter !== "all") r = r.filter((x) => x._version === verFilter);
    if (catFilter !== "all") r = r.filter((x) => x.category === catFilter);
    if (deferredSearch) {
      const q = deferredSearch.toLowerCase();
      r = r.filter(
        (x) =>
          x["Feature ID"].toLowerCase().includes(q) ||
          x.Description.toLowerCase().includes(q) ||
          x.category.toLowerCase().includes(q)
      );
    }
    return r;
  }, [rows, verFilter, catFilter, deferredSearch]);

  useMemo(() => setSelected(new Set()), [filtered]);

  // Docs URL: follow the version filter; fall back to latest when "all"
  const sourceUrl = sourceUrls
    ? verFilter !== "all"
      ? sourceUrls[verFilter]
      : [...versions].reverse().map((v) => sourceUrls[v]).find(Boolean)
    : undefined;

  const allChecked  = filtered.length > 0 && selected.size === filtered.length;
  const someChecked = selected.size > 0 && !allChecked;

  function toggleAll() {
    setSelected(allChecked ? new Set() : new Set(filtered.map((_, i) => i)));
  }
  function toggle(i: number) {
    setSelected((prev) => {
      const n = new Set(prev);
      n.has(i) ? n.delete(i) : n.add(i);
      return n;
    });
  }

  const exportRows = selected.size > 0 ? filtered.filter((_, i) => selected.has(i)) : filtered;
  const exportData = exportRows.map((r) => ({
    Version: r._version,
    Category: r.category,
    "Feature ID": r["Feature ID"],
    Description: r.Description,
  }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex-1 min-w-48">
          <SearchBar value={search} onChange={setSearch} placeholder="Search features…" />
        </div>
        <VersionFilter versions={versions} selected={verFilter} onChange={setVerFilter} />
        <select
          value={catFilter}
          onChange={(e) => setCatFilter(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500 transition-colors"
        >
          {categories.map((c) => (
            <option key={c} value={c}>{c === "all" ? "All categories" : c}</option>
          ))}
        </select>
        <ExportButton
          data={exportData}
          filename="new_features"
          keys={["Version", "Category", "Feature ID", "Description"]}
          selectionCount={selected.size}
        />
        {sourceUrl && (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-brand-400 transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
            View in Docs
          </a>
        )}
      </div>

      <div className="flex items-center gap-3 text-xs text-gray-500">
        <span>{filtered.length} feature{filtered.length !== 1 ? "s" : ""}</span>
        {selected.size > 0 && (
          <span className="text-brand-500 font-medium">
            {selected.size} selected
            <button onClick={() => setSelected(new Set())} className="ml-2 text-gray-500 hover:text-gray-300">clear</button>
          </span>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-900 border-b border-gray-800">
              <th className="py-2.5 px-3 w-8">
                <input
                  type="checkbox"
                  checked={allChecked}
                  ref={(el) => { if (el) el.indeterminate = someChecked; }}
                  onChange={toggleAll}
                  className="accent-brand-500 cursor-pointer"
                />
              </th>
              <th className="text-left text-xs font-medium py-2.5 px-4 w-24">Version</th>
              <th className="text-left text-xs font-medium py-2.5 px-4 w-40">Category</th>
              <th className="text-left text-xs font-medium py-2.5 px-4 w-32">Feature ID</th>
              <th className="text-left text-xs font-medium py-2.5 px-4">Description</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center text-gray-600 py-12 text-sm">
                  No features match the current filters.
                </td>
              </tr>
            )}
            {filtered.map((row, i) => (
              <tr
                key={i}
                onClick={() => toggle(i)}
                className={`border-b border-gray-800/50 cursor-pointer transition-colors ${
                  selected.has(i) ? "bg-brand-500/10" : "hover:bg-gray-900/30"
                }`}
              >
                <td className="py-2.5 px-3 text-center" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected.has(i)}
                    onChange={() => toggle(i)}
                    className="accent-brand-500 cursor-pointer"
                  />
                </td>
                <td className="py-2.5 px-4 font-mono text-xs text-gray-400 whitespace-nowrap">{row._version}</td>
                <td className="py-2.5 px-4 text-xs text-emerald-400">{row.category}</td>
                <td className="py-2.5 px-4 font-mono text-xs text-sky-400 whitespace-nowrap">{row["Feature ID"]}</td>
                <td className="py-2.5 px-4 text-xs text-gray-300 leading-relaxed">{row.Description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
