import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { makeStore } from "@/app/store";
import { apiError, json, mockFetch } from "@/test/fetchMock";
import { USER, renderWithProviders } from "@/test/utils";
import { GithubPage } from "./GithubPage";

const OVERVIEW = {
  profile: { login: "octocat", name: "The Octocat", avatar_url: "https://a/x.png", html_url: "https://github.com/octocat",
             bio: "A cat.", company: null, location: "SF", blog: null, followers: 10, following: 2, public_repos: 8 },
  repos: [{ name: "hello", html_url: "https://github.com/octocat/hello", description: "Hi", language: "Python",
            stargazers_count: 3, forks_count: 1, updated_at: new Date().toISOString() }],
};
const INSIGHT = {
  week_start: "2026-09-21", github_username: "octocat", created_at: "2026-09-28T00:30:00Z",
  stats: { commits: 11, pull_requests_opened: 1, active_days: 4 },
  summary: { headline: "A busy week.", highlights: ["11 commits.", "One PR."], suggestions: ["Review a PR."] },
};

function store(githubUsername: string | null) {
  return makeStore({
    auth: { status: "authenticated", accessToken: "t", user: { ...USER, github_username: githubUsername }, notice: null },
  });
}

describe("GithubPage", () => {
  it("shows the user's own profile, repos and insights", async () => {
    mockFetch({
      "GET /api/v1/github/overview": () => json(OVERVIEW),
      "GET /api/v1/github/insights": () => json([INSIGHT]),
    });
    renderWithProviders(<GithubPage />, { store: store("octocat") });

    expect(await screen.findByRole("heading", { name: "The Octocat" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "hello" })).toHaveAttribute("href", "https://github.com/octocat/hello");
    expect(await screen.findByText("A busy week.")).toBeInTheDocument();
    expect(screen.getByText(/11 commits · 1 PRs opened/)).toBeInTheDocument();
  });

  it("says so when the user doesn't exist", async () => {
    mockFetch({ "GET /api/v1/github/overview": () => apiError(404, "GITHUB_USER_NOT_FOUND", "No such GitHub user.") });
    renderWithProviders(<GithubPage />, { store: store(null) });
    const user = userEvent.setup();
    const input = screen.getByLabelText("GitHub username");
    await user.clear(input);
    await user.type(input, "ghost-user");
    expect(await screen.findByText('No GitHub user called "ghost-user".')).toBeInTheDocument();
  });

  it("points to Settings when no GitHub username is set", async () => {
    mockFetch({ "GET /api/v1/github/overview": () => json(OVERVIEW) });
    renderWithProviders(<GithubPage />, { store: store(null) });
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(screen.queryByRole("button", { name: "Generate now" })).toBeNull();
  });
});
