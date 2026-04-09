import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from './hooks/redux';
import { setUser } from './features/auth/authSlice';
import { supabase } from './lib/supabase';
import { Layout } from './components/layout/Layout';

const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const GithubAnalytics = lazy(() => import('./features/github/GithubPage').then(m => ({ default: m.GithubAnalytics })));
const SnippetsPage = lazy(() => import('./features/snippets/SnippetsPage').then(m => ({ default: m.SnippetsPage })));
const NotesPage = lazy(() => import('./features/notes/NotesPage').then(m => ({ default: m.NotesPage })));
const TimerPage = lazy(() => import('./features/timer/TimerPage').then(m => ({ default: m.TimerPage })));
const ApiTesterPage = lazy(() => import('./features/api-tester/ApiTesterPage').then(m => ({ default: m.ApiTesterPage })));
const AuthPage = lazy(() => import('./features/auth/AuthPage').then(m => ({ default: m.AuthPage })));

const PageLoader = () => (
  <div className="flex items-center justify-center h-full min-h-[200px]">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
  </div>
);

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

  return (
    <Router>
      {isLoading ? (
        <div className="flex items-center justify-center h-screen bg-background">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
        </div>
      ) : !isAuthenticated ? (
        <Suspense fallback={<PageLoader />}>
          <AuthPage />
        </Suspense>
      ) : (
        <Layout>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/github" element={<GithubAnalytics />} />
              <Route path="/snippets" element={<SnippetsPage />} />
              <Route path="/notes" element={<NotesPage />} />
              <Route path="/timer" element={<TimerPage />} />
              <Route path="/api" element={<ApiTesterPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </Layout>
      )}
    </Router>
  );
}

export default App;
