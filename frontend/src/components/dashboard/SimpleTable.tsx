import { useState, useMemo, useDeferredValue } from "react";
import { ExternalLink } from "lucide-react";
import type { TableItem, VersionData, JobDetail } from "../../types";
import SearchBar from "./SearchBar";
import VersionFilter from "./VersionFilter";
import ExportButton from "./ExportButton";

type SectionKey = keyof Pick<VersionData, "changes_cli" | "changes_default" | "changes_tablesize">;

interface Props {
  job: JobDetail;
  sectionKey: SectionKey;
  idLabel?: string;
  sourceUrls?: Record<string, string>;
  globalSel?: Set<string>;
  onGlobalToggle?: (id: string) => void;
}

interface Row extends TableItem {
  _version: string;
}

function itemId(sectionKey: string, row: Row) {
  return `${sectionKey}|${row._version}|${row["Bug ID"]}`;
}

export default function SimpleTable({
  job,
  sectionKey,
  idLabel = "Bug ID",
  sourceUrls,
  globalSel,
  onGlobalToggle,
}: Props) {
  const [search, setSearch]     = useState("");
  const deferredSearch = useDeferredValue(search);
  const [verFilter, setVerFilter] = useState<string | "all">("all");
  const [localSel, setLocalSel] = useState<Set<number>>(new Set());

  const isGlobal = !!globalSel && !!onGlobalToggle;

  const versions = job.versions ?? [];
  const allData  = job.all_data ?? {};

  const rows = useMemo<Row[]>(() => {
    const out: Row[] = [];
    for (const ver of versions) {
      const items = (allData[ver]?.[sectionKey] ?? []) as TableItem[];
      for (const item of items) out.push({ ...item, _version: ver });
    }
    return out;
  }, [versions, allData, sectionKey]);

  const filtered = useMemo(() => {
    let r = rows;
    if (verFilter !== "all") r = r.filter((x) => x._version === verFilter);
    if (deferredSearch) {
      const q = deferredSearch.toLowerCase();
      r = r.filter(
        (x) => x["Bug ID"].toLowerCase().includes(q) || x.Description.toLowerCase().includes(q)
      );
    }
    return r;
  }, [rows, verFilter, deferredSearch]);

  useMemo(() => { if (!isGlobal) setLocalSel(new Set()); }, [filtered, isGlobal]);

  const isChecked = (row: Row, i: number) =>
    isGlobal ? globalSel!.has(itemId(sectionKey, row)) : localSel.has(i);

  const allChecked = filtered.length > 0 && (
    isGlobal
      ? filtered.every((row) => globalSel!.has(itemId(sectionKey, row)))
      : localSel.size === filtered.length
  );
  const someChecked = isGlobal
    ? filtered.some((row) => globalSel!.has(itemId(sectionKey, row))) && !allChecked
    : localSel.size > 0 && !allChecked;

  function toggleAll() {
    if (isGlobal) {
      if (allChecked) {
        filtered.forEach((row) => { if (globalSel!.has(itemId(sectionKey, row))) onGlobalToggle!(itemId(sectionKey, row)); });
      } else {
        filtered.forEach((row) => { if (!globalSel!.has(itemId(sectionKey, row))) onGlobalToggle!(itemId(sectionKey, row)); });
      }
    } else {
      setLocalSel(allChecked ? new Set() : new Set(filtered.map((_, i) => i)));
    }
  }

  function toggle(row: Row, i: number) {
    if (isGlobal) {
      onGlobalToggle!(itemId(sectionKey, row));
    } else {
      setLocalSel((prev) => {
        const n = new Set(prev);
        n.has(i) ? n.delete(i) : n.add(i);
        return n;
      });
    }
  }

  const selectedInSection = isGlobal
    ? filtered.filter((row) => globalSel!.has(itemId(sectionKey, row)))
    : filtered.filter((_, i) => localSel.has(i));

  const exportRows = selectedInSection.length > 0 ? selectedInSection : filtered;
  const exportData = exportRows.map((r) => ({
    Version: r._version,
    [idLabel]: r["Bug ID"],
    Description: r.Description,
  }));

  const selectedCount = isGlobal ? selectedInSection.length : localSel.size;

  // Docs URL: use the selected version's URL, or the latest available when "all"
  const sourceUrl = sourceUrls
    ? verFilter !== "all"
      ? sourceUrls[verFilter]
      : [...versions].reverse().map((v) => sourceUrls[v]).find(Boolean)
    : undefined;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex-1 min-w-48">
          <SearchBar value={search} onChange={setSearch} placeholder="Search…" />
        </div>
        <VersionFilter versions={versions} selected={verFilter} onChange={setVerFilter} />
        <ExportButton
          data={exportData}
          filename={sectionKey}
          keys={["Version", idLabel, "Description"]}
          selectionCount={selectedCount}
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
        <span>{filtered.length} item{filtered.length !== 1 ? "s" : ""}</span>
        {selectedCount > 0 && !isGlobal && (
          <span className="text-brand-500 font-medium">
            {selectedCount} selected
            <button onClick={() => setLocalSel(new Set())} className="ml-2 text-gray-500 hover:text-gray-300">clear</button>
          </span>
        )}
        {selectedCount > 0 && isGlobal && (
          <span className="text-brand-500 font-medium">{selectedCount} selected in this section</span>
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
              <th className="text-left text-xs font-medium py-2.5 px-4 w-24 whitespace-nowrap">Version</th>
              <th className="text-left text-xs font-medium py-2.5 px-4 w-32 whitespace-nowrap">{idLabel}</th>
              <th className="text-left text-xs font-medium py-2.5 px-4">Description</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} className="text-center text-gray-600 py-12 text-sm">
                  No items match the current filters.
                </td>
              </tr>
            )}
            {filtered.map((row, i) => (
              <tr
                key={i}
                onClick={() => toggle(row, i)}
                className={`border-b border-gray-800/50 cursor-pointer transition-colors ${
                  isChecked(row, i) ? "bg-brand-500/10" : "hover:bg-gray-900/30"
                }`}
              >
                <td className="py-2.5 px-3 text-center" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={isChecked(row, i)}
                    onChange={() => toggle(row, i)}
                    className="accent-brand-500 cursor-pointer"
                  />
                </td>
                <td className="py-2.5 px-4 font-mono text-xs text-gray-400 whitespace-nowrap">{row._version}</td>
                <td className="py-2.5 px-4 font-mono text-xs text-sky-400 whitespace-nowrap">{row["Bug ID"]}</td>
                <td className="py-2.5 px-4 text-xs text-gray-300 leading-relaxed">{row.Description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
