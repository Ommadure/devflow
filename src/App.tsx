import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from './hooks/redux';
import { setUser, setLoading } from './features/auth/authSlice';
import { supabase } from './lib/supabase';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/Dashboard';
import { GithubAnalytics } from './features/github/GithubPage';
import { SnippetsPage } from './features/snippets/SnippetsPage';
import { NotesPage } from './features/notes/NotesPage';
import { TimerPage } from './features/timer/TimerPage';
import { ApiTesterPage } from './features/api-tester/ApiTesterPage';
import { AuthPage } from './features/auth/AuthPage';

function App() {
  const dispatch = useAppDispatch();
  const { isAuthenticated, isLoading } = useAppSelector((state) => state.auth);

  useEffect(() => {
    // Check active sessions and sets the user
    supabase.auth.getSession().then(({ data: { session } }) => {
      dispatch(setUser(session?.user ?? null));
    });

    // Listen for changes on auth state (logged in, signed out, etc.)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      dispatch(setUser(session?.user ?? null));
    });

    return () => subscription.unsubscribe();
  }, [dispatch]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage />;
  }

  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/github" element={<GithubAnalytics />} />
          <Route path="/snippets" element={<SnippetsPage />} />
          <Route path="/notes" element={<NotesPage />} />
          <Route path="/timer" element={<TimerPage />} />
          <Route path="/api" element={<ApiTesterPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
