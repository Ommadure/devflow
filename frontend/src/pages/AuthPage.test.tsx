import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { apiError, json, mockFetch } from "@/test/fetchMock";
import { renderWithProviders, session } from "@/test/utils";
import { AuthPage } from "./AuthPage";

function anonymousStore() {
  return makeStore({ auth: { status: "anonymous", accessToken: null, user: null, notice: null } });
}

describe("AuthPage", () => {
  it("signs in and stores the session", async () => {
    const api = mockFetch({ "POST /api/v1/auth/login": () => json(session("access-9")) });
    const { store } = renderWithProviders(<AuthPage />, { store: anonymousStore() });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email"), "om@example.com");
    await user.type(screen.getByLabelText("Password"), "Correct-Horse-9");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await expect.poll(() => store.getState().auth.accessToken).toBe("access-9");
    expect(await api.calls[0]!.json()).toEqual({ email: "om@example.com", password: "Correct-Horse-9" });
  });

  it("shows the server's message when sign-in fails", async () => {
    mockFetch({
      "POST /api/v1/auth/login": () => apiError(401, "INVALID_CREDENTIALS", "Incorrect email or password."),
    });
    renderWithProviders(<AuthPage />, { store: anonymousStore() });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Email"), "om@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  });

  it("only enables sign-up once the password meets every rule", async () => {
    renderWithProviders(<AuthPage />, { store: anonymousStore() });
    const user = userEvent.setup();

    await user.click(screen.getByRole("tab", { name: "Create account" }));
    await user.type(screen.getByLabelText("Email"), "om@example.com");
    const password = screen.getByLabelText("Password");
    const submit = screen.getByRole("button", { name: "Create account" });

    await user.type(password, "weakpass");
    expect(submit).toBeDisabled();
    expect(screen.getByText("A number")).toHaveTextContent("(not met)");

    await user.clear(password);
    await user.type(password, "Correct-Horse-9");
    expect(submit).toBeEnabled();
    expect(screen.getByText("A number")).toHaveTextContent("(met)");
  });

  it("switches tabs with the arrow keys", async () => {
    renderWithProviders(<AuthPage />, { store: anonymousStore() });
    const user = userEvent.setup();

    await user.click(screen.getByRole("tab", { name: "Sign in" }));
    await user.keyboard("{ArrowRight}");

    const register = screen.getByRole("tab", { name: "Create account" });
    expect(register).toHaveAttribute("aria-selected", "true");
    expect(register).toHaveFocus();
  });

  it("toggles password visibility", async () => {
    renderWithProviders(<AuthPage />, { store: anonymousStore() });
    const user = userEvent.setup();
    const password = screen.getByLabelText("Password");

    expect(password).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
  });

  it("shows why the user was signed out", () => {
    const store = makeStore({
      auth: { status: "anonymous", accessToken: null, user: null, notice: "Your session has ended." },
    });
    renderWithProviders(<AuthPage />, { store });
    expect(screen.getByRole("status")).toHaveTextContent("Your session has ended.");
  });
});
