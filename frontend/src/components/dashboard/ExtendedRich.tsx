import { useState, useEffect } from "react";
import { ExternalLink } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { JobDetail, RichBlock, RichSection } from "../../types";

const mdComponents = {
  h1: ({ children }: { children?: React.ReactNode }) => <h1 className="text-lg font-semibold text-white mt-6 mb-2">{children}</h1>,
  h2: ({ children }: { children?: React.ReactNode }) => <h2 className="text-base font-semibold text-white mt-5 mb-2">{children}</h2>,
  h3: ({ children }: { children?: React.ReactNode }) => <h3 className="text-sm font-semibold text-gray-200 mt-4 mb-1.5">{children}</h3>,
  h4: ({ children }: { children?: React.ReactNode }) => <h4 className="text-sm font-medium text-gray-300 mt-3 mb-1">{children}</h4>,
  p:  ({ children }: { children?: React.ReactNode }) => <p className="text-sm leading-relaxed mb-2 text-gray-300">{children}</p>,
  ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc list-inside space-y-1 mb-3 ml-2">{children}</ul>,
  ol: ({ children }: { children?: React.ReactNode }) => <ol className="list-decimal list-inside space-y-1 mb-3 ml-2">{children}</ol>,
  li: ({ children }: { children?: React.ReactNode }) => <li className="text-sm text-gray-300">{children}</li>,
  code: ({ children, className }: { children?: React.ReactNode; className?: string }) =>
    className
      ? <code className="block bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 mb-3 text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap">{children}</code>
      : <code className="bg-gray-950 px-1 py-0.5 rounded text-xs font-mono text-gray-300">{children}</code>,
  pre: ({ children }: { children?: React.ReactNode }) => <pre className="mb-3">{children}</pre>,
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="overflow-x-auto rounded-xl border border-gray-800 mb-4">
      <table className="w-full text-sm border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => <thead className="bg-gray-900 border-b border-gray-800">{children}</thead>,
  th: ({ children }: { children?: React.ReactNode }) => <th className="text-left text-xs font-medium py-2.5 px-4 text-gray-300">{children}</th>,
  td: ({ children }: { children?: React.ReactNode }) => <td className="py-2.5 px-4 text-xs text-gray-300 border-b border-gray-800/50 leading-relaxed">{children}</td>,
  tr: ({ children }: { children?: React.ReactNode }) => <tr className="hover:bg-gray-900/30 transition-colors">{children}</tr>,
  blockquote: ({ children }: { children?: React.ReactNode }) => <blockquote className="border-l-2 border-gray-600 pl-4 my-2 text-gray-400 italic">{children}</blockquote>,
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand-400 hover:underline">{children}</a>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-semibold text-white">{children}</strong>,
  hr: () => <hr className="border-gray-700 my-4" />,
};

interface Props {
  job: JobDetail;
  slugKey: string;
}

function Block({ block }: { block: RichBlock }) {
  switch (block.type) {
    case "heading": {
      const sizes: Record<number, string> = {
        2: "text-base font-semibold text-white mt-5 mb-2",
        3: "text-sm font-semibold text-gray-200 mt-4 mb-1.5",
        4: "text-sm font-medium text-gray-300 mt-3 mb-1",
        5: "text-xs font-medium text-gray-400 mt-2 mb-1 uppercase tracking-wide",
        6: "text-sm font-semibold text-white mt-3 mb-1",  // inline bold sub-heading (e.g. Fortinet h6)
      };
      return (
        <div className={sizes[block.level ?? 2] ?? sizes[2]}>
          {block.text}
        </div>
      );
    }
    case "paragraph":
      return (
        <p className={`text-sm leading-relaxed mb-2 ${block.bold ? "font-semibold text-white" : "text-gray-300"}`}>
          {block.text}
        </p>
      );

    case "code":
      return (
        <pre className="bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 mb-3 text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap">
          {block.text}
        </pre>
      );

    case "list":
      return (
        <ul className="list-disc list-inside space-y-1 mb-3 ml-2">
          {block.items?.map((item, i) => (
            <li key={i} className="text-sm text-gray-300">{item}</li>
          ))}
        </ul>
      );

    case "table":
      return (
        <div className="overflow-x-auto rounded-xl border border-gray-800 mb-4">
          <table className="w-full text-sm border-collapse">
            {block.headers && block.headers.length > 0 && (
              <thead>
                <tr className="bg-gray-900 border-b border-gray-800">
                  {block.headers.map((h, i) => (
                    <th key={i} className="text-left text-xs font-medium py-2.5 px-4">{h}</th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {block.rows?.map((row, ri) => (
                <tr key={ri} className="border-b border-gray-800/50 hover:bg-gray-900/30 transition-colors">
                  {row.map((cell, ci) => (
                    <td key={ci} className="py-2.5 px-4 text-xs text-gray-300 leading-relaxed">{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );

    default:
      return null;
  }
}

export default function ExtendedRich({ job, slugKey }: Props) {
  const versions = (job.versions ?? []).filter((v) => {
    const d = (job.all_data?.[v] as Record<string, unknown> | undefined)?.[slugKey];
    const s = d as RichSection | undefined;
    return !!(s?.markdown || s?.blocks?.length);
  });

  const [selected, setSelected] = useState<string>(versions[0] ?? "");

  // When the section changes (slugKey prop), reset to the first available version
  useEffect(() => {
    setSelected(versions[0] ?? "");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slugKey]);

  if (versions.length === 0) {
    return (
      <div className="text-center text-gray-600 py-12 text-sm">
        No content available for this section.
      </div>
    );
  }

  const versionData = (job.all_data?.[selected] as Record<string, unknown> | undefined);
  const section = versionData?.[slugKey] as RichSection | undefined;
  const sourceUrl = (versionData?._section_urls as Record<string, string> | undefined)?.[slugKey];

  return (
    <div className="space-y-4">
      {/* Version selector + source link */}
      {(versions.length > 1 || sourceUrl) && (
        <div className="flex flex-wrap items-center gap-2">
          {versions.map((v) => (
            <button
              key={v}
              onClick={() => setSelected(v)}
              className={`px-3 py-1 rounded-lg text-xs font-mono font-medium transition-colors ${
                selected === v
                  ? "bg-brand-500 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}
            >
              {v}
            </button>
          ))}
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto flex items-center gap-1 text-xs text-gray-500 hover:text-brand-400 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              View in Docs
            </a>
          )}
        </div>
      )}

      {/* Content */}
      {section ? (
        section.markdown ? (
          /* PDF source: render extracted markdown (searchable, selectable) */
          <div className="bg-navy-800 border border-navy-700 rounded-xl px-6 py-5">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
              {section.markdown}
            </ReactMarkdown>
          </div>
        ) : (
          /* Scrape source: render parsed blocks */
          <div className="bg-navy-800 border border-navy-700 rounded-xl px-6 py-5">
            {section.blocks.map((block, i) => (
              <Block key={i} block={block} />
            ))}
          </div>
        )
      ) : (
        <div className="text-center text-gray-600 py-12 text-sm">
          No content for v{selected}.
        </div>
      )}
    </div>
  );
}
