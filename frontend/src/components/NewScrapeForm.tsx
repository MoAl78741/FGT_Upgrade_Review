import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play, Loader2, CheckCircle, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Job } from "../types";
import { useSettings } from "../contexts/SettingsContext";

export default function NewScrapeForm() {
  const [fromVer, setFromVer]   = useState("");
  const [toVer, setToVer]       = useState("");
  const [error, setError]       = useState("");
  const [forceRescrape, setForceRescrape] = useState(false);
  const [existingJob, setExistingJob] = useState<{ id: string; status: string } | null>(null);
  const { settings } = useSettings();
  const { selenium, gridUrl } = settings;

  const navigate = useNavigate();
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (force: boolean = false) =>
      api.createJob(fromVer.trim(), toVer.trim(), selenium, selenium ? gridUrl.trim() : undefined, force || forceRescrape),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      setError("");
      setExistingJob(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    const jobs = qc.getQueryData<Job[]>(["jobs"]) ?? [];
    const existing = jobs.find(
      (j) =>
        (j.status === "completed" || j.status === "running" || j.status === "pending") &&
        j.from_version === fromVer.trim() &&
        j.to_version === toVer.trim()
    );
    if (existing) {
      setExistingJob({ id: existing.id, status: existing.status });
      return;
    }

    mutation.mutate(false);
  }

  async function handleConfirmRescrape() {
    setError("");
    try {
      if (existingJob) {
        await api.deleteJob(existingJob.id);
        qc.invalidateQueries({ queryKey: ["jobs"] });
      }
    } catch {
      // Ignore delete errors — job may already be gone
    }
    setExistingJob(null);
    mutation.mutate(true); // always bypass cache when explicitly re-scraping
  }

  const verPattern = /^\d+\.\d+\.\d+$/;
  const valid =
    verPattern.test(fromVer.trim()) &&
    verPattern.test(toVer.trim()) &&
    fromVer.trim() !== toVer.trim();

  return (
    <form onSubmit={handleSubmit} className="bg-navy-800 border border-navy-700 rounded-xl overflow-hidden">
      {/* Top accent bar */}
      <div
        className="h-0.5"
        style={{ background: "linear-gradient(90deg, rgb(var(--accent)) 0%, rgb(var(--accent) / 0.3) 60%, transparent 100%)" }}
      />

      <div className="p-6">
        {/* Header */}
        <div className="flex items-center gap-2 mb-5">
          <div
            className="w-1 h-5 rounded-full"
            style={{ background: "rgb(var(--accent))" }}
          />
          <h2 className="text-white font-semibold text-sm tracking-wide uppercase">Gather Documents</h2>
        </div>

        {/* Version inputs row */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3 mb-5">
          {/* From version */}
          <label className="flex-1">
            <span className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1.5 block">
              From Version
              <span className="normal-case text-gray-600 ml-1 font-normal">currently on</span>
            </span>
            <input
              type="text"
              placeholder="7.2.8"
              value={fromVer}
              onChange={(e) => { setFromVer(e.target.value); setExistingJob(null); }}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition-colors font-mono tracking-wider"
            />
          </label>

          {/* Arrow divider */}
          <div className="flex sm:flex-col items-center justify-center sm:pb-1.5 px-1">
            <div className="flex sm:flex-col items-center gap-0.5">
              <div className="w-6 h-px sm:w-px sm:h-6 bg-gray-700" />
              <span className="text-gray-600 text-xs font-mono">→</span>
              <div className="w-6 h-px sm:w-px sm:h-6 bg-gray-700" />
            </div>
          </div>

          {/* To version */}
          <label className="flex-1">
            <span className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1.5 block">
              To Version
              <span className="normal-case text-gray-600 ml-1 font-normal">upgrading to</span>
            </span>
            <input
              type="text"
              placeholder="7.4.11"
              value={toVer}
              onChange={(e) => { setToVer(e.target.value); setExistingJob(null); }}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition-colors font-mono tracking-wider"
            />
          </label>
        </div>

        {/* Force rescrape toggle */}
        <label className="flex items-center gap-2.5 mb-4 cursor-pointer w-fit">
          <div
            onClick={() => setForceRescrape((v) => !v)}
            className={`relative w-8 h-4 rounded-full transition-colors ${forceRescrape ? "bg-brand-500" : "bg-gray-700"}`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${forceRescrape ? "translate-x-4" : "translate-x-0"}`}
            />
          </div>
          <span className="text-xs text-gray-400 select-none flex items-center gap-1.5">
            <RefreshCw className="w-3 h-3" />
            Bypass cache (force fresh scrape)
          </span>
        </label>

        {error && (
          <div className="text-red-400 text-sm mb-4 bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-2.5 flex items-start gap-2">
            <span className="shrink-0 mt-0.5">⚠</span>
            <span>{error}</span>
          </div>
        )}

        {existingJob ? (
          existingJob.status === "completed" ? (
            <div className="flex flex-wrap items-center gap-3 p-3.5 bg-emerald-900/20 border border-emerald-700/40 rounded-lg">
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
              <span className="text-sm text-emerald-200 flex-1">
                A report already exists for this version range.
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => navigate(`/report/${existingJob.id}`)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-brand-500 hover:bg-brand-600 rounded-lg transition-colors"
                  style={{ boxShadow: "0 2px 8px rgb(var(--accent) / 0.3)" }}
                >
                  View Report
                </button>
                <button
                  type="button"
                  disabled={mutation.isPending}
                  onClick={handleConfirmRescrape}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-300 hover:text-white bg-gray-700 hover:bg-gray-600 disabled:opacity-40 rounded-lg transition-colors"
                >
                  {mutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                  {mutation.isPending ? "Starting…" : "↻ Scrape Fresh"}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3 p-3.5 bg-blue-900/20 border border-blue-700/40 rounded-lg">
              <Loader2 className="w-4 h-4 text-blue-400 shrink-0 animate-spin" />
              <span className="text-sm text-blue-200 flex-1">
                A scrape is already in progress for this range.
              </span>
              <button
                type="button"
                onClick={() => navigate(`/report/${existingJob.id}`)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-brand-500 hover:bg-brand-600 rounded-lg transition-colors"
                style={{ boxShadow: "0 2px 8px rgb(var(--accent) / 0.3)" }}
              >
                View Progress
              </button>
            </div>
          )
        ) : (
          <button
            type="submit"
            disabled={!valid || mutation.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-lg transition-all duration-150"
            style={{ boxShadow: valid && !mutation.isPending ? "0 2px 12px rgb(var(--accent) / 0.3)" : undefined }}
          >
            {mutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {mutation.isPending ? "Starting…" : "Start Scrape"}
          </button>
        )}
      </div>
    </form>
  );
}
