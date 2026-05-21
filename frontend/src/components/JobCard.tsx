import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, Loader2, XCircle, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import type { Job } from "../types";
import { api } from "../api";

interface Props {
  job: Job;
}

function scrapeProgress(log: string | null | undefined, status: string): number {
  if (status === "completed") return 100;
  if (status === "failed")    return 0;
  if (!log)                   return 5;
  if (log.includes("Complete —"))   return 100;
  if (log.includes("Step 4/4"))     return 88;
  if (log.includes("Step 3/4"))     return 66;
  if (log.includes("Step 2/4"))     return 44;
  if (log.includes("Step 1/4"))     return 22;
  return 5;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending:   <Clock className="w-4 h-4 text-gray-400" />,
  running:   <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />,
  completed: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
  failed:    <XCircle className="w-4 h-4 text-red-400" />,
};

const STATUS_LABEL: Record<string, string> = {
  pending:   "Pending",
  running:   "Running",
  completed: "Completed",
  failed:    "Failed",
};

const STATUS_COLOR: Record<string, string> = {
  pending:   "text-gray-400 bg-gray-800",
  running:   "text-blue-300 bg-blue-900/30",
  completed: "text-emerald-300 bg-emerald-900/30",
  failed:    "text-red-300 bg-red-900/30",
};

const STATUS_LEFT_BORDER: Record<string, string> = {
  pending:   "border-l-2 border-l-gray-600",
  running:   "border-l-2 border-l-blue-500",
  completed: "border-l-2 border-l-emerald-500",
  failed:    "border-l-2 border-l-red-500",
};

export default function JobCard({ job: initial }: Props) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const isActive = initial.status === "pending" || initial.status === "running";

  const { data: job } = useQuery({
    queryKey: ["job", initial.id],
    queryFn: () => api.getJob(initial.id),
    enabled: isActive,
    refetchInterval: isActive ? 2000 : false,
    initialData: initial,
    initialDataUpdatedAt: 0, // treat list-level data as immediately stale so Report gets a fresh fetch
    select: (d) => ({ ...d } as Job),
  });

  const current = (job as Job) ?? initial;

  const [logOpen, setLogOpen] = useState(false);

  useEffect(() => {
    if (current.status === "completed" || current.status === "failed") {
      qc.invalidateQueries({ queryKey: ["jobs"] });
    }
  }, [current.status, qc]);

  // Auto-scroll log to bottom while open and running
  const logRef = useRef<HTMLPreElement>(null);
  useEffect(() => {
    if (logOpen && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [current.log, logOpen]);

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteJob(current.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });

  const hasLog = !!current.log?.trim();

  return (
    <div className={`bg-navy-800 border border-navy-700 rounded-xl overflow-hidden ${STATUS_LEFT_BORDER[current.status]} transition-all duration-300`}>
      {/* Header row */}
      <div className="flex items-center gap-3 px-5 py-3.5">
        <div className={`flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full shrink-0 ${STATUS_COLOR[current.status]}`}>
          {STATUS_ICON[current.status]}
          {STATUS_LABEL[current.status]}
        </div>

        <span className="text-white font-mono text-sm font-semibold tracking-wide">
          {current.from_version}
          <span className="text-gray-500 mx-1.5">→</span>
          {current.to_version}
        </span>

        {current.source === "pdf" && (
          <span className="text-xs text-gray-500 bg-gray-800 border border-gray-700 px-2 py-0.5 rounded font-mono">pdf</span>
        )}
        {current.use_selenium && (
          <span className="text-xs text-gray-500 bg-gray-800 border border-gray-700 px-2 py-0.5 rounded font-mono">selenium</span>
        )}

        <span className="ml-auto text-xs text-gray-600 shrink-0 tabular-nums">
          {new Date(current.created_at).toLocaleString()}
        </span>

        {current.status === "completed" && (
          <button
            onClick={() => navigate(`/reports/${current.id}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-emerald-700 hover:bg-emerald-600 rounded-lg transition-colors shrink-0"
            style={{ boxShadow: "0 1px 8px rgba(16,185,129,0.25)" }}
          >
            Open Report
          </button>
        )}

        {/* Log toggle */}
        {hasLog && (
          <button
            onClick={() => setLogOpen((v) => !v)}
            className="text-gray-600 hover:text-gray-300 transition-colors shrink-0 p-0.5 rounded hover:bg-gray-800"
            title={logOpen ? "Hide log" : "Show log"}
          >
            {logOpen
              ? <ChevronDown className="w-4 h-4" />
              : <ChevronRight className="w-4 h-4" />}
          </button>
        )}

        <button
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
          title={current.status === "running" ? "Force stop and delete this job" : "Delete job"}
          className="text-gray-700 hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors shrink-0 p-0.5 rounded hover:bg-gray-800"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Progress bar — visible while pending or running */}
      {(current.status === "pending" || current.status === "running") && (() => {
        const pct = scrapeProgress(current.log, current.status);
        const stepLabel = (current.log?.match(/Step \d\/\d[^\n]*/g) ?? []).slice(-1)[0]?.trim() ?? "Starting…";
        return (
          <div className="mx-5 mb-3.5">
            <div className="flex justify-between items-center text-xs mb-1.5">
              <span className="text-gray-500 font-mono truncate max-w-[70%]">{stepLabel}</span>
              <span className="text-gray-400 font-mono font-medium tabular-nums">{pct}%</span>
            </div>
            <div className="h-1.5 bg-navy-900 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${pct}%`,
                  background: "linear-gradient(90deg, rgb(var(--accent-dark)), rgb(var(--accent)))",
                  boxShadow: "0 0 8px rgb(var(--accent) / 0.5)",
                }}
              />
            </div>
          </div>
        );
      })()}

      {/* Error */}
      {current.error_message && (
        <div className="mx-5 mb-3 text-sm text-red-300 bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-2">
          {current.error_message}
        </div>
      )}

      {/* Collapsible log */}
      {hasLog && logOpen && (
        <pre
          ref={logRef}
          className="mx-5 mb-4 text-xs font-mono text-gray-400 bg-gray-950 border border-gray-800 rounded-lg px-3 py-2.5 max-h-44 overflow-y-auto whitespace-pre-wrap leading-relaxed"
        >
          {current.log!.trim()}
        </pre>
      )}
    </div>
  );
}
