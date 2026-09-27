import { baseApi } from "@/lib/api/baseApi";
import type { DashboardSummary, PomodoroSession } from "@/lib/api/types";

export const pomodoroApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    recordSession: build.mutation<PomodoroSession, { duration_seconds: number }>({
      query: (body) => ({ url: "/pomodoro/sessions", method: "POST", body }),
      invalidatesTags: ["PomodoroSession", "Dashboard"],
    }),
    getSummary: build.query<DashboardSummary, string>({
      query: (tz) => ({ url: "/dashboard/summary", params: { tz } }),
      providesTags: ["Dashboard"],
    }),
  }),
});

export const { useRecordSessionMutation, useGetSummaryQuery } = pomodoroApi;

/** The browser's IANA timezone ("Asia/Kolkata"), so "today" means the user's today. */
export const browserTimeZone = (): string => Intl.DateTimeFormat().resolvedOptions().timeZone;
