import { Suspense, lazy, useEffect, useState } from 'react';
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
const AuthCallback = lazy(() => import('./pages/AuthCallback').then(m => ({ default: m.default })));

const PageLoader = () => (
  <div className="flex items-center justify-center h-full min-h-[200px]">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
  </div>
);

function App() {
  const dispatch = useAppDispatch();
  const { isAuthenticated, isLoading, user } = useAppSelector((state) => state.auth);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const initializeAuth = async () => {
      try {
        const { data: { session }, error } = await supabase.auth.getSession();
        
        if (error) {
          console.error('Auth session error:', error.message);
          if (isMounted) {
            setAuthError(error.message);
            dispatch(setUser(null));
          }
          return;
        }

        if (isMounted) {
          dispatch(setUser(session?.user ?? null));
        }
      } catch (err) {
        console.error('Auth initialization error:', err);
        if (isMounted) {
          dispatch(setUser(null));
        }
      }
    };

    initializeAuth();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (isMounted) {
        dispatch(setUser(session?.user ?? null));
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [dispatch]);

  if (authError) {
    console.log('Auth error state:', authError);
  }

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
              <Route path="/auth/callback" element={<AuthCallback />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </Layout>
      )}
    </Router>
  );
}

export default App;
