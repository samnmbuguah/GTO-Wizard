import React, { useState, useEffect, useCallback } from 'react';
import { Database, Search, Percent, Layers, ChevronRight, Info, Upload, X, FileJson, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { Solution } from '../types/poker';
import { apiClient } from '../api/client';

const LibraryView: React.FC = () => {
  const navigate = useNavigate();
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [rakeFilter, setRakeFilter] = useState<string>('');
  const [stackFilter, setStackFilter] = useState<string>('');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const fetchSolutions = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiClient.get<Solution[]>('/solutions/', {
        rake: rakeFilter,
        stack_depth: stackFilter
      });
      setSolutions(data);
    } catch (err) {
      console.error('Failed to fetch solutions:', err);
    } finally {
      setLoading(false);
    }
  }, [rakeFilter, stackFilter]);

  useEffect(() => {
    fetchSolutions();
  }, [fetchSolutions]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setUploadError(null);
      setUploadSuccess(false);

      const formData = new FormData();
      formData.append('file', file);

      await apiClient.post('/solutions/upload/', formData);
      
      setUploadSuccess(true);
      fetchSolutions();
      setTimeout(() => setShowUploadModal(false), 2000);
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload solution');
    } finally {
      setUploading(false);
    }
  };

  const filteredSolutions = solutions.filter(s => 
    s.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-8 animate-in mx-auto max-w-7xl">
      {/* Header & Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h2 className="text-3xl font-black tracking-tight">Solution Library</h2>
          <p className="text-muted text-sm mt-1 font-medium italic">Powered by Private Pio-Style Instant Rendering</p>
        </div>

        <div className="flex items-center gap-4">
          <button 
            onClick={() => setShowUploadModal(true)}
            className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl text-xs font-black uppercase tracking-widest shadow-lg shadow-indigo-600/20 transition-all transform hover:scale-105 active:scale-95"
          >
            <Upload className="w-4 h-4" />
            Upload Solution
          </button>
          
          <div className="relative group flex-1 min-w-[300px]">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted group-focus-within:text-indigo-500 transition-colors" />
          <input 
            type="text" 
            placeholder="Search by spot name..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-12 pr-4 py-4 bg-card border border-border rounded-3xl text-sm focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none transition-all shadow-lg shadow-black/5"
          />
        </div>
      </div>
    </div>

      {/* Advanced Filters Bar */}
      <div className="flex flex-wrap items-center gap-4 bg-card/60 p-4 rounded-3xl border border-border backdrop-blur-md">
        <div className="flex items-center gap-3 px-4 py-2 bg-background rounded-2xl border border-border shadow-sm">
           <Percent className="w-4 h-4 text-indigo-500" />
           <select 
             className="bg-transparent text-xs font-bold uppercase tracking-widest outline-none cursor-pointer"
             value={rakeFilter}
             onChange={(e) => setRakeFilter(e.target.value)}
           >
             <option value="">Any Rake</option>
             <option value="0.05">5% Rake</option>
             <option value="0.025">2.5% Rake</option>
             <option value="0">No Rake</option>
           </select>
        </div>

        <div className="flex items-center gap-3 px-4 py-2 bg-background rounded-2xl border border-border shadow-sm">
           <Layers className="w-4 h-4 text-violet-500" />
           <select 
             className="bg-transparent text-xs font-bold uppercase tracking-widest outline-none cursor-pointer"
             value={stackFilter}
             onChange={(e) => setStackFilter(e.target.value)}
           >
             <option value="">Any Stack</option>
             <option value="20">20bb</option>
             <option value="40">40bb</option>
             <option value="60">60bb</option>
             <option value="100">100bb</option>
             <option value="150">150bb</option>
           </select>
        </div>

        <div className="ml-auto px-4 py-2 rounded-2xl flex items-center gap-2 text-[10px] font-bold text-muted uppercase tracking-widest font-sans">
           <Info className="w-3.5 h-3.5" />
           <span>{filteredSolutions.length} Results found</span>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-card h-64 rounded-[2.5rem] border border-border animate-pulse shadow-xl"></div>
          ))
        ) : filteredSolutions.length > 0 ? (
          filteredSolutions.map((spot) => (
            <div 
              key={spot.id} 
              onClick={() => navigate(`/dashboard/${spot.id}`)}
              className="group bg-card p-8 rounded-[2.5rem] border border-border hover:border-indigo-500 transition-all shadow-xl hover:shadow-2xl hover:shadow-indigo-500/10 hover:-translate-y-1 cursor-pointer relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full -mr-16 -mt-16 blur-2xl group-hover:bg-indigo-500/10 transition-colors"></div>
              
              <div className="w-14 h-14 bg-indigo-500/10 rounded-2xl flex items-center justify-center text-indigo-500 mb-6 group-hover:bg-indigo-500 group-hover:text-white transition-all shadow-sm">
                <Database className="w-7 h-7" />
              </div>
              
              <h3 className="text-xl font-black mb-3 leading-tight">{spot.name}</h3>
              
              <div className="flex flex-wrap gap-2 mb-6">
                <span className="px-3 py-1 bg-background text-[10px] font-black text-muted rounded-full uppercase tracking-widest border border-border">
                   Rake: {( (spot.rake || 0) * 100 ).toFixed(1)}%
                </span>
                <span className="px-3 py-1 bg-background text-[10px] font-black text-muted rounded-full uppercase tracking-widest border border-border">
                   Depth: {spot.stack_depth}bb
                </span>
              </div>

              <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest border-t border-border/50 pt-6">
                <div className="flex items-center gap-2 text-indigo-500">
                  <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(99,102,241,0.5)]"></div>
                  <span>Instant View Ready</span>
                </div>
                <div className="flex items-center gap-1 group-hover:translate-x-1 transition-transform text-muted group-hover:text-indigo-500 font-black">
                  <span>Browse</span>
                  <ChevronRight className="w-3 h-3" />
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="col-span-full py-20 text-center space-y-4">
             <div className="w-20 h-20 bg-card rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl border border-border">
                <Search className="w-10 h-10 text-muted" />
             </div>
             <h3 className="text-xl font-black">No matches found</h3>
             <p className="text-muted text-sm">Try adjusting your rake or stack depth filters.</p>
             <button 
               onClick={() => { setRakeFilter(''); setStackFilter(''); setSearch(''); }}
               className="px-6 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-600/20"
             >
               Clear all filters
             </button>
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="bg-card w-full max-w-md rounded-[2.5rem] border border-border shadow-2xl p-8 relative overflow-hidden">
            <button 
              onClick={() => setShowUploadModal(false)}
              className="absolute top-6 right-6 text-muted hover:text-white transition-colors"
            >
              <X className="w-6 h-6" />
            </button>

            <div className="text-center space-y-4">
              <div className="w-20 h-20 bg-indigo-500/10 rounded-3xl flex items-center justify-center text-indigo-500 mx-auto">
                <FileJson className="w-10 h-10" />
              </div>
              <div>
                <h3 className="text-2xl font-black">Import Solver Solution</h3>
                <p className="text-muted text-sm px-4">Upload a .zip package containing metadata.json and nodes.json (SIF v1.0)</p>
              </div>

              <div className="pt-6">
                <label className={`
                  flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-[2rem] cursor-pointer transition-all
                  ${uploading ? 'bg-background/50 border-indigo-500/50 pointer-events-none' : 'hover:bg-indigo-500/5 border-border hover:border-indigo-500'}
                  ${uploadSuccess ? 'border-emerald-500 bg-emerald-500/5' : ''}
                `}>
                  <div className="flex flex-col items-center justify-center pt-5 pb-6">
                    {uploading ? (
                      <>
                        <Loader2 className="w-10 h-10 text-indigo-500 animate-spin mb-4" />
                        <p className="text-sm font-bold text-indigo-500 uppercase tracking-widest">Processing Data...</p>
                      </>
                    ) : uploadSuccess ? (
                      <>
                        <div className="w-12 h-12 bg-emerald-500 text-white rounded-full flex items-center justify-center mb-4">
                          <Database className="w-6 h-6" />
                        </div>
                        <p className="text-sm font-bold text-emerald-500 uppercase tracking-widest">Import Success!</p>
                      </>
                    ) : (
                      <>
                        <Upload className="w-10 h-10 text-muted mb-4 group-hover:text-indigo-500 transition-colors" />
                        <p className="text-sm font-bold uppercase tracking-widest">Click to upload .zip</p>
                        <p className="text-xs text-muted mt-2">Max file size: 50MB</p>
                      </>
                    )}
                  </div>
                  <input type="file" className="hidden" accept=".zip" onChange={handleFileUpload} />
                </label>
              </div>

              {uploadError && (
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-500 text-xs font-bold animate-in slide-in-from-top-2">
                  {uploadError}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LibraryView;
