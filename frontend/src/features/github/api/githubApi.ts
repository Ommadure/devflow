import { baseApi } from "@/lib/api/baseApi";
import type { Schemas } from "@/lib/api/types";

export type GithubOverview = Schemas["GithubOverview"];
export type Insight = Schemas["InsightOut"];

export const githubApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getOverview: build.query<GithubOverview, string>({
      query: (username) => ({ url: "/github/overview", params: { username } }),
      keepUnusedDataFor: 900, // matches the server's 15-minute cache
    }),
    listInsights: build.query<Insight[], void>({
      query: () => ({ url: "/github/insights", params: { limit: 4 } }),
      providesTags: ["GithubInsight"],
    }),
    generateInsight: build.mutation<Insight, void>({
      query: () => ({ url: "/github/insights/generate", method: "POST" }),
      invalidatesTags: ["GithubInsight", "AiUsage"],
    }),
  }),
});

export const { useGetOverviewQuery, useListInsightsQuery, useGenerateInsightMutation } = githubApi;
