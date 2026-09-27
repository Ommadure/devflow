import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { apiError, json, mockFetch } from "@/test/fetchMock";
import { renderWithProviders, signedInState } from "@/test/utils";
import { ApiTesterPage } from "./ApiTesterPage";

const OK = {
  status: 404, status_text: "Not Found", headers: [["content-type", "application/json"], ["x-request-id", "abc"]],
  body: '{"error":"no such item"}', body_truncated: false, elapsed_ms: 123, size_bytes: 24,
  final_url: "https://api.example.com/items/9", redirects: [],
};

function renderPage() {
  return renderWithProviders(<ApiTesterPage />, { store: makeStore(signedInState()) });
}

describe("ApiTesterPage", () => {
  it("sends through the server and shows status, timing, pretty body and headers", async () => {
    const api = mockFetch({ "POST /api/v1/api-tester/send": () => json(OK) });
    renderPage();
    const user = userEvent.setup();

    await user.clear(screen.getByLabelText("URL"));
    await user.type(screen.getByLabelText("URL"), "https://api.example.com/items/9");
    await user.click(screen.getByRole("button", { name: "Send" }));

    const response = await screen.findByRole("region", { name: "Response" });
    expect(within(response).getByText("404 Not Found")).toBeInTheDocument();
    expect(within(response).getByText("123 ms")).toBeInTheDocument();
    expect(within(response).getByLabelText("Response body").textContent).toBe('{\n  "error": "no such item"\n}');
    await user.click(within(response).getByRole("tab", { name: /headers/ }));
    expect(within(response).getByText("x-request-id")).toBeInTheDocument();

    expect(await api.calls[0]!.json()).toEqual({
      method: "GET", url: "https://api.example.com/items/9", headers: { Accept: "application/json" }, body: null,
    });
  });

  it("explains a refused private address", async () => {
    mockFetch({
      "POST /api/v1/api-tester/send": () =>
        apiError(422, "BLOCKED_DESTINATION", "That address is on a private or reserved network."),
    });
    renderPage();
    const user = userEvent.setup();
    await user.clear(screen.getByLabelText("URL"));
    await user.type(screen.getByLabelText("URL"), "http://169.254.169.254/");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("private or reserved network");
  });

  it("won't send invalid header JSON", async () => {
    renderPage();
    const user = userEvent.setup();
    const headers = screen.getByLabelText("Headers (JSON)");
    await user.clear(headers);
    await user.type(headers, "not json");
    expect(screen.getByText(/Headers must be JSON/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("imports a cURL command into the form", async () => {
    mockFetch({
      "POST /api/v1/api-tester/parse-curl": () =>
        json({ method: "POST", url: "https://api.example.com/items", headers: { "Content-Type": "application/json" },
               body: '{"a":1}', warnings: ["Ignored an option DevFlow doesn't support: --cert"] }),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Import cURL" }));
    await user.type(screen.getByLabelText("cURL command"), "curl https://api.example.com/items");
    await user.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(screen.getByLabelText("URL")).toHaveValue("https://api.example.com/items"));
    expect(screen.getByLabelText("Method")).toHaveValue("POST");
    expect(screen.getByLabelText(/^Body/)).toHaveValue('{"a":1}');
    expect(screen.getByText(/--cert/)).toBeInTheDocument();
  });

  it("asks the AI to explain an error response", async () => {
    const api = mockFetch({
      "POST /api/v1/api-tester/send": () => json(OK),
      "POST /api/v1/api-tester/explain-error": () =>
        json({ likely_causes: ["Item 9 doesn't exist."], suggested_fixes: ["List items first."], confidence: "high" }),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Send" }));
    await user.click(await screen.findByRole("button", { name: "Explain this error" }));

    expect(await screen.findByText("Item 9 doesn't exist.")).toBeInTheDocument();
    expect(screen.getByText(/confidence: high/)).toBeInTheDocument();
    const sent = await api.calls.find((c) => c.url.endsWith("/explain-error"))!.json();
    expect(sent).toMatchObject({ status: 404, url: "https://api.example.com/items/9" });
  });
});
