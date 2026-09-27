import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { resetRefreshStateForTests } from "@/lib/api/refresh";

// jsdom has <dialog> but not showModal()/close(). Toggle the `open` attribute, which is
// what tests observe; focus trapping and Escape are the real browser's job.
if (typeof HTMLDialogElement.prototype.showModal !== "function") {
  if (!("open" in HTMLDialogElement.prototype)) {
    Object.defineProperty(HTMLDialogElement.prototype, "open", {
      get(this: HTMLDialogElement) {
        return this.hasAttribute("open");
      },
    });
  }
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  resetRefreshStateForTests();
});
