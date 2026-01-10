import React, { useState, useEffect } from 'react';
import { Download, Music, Search, Disc, CheckCircle2, AlertCircle, Sparkles, List, Play, FileArchive, Loader2, BarChart3, ChevronRight } from 'lucide-react';

export default function App() {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState('idle'); // idle, processing, success, error
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState('');
  
  // Trạng thái zipping
  const [isZipping, setIsZipping] = useState(false);
  const [zipStatusText, setZipStatusText] = useState(''); 
  const [trackStatuses, setTrackStatuses] = useState({}); 

  // Giả lập loading bar
  useEffect(() => {
    let interval;
    if (status === 'processing') {
      setProgress(10);
      interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) return 90; 
          return prev + (prev < 50 ? 5 : 1);
        });
      }, 300);
    } else if (status === 'success' || status === 'error') {
      clearInterval(interval);
      setProgress(100);
    }
    return () => clearInterval(interval);
  }, [status]);

  const handleFetchInfo = async () => {
    if (!url.includes('spotify.com')) {
      setStatus('error');
      setMessage('Link không hợp lệ! Hãy dán link Spotify.');
      return;
    }

    setStatus('processing');
    setMessage('Đang phân tích dữ liệu...');
    setResult(null);
    setTrackStatuses({});
    setIsZipping(false);
    setZipStatusText('');

    try {
      const response = await fetch('http://localhost:5000/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url }),
      });

      const data = await response.json();

      if (response.ok) {
        setStatus('success');
        setResult(data); 
      } else {
        setStatus('error');
        setMessage(data.error || 'Lỗi từ Server.');
      }
    } catch (error) {
      setStatus('error');
      setMessage('Không kết nối được Backend.');
    }
  };

  const downloadTrack = async (trackUrl, trackId) => {
    setTrackStatuses(prev => ({ ...prev, [trackId]: 'loading' }));

    try {
      const response = await fetch('http://localhost:5000/api/download_track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: trackUrl }),
      });

      const data = await response.json();

      if (response.ok) {
        setTrackStatuses(prev => ({ ...prev, [trackId]: 'success' }));
        const link = document.createElement('a');
        link.href = `http://localhost:5000${data.download_url}`;
        link.download = '';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        setTrackStatuses(prev => ({ ...prev, [trackId]: 'error' }));
      }
    } catch (e) {
      setTrackStatuses(prev => ({ ...prev, [trackId]: 'error' }));
    }
  };

  const downloadZip = async () => {
    if (!result || isZipping) return;
    
    setIsZipping(true);
    setZipStatusText('Đang khởi tạo phiên làm việc...');
    
    let trackIndex = 0;
    const progressInterval = setInterval(() => {
      if (result.tracks && trackIndex < result.tracks.length) {
        setZipStatusText(`Đang xử lý: ${result.tracks[trackIndex].name}...`);
        trackIndex++;
      } else {
        setZipStatusText('Đang nén file và tạo gói tải xuống (Sắp xong)...');
      }
    }, 4000); 

    try {
      const response = await fetch('http://localhost:5000/api/download_zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url }),
      });

      const data = await response.json();

      if (response.ok) {
        setZipStatusText('Hoàn tất! Đang tải file về máy...');
        const link = document.createElement('a');
        link.href = `http://localhost:5000${data.download_url}`;
        link.download = '';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        alert("Lỗi khi tạo file Zip: " + data.error);
      }
    } catch (e) {
      alert("Lỗi kết nối hoặc xử lý quá lâu.");
    } finally {
      clearInterval(progressInterval); 
      setIsZipping(false);
      setTimeout(() => setZipStatusText(''), 3000);
    }
  };

  const handleReset = () => {
    setStatus('idle');
    setUrl('');
    setProgress(0);
    setResult(null);
    setTrackStatuses({});
    setIsZipping(false);
    setZipStatusText('');
  }

  // Visualizer bars component
  const MusicBars = () => (
    <div className="flex items-end gap-1 h-8 mb-2">
      <div className="w-1.5 bg-green-500 rounded-t-full animate-[bounce_1s_infinite] h-[60%]"></div>
      <div className="w-1.5 bg-green-400 rounded-t-full animate-[bounce_1.2s_infinite] h-[80%]"></div>
      <div className="w-1.5 bg-green-300 rounded-t-full animate-[bounce_0.8s_infinite] h-[40%]"></div>
      <div className="w-1.5 bg-emerald-400 rounded-t-full animate-[bounce_1.5s_infinite] h-[100%]"></div>
      <div className="w-1.5 bg-emerald-500 rounded-t-full animate-[bounce_1.1s_infinite] h-[50%]"></div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#09090b] text-white font-sans selection:bg-green-500 selection:text-black overflow-x-hidden relative flex flex-col">
      
      {/* --- TECH BACKGROUND PATTERN --- */}
      <div className="fixed inset-0 z-0 pointer-events-none">
          {/* Grid lines */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
          {/* Blobs */}
          <div className="absolute top-[-10%] left-[-10%] w-[600px] h-[600px] bg-green-500/10 rounded-full blur-[120px] animate-pulse"></div>
          <div className="absolute top-[20%] right-[-10%] w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[120px]"></div>
          <div className="absolute bottom-[-10%] left-[20%] w-[600px] h-[600px] bg-emerald-500/5 rounded-full blur-[100px]"></div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8 relative z-10 flex-1 flex flex-col">
        
        {/* --- HEADER --- */}
        <header className="flex flex-col items-center justify-center mb-12 pt-8">
           <div className="flex items-center gap-2 mb-4 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 backdrop-blur-md shadow-lg shadow-green-500/5 hover:border-green-500/30 transition-colors cursor-default">
             <Sparkles className="w-3.5 h-3.5 text-yellow-400" />
             <span className="text-[10px] font-bold text-gray-300 tracking-widest uppercase">Version 2.0 Beta</span>
           </div>
           
           <div className="flex items-center gap-3">
             <MusicBars />
             <h1 className="text-6xl md:text-7xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-br from-white via-gray-200 to-gray-500 drop-shadow-2xl">
               Spoti<span className="text-green-500">Down</span>
             </h1>
           </div>
           <p className="text-gray-400 mt-4 text-lg max-w-lg text-center font-light">
             Trình tải nhạc <span className="text-green-400 font-medium">High Quality</span> từ Spotify. <br/>
             Hỗ trợ tải lẻ, Playlist và Album trọn bộ.
           </p>
        </header>

        {/* --- SEARCH BOX (CENTERED) --- */}
        {(!result || status === 'processing') && (
          <div className="flex-1 flex flex-col items-center justify-start pt-8">
            <div className="w-full max-w-2xl transform transition-all hover:scale-[1.01] duration-300">
               <div className="relative group rounded-3xl p-[1px] bg-gradient-to-r from-gray-800 via-gray-700 to-gray-800 hover:from-green-500 hover:via-emerald-500 hover:to-teal-500 transition-all duration-500 shadow-2xl shadow-black/50">
                  <div className="relative flex items-center bg-[#121212] rounded-[23px] h-16 md:h-20 px-2 overflow-hidden">
                    
                    <div className="pl-6 text-gray-400 group-focus-within:text-green-400 transition-colors">
                      <Search className="w-6 h-6 md:w-8 md:h-8" />
                    </div>
                    
                    <input 
                      type="text" 
                      placeholder="Dán link Spotify vào đây (Track, Album, Playlist)..." 
                      className="w-full h-full bg-transparent border-none text-white px-4 md:px-6 text-lg md:text-xl outline-none placeholder:text-gray-600 font-medium"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      disabled={status === 'processing'}
                      onKeyDown={(e) => e.key === 'Enter' && handleFetchInfo()}
                      autoFocus
                    />
                    
                    <button 
                      onClick={handleFetchInfo}
                      disabled={!url || status === 'processing'}
                      className="m-2 h-12 w-12 md:h-14 md:w-14 bg-white text-black rounded-2xl flex items-center justify-center hover:bg-green-400 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-white/5"
                    >
                      {status === 'processing' ? <Loader2 className="w-6 h-6 animate-spin" /> : <ChevronRight className="w-7 h-7" />}
                    </button>
                  </div>
               </div>

               {/* Hint / Status */}
               <div className="mt-8 text-center min-h-[60px]">
                 {status === 'processing' ? (
                   <div className="space-y-3 w-2/3 mx-auto">
                      <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                        <div className="h-full bg-green-500 animate-[loading_1s_ease-in-out_infinite]" style={{ width: `${progress}%` }}></div>
                      </div>
                      <p className="text-green-400 font-mono text-sm animate-pulse">CONNECTING TO SERVER...</p>
                   </div>
                 ) : status === 'error' ? (
                   <div className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-200 animate-in fade-in slide-in-from-top-2">
                     <AlertCircle className="w-5 h-5" />
                     <span>{message}</span>
                   </div>
                 ) : (
                    <div className="flex justify-center gap-8 text-gray-500 text-sm font-medium">
                        <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-500"/> No Login Required</span>
                        <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-500"/> 320kbps MP3</span>
                        <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-green-500"/> Full Metadata</span>
                    </div>
                 )}
               </div>
            </div>
          </div>
        )}

        {/* --- RESULT VIEW (SPLIT LAYOUT) --- */}
        {status === 'success' && result && (
          <div className="w-full max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-12 duration-700">
             
             {/* Nút quay lại */}
             <button onClick={handleReset} className="mb-6 text-gray-500 hover:text-white flex items-center gap-2 transition-colors group text-sm font-medium">
                <div className="p-1 rounded-full bg-white/5 group-hover:bg-white/10"><ChevronRight className="w-4 h-4 rotate-180" /></div>
                Quay lại tìm kiếm
             </button>

             {/* GRID LAYOUT: Left (Info) - Right (Tracks) */}
             <div className={`grid gap-8 ${result.type === 'track' ? 'grid-cols-1 max-w-2xl mx-auto' : 'lg:grid-cols-[400px_1fr]'}`}>
                
                {/* --- LEFT COLUMN: INFO CARD --- */}
                <div className="h-fit lg:sticky lg:top-8">
                  <div className="bg-[#18181b]/80 backdrop-blur-2xl border border-white/10 rounded-[32px] p-6 lg:p-8 shadow-2xl shadow-black/50 overflow-hidden relative">
                    {/* Background Blur Effect inside Card */}
                    <div className="absolute top-0 left-0 w-full h-48 bg-gradient-to-b from-green-500/10 to-transparent pointer-events-none"></div>

                    <div className="relative z-10 flex flex-col items-center text-center">
                        <div className="w-64 h-64 lg:w-full lg:h-auto lg:aspect-square rounded-2xl shadow-2xl mb-6 relative group">
                            <img src={result.cover} alt="Cover" className="w-full h-full object-cover rounded-2xl border border-white/10 group-hover:scale-[1.02] transition-transform duration-500" />
                            <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-md text-white text-xs font-bold px-3 py-1 rounded-full border border-white/20 uppercase tracking-widest">
                                {result.type}
                            </div>
                        </div>

                        <h2 className="text-2xl md:text-3xl font-bold text-white leading-tight mb-2">{result.name}</h2>
                        <p className="text-lg text-gray-400 font-medium mb-6 flex items-center justify-center gap-2">
                           <Music className="w-5 h-5 text-green-500" /> {result.artist}
                        </p>

                        {/* Actions */}
                        {result.type === 'track' ? (
                            <button 
                                onClick={() => downloadTrack(url, result.id)}
                                className="w-full bg-green-500 hover:bg-green-400 text-black font-bold py-4 rounded-xl transition-all hover:scale-[1.02] hover:shadow-lg hover:shadow-green-500/20 flex items-center justify-center gap-2"
                            >
                                <Download className="w-5 h-5" /> Tải Ngay
                            </button>
                        ) : (
                            <div className="w-full space-y-3">
                                <div className="grid grid-cols-2 gap-3 mb-4">
                                    <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col items-center">
                                        <span className="text-xs text-gray-500 uppercase font-bold">Tracks</span>
                                        <span className="text-xl font-bold text-white">{result.tracks.length}</span>
                                    </div>
                                    <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col items-center">
                                        <span className="text-xs text-gray-500 uppercase font-bold">Format</span>
                                        <span className="text-xl font-bold text-white">MP3</span>
                                    </div>
                                </div>

                                <button 
                                    onClick={downloadZip}
                                    disabled={isZipping}
                                    className={`w-full py-4 rounded-xl font-bold flex items-center justify-center gap-3 transition-all ${
                                        isZipping 
                                        ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 cursor-wait' 
                                        : 'bg-green-500 hover:bg-green-400 text-black shadow-lg hover:shadow-green-500/20 hover:scale-[1.02]'
                                    }`}
                                >
                                    {isZipping ? <Loader2 className="w-5 h-5 animate-spin"/> : <FileArchive className="w-5 h-5"/>}
                                    {isZipping ? "Đang xử lý..." : "Tải trọn bộ (.zip)"}
                                </button>
                                
                                {zipStatusText && (
                                    <div className="p-3 bg-yellow-500/5 border border-yellow-500/10 rounded-lg text-xs text-yellow-200 text-center animate-pulse">
                                        {zipStatusText}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                  </div>
                </div>

                {/* --- RIGHT COLUMN: TRACKLIST --- */}
                {result.type !== 'track' && result.tracks && (
                    <div className="bg-[#18181b]/50 backdrop-blur-xl border border-white/5 rounded-[32px] overflow-hidden flex flex-col shadow-2xl h-fit min-h-[500px]">
                        <div className="p-6 border-b border-white/5 bg-white/5 flex items-center justify-between sticky top-0 z-20 backdrop-blur-md">
                            <h3 className="font-bold text-lg flex items-center gap-2 text-white">
                                <List className="w-5 h-5 text-green-500" /> Danh sách phát
                            </h3>
                            <span className="text-xs font-mono text-gray-500 bg-black/20 px-2 py-1 rounded">
                                {result.tracks.length} items
                            </span>
                        </div>
                        
                        <div className="divide-y divide-white/5">
                            {result.tracks.map((track, idx) => {
                                const status = trackStatuses[track.id];
                                return (
                                    <div key={track.id} className="group p-4 hover:bg-white/5 transition-colors flex items-center gap-4 relative">
                                        {/* Hover Glow */}
                                        <div className="absolute inset-0 bg-green-500/0 group-hover:bg-green-500/5 transition-colors pointer-events-none"></div>

                                        <span className="text-gray-600 font-mono w-6 text-center text-sm group-hover:text-green-500 transition-colors">
                                            {idx + 1}
                                        </span>
                                        
                                        <img src={track.cover || result.cover} className="w-12 h-12 rounded-lg bg-gray-800 object-cover shadow-sm group-hover:shadow-md transition-all" alt="" />
                                        
                                        <div className="flex-1 min-w-0">
                                            <h4 className="font-bold text-gray-200 truncate group-hover:text-white transition-colors">{track.name}</h4>
                                            <p className="text-xs text-gray-500 truncate">{track.artist}</p>
                                        </div>

                                        <button 
                                            onClick={() => downloadTrack(track.url, track.id)}
                                            disabled={status === 'loading' || status === 'success'}
                                            className={`
                                                w-10 h-10 rounded-full flex items-center justify-center transition-all
                                                ${status === 'loading' ? 'bg-yellow-500/10 text-yellow-500' : ''}
                                                ${status === 'success' ? 'bg-green-500/20 text-green-500' : ''}
                                                ${status === 'error' ? 'bg-red-500/10 text-red-500' : ''}
                                                ${!status ? 'bg-white/5 text-gray-400 hover:bg-green-500 hover:text-black hover:scale-110 shadow-lg' : ''}
                                            `}
                                            title="Tải bài này"
                                        >
                                            {status === 'loading' && <Disc className="w-5 h-5 animate-spin"/>}
                                            {status === 'success' && <CheckCircle2 className="w-5 h-5"/>}
                                            {status === 'error' && <AlertCircle className="w-5 h-5"/>}
                                            {!status && <Download className="w-5 h-5"/>}
                                        </button>
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                )}
             </div>
          </div>
        )}
      </div>
      
      {/* Footer */}
      <footer className="text-center py-6 text-gray-600 text-xs relative z-10">
        <p>© 2024 SpotiDown Pro. Educational Purposes Only.</p>
      </footer>
    </div>
  );
}