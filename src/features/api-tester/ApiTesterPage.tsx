import { useMemo, useState } from "react";
import { Play, Loader2, AlertCircle } from "lucide-react";
import { executeRequest, ApiResponse } from "./apiUtils";

const formatResponseBody = (data: ApiResponse["data"]) => {
  if (typeof data === "string") return data;
  if (data == null) return "";
  if (typeof data === "bigint") return data.toString();

  try {
    const seen = new WeakSet<object>();

    return JSON.stringify(
      data,
      (_key, value) => {
        if (typeof value === "bigint") {
          return value.toString();
        }

        if (value && typeof value === "object") {
          if (seen.has(value)) {
            return "[Circular]";
          }

          seen.add(value);
        }

        return value;
      },
      2,
    );
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown serialization error";
    return `Unable to display response body: ${message}`;
  }
};

export function ApiTesterPage() {
  const [url, setUrl] = useState(
    "https://jsonplaceholder.typicode.com/posts/1",
  );
  const [method, setMethod] = useState("GET");
  const [headers, setHeaders] = useState(
    '{\n  "Content-Type": "application/json"\n}',
  );
  const [body, setBody] = useState("");

  const [activeTab, setActiveTab] = useState<"headers" | "body">("headers");

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<ApiResponse | null>(null);

  const responseBodyText = useMemo(() => {
    if (!response || response.error) return "";
    return formatResponseBody(response.data);
  }, [response]);

  const handleSend = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setResponse(null);
    const result = await executeRequest(method, url, headers, body);
    setResponse(result);
    setLoading(false);
  };

  const getStatusColor = (status: number) => {
    if (status === 0) return "text-red-500";
    if (status >= 200 && status < 300) return "text-green-500";
    if (status >= 300 && status < 400) return "text-blue-500";
    if (status >= 400 && status < 500) return "text-yellow-500";
    return "text-red-500";
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">API Tester</h1>
        <p className="text-gray-400 mt-1">Test and debug REST APIs safely.</p>
      </div>

      {/* URL & Method */}
      <div className="flex flex-col md:flex-row gap-4">
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          className="input-field md:w-32 bg-surface font-bold"
          aria-label="HTTP method selection"
        >
          {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Enter API URL (e.g., https://api.example.com/v1/users)"
          className="input-field flex-1 font-mono text-sm"
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          aria-label="API endpoint URL"
          aria-describedby="url-help"
        />
        <div id="url-help" className="sr-only">Enter the full URL of the API endpoint you want to test</div>
        <button
          onClick={handleSend}
          disabled={loading || !url}
          className="btn-primary flex items-center justify-center gap-2 md:w-32"
          aria-label={loading ? "Sending request..." : "Send API request"}
          aria-disabled={loading || !url}
        >
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
          ) : (
            <Play className="w-5 h-5" aria-hidden="true" />
          )}
          Send
        </button>
      </div>

      {/* Request Options */}
      <div className="card overflow-hidden">
        <div className="flex border-b border-border bg-background" role="tablist" aria-label="Request options">
          <button
            onClick={() => setActiveTab("headers")}
            className={`px-6 py-3 text-sm font-medium transition-colors ${activeTab === "headers" ? "text-accent border-b-2 border-accent" : "text-gray-400 hover:text-white"}`}
            role="tab"
            aria-selected={activeTab === "headers"}
            aria-controls="headers-panel"
            id="headers-tab"
          >
            Headers
          </button>
          <button
            onClick={() => setActiveTab("body")}
            className={`px-6 py-3 text-sm font-medium transition-colors ${activeTab === "body" ? "text-accent border-b-2 border-accent" : "text-gray-400 hover:text-white"}`}
            role="tab"
            aria-selected={activeTab === "body"}
            aria-controls="body-panel"
            id="body-tab"
          >
            Body
          </button>
        </div>
        <div className="p-0">
          {activeTab === "headers" ? (
            <textarea
              value={headers}
              onChange={(e) => setHeaders(e.target.value)}
              placeholder="{\n  // Enter JSON headers here\n}"
              className="w-full h-32 md:h-48 bg-surface text-gray-300 font-mono text-sm p-4 focus:outline-none resize-none"
              aria-labelledby="headers-tab"
              aria-describedby="headers-help"
              id="headers-panel"
              role="tabpanel"
            />
          ) : (
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="{\n  // Enter JSON body here\n}"
              disabled={method === "GET" || method === "DELETE"}
              className="w-full h-32 md:h-48 bg-surface text-gray-300 font-mono text-sm p-4 focus:outline-none resize-none disabled:opacity-50"
              aria-labelledby="body-tab"
              aria-describedby="body-help"
              id="body-panel"
              role="tabpanel"
            />
          )}
        </div>
        <div id="headers-help" className="sr-only">Enter request headers in JSON format</div>
        <div id="body-help" className="sr-only">Enter request body in JSON format</div>
      </div>

      {/* Response Area */}
      {response && (
        <div className="card overflow-hidden flex flex-col h-96 md:h-[500px]" role="region" aria-labelledby="response-heading">
          <div className="p-4 border-b border-border bg-surface flex items-center justify-between">
            <h3 id="response-heading" className="font-bold text-white">Response</h3>
            <div className="flex gap-6 text-sm font-mono" aria-live="polite" aria-atomic="true">
              <div className="flex gap-2">
                <span className="text-gray-400">Status:</span>
                <span
                  className={`font-bold ${getStatusColor(response.status)}`}
                  aria-label={`HTTP status ${response.status === 0 ? "Error" : response.status} ${response.statusText}`}
                >
                  {response.status === 0 ? "ERR" : response.status}{" "}
                  {response.statusText}
                </span>
              </div>
              <div className="flex gap-2">
                <span className="text-gray-400">Time:</span>
                <span className="text-green-400 font-bold" aria-label={`Response time ${response.time} milliseconds`}>
                  {response.time} ms
                </span>
              </div>
            </div>
          </div>

          <div className="flex-1 flex overflow-hidden">
            {response.error ? (
              <div className="flex-1 p-6 flex flex-col items-center justify-center text-red-400 gap-4" role="alert">
                <AlertCircle className="w-12 h-12 opacity-50" aria-hidden="true" />
                <p className="text-center max-w-md">{response.error}</p>
              </div>
            ) : (
              <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
                <div className="flex-1 overflow-auto bg-background p-4 border-r border-border/50">
                  <h4 className="text-xs font-bold text-gray-500 uppercase mb-2">
                    Body
                  </h4>
                  <pre
                    className="font-mono text-sm text-gray-300 whitespace-pre-wrap overflow-x-auto"
                    aria-label="Response body content"
                    role="log"
                    aria-live="polite"
                  >
                    {responseBodyText}
                  </pre>
                </div>
                <div className="w-full md:w-64 overflow-auto bg-surface p-4">
                  <h4 className="text-xs font-bold text-gray-500 uppercase mb-2">
                    Headers
                  </h4>
                  <div className="space-y-2" role="list" aria-label="Response headers">
                    {Object.entries(response.headers).map(([key, value]) => (
                      <div key={key} className="text-xs" role="listitem">
                        <span className="font-bold text-gray-400">{key}:</span>
                        <span
                          className="text-gray-300 block truncate"
                          title={value}
                          aria-label={`${key} header value: ${value}`}
                        >
                          {value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
