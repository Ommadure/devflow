import { useCallback, useId, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Note } from "@/lib/api/types";
import { cn } from "@/lib/utils/cn";
import { useUpdateNoteMutation } from "../api/notesApi";
import { useAutosave, type SaveStatus } from "../hooks/useAutosave";

type Draft = { title: string; content: string };
const sameDraft = (a: Draft, b: Draft) => a.title === b.title && a.content === b.content;

const STATUS_TEXT: Record<SaveStatus, string> = {
  saved: "Saved",
  pending: "Unsaved changes",
  saving: "Saving…",
  error: "Couldn't save",
};

/** Mounted once per note (keyed by id), so switching notes starts from that note's text. */
export function NoteEditor({ note }: { note: Note }) {
  const [draft, setDraft] = useState<Draft>({ title: note.title, content: note.content });
  const [view, setView] = useState<"write" | "preview">("write");
  const [update] = useUpdateNoteMutation();
  const titleId = useId();
  const contentId = useId();

  const save = useCallback(
    (value: Draft) => update({ id: note.id, changes: value }).unwrap(),
    [note.id, update],
  );
  const { status, change, flush } = useAutosave(draft, save, { isEqual: sameDraft });

  function edit(changes: Partial<Draft>) {
    const next = { ...draft, ...changes };
    setDraft(next);
    change(next);
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex items-center gap-3">
        <label htmlFor={titleId} className="sr-only">
          Title
        </label>
        <input id={titleId} value={draft.title} maxLength={200} placeholder="Untitled"
          onChange={(e) => edit({ title: e.target.value })}
          className="min-w-0 flex-1 bg-transparent text-xl font-semibold outline-none placeholder:text-text/30" />
        <p aria-live="polite" className={cn("shrink-0 text-xs", status === "error" ? "text-danger" : "text-text/50")}>
          {STATUS_TEXT[status]}
          {status === "error" && (
            <button type="button" className="ml-2 underline" onClick={() => void flush()}>
              Retry
            </button>
          )}
        </p>
      </div>

      <div role="group" aria-label="Editor mode" className="flex w-fit gap-1 rounded-lg bg-background p-1">
        {(["write", "preview"] as const).map((mode) => (
          <button key={mode} type="button" aria-pressed={view === mode} onClick={() => setView(mode)}
            className={cn("rounded-md px-3 py-1 text-xs capitalize",
              view === mode ? "bg-surface-2 text-text" : "text-text/60 hover:text-text")}>
            {mode}
          </button>
        ))}
      </div>

      {view === "write" ? (
        <>
          <label htmlFor={contentId} className="sr-only">
            Content (markdown)
          </label>
          <textarea id={contentId} value={draft.content} spellCheck
            placeholder="Write in markdown: # headings, **bold**, - lists, ```code```, | tables |"
            onChange={(e) => edit({ content: e.target.value })}
            className="input-field min-h-96 flex-1 resize-none font-mono text-sm leading-relaxed" />
        </>
      ) : (
        // react-markdown never renders raw HTML and drops javascript: links by default, so a
        // note can't inject script into the page.
        <div className="prose prose-invert max-w-none flex-1 overflow-auto rounded-lg border border-border p-4 prose-pre:bg-background">
          {draft.content.trim() ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{draft.content}</ReactMarkdown>
          ) : (
            <p className="text-text/40">Nothing to preview yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
