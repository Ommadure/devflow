import { useState, useEffect } from 'react';
import { supabase } from '../../lib/supabase';
import { Activity, Mail, Loader2, Lock, Eye, EyeOff } from 'lucide-react';

type AuthMode = 'signin' | 'signup' | 'forgot' | 'magiclink';

const PASSWORD_RULES = {
  minLength: 8,
  requireUppercase: true,
  requireLowercase: true,
  requireNumber: true,
};

function getPasswordStrength(password: string): { score: number; label: string; color: string } {
  let score = 0;
  if (password.length >= PASSWORD_RULES.minLength) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[a-z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  if (score <= 2) return { score, label: 'Weak', color: 'bg-red-500' };
  if (score <= 4) return { score, label: 'Medium', color: 'bg-yellow-500' };
  return { score, label: 'Strong', color: 'bg-green-500' };
}

function validatePassword(password: string): string[] {
  const errors: string[] = [];
  if (password.length < PASSWORD_RULES.minLength) errors.push(`At least ${PASSWORD_RULES.minLength} characters`);
  if (PASSWORD_RULES.requireUppercase && !/[A-Z]/.test(password)) errors.push('One uppercase letter');
  if (PASSWORD_RULES.requireLowercase && !/[a-z]/.test(password)) errors.push('One lowercase letter');
  if (PASSWORD_RULES.requireNumber && !/[0-9]/.test(password)) errors.push('One number');
  return errors;
}

export function AuthPage() {
  const [mode, setMode] = useState<AuthMode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => setResendCooldown((p) => Math.max(0, p - 1)), 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
      if (authError) {
        if (authError.message.includes('Email not confirmed')) {
          setError('Email not verified. Please check your inbox and verify your email address.');
        } else {
          setError(authError.message);
        }
        return;
      }
    } catch (err: any) {
      setError(err.message || 'Sign in failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { error: authError, data } = await supabase.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: window.location.origin },
      });
      if (authError) throw authError;
      if (data.user && !data.session) {
        setInfo('Account created! Check your email to verify your address before signing in.');
        setMode('signin');
      }
    } catch (err: any) {
      setError(err.message || 'Sign up failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError('Please enter your email address.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/auth/callback`,
      });
      if (authError) throw authError;
      setInfo('Password reset link sent! Check your email.');
      setMode('signin');
    } catch (err: any) {
      setError(err.message || 'Failed to send reset email.');
    } finally {
      setLoading(false);
    }
  };

  const handleMagicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (resendCooldown > 0) return;
    setLoading(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: window.location.origin },
      });
      if (authError) throw authError;
      setInfo('Check your email for the magic link to sign in.');
      setResendCooldown(60);
    } catch (err: any) {
      setError(err.message || 'Failed to send magic link.');
    } finally {
      setLoading(false);
    }
  };

  const passwordErrors = password ? validatePassword(password) : [];
  const passwordStrength = password ? getPasswordStrength(password) : null;
  const isPasswordValid = passwordErrors.length === 0;

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center">
          <Activity className="w-12 h-12 text-accent" />
        </div>
        <h2 className="mt-6 text-center text-3xl font-extrabold text-white">
          {mode === 'signup' ? 'Create your account' : mode === 'forgot' ? 'Reset your password' : mode === 'magiclink' ? 'Sign in with magic link' : 'Sign in to DevFlow'}
        </h2>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="card p-8">
          <div className="flex gap-2 mb-6 p-1 bg-border rounded-lg">
            <button
              type="button"
              onClick={() => { setMode('signin'); setError(null); setInfo(null); }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${mode === 'signin' ? 'bg-surface text-white' : 'text-gray-400 hover:text-white'}`}
            >
              Password
            </button>
            <button
              type="button"
              onClick={() => { setMode('magiclink'); setError(null); setInfo(null); }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${mode === 'magiclink' ? 'bg-surface text-white' : 'text-gray-400 hover:text-white'}`}
            >
              Magic Link
            </button>
          </div>

          <form className="space-y-5" onSubmit={(e) => {
            if (mode === 'signin') return handleSignIn(e);
            if (mode === 'signup') return handleSignUp(e);
            if (mode === 'forgot') return handleForgotPassword(e);
            if (mode === 'magiclink') return handleMagicLink(e);
          }}>
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-md text-sm">
                {error}
              </div>
            )}
            {info && (
              <div className="bg-green-500/10 border border-green-500/20 text-green-400 p-3 rounded-md text-sm">
                {info}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-300">Email address</label>
              <div className="mt-1 relative">
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

            {mode !== 'forgot' && mode !== 'magiclink' && (
              <div>
                <label className="block text-sm font-medium text-gray-300">Password</label>
                <div className="mt-1 relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-gray-500" />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-field w-full pl-10 pr-10"
                    placeholder={mode === 'signup' ? 'Create a strong password' : '••••••••'}
                    minLength={mode === 'signup' ? PASSWORD_RULES.minLength : 1}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 hover:text-white"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>

                {mode === 'signup' && password && (
                  <div className="mt-2 space-y-2">
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5, 6].map((i) => (
                        <div
                          key={i}
                          className={`h-1 flex-1 rounded-full transition-colors ${passwordStrength && i <= passwordStrength.score ? passwordStrength.color : 'bg-border'}`}
                        />
                      ))}
                    </div>
                    <p className={`text-xs ${passwordStrength ? `text-${passwordStrength.color.replace('bg-', '')}` : 'text-gray-500'}`}>
                      {passwordStrength?.label}
                    </p>
                    {passwordErrors.length > 0 && (
                      <ul className="text-xs text-gray-400 space-y-1">
                        {passwordErrors.map((err, idx) => <li key={idx}>• {err}</li>)}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )}

            {mode === 'magiclink' && (
              <p className="text-sm text-gray-400">
                We'll email you a magic link for password-free sign-in.
              </p>
            )}

            <button
              type="submit"
              disabled={loading || (mode === 'signup' && !isPasswordValid) || (mode === 'magiclink' && resendCooldown > 0)}
              className="btn-primary w-full py-2.5 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin mx-auto" />
              ) : mode === 'signup' ? (
                'Create account'
              ) : mode === 'forgot' ? (
                'Send reset link'
              ) : mode === 'magiclink' ? (
                resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Send magic link'
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <div className="mt-6 space-y-3 text-sm text-center">
            {mode === 'signin' && (
              <>
                <button
                  type="button"
                  onClick={() => { setMode('forgot'); setError(null); setInfo(null); }}
                  className="block w-full text-gray-400 hover:text-white"
                >
                  Forgot your password?
                </button>
                <p className="text-gray-500">
                  Need an account?{' '}
                  <button type="button" onClick={() => { setMode('signup'); setError(null); setInfo(null); }} className="text-accent hover:underline">
                    Sign up
                  </button>
                </p>
              </>
            )}
            {mode === 'signup' && (
              <p className="text-gray-500">
                Already have an account?{' '}
                <button type="button" onClick={() => { setMode('signin'); setError(null); setInfo(null); }} className="text-accent hover:underline">
                  Sign in
                </button>
              </p>
            )}
            {mode === 'forgot' && (
              <button type="button" onClick={() => setMode('signin')} className="text-gray-400 hover:text-white">
                Back to sign in
              </button>
            )}
            {mode === 'magiclink' && (
              <button type="button" onClick={() => { setMode('signin'); setError(null); setInfo(null); }} className="text-gray-400 hover:text-white">
                Back to password sign in
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
