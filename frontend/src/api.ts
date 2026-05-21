import type { Job, JobDetail } from "./types";

const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  listJobs: () => req<Job[]>("/jobs"),

  getJob: (id: string) => req<JobDetail>(`/jobs/${id}`),

  createJob: (from_version: string, to_version: string, use_selenium: boolean, grid_url?: string, force_rescrape?: boolean) =>
    req<Job>("/jobs", {
      method: "POST",
      body: JSON.stringify({ from_version, to_version, use_selenium, grid_url, force_rescrape: force_rescrape ?? false }),
    }),

  uploadPdfs: async (files: File[]): Promise<Job> => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const res = await fetch(`${BASE}/jobs/upload`, { method: "POST", body: fd });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  },

  deleteJob: (id: string) => req<void>(`/jobs/${id}`, { method: "DELETE" }),
};
