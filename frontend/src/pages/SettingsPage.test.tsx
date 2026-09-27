import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { apiError, json, mockFetch } from "@/test/fetchMock";
import { USER, renderWithProviders, session, signedInState } from "@/test/utils";
import { SettingsPage } from "./SettingsPage";

function renderSettings() {
  return renderWithProviders(<SettingsPage />, { store: makeStore(signedInState()) });
}

describe("SettingsPage", () => {
  it("shows Connected with the user id from /me", async () => {
    mockFetch({ "GET /api/v1/me": () => json(USER) });
    renderSettings();

    const card = screen.getByRole("region", { name: "API connection" });
    expect(await within(card).findByText("Connected")).toBeInTheDocument();
    expect(within(card).getByText(USER.id)).toBeInTheDocument();
  });

  it("shows the error code, message and request id when /me fails", async () => {
    mockFetch({ "GET /api/v1/me": () => apiError(500, "INTERNAL_ERROR", "Something went wrong.") });
    renderSettings();

    const card = screen.getByRole("region", { name: "API connection" });
    expect(await within(card).findByText("INTERNAL_ERROR: Something went wrong.")).toBeInTheDocument();
    expect(within(card).getByText("Request ID: req-test")).toBeInTheDocument();
  });

  it("changes the password and keeps the fresh session", async () => {
    const api = mockFetch({
      "GET /api/v1/me": () => json(USER),
      "POST /api/v1/me/password": () => json(session("access-new")),
    });
    const { store } = renderSettings();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Current password"), "Correct-Horse-9");
    await user.type(screen.getByLabelText("New password"), "Brand-New-Pass-7");
    await user.type(screen.getByLabelText("Confirm new password"), "Brand-New-Pass-7");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByText(/signed out on every other device/)).toBeInTheDocument();
    expect(store.getState().auth.accessToken).toBe("access-new");
    const sent = api.calls.find((call) => call.url.endsWith("/me/password"))!;
    expect(await sent.json()).toEqual({
      current_password: "Correct-Horse-9",
      new_password: "Brand-New-Pass-7",
    });
  });

  it("says when the current password is wrong", async () => {
    mockFetch({
      "GET /api/v1/me": () => json(USER),
      "POST /api/v1/me/password": () =>
        apiError(422, "INVALID_CURRENT_PASSWORD", "Current password is incorrect."),
    });
    renderSettings();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Current password"), "wrong");
    await user.type(screen.getByLabelText("New password"), "Brand-New-Pass-7");
    await user.type(screen.getByLabelText("Confirm new password"), "Brand-New-Pass-7");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(await screen.findByText("Current password is incorrect.")).toBeInTheDocument();
  });

  it("won't submit when the confirmation doesn't match", async () => {
    mockFetch({ "GET /api/v1/me": () => json(USER) });
    renderSettings();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Current password"), "Correct-Horse-9");
    await user.type(screen.getByLabelText("New password"), "Brand-New-Pass-7");
    await user.type(screen.getByLabelText("Confirm new password"), "Brand-New-Pass-8");

    expect(screen.getByText("The new passwords don't match.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Change password" })).toBeDisabled();
  });
});
