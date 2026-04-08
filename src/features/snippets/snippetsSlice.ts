import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { supabase } from '../../lib/supabase';

export interface Snippet {
  id: string;
  title: string;
  code: string;
  language: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

interface SnippetsState {
  snippets: Snippet[];
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

const initialState: SnippetsState = {
  snippets: [],
  status: 'idle',
  error: null,
};

export const fetchSnippets = createAsyncThunk('snippets/fetchSnippets', async () => {
  const { data, error } = await supabase
    .from('snippets')
    .select('*')
    .order('updated_at', { ascending: false });

  if (error) throw error;
  
  return data.map((s: any) => ({
    id: s.id,
    title: s.title,
    code: s.code,
    language: s.language,
    tags: s.tags,
    createdAt: s.created_at,
    updatedAt: s.updated_at,
  })) as Snippet[];
});

export const addSnippet = createAsyncThunk('snippets/addSnippet', async (snippet: Omit<Snippet, 'id' | 'createdAt' | 'updatedAt'>) => {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('No user logged in');

  const { data, error } = await supabase
    .from('snippets')
    .insert([
      { 
        user_id: user.id,
        title: snippet.title,
        code: snippet.code,
        language: snippet.language,
        tags: snippet.tags
      }
    ])
    .select()
    .single();

  if (error) throw error;
  
  return {
    id: data.id,
    title: data.title,
    code: data.code,
    language: data.language,
    tags: data.tags,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  } as Snippet;
});

export const updateSnippet = createAsyncThunk('snippets/updateSnippet', async (snippet: Snippet) => {
  const { data, error } = await supabase
    .from('snippets')
    .update({ 
      title: snippet.title, 
      code: snippet.code, 
      language: snippet.language, 
      tags: snippet.tags 
    })
    .eq('id', snippet.id)
    .select()
    .single();

  if (error) throw error;
  
  return {
    id: data.id,
    title: data.title,
    code: data.code,
    language: data.language,
    tags: data.tags,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  } as Snippet;
});

export const deleteSnippet = createAsyncThunk('snippets/deleteSnippet', async (id: string) => {
  const { error } = await supabase
    .from('snippets')
    .delete()
    .eq('id', id);

  if (error) throw error;
  return id;
});

export const snippetsSlice = createSlice({
  name: 'snippets',
  initialState,
  reducers: {},
  extraReducers(builder) {
    builder
      .addCase(fetchSnippets.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchSnippets.fulfilled, (state, action) => {
        state.status = 'succeeded';
        state.snippets = action.payload;
      })
      .addCase(fetchSnippets.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message || 'Failed to fetch snippets';
      })
      .addCase(addSnippet.fulfilled, (state, action) => {
        state.snippets.unshift(action.payload);
      })
      .addCase(updateSnippet.fulfilled, (state, action) => {
        const index = state.snippets.findIndex(s => s.id === action.payload.id);
        if (index !== -1) {
          state.snippets[index] = action.payload;
        }
      })
      .addCase(deleteSnippet.fulfilled, (state, action) => {
        state.snippets = state.snippets.filter(s => s.id !== action.payload);
      });
  }
});

export default snippetsSlice.reducer;
