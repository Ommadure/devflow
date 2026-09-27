import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { json, mockFetch } from "@/test/fetchMock";
import { renderWithProviders, signedInState } from "@/test/utils";
import { AppLayout } from "./AppLayout";

function renderLayout(route = "/") {
  return renderWithProviders(
    <AppLayout>
      <p>page content</p>
    </AppLayout>,
    { store: makeStore(signedInState()), route },
  );
}

describe("AppLayout", () => {
  it("marks the current page in the navigation", () => {
    renderLayout("/settings");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
  });

  it("offers a skip link to the main content", () => {
    renderLayout();
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main");
  });

  it("opens the mobile drawer and closes it with Escape", async () => {
    renderLayout();
    const user = userEvent.setup();
    const toggle = screen.getByRole("button", { name: "Open navigation" });

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("closes the drawer after navigating", async () => {
    renderLayout();
    const user = userEvent.setup();
    const toggle = screen.getByRole("button", { name: "Open navigation" });

    await user.click(toggle);
    await user.click(screen.getByRole("link", { name: "Notes" }));
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("signs out", async () => {
    const api = mockFetch({ "POST /api/v1/auth/logout": () => new Response(null, { status: 204 }) });
    const { store } = renderLayout();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    await expect.poll(() => store.getState().auth.status).toBe("anonymous");
    expect(api.count("POST /api/v1/auth/logout")).toBe(1);
  });

  it("signs out locally even if the server call fails", async () => {
    mockFetch({ "POST /api/v1/auth/logout": () => json({}, 500) });
    const { store } = renderLayout();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    await expect.poll(() => store.getState().auth.status).toBe("anonymous");
  });
});
