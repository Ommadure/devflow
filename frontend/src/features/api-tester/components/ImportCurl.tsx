import { useId, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/ui/Loaders";
import { toApiError } from "@/lib/api/errors";
import { useParseCurlMutation, type CurlParsed } from "../api/apiTesterApi";

/** Paste a cURL command (DevTools → Copy as cURL); parsed on the server by rules, not AI. */
export function ImportCurl({ onImport }: { onImport: (parsed: CurlParsed) => void }) {
  const [command, setCommand] = useState("");
  const [parse, { isLoading, error }] = useParseCurlMutation();
  const id = useId();

  async function submit() {
    const parsed = await parse(command).unwrap().catch(() => null);
    if (parsed) onImport(parsed);
  }

  return (
    <div className="space-y-3">
      <label htmlFor={id} className="label">cURL command</label>
      <textarea id={id} className="input-field min-h-40 font-mono text-xs" value={command} spellCheck={false}
        placeholder={"curl 'https://api.example.com/items' \\\n  -H 'Authorization: Bearer …'"}
        onChange={(e) => setCommand(e.target.value)} />
      {error && <Alert tone="error">{toApiError(error).message}</Alert>}
      <div className="flex justify-end">
        <button type="button" className="btn-primary" disabled={!command.trim() || isLoading} onClick={() => void submit()}>
          {isLoading && <Spinner className="size-4" />} Import
        </button>
      </div>
    </div>
  );
}
