import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/ui/Loaders";
import type { StreamState } from "@/lib/api/useStream";

interface Props {
  stream: Pick<StreamState<unknown>, "status" | "text" | "error">;
  /** Rendered in place of markdown links, e.g. clickable citations. */
  renderLink?: (href: string, children: ReactNode) => ReactNode;
  markdown?: string;
}

/** An answer as it arrives: markdown re-rendered on every token, then a final state. */
export function StreamedMarkdown({ stream, renderLink, markdown }: Props) {
  const text = markdown ?? stream.text;
  return (
    <div className="space-y-3">
      {text && (
        // aria-live off while streaming: announcing every token would drown screen readers;
        // the finished answer is announced once via the status line below.
        <div className="prose prose-invert max-w-none text-sm prose-pre:bg-background">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={
              renderLink
                ? { a: ({ href, children }) => <>{renderLink(href ?? "", children)}</> }
                : undefined
            }
          >
            {text}
          </ReactMarkdown>
        </div>
      )}
      <div aria-live="polite" className="text-xs text-text/50">
        {stream.status === "streaming" && (
          <span className="inline-flex items-center gap-2">
            <Spinner className="size-3.5" /> Writing…
          </span>
        )}
        {stream.status === "stopped" && "Stopped."}
        {stream.status === "done" && <span className="sr-only">Answer complete.</span>}
      </div>
      {stream.status === "error" && stream.error && <Alert tone="error">{stream.error.message}</Alert>}
    </div>
  );
}
