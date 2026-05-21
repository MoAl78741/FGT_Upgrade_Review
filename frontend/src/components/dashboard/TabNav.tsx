interface Tab {
  id: string;
  label: string;
  count?: number;
}

interface Props {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
}

export default function TabNav({ tabs, active, onChange }: Props) {
  return (
    <div className="border-b border-gray-800 overflow-x-auto">
      <div className="flex gap-0.5 px-1 pt-1">
        {tabs.map((tab) => {
          const isActive = active === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onChange(tab.id)}
              className={`relative px-3.5 py-2 text-sm font-medium whitespace-nowrap rounded-t-lg transition-all duration-150 ${
                isActive
                  ? "text-white"
                  : "text-gray-500 hover:text-gray-300 hover:bg-navy-800/60"
              }`}
              style={isActive ? {
                background: "rgb(var(--surface))",
                boxShadow: "inset 0 1px 0 rgb(var(--accent) / 0.6), 0 -1px 0 rgb(var(--surface)) ",
              } : undefined}
            >
              {/* Active accent line at top */}
              {isActive && (
                <span
                  className="absolute top-0 left-3 right-3 h-0.5 rounded-full"
                  style={{ background: "rgb(var(--accent))" }}
                />
              )}

              <span className="relative flex items-center gap-1.5">
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded font-mono font-medium tabular-nums transition-all ${
                      isActive
                        ? ""
                        : "opacity-70"
                    }`}
                    style={isActive ? {
                      background: "rgb(var(--accent) / 0.15)",
                      color: "rgb(var(--accent))",
                      border: "1px solid rgb(var(--accent) / 0.3)",
                    } : {
                      background: "rgb(var(--surface-deep))",
                      color: "#6b7280",
                      border: "1px solid rgb(var(--surface-border))",
                    }}
                  >
                    {tab.count}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
