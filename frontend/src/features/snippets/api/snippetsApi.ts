import { baseApi } from "@/lib/api/baseApi";
import type { Page, Schemas, SearchHit, SearchMode, Snippet, TagCount } from "@/lib/api/types";

export interface SnippetFilters {
  tag?: string;
  favorite?: boolean;
}

export interface SnippetSearch extends SnippetFilters {
  q: string;
  mode: SearchMode;
}
type SnippetCreate = Schemas["SnippetCreate"];
type SnippetUpdate = Schemas["SnippetUpdate"];

const PAGE_SIZE = 20;

// Any change to a snippet can change the list, the tag chips and the dashboard count.
const CHANGED = ["Snippet", "SnippetTags", "Dashboard"] as const;

export const snippetsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // Cursor pagination: each page's `next_cursor` is the next page's param; null = done.
    listSnippets: build.infiniteQuery<Page<Snippet>, SnippetFilters, string>({
      infiniteQueryOptions: {
        initialPageParam: "",
        getNextPageParam: (lastPage) => lastPage.next_cursor,
      },
      query: ({ queryArg, pageParam }) => ({
        url: "/snippets",
        params: {
          limit: PAGE_SIZE,
          ...(pageParam && { cursor: pageParam }),
          ...(queryArg.tag && { tag: queryArg.tag }),
          ...(queryArg.favorite && { favorite: true }),
        },
      }),
      providesTags: ["Snippet"],
    }),
    // Ranked results, not a paginated list: the top 20 by fused score.
    searchSnippets: build.query<{ items: SearchHit[] }, SnippetSearch>({
      query: ({ q, mode, tag, favorite }) => ({
        url: "/snippets/search",
        params: { q, mode, limit: 20, ...(tag && { tag }), ...(favorite && { favorite: true }) },
      }),
      providesTags: ["Snippet"],
    }),
    listTags: build.query<TagCount[], void>({
      query: () => "/snippets/tags",
      providesTags: ["SnippetTags"],
    }),
    createSnippet: build.mutation<Snippet, SnippetCreate>({
      query: (body) => ({ url: "/snippets", method: "POST", body }),
      invalidatesTags: [...CHANGED],
    }),
    updateSnippet: build.mutation<Snippet, { id: string; changes: SnippetUpdate }>({
      query: ({ id, changes }) => ({ url: `/snippets/${id}`, method: "PATCH", body: changes }),
      invalidatesTags: [...CHANGED],
    }),
    deleteSnippet: build.mutation<null, string>({
      query: (id) => ({ url: `/snippets/${id}`, method: "DELETE" }),
      invalidatesTags: [...CHANGED],
    }),
  }),
});

export const {
  useListSnippetsInfiniteQuery,
  useSearchSnippetsQuery,
  useListTagsQuery,
  useCreateSnippetMutation,
  useUpdateSnippetMutation,
  useDeleteSnippetMutation,
} = snippetsApi;
