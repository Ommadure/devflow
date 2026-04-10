-- ============================================
-- SIMPLE: Just create user_stats table (trigger already exists)
-- ============================================

-- Create user_stats table
CREATE TABLE IF NOT EXISTS public.user_stats (
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    completed_sessions INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id)
);

-- Enable RLS
ALTER TABLE public.user_stats ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT USAGE ON SCHEMA public TO postgres, authenticated, anon, service_role;
GRANT ALL ON public.user_stats TO postgres, authenticated, anon, service_role;

-- Create policies
DROP POLICY IF EXISTS "Users can view their own stats" ON public.user_stats;
CREATE POLICY "Users can view their own stats" ON public.user_stats FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own stats" ON public.user_stats;
CREATE POLICY "Users can insert their own stats" ON public.user_stats FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own stats" ON public.user_stats;
CREATE POLICY "Users can update their own stats" ON public.user_stats FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Update the existing trigger function to handle errors gracefully
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_stats (user_id, completed_sessions)
    VALUES (NEW.id, 0)
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    -- Log the error but don't fail the user creation
    RAISE NOTICE 'Could not create user_stats: %', SQLERRM;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Verify
SELECT 'user_stats table created' as status;
SELECT count(*) as user_stats_count FROM public.user_stats;