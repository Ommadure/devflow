/** Pretty-print JSON bodies; anything else is shown as it came. */
export function prettyBody(body: string, headers: Array<[string, string]>): { text: string; isJson: boolean } {
  const type = headers.find(([name]) => name.toLowerCase() === "content-type")?.[1] ?? "";
  const looksJson = type.includes("json") || /^\s*[[{]/.test(body);
  if (looksJson) {
    try {
      return { text: JSON.stringify(JSON.parse(body), null, 2), isJson: true };
    } catch {
      // not actually JSON (or truncated mid-document): show it raw
    }
  }
  return { text: body, isJson: false };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

/** Parse the headers editor: a JSON object of string values, or an explanation why not. */
export function parseHeaders(text: string): { headers: Record<string, string> } | { error: string } {
  if (!text.trim()) return { headers: {} };
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return { error: 'Headers must be JSON, e.g. {"Accept": "application/json"}' };
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return { error: "Headers must be a JSON object." };
  }
  const entries = Object.entries(value as Record<string, unknown>);
  if (entries.some(([, v]) => typeof v !== "string")) return { error: "Every header value must be a string." };
  return { headers: Object.fromEntries(entries) as Record<string, string> };
}

export const BODYLESS = new Set(["GET", "HEAD", "DELETE", "OPTIONS"]);
