import React, { useState, useEffect } from 'react';
import { Download, Music, Search, Disc, CheckCircle2, AlertCircle, Sparkles, List, Play, FileArchive, Loader2, BarChart3, ChevronRight } from 'lucide-react';

// --- CẤU HÌNH ĐƠN GIẢN (HARDCODED) ---
const API_BASE_URL = 'https://spotidown-project.onrender.com';

export default function App() {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState('idle'); // idle, processing, success, error
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState('');
  
  // Trạng thái zipping (Async)
  const [isZipping, setIsZipping] = useState(false);
  const [zipStatusText, setZipStatusText] = useState(''); 
  const [zipProgress, setZipProgress] = useState(0); 
  const [trackStatuses, setTrackStatuses] = useState({}); 
  
  // Trạng thái chờ Cold Start (Server khởi động chậm)
  const [isTakingLong, setIsTakingLong] = useState(false);

  // Giả lập loading bar
  useEffect(() => {
    let interval;
    let timeout;

    if (status === 'processing') {
      setProgress(10);
      setIsTakingLong(false);

      // Tăng progress bar giả lập
      interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) return 90; 
          return prev + (prev < 50 ? 5 : 1);
        });
      }, 300);

      // Nếu sau 5 giây chưa xong thì báo hiệu server đang khởi động
      timeout = setTimeout(() => {
        setIsTakingLong(true);
      }, 5000);

    } else if (status === 'success' || status === 'error') {
      clearInterval(interval);
      clearTimeout(timeout);
      setProgress(100);
      setIsTakingLong(false);
    }

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [status]);

  const handleFetchInfo = async () => {
    if (!url.includes('spotify.com')) {
      setStatus('error');
      setMessage('Link không hợp lệ! Hãy dán link Spotify.');
      return;
    }

    setStatus('processing');
    setMessage('Đang kết nối server...');
    setResult(null);
    setTrackStatuses({});
    setIsZipping(false);
    setZipStatusText('');
    setZipProgress(0);

    try {
      // Gọi API lấy thông tin
      const response = await fetch(`${API_BASE_URL}/api/info`, {
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
      console.error("Fetch error:", error);
      setStatus('error');
      // Thông báo rõ ràng hơn nếu kết nối thất bại
      setMessage('Không thể kết nối đến Server. Vui lòng thử lại sau giây lát (Server Render Free có thể đang ngủ).');
    }
  };

  const downloadTrack = async (trackUrl, trackId) => {
    setTrackStatuses(prev => ({ ...prev, [trackId]: 'loading' }));

    try {
      const response = await fetch(`${API_BASE_URL}/api/download_track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: trackUrl }),
      });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        setTrackStatuses(prev => ({ ...prev, [trackId]: 'success' }));
        const link = document.createElement('a');
        // Đảm bảo link tải về đầy đủ
        link.href = data.download_url.startsWith('http') ? data.download_url : `${API_BASE_URL}${data.download_url}`;
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

  // --- LOGIC TẢI ZIP BẤT ĐỒNG BỘ (ASYNC POLLING) ---
  const downloadZip = async () => {
    if (!result || isZipping) return;
    
    setIsZipping(true);
    setZipStatusText('Đang khởi tạo phiên làm việc...');
    setZipProgress(5);
    
    try {
      // 1. Gửi yêu cầu bắt đầu
      const startRes = await fetch(`${API_BASE_URL}/api/start_zip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url }),
      });
      
      const startData = await startRes.json();
      if (!startRes.ok) throw new Error(startData.error || 'Lỗi khởi tạo');
      
      const taskId = startData.task_id;
      
      // 2. Hỏi thăm server liên tục (Polling) mỗi 2 giây
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_BASE_URL}/api/status_zip/${taskId}`);
          const statusData = await statusRes.json();
          
          if (statusData.status === 'processing' || statusData.status === 'queued') {
             setZipStatusText(statusData.progress || 'Đang xử lý...');
             setZipProgress(statusData.percent || 10);
             
          } else if (statusData.status === 'completed') {
             clearInterval(pollInterval);
             setZipStatusText('Hoàn tất! Đang tải file về...');
             setZipProgress(100);
             
             const link = document.createElement('a');
             link.href = statusData.download_url.startsWith('http') ? statusData.download_url : `${API_BASE_URL}${statusData.download_url}`;
             link.download = '';
             document.body.appendChild(link);
             link.click();
             document.body.removeChild(link);
             
             setTimeout(() => {
                 setIsZipping(false);
                 setZipStatusText('');
             }, 3000);

          } else if (statusData.status === 'error') {
             clearInterval(pollInterval);
             setZipStatusText(`Lỗi: ${statusData.error}`);
             setIsZipping(false);
             alert(`Lỗi tải xuống: ${statusData.error}`);
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 2000);

    } catch (e) {
      setZipStatusText(`Lỗi kết nối: ${e.message}`);
      setIsZipping(false);
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
    setZipProgress(0);
    setIsTakingLong(false);
  }

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
      
      {/* Background */}
      <div className="fixed inset-0 z-0 pointer-events-none">
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
          <div className="absolute top-[-10%] left-[-10%] w-[600px] h-[600px] bg-green-500/10 rounded-full blur-[120px] animate-pulse"></div>
          <div className="absolute top-[20%] right-[-10%] w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[120px]"></div>
          <div className="absolute bottom-[-10%] left-[20%] w-[600px] h-[600px] bg-emerald-500/5 rounded-full blur-[100px]"></div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8 relative z-10 flex-1 flex flex-col">
        
        {/* Header */}
        <header className="flex flex-col items-center justify-center mb-12 pt-8">
           <div className="flex items-center gap-2 mb-4 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 backdrop-blur-md shadow-lg shadow-green-500/5 hover:border-green-500/30 transition-colors cursor-default">
             <Sparkles className="w-3.5 h-3.5 text-yellow-400" />
             <span className="text-[10px] font-bold text-gray-300 tracking-widest uppercase">Version 3.4 Stable</span>
           </div>
           
           <div className="flex items-center gap-3">
             <MusicBars />
             <h1 className="text-6xl md:text-7xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-br from-white via-gray-200 to-gray-500 drop-shadow-2xl">
               Spoti<span className="text-green-500">Down</span>
             </h1>
           </div>
           <p className="text-gray-400 mt-4 text-lg max-w-lg text-center font-light">
             Trình tải nhạc <span className="text-green-400 font-medium">High Quality</span> từ Spotify. <br/>
             Hỗ trợ tải lẻ và Album trọn bộ (SoundCloud Engine).
           </p>
        </header>

        {/* Search Box */}
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
                      placeholder="Dán link Spotify vào đây..." 
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
                      
                      {/* Thông báo Cold Start */}
                      {isTakingLong && (
                        <div className="mt-2 text-yellow-300 text-xs bg-yellow-500/10 border border-yellow-500/20 p-2 rounded-lg animate-in fade-in">
                           <i className="fa-solid fa-mug-hot mr-2"></i>
                           Server Render Free đang khởi động (Cold Start). Vui lòng đợi 30s-1ph...
                        </div>
                      )}
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
                    </div>
                 )}
               </div>
            </div>
          </div>
        )}

        {/* Result View */}
        {status === 'success' && result && (
          <div className="w-full max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-12 duration-700">
             
             <button onClick={handleReset} className="mb-6 text-gray-500 hover:text-white flex items-center gap-2 transition-colors group text-sm font-medium">
                <div className="p-1 rounded-full bg-white/5 group-hover:bg-white/10"><ChevronRight className="w-4 h-4 rotate-180" /></div>
                Quay lại tìm kiếm
             </button>

             <div className={`grid gap-8 ${result.type === 'track' ? 'grid-cols-1 max-w-2xl mx-auto' : 'lg:grid-cols-[400px_1fr]'}`}>
                
                {/* Left Column */}
                <div className="h-fit lg:sticky lg:top-8">
                  <div className="bg-[#18181b]/80 backdrop-blur-2xl border border-white/10 rounded-[32px] p-6 lg:p-8 shadow-2xl relative">
                    <div className="relative z-10 flex flex-col items-center text-center">
                        <img src={result.cover} alt="Cover" className="w-64 h-64 rounded-2xl shadow-2xl mb-6 object-cover" />
                        <h2 className="text-2xl font-bold text-white mb-2">{result.name}</h2>
                        <p className="text-lg text-gray-400 mb-6 flex items-center justify-center gap-2">
                           <Music className="w-5 h-5 text-green-500" /> {result.artist}
                        </p>

                        {result.type === 'track' ? (
                            <button 
                                onClick={() => downloadTrack(url, result.id)}
                                className="w-full bg-green-500 hover:bg-green-400 text-black font-bold py-4 rounded-xl transition-all flex items-center justify-center gap-2"
                            >
                                {trackStatuses[result.id] === 'loading' ? 'Đang tải...' : 'Tải Ngay'}
                            </button>
                        ) : (
                            <div className="w-full space-y-3">
                                <button 
                                    onClick={downloadZip}
                                    disabled={isZipping}
                                    className={`w-full py-4 rounded-xl font-bold flex items-center justify-center gap-3 transition-all ${
                                        isZipping 
                                        ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 cursor-wait' 
                                        : 'bg-green-500 hover:bg-green-400 text-black'
                                    }`}
                                >
                                    {isZipping ? <Loader2 className="w-5 h-5 animate-spin"/> : <FileArchive className="w-5 h-5"/>}
                                    {isZipping ? "Đang xử lý..." : "Tải trọn bộ (.zip)"}
                                </button>
                                
                                {isZipping && (
                                    <div className="space-y-2">
                                        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                                            <div 
                                                className="h-full bg-green-500 transition-all duration-300 ease-out" 
                                                style={{ width: `${zipProgress}%` }}
                                            ></div>
                                        </div>
                                        <p className="text-xs text-yellow-200 text-center animate-pulse font-mono">
                                            {zipStatusText}
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                  </div>
                </div>

                {/* Right Column (Tracklist) */}
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
                                    <div key={idx} className="group p-4 hover:bg-white/5 transition-colors flex items-center gap-4 relative">
                                        <span className="text-gray-600 font-mono w-6 text-center text-sm">{idx + 1}</span>
                                        <img src={track.cover || result.cover} className="w-12 h-12 rounded-lg bg-gray-800 object-cover" alt="" />
                                        
                                        <div className="flex-1 min-w-0">
                                            <h4 className="font-bold text-gray-200 truncate">{track.name}</h4>
                                            <p className="text-xs text-gray-500 truncate">{track.artist}</p>
                                        </div>

                                        <button 
                                            onClick={() => downloadTrack(track.url, track.id)}
                                            className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${!status ? 'bg-white/5 hover:bg-green-500 hover:text-black' : ''} ${status === 'loading' ? 'bg-yellow-500/20 text-yellow-500' : ''} ${status === 'success' ? 'bg-green-500/20 text-green-500' : ''}`}
                                        >
                                            {status === 'loading' && <Loader2 className="w-5 h-5 animate-spin"/>}
                                            {status === 'success' && <CheckCircle2 className="w-5 h-5"/>}
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
      
      <footer className="text-center py-6 text-gray-600 text-xs relative z-10">
        <p>© 2026 SpotiDown Pro. Educational Purposes Only.</p>
      </footer>
    </div>
  );
}
