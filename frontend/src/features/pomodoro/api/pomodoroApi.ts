import { baseApi } from "@/lib/api/baseApi";
import type { DashboardSummary, PomodoroSession, Schemas } from "@/lib/api/types";

export type PomodoroStats = Schemas["PomodoroStats"];

export const pomodoroApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    recordSession: build.mutation<PomodoroSession, { duration_seconds: number }>({
      query: (body) => ({ url: "/pomodoro/sessions", method: "POST", body }),
      invalidatesTags: ["PomodoroSession", "Dashboard"],
    }),
    getStats: build.query<PomodoroStats, { range: "7d" | "30d"; tz: string }>({
      query: ({ range, tz }) => ({ url: "/pomodoro/stats", params: { range, tz } }),
      providesTags: ["PomodoroSession"],
    }),
    getSummary: build.query<DashboardSummary, string>({
      query: (tz) => ({ url: "/dashboard/summary", params: { tz } }),
      providesTags: ["Dashboard"],
    }),
  }),
});

export const { useRecordSessionMutation, useGetSummaryQuery, useGetStatsQuery } = pomodoroApi;

/** The browser's IANA timezone ("Asia/Kolkata"), so "today" means the user's today. */
export const browserTimeZone = (): string => Intl.DateTimeFormat().resolvedOptions().timeZone;
