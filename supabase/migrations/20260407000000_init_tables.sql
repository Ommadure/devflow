-- Create snippets table
CREATE TABLE snippets (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  title TEXT NOT NULL,
  code TEXT NOT NULL,
  language TEXT,
  tags TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for user-scoped sorting by updated time
CREATE INDEX snippets_user_updated_idx ON snippets (user_id, updated_at DESC);

-- Enable RLS for snippets
ALTER TABLE snippets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own snippets" ON snippets FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own snippets" ON snippets FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own snippets" ON snippets FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete their own snippets" ON snippets FOR DELETE USING (auth.uid() = user_id);

GRANT ALL ON snippets TO authenticated;

-- Create notes table
CREATE TABLE notes (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for user-scoped sorting by updated time
CREATE INDEX notes_user_updated_idx ON notes (user_id, updated_at DESC);

-- Enable RLS for notes
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own notes" ON notes FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own notes" ON notes FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own notes" ON notes FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete their own notes" ON notes FOR DELETE USING (auth.uid() = user_id);

GRANT ALL ON notes TO authenticated;

-- Create user_stats table (for timer and other global stats)
CREATE TABLE user_stats (
  user_id UUID REFERENCES auth.users(id) PRIMARY KEY,
  completed_sessions INTEGER DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS for user_stats
ALTER TABLE user_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own stats" ON user_stats FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own stats" ON user_stats FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own stats" ON user_stats FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete their own stats" ON user_stats FOR DELETE USING (auth.uid() = user_id);

GRANT ALL ON user_stats TO authenticated;

-- Create a trigger to auto-update the updated_at column
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_snippets_modtime
BEFORE UPDATE ON snippets
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

CREATE TRIGGER update_notes_modtime
BEFORE UPDATE ON notes
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

CREATE TRIGGER update_user_stats_modtime
BEFORE UPDATE ON user_stats
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
