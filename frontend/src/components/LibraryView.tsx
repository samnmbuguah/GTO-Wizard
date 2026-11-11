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
        stack_depth: stackFilter,
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

  const filteredSolutions = solutions.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-full bg-[#00140f] p-6 lg:p-8 space-y-6 animate-in text-[#ccdbdc]">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Header & Search */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#2d393b] pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-[#182628] border border-[#2d393b] rounded-[4px] flex items-center justify-center text-[#7aa6da]">
                <Database className="w-5 h-5" />
              </div>
              <h2 className="text-2xl font-black uppercase tracking-wider text-white">Solution Library</h2>
            </div>
            <p className="text-[#a1b4d9] text-xs mt-1 font-mono">
              Pre-computed CFR solutions & live solver lookup points
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-[#7aa6da] hover:bg-[#6894c7] text-[#00140f] rounded-[4px] text-xs font-black uppercase tracking-wider transition-all shadow-md active:scale-95 cursor-pointer"
            >
              <Upload className="w-4 h-4" />
              Upload Solution
            </button>

            <div className="relative group flex-1 min-w-[260px]">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8b9ea0] group-focus-within:text-[#7aa6da] transition-colors" />
              <input
                type="text"
                placeholder="Search solutions..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-[#182628] border border-[#2d393b] rounded-[4px] text-xs text-white placeholder-[#8b9ea0] focus:border-[#7aa6da] focus:outline-none transition-all font-mono"
              />
            </div>
          </div>
        </div>

        {/* Filters Bar */}
        <div className="flex flex-wrap items-center gap-3 bg-[#182628] p-3 rounded-[6px] border border-[#2d393b]">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[#00140f] rounded-[4px] border border-[#2d393b]">
            <Percent className="w-3.5 h-3.5 text-[#7aa6da]" />
            <select
              className="bg-transparent text-[11px] font-bold uppercase tracking-wider text-[#ccdbdc] outline-none cursor-pointer"
              value={rakeFilter}
              onChange={(e) => setRakeFilter(e.target.value)}
            >
              <option value="" className="bg-[#182628] text-white">Any Rake</option>
              <option value="0.05" className="bg-[#182628] text-white">5.0% Rake</option>
              <option value="0.025" className="bg-[#182628] text-white">2.5% Rake</option>
              <option value="0" className="bg-[#182628] text-white">No Rake</option>
            </select>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 bg-[#00140f] rounded-[4px] border border-[#2d393b]">
            <Layers className="w-3.5 h-3.5 text-[#64ffda]" />
            <select
              className="bg-transparent text-[11px] font-bold uppercase tracking-wider text-[#ccdbdc] outline-none cursor-pointer"
              value={stackFilter}
              onChange={(e) => setStackFilter(e.target.value)}
            >
              <option value="" className="bg-[#182628] text-white">Any Stack</option>
              <option value="20" className="bg-[#182628] text-white">20bb</option>
              <option value="40" className="bg-[#182628] text-white">40bb</option>
              <option value="60" className="bg-[#182628] text-white">60bb</option>
              <option value="100" className="bg-[#182628] text-white">100bb</option>
              <option value="150" className="bg-[#182628] text-white">150bb</option>
            </select>
          </div>

          <div className="ml-auto flex items-center gap-2 text-[11px] font-bold text-[#8b9ea0] uppercase tracking-wider font-mono">
            <Info className="w-3.5 h-3.5 text-[#7aa6da]" />
            <span>{filteredSolutions.length} Solutions</span>
          </div>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-[#182628] h-48 rounded-[6px] border border-[#2d393b] animate-pulse"></div>
            ))
          ) : filteredSolutions.length > 0 ? (
            filteredSolutions.map((spot) => (
              <div
                key={spot.id}
                onClick={() => navigate(`/dashboard/${spot.id}`)}
                className="group bg-[#182628] p-5 rounded-[6px] border border-[#2d393b] hover:border-[#7aa6da] hover:bg-[#1f2b2d] transition-all shadow-md cursor-pointer relative flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="px-2 py-0.5 bg-[#00140f] text-[10px] font-mono font-bold text-[#7aa6da] rounded-[3px] border border-[#2d393b] uppercase">
                      ID #{spot.id}
                    </span>
                    <div className="flex items-center gap-1.5 text-[10px] text-[#64ffda] font-mono">
                      <div className="w-1.5 h-1.5 bg-[#64ffda] rounded-full animate-pulse shadow-[0_0_6px_#64ffda]"></div>
                      <span>Instant View Ready</span>
                    </div>
                  </div>

                  <h3 className="text-base font-black text-white group-hover:text-[#64ffda] transition-colors mb-3">
                    {spot.name}
                  </h3>

                  <div className="flex flex-wrap gap-2 mb-4">
                    <span className="px-2.5 py-1 bg-[#00140f] text-[10px] font-mono font-bold text-[#ccdbdc] rounded-[3px] border border-[#2d393b] uppercase">
                      Rake: {((spot.rake || 0) * 100).toFixed(1)}%
                    </span>
                    <span className="px-2.5 py-1 bg-[#00140f] text-[10px] font-mono font-bold text-[#ccdbdc] rounded-[3px] border border-[#2d393b] uppercase">
                      Depth: {spot.stack_depth}bb
                    </span>
                  </div>
                </div>

                <div className="flex justify-between items-center text-[10.5px] font-black uppercase tracking-wider border-t border-[#2d393b] pt-3 text-[#8b9ea0] group-hover:text-[#7aa6da] transition-colors">
                  <span>Open Spot in Solver</span>
                  <div className="flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                    <span>Browse</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="col-span-full py-16 text-center space-y-4 bg-[#182628] rounded-[6px] border border-[#2d393b]">
              <div className="w-14 h-14 bg-[#00140f] rounded-[6px] border border-[#2d393b] flex items-center justify-center mx-auto text-[#8b9ea0]">
                <Search className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-black text-white">No matches found</h3>
              <p className="text-[#8b9ea0] text-xs">Try adjusting your rake or stack depth filters.</p>
              <button
                onClick={() => {
                  setRakeFilter('');
                  setStackFilter('');
                  setSearch('');
                }}
                className="px-4 py-2 bg-[#7aa6da] hover:bg-[#6894c7] text-[#00140f] rounded-[4px] text-xs font-black uppercase tracking-wider transition-all cursor-pointer"
              >
                Clear all filters
              </button>
            </div>
          )}
        </div>

        {/* Upload Modal */}
        {showUploadModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
            <div className="bg-[#182628] w-full max-w-md rounded-[6px] border border-[#2d393b] shadow-2xl p-6 relative">
              <button
                onClick={() => setShowUploadModal(false)}
                className="absolute top-4 right-4 text-[#8b9ea0] hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="text-center space-y-3">
                <div className="w-12 h-12 bg-[#00140f] rounded-[4px] border border-[#2d393b] flex items-center justify-center text-[#7aa6da] mx-auto">
                  <FileJson className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-black uppercase tracking-wider text-white">Import Solver Solution</h3>
                  <p className="text-[#8b9ea0] text-xs mt-1">Upload a .zip package containing metadata.json and nodes.json (SIF v1.0)</p>
                </div>

                <div className="pt-4">
                  <label
                    className={`flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-[4px] cursor-pointer transition-all ${
                      uploading
                        ? 'bg-[#00140f]/50 border-[#7aa6da]/50 pointer-events-none'
                        : 'border-[#2d393b] hover:border-[#7aa6da] bg-[#00140f]'
                    } ${uploadSuccess ? 'border-emerald-500 bg-emerald-500/10' : ''}`}
                  >
                    <div className="flex flex-col items-center justify-center p-4">
                      {uploading ? (
                        <>
                          <Loader2 className="w-8 h-8 text-[#7aa6da] animate-spin mb-3" />
                          <p className="text-xs font-bold text-[#7aa6da] uppercase tracking-wider">Processing Data...</p>
                        </>
                      ) : uploadSuccess ? (
                        <>
                          <div className="w-10 h-10 bg-emerald-500 text-white rounded-full flex items-center justify-center mb-3">
                            <Database className="w-5 h-5" />
                          </div>
                          <p className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Import Success!</p>
                        </>
                      ) : (
                        <>
                          <Upload className="w-8 h-8 text-[#8b9ea0] mb-3 group-hover:text-[#7aa6da] transition-colors" />
                          <p className="text-xs font-bold uppercase tracking-wider text-white">Click to upload .zip</p>
                          <p className="text-[10px] text-[#8b9ea0] mt-1 font-mono">Max file size: 50MB</p>
                        </>
                      )}
                    </div>
                    <input type="file" className="hidden" accept=".zip" onChange={handleFileUpload} />
                  </label>
                </div>

                {uploadError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-[4px] text-red-400 text-xs font-bold animate-in">
                    {uploadError}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LibraryView;
