import { Code, Plus, Search, Star } from "lucide-react";
import { useId, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { PageLoader, Spinner } from "@/components/ui/Loaders";
import { Modal } from "@/components/ui/Modal";
import {
  SnippetCard,
  SnippetForm,
  useDeleteSnippetMutation,
  useListSnippetsInfiniteQuery,
  useListTagsQuery,
  type SnippetFilters,
} from "@/features/snippets";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { toApiError } from "@/lib/api/errors";
import type { Snippet } from "@/lib/api/types";
import { cn } from "@/lib/utils/cn";

type Editing = { mode: "create" } | { mode: "edit"; snippet: Snippet } | null;

export function SnippetsPage() {
  const [search, setSearch] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [favorite, setFavorite] = useState(false);
  const [editing, setEditing] = useState<Editing>(null);
  const [deleting, setDeleting] = useState<Snippet | null>(null);
  const searchId = useId();

  // Filtering happens on the server; the debounce keeps typing from firing a request per key.
  const q = useDebouncedValue(search.trim(), 300);
  const filters: SnippetFilters = { q: q || undefined, tag: tag ?? undefined, favorite };
  const list = useListSnippetsInfiniteQuery(filters);
  const { data: tags = [] } = useListTagsQuery();
  const [deleteSnippet] = useDeleteSnippetMutation();

  const snippets = list.data?.pages.flatMap((page) => page.items) ?? [];
  const filtering = Boolean(q || tag || favorite);

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
            <input id={searchId} type="search" className="input-field pl-9" placeholder="Search title, description or code…"
              value={search} onChange={(e) => setSearch(e.target.value)} />
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

      {list.isLoading ? (
        <PageLoader label="Loading snippets…" />
      ) : list.error ? (
        <Alert tone="error">{toApiError(list.error).message}</Alert>
      ) : snippets.length === 0 ? (
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
          <div className="grid gap-4 lg:grid-cols-2" aria-busy={list.isFetching}>
            {snippets.map((snippet, index) => (
              <SnippetCard key={snippet.id} snippet={snippet} index={index}
                onEdit={(s) => setEditing({ mode: "edit", snippet: s })} onDelete={setDeleting} />
            ))}
          </div>
          {list.hasNextPage && (
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
