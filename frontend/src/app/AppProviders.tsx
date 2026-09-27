import type { ReactNode } from "react";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router";
import type { AppStore } from "./store";

export function AppProviders({ store, children }: { store: AppStore; children: ReactNode }) {
  return (
    <Provider store={store}>
      <BrowserRouter>{children}</BrowserRouter>
    </Provider>
  );
}
