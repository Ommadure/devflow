import { describe, expect, it } from "vitest";
import { linkCitations } from "./citations";

describe("linkCitations", () => {
  it("links citations that match a source", () => {
    expect(linkCitations("Restart it [1][2].", 2)).toBe("Restart it [1](#source-1)[2](#source-2).");
  });

  it("leaves citations of missing sources and existing links alone", () => {
    expect(linkCitations("See [7] and [docs](https://x.dev) and [1](#source-1)", 2)).toBe(
      "See [7] and [docs](https://x.dev) and [1](#source-1)",
    );
  });
});
