import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { supabase } from '../../lib/supabase';

interface TimerState {
  completedSessions: number;
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
}

const initialState: TimerState = {
  completedSessions: 0,
  status: 'idle',
};

export const fetchStats = createAsyncThunk('timer/fetchStats', async () => {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('No user logged in');

  const { data, error } = await supabase
    .from('user_stats')
    .select('completed_sessions')
    .eq('user_id', user.id)
    .single();

  if (error && error.code !== 'PGRST116') {
    throw error;
  }
  
  return data ? data.completed_sessions : 0;
});

export const addCompletedSession = createAsyncThunk('timer/addCompletedSession', async (_, { getState }) => {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('No user logged in');

  const state: any = getState();
  const newCount = state.timer.completedSessions + 1;

  const { error } = await supabase
    .from('user_stats')
    .upsert({ user_id: user.id, completed_sessions: newCount });

  if (error) throw error;
  
  return newCount;
});

export const resetSessions = createAsyncThunk('timer/resetSessions', async () => {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('No user logged in');

  const { error } = await supabase
    .from('user_stats')
    .upsert({ user_id: user.id, completed_sessions: 0 });

  if (error) throw error;
  
  return 0;
});

export const timerSlice = createSlice({
  name: 'timer',
  initialState,
  reducers: {},
  extraReducers(builder) {
    builder
      .addCase(fetchStats.fulfilled, (state, action) => {
        state.completedSessions = action.payload;
        state.status = 'succeeded';
      })
      .addCase(addCompletedSession.fulfilled, (state, action) => {
        state.completedSessions = action.payload;
      })
      .addCase(resetSessions.fulfilled, (state, action) => {
        state.completedSessions = action.payload;
      });
  }
});

export default timerSlice.reducer;
