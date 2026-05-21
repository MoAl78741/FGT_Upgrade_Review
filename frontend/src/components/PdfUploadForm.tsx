import { useCallback, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Upload, X, Play, Loader2, AlertTriangle } from "lucide-react";
import { api } from "../api";
import type { Job } from "../types";

function extractVersionFromName(filename: string): string | null {
  const m = filename.match(/v?(\d+\.\d+\.\d+)/i);
  return m ? m[1] : null;
}

export default function PdfUploadForm() {
  const [files, setFiles]     = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [error, setError]     = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => api.uploadPdfs(files),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      setError("");
      setFiles([]);
    },
    onError: (e: Error) => setError(e.message),
  });

  function addFiles(incoming: FileList | File[]) {
    const pdfs = Array.from(incoming).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdfs.length < Array.from(incoming).length) {
      setError("Only .pdf files are accepted.");
    } else {
      setError("");
    }
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...pdfs.filter((f) => !names.has(f.name))];
    });
  }

  function removeFile(name: string) {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (files.length === 0) { setError("Please select at least one PDF."); return; }
    mutation.mutate();
  }

  const valid = files.length > 0;

  // Auto-fill to_version from filenames if not set
  const detectedVersions = files
    .map((f) => extractVersionFromName(f.name))
    .filter(Boolean) as string[];

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
          <div className="w-1 h-5 rounded-full" style={{ background: "rgb(var(--accent))" }} />
          <h2 className="text-white font-semibold text-sm tracking-wide uppercase">Upload Release Note PDFs</h2>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`mb-4 flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed cursor-pointer py-8 transition-all duration-150 ${
            dragging
              ? "border-brand-500 bg-brand-500/10"
              : "border-navy-600 hover:border-brand-500/60 bg-navy-900/40 hover:bg-navy-900/60"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf"
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
          <Upload className={`w-6 h-6 transition-colors ${dragging ? "text-brand-500" : "text-gray-600"}`} />
          <p className="text-sm text-gray-400">
            Drop PDF(s) here or <span className="text-brand-500 font-medium">browse</span>
          </p>
          <p className="text-xs text-gray-600">Version is detected from the filename (e.g. fortios-v7.4.11-release-notes.pdf)</p>
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="mb-4 space-y-1.5">
            {files.map((f) => {
              const detected = extractVersionFromName(f.name);
              return (
                <div
                  key={f.name}
                  className="flex items-center gap-2.5 px-3 py-2 bg-navy-900 border border-navy-700 rounded-lg"
                >
                  <FileText className="w-4 h-4 text-brand-500 shrink-0" />
                  <span className="text-sm text-gray-300 truncate flex-1 font-mono">{f.name}</span>
                  {detected && (
                    <span
                      className="text-xs font-mono px-1.5 py-0.5 rounded shrink-0"
                      style={{
                        background: "rgb(var(--accent) / 0.12)",
                        color: "rgb(var(--accent))",
                        border: "1px solid rgb(var(--accent) / 0.25)",
                      }}
                    >
                      v{detected}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => removeFile(f.name)}
                    className="text-gray-600 hover:text-red-400 transition-colors shrink-0"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Detected versions hint */}
        {detectedVersions.length > 0 && (
          <p className="text-xs text-gray-600 mb-4">
            Detected versions from filenames:{" "}
            <span className="text-gray-400 font-mono">{detectedVersions.join(", ")}</span>
          </p>
        )}

        {error && (
          <div className="text-red-400 text-sm mb-4 bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-2.5 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={!valid || mutation.isPending}
          className="flex items-center gap-2 px-5 py-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-lg transition-all duration-150"
          style={{ boxShadow: valid && !mutation.isPending ? "0 2px 12px rgb(var(--accent) / 0.3)" : undefined }}
        >
          {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {mutation.isPending ? "Processing…" : "Process PDFs"}
        </button>
      </div>
    </form>
  );
}
