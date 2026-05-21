interface Props {
  versions: string[];
  selected: string | "all";
  onChange: (v: string | "all") => void;
}

export default function VersionFilter({ versions, selected, onChange }: Props) {
  return (
    <select
      value={selected}
      onChange={(e) => onChange(e.target.value)}
      className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-500 transition-colors"
    >
      <option value="all">All versions</option>
      {versions.map((v) => (
        <option key={v} value={v}>
          v{v}
        </option>
      ))}
    </select>
  );
}
