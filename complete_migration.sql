-- ============================================
-- STEP 1: Create user_stats table (IF NOT EXISTS)
-- ============================================
CREATE TABLE IF NOT EXISTS public.user_stats (
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    completed_sessions INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id)
);

-- ============================================
-- STEP 2: Enable RLS
-- ============================================
ALTER TABLE public.user_stats ENABLE ROW LEVEL SECURITY;

-- ============================================
-- STEP 3: Create policies (DROP first to avoid duplicates)
-- ============================================
DROP POLICY IF EXISTS "Users can view their own stats" ON public.user_stats;
CREATE POLICY "Users can view their own stats" ON public.user_stats
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own stats" ON public.user_stats;
CREATE POLICY "Users can insert their own stats" ON public.user_stats
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own stats" ON public.user_stats;
CREATE POLICY "Users can update their own stats" ON public.user_stats
    FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- ============================================
-- STEP 4: Grant permissions
-- ============================================
GRANT USAGE ON SCHEMA public TO postgres, authenticated, anon, service_role;
GRANT ALL ON public.user_stats TO postgres, authenticated, anon, service_role;

-- ============================================
-- STEP 5: Create update trigger function
-- ============================================
CREATE OR REPLACE FUNCTION public.update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS update_user_stats_modtime ON public.user_stats;
CREATE TRIGGER update_user_stats_modtime
    BEFORE UPDATE ON public.user_stats
    FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

-- ============================================
-- STEP 6: Create new user trigger function
-- ============================================
DROP FUNCTION IF EXISTS public.handle_new_user();
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_stats (user_id, completed_sessions)
    VALUES (NEW.id, 0)
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- STEP 7: Create trigger on auth.users
-- ============================================
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- ============================================
-- STEP 8: Verify everything
-- ============================================
SELECT 'Tables created successfully' as status;
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
SELECT tgname FROM pg_trigger WHERE tgname LIKE '%user%';