import { baseApi } from "@/lib/api/baseApi";
import type { Schemas } from "@/lib/api/types";

export type TagSuggestion = Schemas["SnippetTagSuggestion"];
export type AiUsage = Schemas["AiUsageOut"];
/** A numbered passage an answer may cite. It arrives inside the SSE stream (`sources`
 *  event), so it isn't in the OpenAPI schema: mirrors backend `schemas/ai.py:Source`. */
export interface Source {
  n: number;
  note_id: string;
  note_title: string;
  heading: string | null;
  excerpt: string;
}

export const aiApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getAiUsage: build.query<AiUsage, void>({
      query: () => "/me/ai-usage",
      providesTags: ["AiUsage"],
    }),
    suggestTags: build.mutation<TagSuggestion, string>({
      query: (snippetId) => ({ url: `/snippets/${snippetId}/ai/tags`, method: "POST" }),
      invalidatesTags: ["AiUsage"],
    }),
  }),
});

export const { useGetAiUsageQuery, useSuggestTagsMutation } = aiApi;
