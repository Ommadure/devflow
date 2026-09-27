import { FileInput, Send, ShieldCheck } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/ui/Loaders";
import { Modal } from "@/components/ui/Modal";
import {
  BODYLESS,
  ImportCurl,
  ResponseView,
  parseHeaders,
  useSendRequestMutation,
  type CurlParsed,
  type ProxyRequest,
} from "@/features/api-tester";
import { toApiError } from "@/lib/api/errors";

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] as const;
type HttpMethod = (typeof METHODS)[number];

export function ApiTesterPage() {
  const [method, setMethod] = useState<HttpMethod>("GET");
  const [url, setUrl] = useState("https://api.github.com/zen");
  const [headers, setHeaders] = useState('{\n  "Accept": "application/json"\n}');
  const [body, setBody] = useState("");
  const [importing, setImporting] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [sent, setSent] = useState<ProxyRequest | null>(null);
  const [send, result] = useSendRequestMutation();
  const ids = { method: useId(), url: useId(), headers: useId(), body: useId() };

  const parsedHeaders = parseHeaders(headers);
  const bodyless = BODYLESS.has(method);
  const canSend = url.trim() !== "" && "headers" in parsedHeaders && !result.isLoading;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSend || !("headers" in parsedHeaders)) return;
    const request: ProxyRequest = {
      method, url: url.trim(), headers: parsedHeaders.headers, body: bodyless ? null : body || null,
    };
    setSent(request);
    void send(request);
  }

  function applyImport(parsed: CurlParsed) {
    setMethod((METHODS as readonly string[]).includes(parsed.method) ? (parsed.method as HttpMethod) : "GET");
    setUrl(parsed.url);
    setHeaders(JSON.stringify(parsed.headers, null, 2));
    setBody(parsed.body ?? "");
    setWarnings(parsed.warnings);
    setImporting(false);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">API Tester</h1>
          <p className="flex items-center gap-1.5 text-sm text-text/60">
            <ShieldCheck aria-hidden className="size-4" /> Sent from DevFlow&apos;s server: no browser CORS
            limits, and private networks are off-limits.
          </p>
        </div>
        <button type="button" className="btn-secondary" onClick={() => setImporting(true)}>
          <FileInput aria-hidden className="size-4" /> Import cURL
        </button>
      </header>

      {warnings.length > 0 && (
        <Alert tone="info">
          <p>Imported, with notes:</p>
          <ul className="list-disc pl-4 text-xs">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </Alert>
      )}

      <form onSubmit={submit} className="card space-y-4" noValidate>
        <div className="flex gap-2">
          <label htmlFor={ids.method} className="sr-only">Method</label>
          <select id={ids.method} className="input-field w-32 font-mono" value={method}
            onChange={(e) => setMethod(e.target.value as HttpMethod)}>
            {METHODS.map((m) => <option key={m}>{m}</option>)}
          </select>
          <label htmlFor={ids.url} className="sr-only">URL</label>
          <input id={ids.url} className="input-field font-mono" type="url" value={url} required
            placeholder="https://api.example.com/resource" onChange={(e) => setUrl(e.target.value)} />
          <button type="submit" className="btn-primary" disabled={!canSend}>
            {result.isLoading ? <Spinner className="size-4" /> : <Send aria-hidden className="size-4" />} Send
          </button>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor={ids.headers} className="label">Headers (JSON)</label>
            <textarea id={ids.headers} className="input-field min-h-32 font-mono text-xs" value={headers}
              spellCheck={false} aria-invalid={"error" in parsedHeaders}
              onChange={(e) => setHeaders(e.target.value)} />
            {"error" in parsedHeaders && <p className="mt-1 text-xs text-danger">{parsedHeaders.error}</p>}
          </div>
          <div>
            <label htmlFor={ids.body} className="label">
              Body {bodyless && <span className="font-normal text-text/50">({method} requests have no body)</span>}
            </label>
            <textarea id={ids.body} className="input-field min-h-32 font-mono text-xs" value={body}
              spellCheck={false} disabled={bodyless} onChange={(e) => setBody(e.target.value)} />
          </div>
        </div>
      </form>

      {result.error && <Alert tone="error">{toApiError(result.error).message}</Alert>}
      {result.data && sent && !result.isLoading && <ResponseView request={sent} response={result.data} />}

      <Modal open={importing} title="Import a cURL command" size="lg" onClose={() => setImporting(false)}>
        <ImportCurl onImport={applyImport} />
      </Modal>
    </div>
  );
}
