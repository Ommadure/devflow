// @vitest-environment node
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = import.meta.dirname;
const vercel = JSON.parse(
  readFileSync(resolve(root, "vercel.json"), "utf8"),
) as {
  rewrites: { source: string; destination: string }[];
  headers: { source: string; headers: { key: string; value: string }[] }[];
};
const csp = vercel.headers[0]!.headers.find(
  (h) => h.key === "Content-Security-Policy",
)!.value;
const directive = (name: string) =>
  csp
    .split(";")
    .map((part) => part.trim().split(/\s+/))
    .find(([key]) => key === name)!
    .slice(1);

describe("vercel.json", () => {
  it("proxies exactly /api/v1 to the backend over https, then falls back to the SPA", () => {
    const [api, spa] = vercel.rewrites;
    expect(api!.source).toBe("/api/v1/:path*"); // not /api: the page /api-tester must stay a page
    expect(api!.destination).toMatch(/^https:\/\/[^/]+\/api\/v1\/:path\*$/);
    expect(spa).toEqual({ source: "/(.*)", destination: "/index.html" });
  });

  it("allows no inline or eval'd script, and the app talks only to its own origin", () => {
    expect(directive("script-src")).toEqual(["'self'"]);
    expect(csp).not.toContain("'unsafe-inline'");
    expect(csp).not.toContain("'unsafe-eval'");
    expect(directive("connect-src")).toEqual(["'self'"]); // the API is same-origin via the rewrite
    expect(directive("frame-ancestors")).toEqual(["'none'"]);
  });

  it("allows every external origin index.html loads (edit it, and this says what to add)", () => {
    const html = readFileSync(resolve(root, "index.html"), "utf8");
    expect(html).not.toMatch(/<script>/); // an inline script would need a CSP hash
    const stylesheets = [
      ...html.matchAll(/<link[^>]+href="(https:[^"]+)"[^>]*rel="stylesheet"/g),
    ];
    for (const [, href] of stylesheets) {
      expect(directive("style-src")).toContain(new URL(href!).origin);
    }
  });
});
