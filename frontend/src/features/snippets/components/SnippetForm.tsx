import { useId, useState, type FormEvent } from "react";
import { Spinner } from "@/components/ui/Loaders";
import { ApiErrorMessage } from "@/features/auth";
import { toApiError } from "@/lib/api/errors";
import type { Snippet } from "@/lib/api/types";
import { useCreateSnippetMutation, useUpdateSnippetMutation } from "../api/snippetsApi";
import { parseTags } from "../lib/tags";

/** Create (no `snippet`) or edit (with one). Calls onDone after a successful save. */
export function SnippetForm({ snippet, onDone }: { snippet?: Snippet; onDone: () => void }) {
  const [title, setTitle] = useState(snippet?.title ?? "");
  const [description, setDescription] = useState(snippet?.description ?? "");
  const [language, setLanguage] = useState(snippet?.language ?? "");
  const [tags, setTags] = useState(snippet?.tags.join(", ") ?? "");
  const [code, setCode] = useState(snippet?.code ?? "");
  const [create, createState] = useCreateSnippetMutation();
  const [update, updateState] = useUpdateSnippetMutation();
  const state = snippet ? updateState : createState;
  const ids = { title: useId(), description: useId(), language: useId(), tags: useId(), code: useId() };

  const canSave = title.trim() !== "" && code.trim() !== "";

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSave || state.isLoading) return;
    const fields = {
      title,
      description: description || null,
      language: language || null,
      tags: parseTags(tags),
      code,
    };
    const saved = snippet
      ? await update({ id: snippet.id, changes: fields }).unwrap().catch(() => null)
      : await create({ ...fields, favorite: false }).unwrap().catch(() => null);
    if (saved) onDone();
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {state.error && <ApiErrorMessage error={toApiError(state.error)} />}
      <div>
        <label htmlFor={ids.title} className="label">
          Title
        </label>
        <input id={ids.title} className="input-field" value={title} maxLength={200} required
          onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div>
        <label htmlFor={ids.description} className="label">
          Description <span className="font-normal text-text/50">(optional)</span>
        </label>
        <input id={ids.description} className="input-field" value={description} maxLength={1000}
          onChange={(e) => setDescription(e.target.value)} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor={ids.language} className="label">
            Language
          </label>
          <input id={ids.language} className="input-field" value={language} maxLength={40}
            placeholder="typescript" onChange={(e) => setLanguage(e.target.value)} />
        </div>
        <div>
          <label htmlFor={ids.tags} className="label">
            Tags <span className="font-normal text-text/50">(comma-separated)</span>
          </label>
          <input id={ids.tags} className="input-field" value={tags} placeholder="react, hooks"
            onChange={(e) => setTags(e.target.value)} />
        </div>
      </div>
      <div>
        <label htmlFor={ids.code} className="label">
          Code
        </label>
        <textarea id={ids.code} className="input-field min-h-56 font-mono text-xs" value={code}
          spellCheck={false} required onChange={(e) => setCode(e.target.value)} />
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-secondary" onClick={onDone}>
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={!canSave || state.isLoading}>
          {state.isLoading && <Spinner className="size-4" />}
          {snippet ? "Save changes" : "Add snippet"}
        </button>
      </div>
    </form>
  );
}
