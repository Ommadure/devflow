import { Check, Copy, Pencil, Star, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { SearchHit, Snippet } from "@/lib/api/types";
import { cn } from "@/lib/utils/cn";
import { useUpdateSnippetMutation } from "../api/snippetsApi";

const MATCH_LABELS: Record<SearchHit["match_type"], { label: string; hint: string }> = {
  keyword: { label: "Keyword", hint: "Matched the words you typed" },
  semantic: { label: "Semantic", hint: "Matched by meaning, not by the exact words" },
  both: { label: "Keyword + meaning", hint: "Matched both your words and their meaning" },
};

interface Props {
  snippet: Snippet;
  /** How a search result matched; absent in the plain list. */
  matchType?: SearchHit["match_type"];
  index: number;
  onEdit: (snippet: Snippet) => void;
  onDelete: (snippet: Snippet) => void;
}

export function SnippetCard({ snippet, matchType, index, onEdit, onDelete }: Props) {
  const [copied, setCopied] = useState(false);
  const [update] = useUpdateSnippetMutation();

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    await navigator.clipboard.writeText(snippet.code);
    setCopied(true);
  }

  // Actions are always reachable by keyboard; hover only changes how prominent they are.
  const action = "btn-ghost p-2";
  return (
    <article
      aria-labelledby={`snippet-${snippet.id}`}
      className="card group flex animate-fade-up flex-col gap-3 p-4"
      style={{ "--i": Math.min(index, 10) } as React.CSSProperties}
    >
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 id={`snippet-${snippet.id}`} className="truncate font-semibold">
            {snippet.title}
          </h3>
          {snippet.description && <p className="truncate text-sm text-text/60">{snippet.description}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {matchType && (
            <span title={MATCH_LABELS[matchType].hint}
              className="rounded-full border border-success/40 px-2 py-0.5 text-xs text-success">
              {MATCH_LABELS[matchType].label}
            </span>
          )}
          {snippet.language && (
            <span className="rounded-full bg-accent/15 px-2 py-0.5 font-mono text-xs text-accent">
              {snippet.language}
            </span>
          )}
        </div>
      </header>

      <pre className="max-h-48 overflow-auto rounded-lg bg-background p-3 font-mono text-xs leading-relaxed">
        <code>{snippet.code}</code>
      </pre>

      <footer className="mt-auto flex items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-1">
          <ul className="flex flex-wrap gap-1" aria-label="Tags">
            {snippet.tags.map((tag) => (
              <li key={tag} className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-text/70">
                #{tag}
              </li>
            ))}
          </ul>
          {snippet.embedding_status === "pending" && (
            <span className="text-xs text-text/50" title="Semantic search will find it in a moment">
              Indexing…
            </span>
          )}
          {snippet.embedding_status === "failed" && (
            <span className="text-xs text-warning" title="Keyword search still finds it">
              Not searchable by meaning
            </span>
          )}
        </div>
        <div className="flex shrink-0 opacity-70 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <button type="button" className={action} onClick={() => void copy()}
            aria-label={copied ? "Copied" : `Copy ${snippet.title}`}>
            {copied ? <Check aria-hidden className="size-4 text-success" /> : <Copy aria-hidden className="size-4" />}
          </button>
          <button type="button" className={action} aria-pressed={snippet.favorite}
            aria-label={snippet.favorite ? `Unfavourite ${snippet.title}` : `Favourite ${snippet.title}`}
            onClick={() => void update({ id: snippet.id, changes: { favorite: !snippet.favorite } })}>
            <Star aria-hidden className={cn("size-4", snippet.favorite && "fill-warning text-warning")} />
          </button>
          <button type="button" className={action} onClick={() => onEdit(snippet)} aria-label={`Edit ${snippet.title}`}>
            <Pencil aria-hidden className="size-4" />
          </button>
          <button type="button" className={action} onClick={() => onDelete(snippet)} aria-label={`Delete ${snippet.title}`}>
            <Trash2 aria-hidden className="size-4" />
          </button>
        </div>
      </footer>
    </article>
  );
}
