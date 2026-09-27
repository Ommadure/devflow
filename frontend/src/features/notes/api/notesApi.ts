import { baseApi } from "@/lib/api/baseApi";
import type { Note, Page, Schemas } from "@/lib/api/types";

export interface NoteFilters {
  q?: string;
}

export const notesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listNotes: build.infiniteQuery<Page<Note>, NoteFilters, string>({
      infiniteQueryOptions: {
        initialPageParam: "",
        getNextPageParam: (lastPage) => lastPage.next_cursor,
      },
      query: ({ queryArg, pageParam }) => ({
        url: "/notes",
        params: {
          limit: 50,
          ...(pageParam && { cursor: pageParam }),
          ...(queryArg.q && { q: queryArg.q }),
        },
      }),
      providesTags: ["Note"],
    }),
    getNote: build.query<Note, string>({
      query: (id) => `/notes/${id}`,
      providesTags: (_result, _error, id) => [{ type: "Note", id }],
    }),
    createNote: build.mutation<Note, Schemas["NoteCreate"]>({
      query: (body) => ({ url: "/notes", method: "POST", body }),
      async onQueryStarted(_, { dispatch, queryFulfilled }) {
        const { data } = await queryFulfilled.catch(() => ({ data: null }));
        // Seed the single-note cache so the editor opens without another request.
        if (data) dispatch(notesApi.util.upsertQueryData("getNote", data.id, data));
      },
      invalidatesTags: ["Note", "Dashboard"],
    }),
    updateNote: build.mutation<Note, { id: string; changes: Schemas["NoteUpdate"] }>({
      query: ({ id, changes }) => ({ url: `/notes/${id}`, method: "PATCH", body: changes }),
      // Autosave fires every few seconds while typing. Refetching every list after each save
      // would be wasteful, so patch the saved note into the caches that hold it instead.
      async onQueryStarted({ id }, { dispatch, getState, queryFulfilled }) {
        const { data } = await queryFulfilled.catch(() => ({ data: null }));
        if (!data) return;
        dispatch(notesApi.util.upsertQueryData("getNote", id, data));
        for (const args of notesApi.util.selectCachedArgsForQuery(getState(), "listNotes")) {
          dispatch(
            notesApi.util.updateQueryData("listNotes", args, (draft) => {
              for (const page of draft.pages) {
                const index = page.items.findIndex((note) => note.id === id);
                if (index !== -1) page.items[index] = data;
              }
            }),
          );
        }
      },
    }),
    deleteNote: build.mutation<null, string>({
      query: (id) => ({ url: `/notes/${id}`, method: "DELETE" }),
      invalidatesTags: ["Note", "Dashboard"],
    }),
  }),
});

export const {
  useListNotesInfiniteQuery,
  useGetNoteQuery,
  useCreateNoteMutation,
  useUpdateNoteMutation,
  useDeleteNoteMutation,
} = notesApi;
