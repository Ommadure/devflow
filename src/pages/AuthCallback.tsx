import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { Loader2 } from 'lucide-react';

export default function AuthCallback() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const hash = window.location.hash;
      const params = new URLSearchParams(hash.substring(1));
      const errorParam = params.get('error');
      const errorDescription = params.get('error_description');

      if (errorParam) {
        setError(errorDescription || errorParam);
        setTimeout(() => navigate('/'), 3000);
        return;
      }

      const { data: { session }, error: sessionError } = await supabase.auth.getSession();

      if (sessionError) {
        setError(sessionError.message);
        setTimeout(() => navigate('/'), 3000);
        return;
      }

      if (session) {
        navigate('/');
      } else {
        navigate('/');
      }
    };

    handleCallback();
  }, [navigate]);

  if (error) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center">
        <div className="card p-8 max-w-md text-center">
          <div className="text-red-400 mb-4">Error: {error}</div>
          <p className="text-gray-400 text-sm">Redirecting you back home...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center">
      <Loader2 className="w-8 h-8 text-accent animate-spin mb-4" />
      <p className="text-gray-400">Completing sign in...</p>
    </div>
  );
}
