import type { JobDetail } from "../../types";

interface Props {
  job: JobDetail;
}

const SECTIONS = [
  { key: "changes_cli",       label: "CLI Changes",       color: "text-sky-400",     accent: "#38bdf8",  barColor: "rgb(56 189 248)" },
  { key: "changes_default",   label: "Default Behavior",  color: "text-amber-400",   accent: "#fbbf24",  barColor: "rgb(251 191 36)"  },
  { key: "changes_tablesize", label: "Table Size",        color: "text-violet-400",  accent: "#a78bfa",  barColor: "rgb(167 139 250)" },
  { key: "new_features",      label: "New Features",      color: "text-emerald-400", accent: "#34d399",  barColor: "rgb(52 211 153)"  },
  { key: "known_issues",      label: "Known Issues",      color: "text-red-400",     accent: "#f87171",  barColor: "rgb(248 113 113)" },
] as const;

export default function Overview({ job }: Props) {
  const versions = job.versions ?? [];
  const allData = job.all_data ?? {};

  const totals = Object.fromEntries(
    SECTIONS.map(({ key }) => [
      key,
      versions.reduce((sum, v) => sum + (allData[v]?.[key]?.length ?? 0), 0),
    ])
  );

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {SECTIONS.map(({ key, label, color, accent }) => (
          <div
            key={key}
            className="bg-navy-800 border border-navy-700 rounded-xl p-4 overflow-hidden relative"
            style={{ borderTop: `2px solid ${accent}` }}
          >
            {/* Subtle glow backdrop */}
            <div
              className="absolute top-0 left-0 right-0 h-12 opacity-5 pointer-events-none"
              style={{ background: `linear-gradient(180deg, ${accent}, transparent)` }}
            />
            <div className={`text-4xl font-bold tabular-nums leading-none mb-1.5 ${color}`}>
              {totals[key]}
            </div>
            <div className="text-xs text-gray-500 font-medium leading-tight">{label}</div>
          </div>
        ))}
      </div>

      {/* Per-version breakdown */}
      <div className="overflow-x-auto rounded-xl border border-navy-700">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-gray-800 bg-navy-900">
              <th className="text-left text-xs text-gray-500 font-medium py-2.5 px-4 uppercase tracking-wide">Version</th>
              {SECTIONS.map(({ key, label, accent }) => (
                <th key={key} className="text-right text-xs text-gray-500 font-medium py-2.5 px-3 whitespace-nowrap uppercase tracking-wide">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full"
                      style={{ background: accent }}
                    />
                    {label}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {versions.map((ver) => (
              <tr
                key={ver}
                className="border-b border-gray-800/50 hover:bg-gray-900/30 transition-colors"
              >
                <td className="py-2.5 px-4 font-mono text-white text-xs font-medium">{ver}</td>
                {SECTIONS.map(({ key, color }) => {
                  const count = allData[ver]?.[key]?.length ?? 0;
                  return (
                    <td key={key} className="py-2.5 px-3 text-right tabular-nums text-xs">
                      {count > 0 ? (
                        <span className={`font-semibold ${color}`}>{count}</span>
                      ) : (
                        <span className="text-gray-700">–</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
