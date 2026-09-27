import { Plus, Sparkles } from "lucide-react";
import { Spinner } from "@/components/ui/Loaders";
import { toApiError } from "@/lib/api/errors";
import { useSuggestTagsMutation } from "../api/aiApi";

interface Props {
  snippetId: string;
  currentTags: string[];
  onAddTag: (tag: string) => void;
  onUseLanguage: (language: string) => void;
  onUseDescription: (description: string) => void;
}

/** AI suggestions as chips: nothing changes until the user picks one. */
export function TagSuggestions({ snippetId, currentTags, onAddTag, onUseLanguage, onUseDescription }: Props) {
  const [suggest, { data, isLoading, error }] = useSuggestTagsMutation();
  const newTags = data?.tags.filter((tag) => !currentTags.includes(tag)) ?? [];
  const chip = "inline-flex items-center gap-1 rounded-full border border-accent/40 px-2 py-0.5 text-xs hover:bg-accent/15";

  return (
    <div className="space-y-2 rounded-lg border border-dashed border-border p-3">
      <button type="button" className="btn-ghost -ml-2 px-2 py-1 text-xs" disabled={isLoading}
        onClick={() => void suggest(snippetId)}>
        {isLoading ? <Spinner className="size-3.5" /> : <Sparkles aria-hidden className="size-3.5" />}
        Suggest tags with AI
      </button>
      {error && <p className="text-xs text-danger">{toApiError(error).message}</p>}
      {data && (
        <div className="flex flex-wrap items-center gap-1.5" aria-label="Suggestions">
          {newTags.map((tag) => (
            <button key={tag} type="button" className={chip} onClick={() => onAddTag(tag)} aria-label={`Add tag ${tag}`}>
              <Plus aria-hidden className="size-3" /> #{tag}
            </button>
          ))}
          <button type="button" className={chip} onClick={() => onUseLanguage(data.language)}
            aria-label={`Use language ${data.language}`}>
            <Plus aria-hidden className="size-3" /> {data.language}
          </button>
          <button type="button" className={chip} onClick={() => onUseDescription(data.description)}
            title={data.description}>
            <Plus aria-hidden className="size-3" /> Use description
          </button>
        </div>
      )}
    </div>
  );
}
