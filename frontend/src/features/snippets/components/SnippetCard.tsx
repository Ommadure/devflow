import { Check, Copy, Pencil, Star, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import type { Snippet } from "@/lib/api/types";
import { cn } from "@/lib/utils/cn";
import { useUpdateSnippetMutation } from "../api/snippetsApi";

interface Props {
  snippet: Snippet;
  index: number;
  onEdit: (snippet: Snippet) => void;
  onDelete: (snippet: Snippet) => void;
}

export function SnippetCard({ snippet, index, onEdit, onDelete }: Props) {
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
        {snippet.language && (
          <span className="shrink-0 rounded-full bg-accent/15 px-2 py-0.5 font-mono text-xs text-accent">
            {snippet.language}
          </span>
        )}
      </header>

      <pre className="max-h-48 overflow-auto rounded-lg bg-background p-3 font-mono text-xs leading-relaxed">
        <code>{snippet.code}</code>
      </pre>

      <footer className="mt-auto flex items-center justify-between gap-2">
        <ul className="flex flex-wrap gap-1" aria-label="Tags">
          {snippet.tags.map((tag) => (
            <li key={tag} className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-text/70">
              #{tag}
            </li>
          ))}
        </ul>
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
