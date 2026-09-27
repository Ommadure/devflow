import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/app/App";
import { AppProviders } from "@/app/AppProviders";
import { makeStore } from "@/app/store";
import "@/styles/index.css";

const root = document.getElementById("root");
if (!root) throw new Error("index.html is missing the #root element");

createRoot(root).render(
  <StrictMode>
    <AppProviders store={makeStore()}>
      <App />
    </AppProviders>
  </StrictMode>,
);
