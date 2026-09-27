import { combineSlices, configureStore } from "@reduxjs/toolkit";
import { authSession } from "@/lib/api/authSession";
import { baseApi } from "@/lib/api/baseApi";
import { toasts } from "@/lib/toasts";

const rootReducer = combineSlices(authSession, toasts, baseApi);

export type RootState = ReturnType<typeof rootReducer>;

/** A factory, so every test gets a fresh store (optionally pre-signed-in). */
export function makeStore(preloadedState?: Partial<RootState>) {
  return configureStore({
    reducer: rootReducer,
    preloadedState,
    middleware: (getDefault) => getDefault().concat(baseApi.middleware),
  });
}

export type AppStore = ReturnType<typeof makeStore>;
export type AppDispatch = AppStore["dispatch"];
