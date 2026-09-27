import { Sparkles, Square } from "lucide-react";
import { useState } from "react";
import type { Snippet } from "@/lib/api/types";
import { useStream } from "@/lib/api/useStream";
import { cn } from "@/lib/utils/cn";
import { StreamedMarkdown } from "./StreamedMarkdown";

type Level = "beginner" | "intermediate" | "expert";
const LEVELS: Level[] = ["beginner", "intermediate", "expert"];

/** "Explain this code", streamed. Switching level re-asks at that level. */
export function ExplainPanel({ snippet }: { snippet: Snippet }) {
  const [level, setLevel] = useState<Level>("intermediate");
  const stream = useStream();
  const streaming = stream.status === "streaming";

  const explain = (at: Level) => {
    setLevel(at);
    void stream.start(`/snippets/${snippet.id}/ai/explain`, { level: at });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div role="group" aria-label="Explanation level" className="flex gap-1 rounded-lg bg-background p-1">
          {LEVELS.map((option) => (
            <button key={option} type="button" aria-pressed={level === option} disabled={streaming}
              onClick={() => explain(option)}
              className={cn("rounded-md px-3 py-1 text-xs capitalize",
                level === option ? "bg-surface-2 text-text" : "text-text/60 hover:text-text")}>
              {option}
            </button>
          ))}
        </div>
        {streaming ? (
          <button type="button" className="btn-secondary" onClick={stream.stop}>
            <Square aria-hidden className="size-4" /> Stop
          </button>
        ) : (
          <button type="button" className="btn-primary" onClick={() => explain(level)}>
            <Sparkles aria-hidden className="size-4" /> {stream.status === "idle" ? "Explain" : "Explain again"}
          </button>
        )}
      </div>
      {stream.status === "idle" ? (
        <p className="text-sm text-text/60">
          Pick a level and press Explain. Secrets in the code are removed before it&apos;s sent.
        </p>
      ) : (
        <StreamedMarkdown stream={stream} />
      )}
    </div>
  );
}
