import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { Provider } from "react-redux";
import { MemoryRouter } from "react-router";
import { makeStore, type AppStore, type RootState } from "@/app/store";
import type { SessionOut } from "@/lib/api/types";

export const USER = {
  id: "7d3f8a2e-5b1c-4e9f-a6d0-2c8b1e4f7a90",
  email: "om@example.com",
  github_username: null,
  created_at: "2026-09-26T10:00:00Z",
};

export function session(token = "access-1"): SessionOut {
  return { access_token: token, token_type: "bearer", expires_in: 900, user: USER };
}

export function signedInState(token = "access-1"): Partial<RootState> {
  return { auth: { status: "authenticated", accessToken: token, user: USER, notice: null } };
}

export function renderWithProviders(
  ui: ReactElement,
  { store = makeStore(), route = "/" }: { store?: AppStore; route?: string } = {},
) {
  return {
    store,
    ...render(
      <Provider store={store}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </Provider>,
    ),
  };
}
