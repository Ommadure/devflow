import type { SerializedError } from "@reduxjs/toolkit";
import type { FetchBaseQueryError } from "@reduxjs/toolkit/query";

/** One typed shape for every failure the UI shows, whatever went wrong underneath. */
export interface ApiError {
  status: number; // HTTP status; 0 when no response arrived
  code: string; // stable machine code, e.g. INVALID_CREDENTIALS, NETWORK_ERROR
  message: string; // safe to show to the user
  details: Record<string, unknown>;
  requestId: string | null; // quote this in bug reports; it's in the server logs
}

interface BackendErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id?: string | null;
  };
}

function isBackendErrorBody(data: unknown): data is BackendErrorBody {
  if (typeof data !== "object" || data === null || !("error" in data)) return false;
  const error = (data as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

function isFetchBaseQueryError(error: unknown): error is FetchBaseQueryError {
  return typeof error === "object" && error !== null && "status" in error;
}

export function toApiError(error: FetchBaseQueryError | SerializedError | undefined): ApiError {
  const base = { details: {}, requestId: null };
  if (!error) return { ...base, status: 0, code: "UNKNOWN", message: "Something went wrong." };

  if (!isFetchBaseQueryError(error)) {
    // A thrown JS error (SerializedError), not an HTTP failure.
    return { ...base, status: 0, code: "UNKNOWN", message: error.message ?? "Something went wrong." };
  }

  switch (error.status) {
    case "FETCH_ERROR": // no response: offline, DNS, server down, dropped connection
      return {
        ...base,
        status: 0,
        code: "NETWORK_ERROR",
        message: "Can't reach the server. Check your connection and try again.",
      };
    case "TIMEOUT_ERROR":
      return { ...base, status: 0, code: "TIMEOUT", message: "The server took too long to respond." };
    case "PARSING_ERROR": // e.g. a proxy's HTML error page instead of our JSON
      return {
        ...base,
        status: error.originalStatus,
        code: `HTTP_${error.originalStatus}`,
        message: "The server sent an unexpected response.",
      };
    case "CUSTOM_ERROR":
      return { ...base, status: 0, code: "CUSTOM_ERROR", message: error.error };
  }

  if (isBackendErrorBody(error.data)) {
    const { code, message, details, request_id } = error.data.error;
    return {
      status: error.status,
      code,
      message,
      details: details ?? {},
      requestId: request_id ?? null,
    };
  }
  return {
    ...base,
    status: error.status,
    code: `HTTP_${error.status}`,
    message: "The server sent an unexpected response.",
  };
}
