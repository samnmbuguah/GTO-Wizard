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
      const res = await fetch('http://213.199.50.129:8000/api/token-auth/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          username: username.trim(), 
          password: password.trim() 
        }),
      });

      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('gto_token', data.token);
        localStorage.setItem('gto_user', username);
        navigate('/dashboard');
      } else {
        const errData = await res.json();
        setError(errData.non_field_errors?.[0] || 'Invalid credentials. Please try again.');
      }
    } catch (err) {
      setError('Connection failed. Please check your backend status.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f1f5f9] dark:bg-[#0f172a] flex items-center justify-center p-6 relative overflow-hidden font-sans">
      {/* Dynamic Background Elements */}
      <div className="absolute top-0 left-0 w-full h-full pointer-events-none opacity-20">
         <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-indigo-500 rounded-full blur-[120px] animate-pulse"></div>
         <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-600 rounded-full blur-[150px] animate-pulse" style={{ animationDelay: '1s' }}></div>
      </div>

      <div className="w-full max-w-md bg-white/80 dark:bg-slate-900/80 backdrop-blur-2xl p-10 rounded-[3rem] border border-white/20 dark:border-slate-800/50 shadow-2xl relative z-10 animate-in">
        <div className="flex flex-col items-center mb-10">
          <div className="w-20 h-20 bg-gradient-to-tr from-indigo-600 to-violet-600 rounded-[2rem] flex items-center justify-center shadow-xl shadow-indigo-500/30 mb-6 group hover:rotate-6 transition-transform">
             <Activity className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-black tracking-tight text-slate-900 dark:text-white text-center">
            Private GTO Wizard
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-2 text-sm font-medium">Professional Poker Analysis</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 dark:text-slate-500 ml-1">Username</label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <User className="w-5 h-5 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
              </div>
              <input
                type="text"
                required
                autoComplete="username"
                className="block w-full pl-12 pr-4 py-4 bg-slate-100 dark:bg-slate-800/50 border-2 border-transparent focus:border-indigo-500 rounded-2xl transition-all outline-none text-slate-900 dark:text-white font-medium"
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 dark:text-slate-500 ml-1">Password</label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Lock className="w-5 h-5 text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
              </div>
              <input
                type={showPassword ? "text" : "password"}
                required
                autoComplete="current-password"
                className="block w-full pl-12 pr-12 py-4 bg-slate-100 dark:bg-slate-800/50 border-2 border-transparent focus:border-indigo-500 rounded-2xl transition-all outline-none text-slate-900 dark:text-white font-medium"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button 
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-indigo-500 transition-colors focus:outline-none"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-rose-500 text-xs font-bold animate-in">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <p>{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-2xl text-sm font-black uppercase tracking-widest transition-all shadow-xl shadow-indigo-600/20 active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            ) : (
              <>
                <span>Enter Terminal</span>
                <ChevronRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="mt-10 text-center">
          <p className="text-[10px] text-slate-400 dark:text-slate-500 font-bold uppercase tracking-widest">
            Access Restricted to Authorized Solvers
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginView;
