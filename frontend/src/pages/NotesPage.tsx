import { skipToken } from "@reduxjs/toolkit/query";
import { MessageCircleQuestion, NotebookPen, Plus, Search, Trash2 } from "lucide-react";
import { useId, useState } from "react";
import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { Alert } from "@/components/ui/Alert";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { PageLoader, Spinner } from "@/components/ui/Loaders";
import { AskNotesPanel } from "@/features/ai";
import {
  NoteEditor,
  noteSelected,
  selectActiveNoteId,
  useCreateNoteMutation,
  useDeleteNoteMutation,
  useGetNoteQuery,
  useListNotesInfiniteQuery,
} from "@/features/notes";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { toApiError } from "@/lib/api/errors";
import type { Note } from "@/lib/api/types";
import { formatRelative } from "@/lib/utils/dates";
import { cn } from "@/lib/utils/cn";

export function NotesPage() {
  const dispatch = useAppDispatch();
  const activeId = useAppSelector(selectActiveNoteId);
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState<Note | null>(null);
  const [asking, setAsking] = useState(false);
  const searchId = useId();

  const q = useDebouncedValue(search.trim(), 300);
  const list = useListNotesInfiniteQuery({ q: q || undefined });
  const active = useGetNoteQuery(activeId ?? skipToken);
  const [createNote, { isLoading: creating }] = useCreateNoteMutation();
  const [deleteNote] = useDeleteNoteMutation();

  // Autosave patches notes in place, so re-sort here: the note being edited rises to the top.
  const notes = [...(list.data?.pages.flatMap((page) => page.items) ?? [])].sort((a, b) =>
    b.updated_at.localeCompare(a.updated_at),
  );

  async function newNote() {
    const note = await createNote({ title: "", content: "" }).unwrap().catch(() => null);
    if (note) dispatch(noteSelected(note.id));
  }

  return (
    <div className="grid h-[calc(100vh-4rem)] gap-4 lg:grid-cols-[20rem_1fr]">
      <section aria-labelledby="notes-heading" className="flex min-h-0 flex-col gap-3">
        <div className="flex items-center justify-between">
          <h1 id="notes-heading" className="text-2xl font-semibold">
            Notes
          </h1>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" aria-pressed={asking}
              onClick={() => setAsking((open) => !open)}>
              <MessageCircleQuestion aria-hidden className="size-4" /> Ask
            </button>
            <button type="button" className="btn-primary" onClick={() => void newNote()} disabled={creating}>
              {creating ? <Spinner className="size-4" /> : <Plus aria-hidden className="size-4" />} New
            </button>
          </div>
        </div>
        <div className="relative">
          <label htmlFor={searchId} className="sr-only">
            Search notes
          </label>
          <Search aria-hidden className="pointer-events-none absolute top-2.5 left-3 size-4 text-text/40" />
          <input id={searchId} type="search" className="input-field pl-9" placeholder="Search notes…"
            value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>

        {list.isLoading ? (
          <PageLoader label="Loading notes…" />
        ) : list.error ? (
          <Alert tone="error">{toApiError(list.error).message}</Alert>
        ) : notes.length === 0 ? (
          <p className="p-4 text-center text-sm text-text/60">{q ? "No notes match." : "No notes yet."}</p>
        ) : (
          <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto" aria-label="Notes">
            {notes.map((note) => (
              <li key={note.id} className="group relative">
                <button type="button" aria-current={note.id === activeId ? "true" : undefined}
                  onClick={() => dispatch(noteSelected(note.id))}
                  className={cn(
                    "w-full rounded-lg px-3 py-2 pr-10 text-left transition-colors",
                    note.id === activeId ? "bg-accent/15" : "hover:bg-surface-2",
                  )}>
                  <span className={cn("block truncate text-sm font-medium", !note.title && "text-text/50 italic")}>
                    {note.title || "Untitled"}
                  </span>
                  <span className="block text-xs text-text/50">{formatRelative(note.updated_at)}</span>
                </button>
                <button type="button" onClick={() => setDeleting(note)}
                  aria-label={`Delete ${note.title || "untitled note"}`}
                  className="btn-ghost absolute top-2 right-1 p-1.5 opacity-0 group-hover:opacity-100 focus:opacity-100">
                  <Trash2 aria-hidden className="size-4" />
                </button>
              </li>
            ))}
            {list.hasNextPage && (
              <li>
                <button type="button" className="btn-ghost w-full" onClick={() => void list.fetchNextPage()}>
                  Load more
                </button>
              </li>
            )}
          </ul>
        )}
      </section>

      <div className="flex min-h-0 flex-col gap-4">
      {asking && (
        <div className="card max-h-[50%] shrink-0 overflow-y-auto p-4">
          <AskNotesPanel onOpenNote={(id) => dispatch(noteSelected(id))} />
        </div>
      )}
      <section aria-label="Editor" className="card min-h-0 flex-1 p-4">
        {active.data ? (
          <NoteEditor key={active.data.id} note={active.data} />
        ) : active.isFetching ? (
          <PageLoader />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-text/60">
            <NotebookPen aria-hidden className="size-10 text-text/30" />
            <p>Select a note, or start a new one — or ask your notes a question.</p>
          </div>
        )}
      </section>
      </div>

      <ConfirmDialog
        open={deleting !== null}
        title="Delete note?"
        message={`"${deleting?.title || "Untitled"}" will be deleted. This can't be undone.`}
        onConfirm={async () => {
          await deleteNote(deleting!.id).unwrap();
          if (deleting!.id === activeId) dispatch(noteSelected(null));
        }}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}
