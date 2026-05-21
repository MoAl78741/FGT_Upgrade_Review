import { useState } from "react";
import { X, Download, FileDown } from "lucide-react";
import type { JobDetail } from "../../types";
import { getAvailableSections, downloadHtml } from "../../utils/htmlExport";

interface Props {
  job: JobDetail;
  onClose: () => void;
}

export default function DownloadModal({ job, onClose }: Props) {
  const sections = getAvailableSections(job);
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(sections.map((s) => s.id))
  );

  const allChecked  = selected.size === sections.length;
  const someChecked = selected.size > 0 && !allChecked;

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected(allChecked ? new Set() : new Set(sections.map((s) => s.id)));
  }

  function handleDownload() {
    downloadHtml(job, selected);
    onClose();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(2px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-navy-800 border border-navy-700 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        {/* Header */}
        <div
          className="h-0.5"
          style={{ background: "linear-gradient(90deg, rgb(var(--accent)) 0%, rgb(var(--accent)/0.3) 60%, transparent 100%)" }}
        />
        <div className="flex items-center gap-3 px-5 py-4 border-b border-navy-700">
          <div
            className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0"
            style={{ background: "rgb(var(--accent)/0.12)", border: "1px solid rgb(var(--accent)/0.25)" }}
          >
            <FileDown className="w-4 h-4 text-brand-500" />
          </div>
          <div>
            <h2 className="text-white font-semibold text-sm">Download HTML Report</h2>
            <p className="text-gray-500 text-xs mt-0.5">
              Self-contained file — works offline, no server needed
            </p>
          </div>
          <button
            onClick={onClose}
            className="ml-auto text-gray-600 hover:text-gray-300 transition-colors p-1 rounded hover:bg-gray-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Section selector */}
        <div className="px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-gray-500 uppercase tracking-wide font-medium">
              Sections to include
            </span>
            <label className="flex items-center gap-2 cursor-pointer text-xs text-gray-400 hover:text-gray-200 transition-colors">
              <input
                type="checkbox"
                checked={allChecked}
                ref={(el) => { if (el) el.indeterminate = someChecked; }}
                onChange={toggleAll}
                className="accent-brand-500 cursor-pointer"
              />
              {allChecked ? "Deselect all" : "Select all"}
            </label>
          </div>

          <div className="space-y-1 overflow-y-auto max-h-72 pr-1">
            {sections.map((section) => {
              const isSelected = selected.has(section.id);
              return (
                <label
                  key={section.id}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                    isSelected
                      ? "bg-navy-900 border border-navy-700"
                      : "hover:bg-navy-900/50 border border-transparent"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggle(section.id)}
                    className="accent-brand-500 cursor-pointer shrink-0"
                  />
                  <span className="text-sm text-white flex-1">{section.label}</span>
                  {section.count >= 0 && (
                    <span
                      className="text-xs font-mono tabular-nums px-1.5 py-0.5 rounded"
                      style={{
                        color: isSelected ? "rgb(var(--accent))" : "#6b7280",
                        background: isSelected ? "rgb(var(--accent)/0.1)" : "transparent",
                        border: isSelected ? "1px solid rgb(var(--accent)/0.2)" : "1px solid transparent",
                      }}
                    >
                      {section.count}
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 px-5 py-4 border-t border-navy-700 bg-navy-900">
          <p className="text-xs text-gray-600">
            {selected.size} of {sections.length} section{sections.length !== 1 ? "s" : ""} selected
          </p>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDownload}
              disabled={selected.size === 0}
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-all"
              style={{ boxShadow: selected.size > 0 ? "0 2px 10px rgb(var(--accent)/0.3)" : undefined }}
            >
              <Download className="w-4 h-4" />
              Download
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
