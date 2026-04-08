import { configureStore } from '@reduxjs/toolkit';
import snippetsReducer from '../features/snippets/snippetsSlice';
import notesReducer from '../features/notes/notesSlice';
import timerReducer from '../features/timer/timerSlice';
import authReducer from '../features/auth/authSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    snippets: snippetsReducer,
    notes: notesReducer,
    timer: timerReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
