import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, MapPin, Link as LinkIcon, Building, Users, Star, GitFork, BookOpen } from 'lucide-react';
import { motion } from 'framer-motion';
import { fetchGithubUser, fetchGithubRepos } from './api';
import { useDebounce } from '../../hooks/useDebounce';

export function GithubAnalytics() {
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearch = useDebounce(searchTerm, 500);

  const {
    data: user,
    isLoading: isLoadingUser,
    error: userError,
  } = useQuery({
    queryKey: ['githubUser', debouncedSearch],
    queryFn: () => fetchGithubUser(debouncedSearch),
    enabled: debouncedSearch.length > 0,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const {
    data: repos,
    isLoading: isLoadingRepos,
  } = useQuery({
    queryKey: ['githubRepos', debouncedSearch],
    queryFn: () => fetchGithubRepos(debouncedSearch),
    enabled: !!user,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">GitHub Analytics</h1>
          <p className="text-gray-400 mt-1">Search developers and view their open-source metrics.</p>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative max-w-xl">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
        <input
          type="text"
          placeholder="Search GitHub username..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="input-field w-full pl-10 py-3"
        />
      </div>

      {/* Loading State */}
      {(isLoadingUser || isLoadingRepos) && (
        <div className="animate-pulse space-y-6">
          <div className="card p-6 flex gap-6">
            <div className="w-24 h-24 bg-surface border border-border rounded-full" />
            <div className="space-y-3 flex-1">
              <div className="h-6 bg-surface border border-border rounded w-1/4" />
              <div className="h-4 bg-surface border border-border rounded w-1/2" />
              <div className="h-4 bg-surface border border-border rounded w-1/3" />
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {userError && (
        <div className="card p-6 bg-red-500/10 border-red-500/20 text-red-400">
          {userError instanceof Error ? userError.message : 'An error occurred'}
        </div>
      )}

      {/* Results */}
      {user && !isLoadingUser && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          {/* Profile Card */}
          <div className="card p-6 flex flex-col md:flex-row gap-6 items-start">
            <img
              src={user.avatar_url}
              alt={user.login}
              className="w-24 h-24 rounded-full border-2 border-border"
            />
            <div className="flex-1 space-y-4">
              <div>
                <h2 className="text-2xl font-bold text-white">{user.name || user.login}</h2>
                <a
                  href={user.html_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent hover:underline"
                >
                  @{user.login}
                </a>
              </div>
              
              {user.bio && <p className="text-gray-300">{user.bio}</p>}

              <div className="flex flex-wrap gap-4 text-sm text-gray-400">
                {user.company && (
                  <div className="flex items-center gap-1">
                    <Building className="w-4 h-4" /> {user.company}
                  </div>
                )}
                {user.location && (
                  <div className="flex items-center gap-1">
                    <MapPin className="w-4 h-4" /> {user.location}
                  </div>
                )}
                {user.blog && (
                  <a
                    href={user.blog.startsWith('http') ? user.blog : `https://${user.blog}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 hover:text-accent"
                  >
                    <LinkIcon className="w-4 h-4" /> {user.blog}
                  </a>
                )}
              </div>

              <div className="flex gap-6 pt-2 border-t border-border">
                <div className="flex items-center gap-2">
                  <Users className="w-5 h-5 text-gray-400" />
                  <span className="text-white font-bold">{user.followers}</span>
                  <span className="text-gray-400">followers</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white font-bold">{user.following}</span>
                  <span className="text-gray-400">following</span>
                </div>
                <div className="flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-gray-400" />
                  <span className="text-white font-bold">{user.public_repos}</span>
                  <span className="text-gray-400">repos</span>
                </div>
              </div>
            </div>
          </div>

          {/* Repositories */}
          {repos && repos.length > 0 && (
            <div className="space-y-4">
              <h3 className="text-xl font-bold text-white">Recent Repositories</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {repos.map((repo, i) => (
                  <motion.a
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                    key={repo.id}
                    href={repo.html_url}
                    target="_blank"
                    rel="noreferrer"
                    className="card p-4 flex flex-col hover:border-accent transition-colors"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-bold text-accent break-all">{repo.name}</h4>
                    </div>
                    <p className="text-sm text-gray-400 mb-4 flex-1 line-clamp-2">
                      {repo.description || 'No description provided.'}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      {repo.language && (
                        <div className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-blue-400" />
                          {repo.language}
                        </div>
                      )}
                      <div className="flex items-center gap-1">
                        <Star className="w-4 h-4" /> {repo.stargazers_count}
                      </div>
                      <div className="flex items-center gap-1">
                        <GitFork className="w-4 h-4" /> {repo.forks_count}
                      </div>
                    </div>
                  </motion.a>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
