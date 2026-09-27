import { MessageCircleQuestion, Square } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { useStream } from "@/lib/api/useStream";
import type { Source } from "../api/aiApi";
import { linkCitations } from "../lib/citations";
import { StreamedMarkdown } from "./StreamedMarkdown";

/** Ask a question; the answer cites numbered passages from the user's own notes. */
export function AskNotesPanel({ onOpenNote }: { onOpenNote: (noteId: string) => void }) {
  const [question, setQuestion] = useState("");
  const stream = useStream<Source>();
  const inputId = useId();
  const streaming = stream.status === "streaming";

  function ask(event: FormEvent) {
    event.preventDefault();
    if (question.trim()) void stream.start("/notes/ask", { question: question.trim() });
  }

  const openSource = (n: number) => {
    const source = stream.sources.find((s) => s.n === n);
    if (source) onOpenNote(source.note_id);
  };

  return (
    <section aria-labelledby={`${inputId}-title`} className="space-y-3">
      <h2 id={`${inputId}-title`} className="flex items-center gap-2 text-sm font-semibold">
        <MessageCircleQuestion aria-hidden className="size-4 text-accent" /> Ask your notes
      </h2>
      <form onSubmit={ask} className="flex gap-2">
        <label htmlFor={inputId} className="sr-only">Question</label>
        <input id={inputId} className="input-field" placeholder="e.g. how do I roll back a deploy?"
          value={question} maxLength={500} onChange={(e) => setQuestion(e.target.value)} />
        {streaming ? (
          <button type="button" className="btn-secondary" onClick={stream.stop} aria-label="Stop">
            <Square aria-hidden className="size-4" />
          </button>
        ) : (
          <button type="submit" className="btn-primary" disabled={!question.trim()}>Ask</button>
        )}
      </form>

      {stream.status !== "idle" && (
        <div className="space-y-3 rounded-lg border border-border p-3">
          <StreamedMarkdown
            stream={stream}
            markdown={linkCitations(stream.text, stream.sources.length)}
            renderLink={(href, children) => {
              const n = Number(href.replace("#source-", ""));
              return href.startsWith("#source-") ? (
                <button type="button" onClick={() => openSource(n)} aria-label={`Open source ${n}`}
                  className="mx-0.5 rounded bg-accent/15 px-1 text-xs font-medium text-accent no-underline hover:bg-accent/25">
                  {n}
                </button>
              ) : (
                <span>{children}</span> // other links are shown as text, never followed
              );
            }}
          />
          {stream.sources.length > 0 && (
            <ol className="space-y-1 border-t border-border pt-2 text-xs" aria-label="Sources">
              {stream.sources.map((source) => (
                <li key={source.n} id={`source-${source.n}`}>
                  <button type="button" onClick={() => onOpenNote(source.note_id)}
                    className="text-left text-text/70 hover:text-text">
                    <span className="font-medium text-accent">[{source.n}]</span>{" "}
                    {source.note_title}
                    {source.heading && <> — {source.heading}</>}
                  </button>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  );
}
