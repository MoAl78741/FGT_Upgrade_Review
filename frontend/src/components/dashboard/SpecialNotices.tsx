import { AlertTriangle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { JobDetail } from "../../types";

const mdComponents = {
  h1: ({ children }: { children?: React.ReactNode }) => <h1 className="text-base font-semibold text-amber-300 mt-4 mb-2">{children}</h1>,
  h2: ({ children }: { children?: React.ReactNode }) => <h2 className="text-sm font-semibold text-amber-300 mt-3 mb-1.5">{children}</h2>,
  h3: ({ children }: { children?: React.ReactNode }) => <h3 className="text-sm font-medium text-amber-200 mt-2 mb-1">{children}</h3>,
  p:  ({ children }: { children?: React.ReactNode }) => <p className="text-sm leading-relaxed mb-2 text-gray-300">{children}</p>,
  ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc list-inside space-y-1 mb-3 ml-2">{children}</ul>,
  ol: ({ children }: { children?: React.ReactNode }) => <ol className="list-decimal list-inside space-y-1 mb-3 ml-2">{children}</ol>,
  li: ({ children }: { children?: React.ReactNode }) => <li className="text-sm text-gray-300">{children}</li>,
  code: ({ children, className }: { children?: React.ReactNode; className?: string }) =>
    className
      ? <code className="block bg-amber-950/30 border border-amber-800/40 rounded-lg px-4 py-3 mb-3 text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap">{children}</code>
      : <code className="bg-amber-950/30 px-1 py-0.5 rounded text-xs font-mono text-gray-300">{children}</code>,
  pre: ({ children }: { children?: React.ReactNode }) => <pre className="mb-3">{children}</pre>,
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="overflow-x-auto rounded-xl border border-amber-700/40 mb-4">
      <table className="w-full text-sm border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => <thead className="bg-amber-900/20 border-b border-amber-700/40">{children}</thead>,
  th: ({ children }: { children?: React.ReactNode }) => <th className="text-left text-xs font-medium py-2.5 px-4 text-amber-300">{children}</th>,
  td: ({ children }: { children?: React.ReactNode }) => <td className="py-2.5 px-4 text-xs text-gray-300 border-b border-amber-800/30 leading-relaxed">{children}</td>,
  tr: ({ children }: { children?: React.ReactNode }) => <tr className="hover:bg-amber-900/10 transition-colors">{children}</tr>,
  strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-semibold text-amber-200">{children}</strong>,
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-amber-400 hover:underline">{children}</a>
  ),
};

interface Props {
  job: JobDetail;
}

export default function SpecialNotices({ job }: Props) {
  const notices = job.special_notices ?? [];

  if (notices.length === 0) {
    return (
      <p className="text-gray-500 text-sm py-12 text-center">
        No special notices found for v{job.to_version}.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {notices.map((notice, i) => (
        <div
          key={i}
          className="bg-amber-900/20 border border-amber-700/40 rounded-xl p-5"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            <div>
              {notice.title && (
                <h3 className="text-amber-400 font-semibold text-sm mb-2">{notice.title}</h3>
              )}
              {notice.markdown ? (
                /* PDF source: render extracted markdown (searchable, selectable) */
                <div className="mt-1">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                    {notice.markdown}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-line">
                  {notice.content}
                </p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
