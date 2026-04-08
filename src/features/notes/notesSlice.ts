import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { supabase } from '../../lib/supabase';

export interface Note {
  id: string;
  title: string;
  content: string;
  createdAt: string;
  updatedAt: string;
}

interface NotesState {
  notes: Note[];
  activeNoteId: string | null;
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

const initialState: NotesState = {
  notes: [],
  activeNoteId: null,
  status: 'idle',
  error: null,
};

export const fetchNotes = createAsyncThunk('notes/fetchNotes', async () => {
  const { data, error } = await supabase
    .from('notes')
    .select('*')
    .order('updated_at', { ascending: false });

  if (error) throw error;
  
  return data.map((n: any) => ({
    id: n.id,
    title: n.title,
    content: n.content,
    createdAt: n.created_at,
    updatedAt: n.updated_at,
  })) as Note[];
});

export const addNote = createAsyncThunk('notes/addNote', async (note: { title: string; content: string }) => {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('No user logged in');

  const { data, error } = await supabase
    .from('notes')
    .insert([
      { 
        user_id: user.id,
        title: note.title || 'Untitled Note',
        content: note.content 
      }
    ])
    .select()
    .single();

  if (error) throw error;
  
  return {
    id: data.id,
    title: data.title,
    content: data.content,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  } as Note;
});

export const updateNote = createAsyncThunk('notes/updateNote', async (note: { id: string; title: string; content: string }) => {
  const { data, error } = await supabase
    .from('notes')
    .update({ title: note.title, content: note.content })
    .eq('id', note.id)
    .select()
    .single();

  if (error) throw error;
  
  return {
    id: data.id,
    title: data.title,
    content: data.content,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  } as Note;
});

export const deleteNote = createAsyncThunk('notes/deleteNote', async (id: string) => {
  const { error } = await supabase
    .from('notes')
    .delete()
    .eq('id', id);

  if (error) throw error;
  return id;
});

export const notesSlice = createSlice({
  name: 'notes',
  initialState,
  reducers: {
    setActiveNote: (state, action: PayloadAction<string | null>) => {
      state.activeNoteId = action.payload;
    }
  },
  extraReducers(builder) {
    builder
      .addCase(fetchNotes.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchNotes.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.notes = action.payload;
        if (!state.activeNoteId && action.payload.length > 0) {
          state.activeNoteId = action.payload[0].id;
        }
      })
      .addCase(fetchNotes.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message || 'Failed to fetch notes';
      })
      .addCase(addNote.fulfilled, (state, action) => {
        state.notes.unshift(action.payload);
        state.activeNoteId = action.payload.id;
      })
      .addCase(updateNote.fulfilled, (state, action) => {
        const index = state.notes.findIndex(n => n.id === action.payload.id);
        if (index !== -1) {
          state.notes[index] = action.payload;
        }
      })
      .addCase(deleteNote.fulfilled, (state, action) => {
        state.notes = state.notes.filter(n => n.id !== action.payload);
        if (state.activeNoteId === action.payload) {
          state.activeNoteId = state.notes.length > 0 ? state.notes[0].id : null;
        }
      });
  }
});

export const { setActiveNote } = notesSlice.actions;
export default notesSlice.reducer;