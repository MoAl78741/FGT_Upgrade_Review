import { useState } from "react";
import type { JobDetail } from "../../types";
import KnownIssues from "./KnownIssues";
import ExtendedRich from "./ExtendedRich";

export interface ExtSlug {
  slug: string;
  label: string;
  isIssues: boolean;
  count: number;
}

interface Props {
  job: JobDetail;
  slugs: ExtSlug[];
  globalSel?: Set<string>;
  onGlobalToggle?: (id: string) => void;
}

export default function ExtendedSections({ job, slugs, globalSel, onGlobalToggle }: Props) {
  const [activeSlug, setActiveSlug] = useState<string>(slugs[0]?.slug ?? "");

  if (slugs.length === 0) {
    return (
      <div className="text-center text-gray-600 py-12 text-sm">
        No extended sections found. Run a new scrape to populate full document data.
      </div>
    );
  }

  const active = slugs.find((s) => s.slug === activeSlug);

  // Build sourceUrls for the active slug
  const sourceUrls: Record<string, string> = {};
  for (const ver of job.versions ?? []) {
    const secUrls = (job.all_data?.[ver] as Record<string, unknown>)?._section_urls as Record<string, string> | undefined;
    if (secUrls?.[activeSlug]) sourceUrls[ver] = secUrls[activeSlug];
  }

  return (
    <div className="space-y-4">
      {/* Section picker */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={activeSlug}
          onChange={(e) => setActiveSlug(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500 transition-colors"
        >
          {slugs.map(({ slug, label, count }) => (
            <option key={slug} value={slug}>
              {label}{count > 0 ? ` (${count})` : ""}
            </option>
          ))}
        </select>
        {active && (
          <span className="text-xs text-gray-500">
            {active.isIssues ? "bug / issue table" : "document section"}
          </span>
        )}
      </div>

      {/* Section content — key forces full remount when slug changes */}
      {active?.isIssues ? (
        <KnownIssues
          key={activeSlug}
          job={job}
          dataKey={activeSlug}
          sourceUrls={Object.keys(sourceUrls).length > 0 ? sourceUrls : undefined}
          globalSel={globalSel}
          onGlobalToggle={onGlobalToggle}
        />
      ) : (
        <ExtendedRich key={activeSlug} job={job} slugKey={activeSlug} />
      )}
    </div>
  );
}
