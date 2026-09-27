import { skipToken } from "@reduxjs/toolkit/query";
import { Building2, GitFork, Link2, MapPin, Search, Star } from "lucide-react";
import { useId, useState } from "react";
import { useAppSelector } from "@/app/hooks";
import { Alert } from "@/components/ui/Alert";
import { PageLoader } from "@/components/ui/Loaders";
import { InsightsCard, useGetOverviewQuery } from "@/features/github";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { selectUser } from "@/lib/api/authSession";
import { toApiError } from "@/lib/api/errors";
import { formatRelative } from "@/lib/utils/dates";

export function GithubPage() {
  const user = useAppSelector(selectUser);
  const [username, setUsername] = useState(user?.github_username ?? "octocat");
  const debounced = useDebouncedValue(username.trim(), 500);
  const { data, error, isFetching } = useGetOverviewQuery(debounced || skipToken);
  const inputId = useId();
  const apiError = error ? toApiError(error) : null;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-semibold">GitHub Analytics</h1>
        <div className="relative w-72">
          <label htmlFor={inputId} className="sr-only">GitHub username</label>
          <Search aria-hidden className="pointer-events-none absolute top-2.5 left-3 size-4 text-text/40" />
          <input id={inputId} className="input-field pl-9" value={username} placeholder="GitHub username"
            onChange={(e) => setUsername(e.target.value)} />
        </div>
      </header>

      {isFetching && !data ? (
        <PageLoader label="Loading profile…" />
      ) : apiError ? (
        <Alert tone="error">
          {apiError.code === "GITHUB_USER_NOT_FOUND" ? `No GitHub user called "${debounced}".` : apiError.message}
        </Alert>
      ) : data ? (
        <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
          <section aria-label="Profile" className="card space-y-3">
            <img src={data.profile.avatar_url} alt="" className="size-20 rounded-full" />
            <div>
              <h2 className="text-lg font-semibold">{data.profile.name ?? data.profile.login}</h2>
              <a href={data.profile.html_url} target="_blank" rel="noreferrer" className="text-sm text-accent">
                @{data.profile.login}
              </a>
            </div>
            {data.profile.bio && <p className="text-sm text-text/80">{data.profile.bio}</p>}
            <ul className="space-y-1 text-sm text-text/70">
              {data.profile.company && <li className="flex items-center gap-2"><Building2 aria-hidden className="size-4" />{data.profile.company}</li>}
              {data.profile.location && <li className="flex items-center gap-2"><MapPin aria-hidden className="size-4" />{data.profile.location}</li>}
              {data.profile.blog && <li className="flex items-center gap-2"><Link2 aria-hidden className="size-4" />{data.profile.blog}</li>}
            </ul>
            <dl className="grid grid-cols-3 gap-2 text-center text-sm">
              {([["Followers", data.profile.followers], ["Following", data.profile.following], ["Repos", data.profile.public_repos]] as const).map(([label, value]) => (
                <div key={label} className="rounded-lg bg-background p-2">
                  <dd className="font-semibold">{value}</dd>
                  <dt className="text-xs text-text/50">{label}</dt>
                </div>
              ))}
            </dl>
          </section>
          <section aria-labelledby="repos-title" className="space-y-3">
            <h2 id="repos-title" className="font-semibold">Recently updated repositories</h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {data.repos.map((repo) => (
                <li key={repo.name} className="card space-y-2 p-4">
                  <a href={repo.html_url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">
                    {repo.name}
                  </a>
                  {repo.description && <p className="line-clamp-2 text-sm text-text/70">{repo.description}</p>}
                  <p className="flex flex-wrap items-center gap-3 text-xs text-text/60">
                    {repo.language && <span>{repo.language}</span>}
                    <span className="flex items-center gap-1"><Star aria-hidden className="size-3.5" />{repo.stargazers_count}</span>
                    <span className="flex items-center gap-1"><GitFork aria-hidden className="size-3.5" />{repo.forks_count}</span>
                    <span>updated {formatRelative(repo.updated_at)}</span>
                  </p>
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}

      <InsightsCard githubUsername={user?.github_username ?? null} />
    </div>
  );
}
