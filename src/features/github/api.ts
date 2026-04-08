export interface GithubUser {
  login: string;
  avatar_url: string;
  html_url: string;
  name: string;
  company: string;
  blog: string;
  location: string;
  bio: string;
  public_repos: number;
  followers: number;
  following: number;
  created_at: string;
}

export interface GithubRepo {
  id: number;
  name: string;
  html_url: string;
  description: string;
  stargazers_count: number;
  watchers_count: number;
  language: string;
  forks_count: number;
  updated_at: string;
}

const GITHUB_API = 'https://api.github.com';

export async function fetchGithubUser(username: string): Promise<GithubUser> {
  const response = await fetch(`${GITHUB_API}/users/${username}`);
  if (!response.ok) {
    if (response.status === 404) throw new Error('User not found');
    if (response.status === 403) throw new Error('API rate limit exceeded');
    throw new Error('Failed to fetch user');
  }
  return response.json();
}

export async function fetchGithubRepos(username: string): Promise<GithubRepo[]> {
  const response = await fetch(`${GITHUB_API}/users/${username}/repos?sort=updated&per_page=6`);
  if (!response.ok) {
    throw new Error('Failed to fetch repositories');
  }
  return response.json();
}
