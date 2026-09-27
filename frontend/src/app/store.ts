import { combineSlices, configureStore } from "@reduxjs/toolkit";
import { notesUi } from "@/features/notes/store/notesSlice";
import { timer } from "@/features/pomodoro/store/timerSlice";
import { authSession } from "@/lib/api/authSession";
import { baseApi } from "@/lib/api/baseApi";
import { toasts } from "@/lib/toasts";

const rootReducer = combineSlices(authSession, toasts, notesUi, timer, baseApi);

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
