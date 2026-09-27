import { baseApi } from "@/lib/api/baseApi";
import type { Schemas } from "@/lib/api/types";

export type ProxyRequest = Schemas["ProxyRequest"];
export type ProxyResponse = Schemas["ProxyResponse"];
export type CurlParsed = Schemas["CurlParsed"];
export type ExplainErrorRequest = Schemas["ExplainErrorRequest"];
export type HttpErrorExplanation = Schemas["HttpErrorExplanation"];

export const apiTesterApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // Mutations, not queries: each Send is a deliberate action, never cached or refetched.
    sendRequest: build.mutation<ProxyResponse, ProxyRequest>({
      query: (body) => ({ url: "/api-tester/send", method: "POST", body }),
    }),
    parseCurl: build.mutation<CurlParsed, string>({
      query: (command) => ({ url: "/api-tester/parse-curl", method: "POST", body: { command } }),
    }),
    explainError: build.mutation<HttpErrorExplanation, ExplainErrorRequest>({
      query: (body) => ({ url: "/api-tester/explain-error", method: "POST", body }),
      invalidatesTags: ["AiUsage"],
    }),
  }),
});

export const { useSendRequestMutation, useParseCurlMutation, useExplainErrorMutation } = apiTesterApi;
