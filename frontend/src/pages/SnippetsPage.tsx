import { Code, Plus, Search, Star } from "lucide-react";
import { useId, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { PageLoader, Spinner } from "@/components/ui/Loaders";
import { Modal } from "@/components/ui/Modal";
import { ExplainPanel } from "@/features/ai";
import {
  SnippetCard,
  SnippetForm,
  useDeleteSnippetMutation,
  useListSnippetsInfiniteQuery,
  useListTagsQuery,
  useSearchSnippetsQuery,
  type SnippetFilters,
} from "@/features/snippets";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { toApiError } from "@/lib/api/errors";
import type { SearchMode, Snippet } from "@/lib/api/types";
import { cn } from "@/lib/utils/cn";

type Editing = { mode: "create" } | { mode: "edit"; snippet: Snippet } | null;

const MODES: Array<{ mode: SearchMode; label: string; hint: string }> = [
  { mode: "hybrid", label: "Hybrid", hint: "Words and meaning, fused" },
  { mode: "keyword", label: "Keyword", hint: "Only the words you typed" },
  { mode: "semantic", label: "Semantic", hint: "Only by meaning" },
];
// While the worker is still embedding new snippets, check back every few seconds.
const INDEXING_POLL_MS = 3000;

export function SnippetsPage() {
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [favorite, setFavorite] = useState(false);
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [editing, setEditing] = useState<Editing>(null);
  const [deleting, setDeleting] = useState<Snippet | null>(null);
  const [explaining, setExplaining] = useState<Snippet | null>(null);
  const searchId = useId();

  // Typing debounced: one search when the user pauses, not one per keystroke.
  const q = useDebouncedValue(search.trim(), 300);
  const searching = q !== "";
  const filters: SnippetFilters = { tag: tag ?? undefined, favorite };

  const [pollingInterval, setPollingInterval] = useState(0);
  const list = useListSnippetsInfiniteQuery(filters, { skip: searching, pollingInterval });
  const results = useSearchSnippetsQuery({ q, mode, ...filters }, { skip: !searching });
  const { data: tags = [] } = useListTagsQuery();
  const [deleteSnippet] = useDeleteSnippetMutation();

  const listed = list.data?.pages.flatMap((page) => page.items) ?? [];
  const hits = results.data?.items ?? [];
  const shown: Snippet[] = searching ? hits : listed;
  const active = searching ? results : list;
  const filtering = Boolean(searching || tag || favorite);

  // Poll only while something is still being indexed; stop as soon as it's all ready.
  // (Adjusting state during render — React's pattern for state derived from the previous
  // render's data — because the interval depends on data the same hook returns.)
  const indexing = listed.some((snippet) => snippet.embedding_status === "pending");
  if ((indexing ? INDEXING_POLL_MS : 0) !== pollingInterval) {
    setPollingInterval(indexing ? INDEXING_POLL_MS : 0);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Snippets</h1>
        <button type="button" className="btn-primary" onClick={() => setEditing({ mode: "create" })}>
          <Plus aria-hidden className="size-4" /> Add snippet
        </button>
      </header>

      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <div className="relative min-w-60 flex-1">
            <label htmlFor={searchId} className="sr-only">
              Search snippets
            </label>
            <Search aria-hidden className="pointer-events-none absolute top-2.5 left-3 size-4 text-text/40" />
            <input id={searchId} type="search" className="input-field pl-9"
              placeholder='Search by words or meaning, e.g. "stop a function firing too often"'
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div role="group" aria-label="Search mode" className="flex gap-1 rounded-lg bg-background p-1">
            {MODES.map((option) => (
              <button key={option.mode} type="button" title={option.hint} aria-pressed={mode === option.mode}
                onClick={() => setMode(option.mode)}
                className={cn("rounded-md px-3 py-1 text-xs",
                  mode === option.mode ? "bg-surface-2 text-text" : "text-text/60 hover:text-text")}>
                {option.label}
              </button>
            ))}
          </div>
          <button type="button" aria-pressed={favorite} onClick={() => setFavorite((f) => !f)}
            className={cn("btn-secondary", favorite && "border-warning/60 text-warning")}>
            <Star aria-hidden className={cn("size-4", favorite && "fill-warning")} /> Favourites
          </button>
        </div>
        {tags.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="Filter by tag">
            {tags.map(({ tag: name, count }) => (
              <li key={name}>
                <button type="button" aria-pressed={tag === name}
                  onClick={() => setTag((current) => (current === name ? null : name))}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs transition-colors",
                    tag === name ? "border-accent bg-accent/15 text-text" : "border-border text-text/70 hover:text-text",
                  )}>
                  #{name} <span className="text-text/40">{count}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {active.isLoading ? (
        <PageLoader label={searching ? "Searching…" : "Loading snippets…"} />
      ) : active.error ? (
        <Alert tone="error">{toApiError(active.error).message}</Alert>
      ) : shown.length === 0 ? (
        <div className="card flex flex-col items-center gap-3 py-12 text-center">
          <Code aria-hidden className="size-10 text-text/30" />
          <p className="text-text/70">{filtering ? "No snippets match these filters." : "No snippets yet."}</p>
          {!filtering && (
            <button type="button" className="btn-primary" onClick={() => setEditing({ mode: "create" })}>
              Add your first snippet
            </button>
          )}
        </div>
      ) : (
        <>
          {searching && (
            <p className="text-sm text-text/60" aria-live="polite">
              {hits.length} {hits.length === 1 ? "result" : "results"}, best first
            </p>
          )}
          <div className="grid gap-4 lg:grid-cols-2" aria-busy={active.isFetching}>
            {shown.map((snippet, index) => (
              <SnippetCard key={snippet.id} snippet={snippet} index={index}
                matchType={searching ? hits[index]?.match_type : undefined}
                onEdit={(s) => setEditing({ mode: "edit", snippet: s })} onDelete={setDeleting}
                onExplain={setExplaining} />
            ))}
          </div>
          {!searching && list.hasNextPage && (
            <div className="flex justify-center">
              <button type="button" className="btn-secondary" disabled={list.isFetchingNextPage}
                onClick={() => void list.fetchNextPage()}>
                {list.isFetchingNextPage && <Spinner className="size-4" />} Load more
              </button>
            </div>
          )}
        </>
      )}

      <Modal open={editing !== null} size="lg" onClose={() => setEditing(null)}
        title={editing?.mode === "edit" ? "Edit snippet" : "Add snippet"}>
        {editing && (
          <SnippetForm
            key={editing.mode === "edit" ? editing.snippet.id : "new"}
            snippet={editing.mode === "edit" ? editing.snippet : undefined}
            onDone={() => setEditing(null)}
          />
        )}
      </Modal>

      <Modal open={explaining !== null} size="lg" onClose={() => setExplaining(null)}
        title={`Explain: ${explaining?.title ?? ""}`}>
        {/* Keyed: a different snippet starts a fresh explanation. */}
        {explaining && <ExplainPanel key={explaining.id} snippet={explaining} />}
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        title="Delete snippet?"
        message={`"${deleting?.title ?? ""}" will be deleted. This can't be undone.`}
        onConfirm={() => deleteSnippet(deleting!.id).unwrap()}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}
