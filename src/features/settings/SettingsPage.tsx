import { useState } from 'react';
import { supabase } from '../../lib/supabase';
import { useAppSelector } from '../../hooks/redux';
import { Eye, EyeOff, Loader2, CheckCircle } from 'lucide-react';

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

export function SettingsPage() {
  const user = useAppSelector((state) => state.auth.user);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const newPasswordErrors = newPassword ? validatePassword(newPassword) : [];
  const passwordStrength = newPassword ? getPasswordStrength(newPassword) : null;
  const isNewPasswordValid = newPasswordErrors.length === 0;

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isNewPasswordValid) return;
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const { error: updateError } = await supabase.auth.updateUser({
        password: newPassword,
      });
      if (updateError) throw updateError;

      setSuccess(true);
      setCurrentPassword('');
      setNewPassword('');
    } catch (err: any) {
      setError(err.message || 'Failed to update password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white">Settings</h1>
        <p className="text-gray-400 mt-1">Manage your account preferences</p>
      </div>

      <div className="card p-6 space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-white mb-1">Account</h2>
          <p className="text-sm text-gray-400">Update your account information</p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Email</label>
            <input
              type="email"
              value={user?.email || ''}
              disabled
              className="input-field w-full opacity-60 cursor-not-allowed"
            />
            <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
          </div>
        </div>
      </div>

      <div className="card p-6 space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-white mb-1">Change Password</h2>
          <p className="text-sm text-gray-400">Update your password to keep your account secure</p>
        </div>

        <form onSubmit={handleChangePassword} className="space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-md text-sm">
              {error}
            </div>
          )}
          {success && (
            <div className="bg-green-500/10 border border-green-500/20 text-green-400 p-3 rounded-md text-sm flex items-center gap-2">
              <CheckCircle className="w-4 h-4 shrink-0" />
              Password updated successfully!
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">New Password</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Eye className="h-5 w-5 text-gray-500" />
              </div>
              <input
                type={showNewPassword ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="input-field w-full pl-10 pr-10"
                placeholder="Enter new password"
                minLength={PASSWORD_RULES.minLength}
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 hover:text-white"
              >
                {showNewPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>

            {newPassword && (
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
                {newPasswordErrors.length > 0 && (
                  <ul className="text-xs text-gray-400 space-y-1">
                    {newPasswordErrors.map((err, idx) => <li key={idx}>• {err}</li>)}
                  </ul>
                )}
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={loading || !isNewPasswordValid || !newPassword}
            className="btn-primary py-2.5 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : 'Update Password'}
          </button>
        </form>
      </div>
    </div>
  );
}
