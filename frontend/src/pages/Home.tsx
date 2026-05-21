import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Database, Globe, FileText } from "lucide-react";
import { api } from "../api";
import NewScrapeForm from "../components/NewScrapeForm";
import PdfUploadForm from "../components/PdfUploadForm";
import JobCard from "../components/JobCard";
import type { Job } from "../types";

type InputTab = "scrape" | "pdf";

export default function Home() {
  const [activeTab, setActiveTab] = useState<InputTab>("scrape");

  const { data: jobs, isLoading, error } = useQuery({
    queryKey: ["jobs"],
    queryFn: api.listJobs,
    refetchInterval: 5000,
  });

  const activeCount = jobs?.filter((j: Job) => j.status === "running" || j.status === "pending").length ?? 0;
  const completedCount = jobs?.filter((j: Job) => j.status === "completed").length ?? 0;

  return (
    <div className="max-w-screen-xl mx-auto px-6 py-8 space-y-8">
      {/* Tab switcher */}
      <div className="flex gap-1 p-1 bg-navy-800 border border-navy-700 rounded-xl w-fit">
        {([ ["scrape", Globe, "Scrape"], ["pdf", FileText, "Upload PDFs"] ] as [InputTab, React.ElementType, string][]).map(
          ([id, Icon, label]) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                activeTab === id
                  ? "text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}
              style={
                activeTab === id
                  ? {
                      background: "rgb(var(--accent) / 0.15)",
                      border: "1px solid rgb(var(--accent) / 0.3)",
                      color: "rgb(var(--accent))",
                    }
                  : undefined
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          )
        )}
      </div>

      {activeTab === "scrape" ? <NewScrapeForm /> : <PdfUploadForm />}

      <section>
        {/* Section header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-gray-500" />
            <h2 className="text-white font-semibold text-sm tracking-wide uppercase">
              Jobs
            </h2>
          </div>
          {jobs && jobs.length > 0 && (
            <div className="flex items-center gap-2 ml-1">
              {completedCount > 0 && (
                <span className="text-xs text-gray-500 bg-navy-800 border border-navy-700 px-2 py-0.5 rounded font-mono">
                  {completedCount} completed
                </span>
              )}
              {activeCount > 0 && (
                <span
                  className="text-xs px-2 py-0.5 rounded font-mono font-medium"
                  style={{
                    color: "rgb(var(--accent))",
                    background: "rgb(var(--accent) / 0.1)",
                    border: "1px solid rgb(var(--accent) / 0.25)",
                  }}
                >
                  {activeCount} active
                </span>
              )}
            </div>
          )}
          <div className="flex-1 h-px bg-navy-700 ml-2" />
        </div>

        {isLoading && (
          <div className="flex items-center gap-2.5 text-gray-400 text-sm py-10">
            <Loader2 className="w-4 h-4 animate-spin text-brand-500" />
            <span>Loading jobs…</span>
          </div>
        )}

        {error && (
          <div className="text-red-400 text-sm py-3 px-4 bg-red-900/20 border border-red-800/40 rounded-lg">
            Failed to load jobs: {(error as Error).message}
          </div>
        )}

        {jobs && jobs.length === 0 && (
          <div className="py-12 text-center border border-dashed border-navy-700 rounded-xl bg-navy-800/30">
            <Database className="w-8 h-8 text-gray-700 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">No jobs yet.</p>
            <p className="text-gray-600 text-xs mt-1">Scrape or upload PDFs above to get started.</p>
          </div>
        )}

        <div className="space-y-2.5">
          {jobs?.map((job: Job) => <JobCard key={job.id} job={job} />)}
        </div>
      </section>
    </div>
  );
}
