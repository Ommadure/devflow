import { describe, expect, it } from "vitest";
import { toApiError } from "./errors";

describe("toApiError", () => {
  it("maps the backend error body", () => {
    const error = toApiError({
      status: 401,
      data: {
        error: {
          code: "INVALID_CREDENTIALS",
          message: "Incorrect email or password.",
          details: {},
          request_id: "abc123",
        },
      },
    });
    expect(error).toEqual({
      status: 401,
      code: "INVALID_CREDENTIALS",
      message: "Incorrect email or password.",
      details: {},
      requestId: "abc123",
    });
  });

  it("keeps validation details", () => {
    const error = toApiError({
      status: 422,
      data: {
        error: {
          code: "VALIDATION_FAILED",
          message: "The request is invalid.",
          details: { fields: [{ loc: "body.email", message: "bad" }] },
          request_id: "r",
        },
      },
    });
    expect(error.details).toEqual({ fields: [{ loc: "body.email", message: "bad" }] });
  });

  it("turns a dropped connection into NETWORK_ERROR", () => {
    const error = toApiError({ status: "FETCH_ERROR", error: "TypeError: Failed to fetch" });
    expect(error.code).toBe("NETWORK_ERROR");
    expect(error.status).toBe(0);
  });

  it("handles a proxy's HTML error page", () => {
    const error = toApiError({
      status: "PARSING_ERROR",
      originalStatus: 502,
      data: "<html>Bad Gateway</html>",
      error: "SyntaxError",
    });
    expect(error).toMatchObject({ status: 502, code: "HTTP_502", requestId: null });
  });

  it("handles a JSON body that isn't our error shape", () => {
    expect(toApiError({ status: 500, data: { detail: "x" } })).toMatchObject({
      status: 500,
      code: "HTTP_500",
    });
  });

  it("handles timeouts, custom errors, thrown errors and nothing at all", () => {
    expect(toApiError({ status: "TIMEOUT_ERROR", error: "t" }).code).toBe("TIMEOUT");
    expect(toApiError({ status: "CUSTOM_ERROR", error: "nope" }).message).toBe("nope");
    expect(toApiError({ name: "Error", message: "boom" })).toMatchObject({ code: "UNKNOWN", message: "boom" });
    expect(toApiError(undefined).code).toBe("UNKNOWN");
  });
});
