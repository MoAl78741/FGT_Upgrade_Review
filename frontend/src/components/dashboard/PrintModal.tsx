import { X, Printer } from "lucide-react";

export interface PrintItem {
  compositeId: string;
  sectionLabel: string;
  version: string;
  id: string;
  idLabel: string;
  category?: string;
  description: string;
}

interface Props {
  items: PrintItem[];
  onClose: () => void;
}

export default function PrintModal({ items, onClose }: Props) {
  // Group by sectionLabel
  const grouped = items.reduce<Record<string, PrintItem[]>>((acc, item) => {
    (acc[item.sectionLabel] ??= []).push(item);
    return acc;
  }, {});

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-50 print:hidden"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-4 md:inset-12 z-50 flex flex-col bg-gray-950 border border-gray-700 rounded-xl overflow-hidden print:fixed print:inset-0 print:border-none print:rounded-none print:bg-white">
        {/* Header — hidden when printing */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 shrink-0 print:hidden">
          <span className="text-white font-semibold">
            Print Preview — {items.length} item{items.length !== 1 ? "s" : ""}
          </span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => window.print()}
              className="flex items-center gap-2 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <Printer className="w-4 h-4" />
              Print
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Print title — only visible when printing */}
        <div className="hidden print:block px-6 pt-6 pb-2">
          <h1 className="text-xl font-bold text-black">FortiGate Upgrade Review — Selected Items</h1>
          <p className="text-sm text-gray-600 mt-1">{items.length} item{items.length !== 1 ? "s" : ""} across {Object.keys(grouped).length} section{Object.keys(grouped).length !== 1 ? "s" : ""}</p>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-8 print:overflow-visible print:text-black">
          {Object.entries(grouped).map(([section, sectionItems]) => (
            <div key={section} className="print:break-inside-avoid-page">
              <h2 className="text-sm font-semibold text-brand-400 print:text-black mb-3 pb-1 border-b border-gray-800 print:border-gray-300">
                {section} ({sectionItems.length})
              </h2>
              <div className="overflow-x-auto rounded-xl border border-gray-800 print:border-gray-300 print:rounded-none">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="bg-gray-900 print:bg-gray-100 border-b border-gray-800 print:border-gray-300">
                      <th className="text-left font-medium py-2 px-3 w-20">Version</th>
                      {sectionItems[0]?.category !== undefined && (
                        <th className="text-left font-medium py-2 px-3 w-36">Category</th>
                      )}
                      <th className="text-left font-medium py-2 px-3 w-24">{sectionItems[0]?.idLabel ?? "ID"}</th>
                      <th className="text-left font-medium py-2 px-3">Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sectionItems.map((item) => (
                      <tr
                        key={item.compositeId}
                        className="border-b border-gray-800/50 print:border-gray-200"
                      >
                        <td className="py-2 px-3 font-mono text-gray-400 print:text-black whitespace-nowrap">{item.version}</td>
                        {item.category !== undefined && (
                          <td className="py-2 px-3 text-amber-400 print:text-black">{item.category}</td>
                        )}
                        <td className="py-2 px-3 font-mono text-red-400 print:text-black whitespace-nowrap">{item.id}</td>
                        <td className="py-2 px-3 text-gray-300 print:text-black leading-relaxed">{item.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}

          {items.length === 0 && (
            <div className="text-center text-gray-500 py-16 text-sm">
              No items selected.
            </div>
          )}
        </div>
      </div>
    </>
  );
}
