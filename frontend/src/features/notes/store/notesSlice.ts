import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

/** UI state only; the notes themselves live in the RTK Query cache. */
export const notesUi = createSlice({
  name: "notesUi",
  initialState: { activeNoteId: null as string | null },
  reducers: {
    noteSelected(state, action: PayloadAction<string | null>) {
      state.activeNoteId = action.payload;
    },
  },
  selectors: {
    selectActiveNoteId: (state) => state.activeNoteId,
  },
});

export const { noteSelected } = notesUi.actions;
export const { selectActiveNoteId } = notesUi.selectors;
