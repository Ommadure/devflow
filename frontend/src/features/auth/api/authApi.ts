import { baseApi } from "@/lib/api/baseApi";
import { sessionStarted, signedOut } from "@/lib/api/authSession";
import type { Schemas, SessionOut, User } from "@/lib/api/types";

type Credentials = Schemas["LoginRequest"];
type Registration = Schemas["RegisterRequest"];
type ChangePassword = Schemas["ChangePasswordRequest"];

export const authApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    login: build.mutation<SessionOut, Credentials>({
      query: (body) => ({ url: "/auth/login", method: "POST", body }),
      async onQueryStarted(_, { dispatch, queryFulfilled }) {
        const { data } = await queryFulfilled.catch(() => ({ data: null }));
        if (data) dispatch(sessionStarted(data));
      },
    }),
    register: build.mutation<SessionOut, Registration>({
      query: (body) => ({ url: "/auth/register", method: "POST", body }),
      async onQueryStarted(_, { dispatch, queryFulfilled }) {
        const { data } = await queryFulfilled.catch(() => ({ data: null }));
        if (data) dispatch(sessionStarted(data));
      },
    }),
    logout: build.mutation<null, void>({
      query: () => ({ url: "/auth/logout", method: "POST" }),
      async onQueryStarted(_, { dispatch, queryFulfilled }) {
        // Sign out locally even if the server call fails: the user asked to leave.
        await queryFulfilled.catch(() => undefined);
        dispatch(signedOut());
        dispatch(baseApi.util.resetApiState());
      },
    }),
    getMe: build.query<User, void>({
      query: () => "/me",
      providesTags: ["Me"],
    }),
    changePassword: build.mutation<SessionOut, ChangePassword>({
      query: (body) => ({ url: "/me/password", method: "POST", body }),
      async onQueryStarted(_, { dispatch, queryFulfilled }) {
        const { data } = await queryFulfilled.catch(() => ({ data: null }));
        // Every old session was revoked; this response is the caller's fresh one.
        if (data) dispatch(sessionStarted(data));
      },
      invalidatesTags: ["Me"],
    }),
  }),
});

export const {
  useLoginMutation,
  useRegisterMutation,
  useLogoutMutation,
  useGetMeQuery,
  useChangePasswordMutation,
} = authApi;
