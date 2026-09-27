import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { apiError, json, mockFetch } from "@/test/fetchMock";
import { renderWithProviders, session } from "@/test/utils";
import { App } from "./App";

describe("App auth gate", () => {
  it("shows the sign-in page when there is no session", async () => {
    mockFetch({ "POST /api/v1/auth/refresh": () => apiError(401, "INVALID_REFRESH_TOKEN") });
    renderWithProviders(<App />);

    expect(screen.getByText("Loading DevFlow…")).toBeInTheDocument(); // spinner while checking
    expect(await screen.findByRole("tab", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  });

  it("restores the session from the refresh cookie on load", async () => {
    mockFetch({ "POST /api/v1/auth/refresh": () => json(session()) });
    renderWithProviders(<App />, { route: "/settings" });

    expect(await screen.findByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
  });

  it("explains when the server can't be reached", async () => {
    mockFetch({
      "POST /api/v1/auth/refresh": () => {
        throw new TypeError("Failed to fetch");
      },
    });
    renderWithProviders(<App />);

    expect(await screen.findByText(/can't reach the server/i)).toBeInTheDocument();
  });
});
