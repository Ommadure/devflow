import { createSlice, nanoid, type PayloadAction } from "@reduxjs/toolkit";

export interface Toast {
  id: string;
  tone: "info" | "error" | "success";
  message: string;
}

/** App-wide notifications (e.g. "Too many requests"), rendered by <Toaster />. */
export const toasts = createSlice({
  name: "toasts",
  initialState: [] as Toast[],
  reducers: {
    toastShown: {
      reducer(state, action: PayloadAction<Toast>) {
        // One copy of a message at a time: ten parallel 429s shouldn't stack ten toasts.
        if (!state.some((toast) => toast.message === action.payload.message)) {
          state.push(action.payload);
        }
      },
      prepare(toast: Omit<Toast, "id">) {
        return { payload: { ...toast, id: nanoid() } };
      },
    },
    toastDismissed(state, action: PayloadAction<string>) {
      return state.filter((toast) => toast.id !== action.payload);
    },
  },
  selectors: {
    selectToasts: (state) => state,
  },
});

export const { toastShown, toastDismissed } = toasts.actions;
export const { selectToasts } = toasts.selectors;
