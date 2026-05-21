import { useState, useRef, useEffect } from "react";
import { Download, ChevronDown } from "lucide-react";

interface Props {
  /** Rows to export. Pass selectedRows when a selection is active, otherwise all filtered rows. */
  data: Record<string, unknown>[];
  filename: string;
  keys: string[];
  /** When truthy, label shows "X selected" instead of "Export" */
  selectionCount?: number;
}

function toCSV(data: Record<string, unknown>[], keys: string[]): string {
  const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const header = keys.join(",");
  const rows = data.map((row) => keys.map((k) => esc(String(row[k] ?? ""))).join(","));
  return [header, ...rows].join("\n");
}

function toTXT(data: Record<string, unknown>[], keys: string[]): string {
  const widths = keys.map((k) =>
    Math.min(
      60,
      Math.max(k.length, ...data.map((r) => String(r[k] ?? "").length))
    )
  );
  const pad = (s: string, w: number) => s.substring(0, w).padEnd(w);
  const header = keys.map((k, i) => pad(k, widths[i])).join("  ");
  const sep = widths.map((w) => "─".repeat(w)).join("  ");
  const rows = data.map((row) =>
    keys.map((k, i) => pad(String(row[k] ?? ""), widths[i])).join("  ")
  );
  return [header, sep, ...rows].join("\n");
}

function download(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ExportButton({ data, filename, keys, selectionCount }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const disabled = data.length === 0;
  const label =
    selectionCount !== undefined && selectionCount > 0
      ? `${selectionCount} selected`
      : "Export";

  return (
    <div ref={ref} className="relative">
      <div className="flex items-stretch">
        {/* Main label */}
        <button
          onClick={() => !disabled && setOpen((v) => !v)}
          disabled={disabled}
          className="flex items-center gap-1.5 px-3 py-2 text-xs text-gray-400 hover:text-white bg-gray-900 border border-gray-700 rounded-l-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed border-r-0"
        >
          <Download className="w-3.5 h-3.5" />
          {label}
        </button>
        {/* Chevron trigger */}
        <button
          onClick={() => !disabled && setOpen((v) => !v)}
          disabled={disabled}
          className="flex items-center px-1.5 text-gray-400 hover:text-white bg-gray-900 border border-gray-700 rounded-r-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronDown className="w-3 h-3" />
        </button>
      </div>

      {open && !disabled && (
        <div className="absolute right-0 top-full mt-1 bg-navy-800 border border-navy-700 rounded-lg shadow-xl z-20 min-w-[130px] overflow-hidden">
          <button
            onClick={() => { download(toCSV(data, keys), filename + ".csv", "text/csv"); setOpen(false); }}
            className="w-full text-left px-4 py-2.5 text-xs text-gray-300 hover:bg-gray-800 transition-colors"
          >
            Download CSV
          </button>
          <button
            onClick={() => { download(toTXT(data, keys), filename + ".txt", "text/plain"); setOpen(false); }}
            className="w-full text-left px-4 py-2.5 text-xs text-gray-300 hover:bg-gray-800 transition-colors"
          >
            Download TXT
          </button>
        </div>
      )}
    </div>
  );
}
