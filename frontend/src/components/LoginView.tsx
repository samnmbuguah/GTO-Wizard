import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, User, AlertCircle, ChevronRight, Activity, Eye, EyeOff } from 'lucide-react';

const LoginView: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || '/api';
      const cleanApiUrl = apiUrl.replace(/\/+$/, '');
      const res = await fetch(`${cleanApiUrl}/token-auth/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          username: username.trim(), 
          password: password.trim(), 
        }),
      });

      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('gto_token', data.token);
        localStorage.setItem('gto_user', username);
        navigate('/dashboard');
      } else {
        let errorMsg = 'Invalid credentials. Please try again.';
        try {
          const errData = await res.json();
          errorMsg = errData.non_field_errors?.[0] || errData.detail || errorMsg;
        } catch {
          errorMsg = `Server error (${res.status}). Please check backend status.`;
        }
        setError(errorMsg);
      }
    } catch {
      setError('Connection failed. Please check your backend status.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#00140f] flex items-center justify-center p-6 relative overflow-hidden font-sans text-[#ccdbdc]">
      {/* Background glow subtle geometry */}
      <div className="absolute top-0 left-0 w-full h-full pointer-events-none opacity-25">
        <div className="absolute top-[-15%] left-[-10%] w-[45%] h-[45%] bg-[#182628] rounded-full blur-[140px]"></div>
        <div className="absolute bottom-[-15%] right-[-10%] w-[50%] h-[50%] bg-[#2d393b] rounded-full blur-[160px]"></div>
      </div>

      <div className="w-full max-w-md bg-[#182628] p-8 rounded-[8px] border border-[#2d393b] shadow-2xl relative z-10 animate-in">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 bg-[#00140f] rounded-[6px] border border-[#2d393b] flex items-center justify-center shadow-lg mb-4 text-[#7aa6da]">
            <Activity className="w-7 h-7 text-[#64ffda]" />
          </div>
          <h1 className="text-2xl font-black uppercase tracking-wider text-white text-center">
            Private GTO Wizard
          </h1>
          <p className="text-[#a1b4d9] mt-1 text-xs font-mono">Professional DCFR Solver Terminal</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-wider text-[#8b9ea0] ml-1 font-mono">
              Username
            </label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <User className="w-4 h-4 text-[#8b9ea0] group-focus-within:text-[#7aa6da] transition-colors" />
              </div>
              <input
                type="text"
                required
                autoComplete="username"
                className="block w-full pl-10 pr-4 py-2.5 bg-[#00140f] border border-[#2d393b] focus:border-[#7aa6da] rounded-[4px] transition-all outline-none text-white text-xs font-mono"
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-wider text-[#8b9ea0] ml-1 font-mono">
              Password
            </label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                <Lock className="w-4 h-4 text-[#8b9ea0] group-focus-within:text-[#7aa6da] transition-colors" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                autoComplete="current-password"
                className="block w-full pl-10 pr-10 py-2.5 bg-[#00140f] border border-[#2d393b] focus:border-[#7aa6da] rounded-[4px] transition-all outline-none text-white text-xs font-mono"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button 
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-[#8b9ea0] hover:text-[#7aa6da] transition-colors focus:outline-none cursor-pointer"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-rose-500/10 border border-rose-500/30 rounded-[4px] text-rose-400 text-xs font-bold animate-in">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <p>{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-[#7aa6da] hover:bg-[#6894c7] text-[#00140f] rounded-[4px] text-xs font-black uppercase tracking-wider transition-all shadow-md active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer mt-2"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-[#00140f]/30 border-t-[#00140f] rounded-full animate-spin"></div>
            ) : (
              <>
                <span>Enter Terminal</span>
                <ChevronRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="mt-8 text-center border-t border-[#2d393b] pt-4">
          <p className="text-[10px] text-[#8b9ea0] font-bold uppercase tracking-wider font-mono">
            High-Performance Live Equilibrium Engine
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginView;
