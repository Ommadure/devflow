import { Alert } from "@/components/ui/Alert";
import type { ApiError } from "@/lib/api/errors";

/** A failed request, explained: the message, any field problems, and the request id. */
export function ApiErrorMessage({ error }: { error: ApiError }) {
  const fields = Array.isArray(error.details.fields)
    ? (error.details.fields as Array<{ loc: string; message: string }>)
    : [];
  return (
    <Alert tone="error">
      <p>{error.message}</p>
      {fields.length > 0 && (
        <ul className="mt-1 list-disc pl-4 text-xs">
          {fields.map((field) => (
            <li key={field.loc}>{field.message.replace(/^Value error, /, "")}</li>
          ))}
        </ul>
      )}
    </Alert>
  );
}
