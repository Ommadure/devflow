import { useState, useEffect } from 'react';
import { supabase } from '../../lib/supabase';
import { Activity, Mail, Loader2, CheckCircle } from 'lucide-react';
import { Modal } from '../../components/ui/Modal';

const RESEND_COOLDOWN_SECONDS = 60;

export function AuthPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);

  useEffect(() => {
    if (cooldownSeconds <= 0) return;

    const timer = setInterval(() => {
      setCooldownSeconds((prev) => {
        if (prev <= 1) return 0;
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [cooldownSeconds]);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();

    if (cooldownSeconds > 0) {
      setError(`Please wait ${cooldownSeconds} seconds before requesting a new magic link.`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: window.location.origin,
          shouldCreateUser: true,
        },
      });

      if (error) {
        if (error.status === 429 || error.message.toLowerCase().includes('rate limit')) {
          throw new Error('Too many requests. Please wait a minute before trying again.');
        }
        throw error;
      }

      setShowSuccessModal(true);
      setCooldownSeconds(RESEND_COOLDOWN_SECONDS);
    } catch (err: any) {
      const message = err.message || 'Something went wrong. Please try again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center">
          <Activity className="w-12 h-12 text-accent" />
        </div>
        <h2 className="mt-6 text-center text-3xl font-extrabold text-white">
          Sign in to DevFlow
        </h2>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="card p-8">
          <form className="space-y-6" onSubmit={handleAuth}>
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-md text-sm">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-300">
                Email address
              </label>
              <div className="mt-1 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-gray-500" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-field w-full pl-10"
                  placeholder="you@example.com"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || cooldownSeconds > 0}
              className="btn-primary w-full flex justify-center py-2.5 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : cooldownSeconds > 0 ? (
                `Resend in ${cooldownSeconds}s`
              ) : (
                'Send magic link'
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500">
            We'll email you a one-click sign-in link.
          </p>
        </div>
      </div>

      <Modal
        isOpen={showSuccessModal}
        onClose={() => setShowSuccessModal(false)}
        title="Email Sent"
      >
        <div className="flex flex-col items-center text-center gap-4">
          <div className="p-4 rounded-full bg-green-500/10 text-green-500">
            <CheckCircle className="w-8 h-8" />
          </div>
          <p className="text-gray-300 text-lg leading-relaxed">
            Check your email for the magic login link we just sent to <span className="text-white font-bold">{email}</span>.
          </p>
          <button
            onClick={() => setShowSuccessModal(false)}
            className="btn-primary w-full mt-6 py-3"
          >
            Got it
          </button>
        </div>
      </Modal>
    </div>
  );
}
