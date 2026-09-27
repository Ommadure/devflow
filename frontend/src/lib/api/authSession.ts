import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { SessionOut, User } from "./types";

/**
 * Who is signed in, and the access token that proves it.
 *
 * The token lives only here, in memory — never localStorage — so an XSS bug can't read a
 * long-lived credential. A reload loses it; the silent refresh at startup gets a new one
 * from the HttpOnly refresh cookie, which JavaScript can't read at all.
 *
 * This slice sits in lib/api (not features/auth) because the base query needs the token
 * for every request, and features import the base query — not the other way round.
 */
export interface AuthSessionState {
  status: "checking" | "authenticated" | "anonymous";
  accessToken: string | null;
  user: User | null;
  /** Why the user is looking at the sign-in page, when it isn't obvious. */
  notice: string | null;
}

const initialState: AuthSessionState = {
  status: "checking",
  accessToken: null,
  user: null,
  notice: null,
};

export const authSession = createSlice({
  name: "auth",
  initialState,
  reducers: {
    sessionStarted(state, action: PayloadAction<SessionOut>) {
      state.status = "authenticated";
      state.accessToken = action.payload.access_token;
      state.user = action.payload.user;
      state.notice = null;
    },
    userUpdated(state, action: PayloadAction<User>) {
      state.user = action.payload;
    },
    signedOut(state, action: PayloadAction<{ notice?: string } | undefined>) {
      state.status = "anonymous";
      state.accessToken = null;
      state.user = null;
      state.notice = action.payload?.notice ?? null;
    },
  },
  selectors: {
    selectAuthStatus: (state) => state.status,
    selectAccessToken: (state) => state.accessToken,
    selectUser: (state) => state.user,
    selectAuthNotice: (state) => state.notice,
  },
});

export const { sessionStarted, signedOut, userUpdated } = authSession.actions;
export const { selectAuthStatus, selectAccessToken, selectUser, selectAuthNotice } =
  authSession.selectors;
