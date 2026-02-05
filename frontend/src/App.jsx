import React, { useState, useEffect } from 'react';
import { Toaster, toast } from 'sonner';
import { History } from 'lucide-react';
import Header from './components/Header';
import Footer from './components/Footer';
import SearchBar from './components/SearchBar';
import ResultDetails from './components/ResultDetails';
import TrackList from './components/TrackList';
import DownloadHistory from './components/DownloadHistory';

// --- CONFIG ---
const API_BASE_URL = 'http://217.154.161.167:12065';

export default function App() {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState('idle'); // idle, processing, success, error
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState('');

  // Zipping State
  const [isZipping, setIsZipping] = useState(false);
  const [zipStatusText, setZipStatusText] = useState('');
  const [zipProgress, setZipProgress] = useState(0);
  const [trackStatuses, setTrackStatuses] = useState({});

  // UX State
  const [isTakingLong, setIsTakingLong] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  // Simulated Progress Bar
  useEffect(() => {
    let interval;
    let timeout;

    if (status === 'processing') {
      setProgress(10);
      setIsTakingLong(false);

      interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) return 90;
          return prev + (prev < 50 ? 5 : 1);
        });
      }, 300);

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

  const addToHistory = (item) => {
    const historyItem = {
      id: item.id || Date.now(),
      name: item.name,
      artist: item.artist,
      cover: item.cover,
      url: item.url, // Original Spotify Link
      timestamp: Date.now()
    };

    const currentHistory = JSON.parse(localStorage.getItem('spotidown_history') || '[]');
    // Avoid duplicates at top
    const newHistory = [historyItem, ...currentHistory.filter(h => h.id !== historyItem.id)].slice(0, 50);
    localStorage.setItem('spotidown_history', JSON.stringify(newHistory));
  };

  const handleFetchInfo = async () => {
    if (!url.includes('spotify.com')) {
      setStatus('error');
      setMessage('Link không hợp lệ! Hãy dán link Spotify.');
      toast.error('Link không hợp lệ! Hãy dán link Spotify.');
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
      const response = await fetch(`${API_BASE_URL}/api/info`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url }),
      });

      const data = await response.json();

      if (response.ok) {
        setStatus('success');
        setResult(data);
        toast.success(`Đã tìm thấy: ${data.name}`);
      } else {
        setStatus('error');
        setMessage(data.error || 'Lỗi từ Server.');
        toast.error(data.error || 'Lỗi từ Server.');
      }
    } catch (error) {
      console.error("Fetch error:", error);
      setStatus('error');
      setMessage(`Lỗi kết nối: ${error.message}`);
      toast.error(`Lỗi: ${error.message}`);
      toast.error('Không thể kết nối đến Server. Vui lòng thử lại.');
    }
  };

  const downloadTrack = async (trackUrl, trackId) => {
    setTrackStatuses(prev => ({ ...prev, [trackId]: 'loading' }));

    // Helper to find track info for history
    let trackInfo = result;
    if (result.type !== 'track') {
      trackInfo = result.tracks.find(t => t.id === trackId);
    }

    // Add to History immediately (optimistic)
    if (trackInfo) {
      addToHistory({ ...trackInfo, url: trackUrl }); // Use specific track url
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/download_track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: trackUrl }),
      });

      const data = await response.json();

      if (response.ok && data.status === 'success') {
        setTrackStatuses(prev => ({ ...prev, [trackId]: 'success' }));
        toast.success(`Tải thành công: ${trackInfo?.name || 'Bài hát'}`);

        const link = document.createElement('a');
        link.href = data.download_url.startsWith('http') ? data.download_url : `${API_BASE_URL}${data.download_url}`;
        link.download = '';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        setTrackStatuses(prev => ({ ...prev, [trackId]: 'error' }));
        toast.error(`Lỗi tải: ${trackInfo?.name || 'Bài hát'}`);
      }
    } catch (e) {
      setTrackStatuses(prev => ({ ...prev, [trackId]: 'error' }));
      toast.error(`Lỗi: ${e.message}`);
    }
  };

  const downloadZip = async () => {
    if (!result || isZipping) return;

    setIsZipping(true);
    setZipStatusText('Đang khởi tạo phiên làm việc...');
    setZipProgress(5);

    addToHistory({ ...result, url: url }); // Save Album/Playlist to history

    try {
      const startRes = await fetch(`${API_BASE_URL}/api/start_zip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url }),
      });

      const startData = await startRes.json();
      if (!startRes.ok) throw new Error(startData.error || 'Lỗi khởi tạo');

      const taskId = startData.task_id;

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
            toast.success('Nén file hoàn tất! Đang tải xuống...');

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
            toast.error(`Lỗi nén file: ${statusData.error}`);
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 2000);

    } catch (e) {
      setZipStatusText(`Lỗi kết nối: ${e.message}`);
      setIsZipping(false);
      toast.error(`Không thể bắt đầu nén file.`);
    }
  };

  const handleReset = () => {
    setStatus('idle');
    setUrl('');
    setProgress(0);
    setResult(null);
    setTrackStatuses({});
    setIsZipping(false);
  }

  return (
    <div className="min-h-screen bg-surface-dark relative flex flex-col overflow-x-hidden">

      {/* Background Decor */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
        <div className="absolute top-[-10%] left-[-10%] w-[600px] h-[600px] bg-primary/10 rounded-full blur-[120px] animate-pulse"></div>
        <div className="absolute top-[20%] right-[-10%] w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[120px]"></div>
      </div>

      <div className="container mx-auto px-4 py-8 relative z-10 flex-1 flex flex-col">

        {/* Top Bar Actions */}
        <div className="absolute top-4 right-4 z-50">
          <button
            onClick={() => setShowHistory(true)}
            className="p-3 bg-surface-light/50 backdrop-blur-md border border-white/10 rounded-full hover:bg-white/10 hover:border-primary/50 transition-all text-gray-400 hover:text-primary shadow-lg"
            title="Lịch sử tải về"
          >
            <History className="w-5 h-5" />
          </button>
        </div>

        <DownloadHistory isOpen={showHistory} onClose={() => setShowHistory(false)} />
        <Toaster theme="dark" position="top-center" richColors />

        <Header />

        {(!result || status === 'processing') && (
          <SearchBar
            url={url}
            setUrl={setUrl}
            handleFetchInfo={handleFetchInfo}
            status={status}
            progress={progress}
            message={message}
            isTakingLong={isTakingLong}
          />
        )}

        {status === 'success' && result && (
          <div className="w-full max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-12 duration-700">
            <div className="flex justify-between items-center mb-6">
              <button onClick={handleReset} className="text-gray-500 hover:text-white flex items-center gap-2 transition-colors group text-sm font-medium px-4 py-2 hover:bg-white/5 rounded-full">
                <div className="p-1 rounded-full bg-white/5 group-hover:bg-white/10 border border-white/5">
                  <svg className="w-4 h-4 rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
                Quay lại tìm kiếm
              </button>
            </div>

            <div className={`grid gap-8 ${result.type === 'track' ? 'grid-cols-1 max-w-2xl mx-auto' : 'lg:grid-cols-[400px_1fr]'}`}>

              <ResultDetails
                result={result}
                downloadTrack={downloadTrack}
                downloadZip={downloadZip}
                isZipping={isZipping}
                zipProgress={zipProgress}
                zipStatusText={zipStatusText}
                trackStatuses={trackStatuses}
              />

              {result.tracks && (
                <TrackList
                  tracks={result.tracks}
                  trackStatuses={trackStatuses}
                  downloadTrack={downloadTrack}
                  cover={result.cover}
                />
              )}
            </div>
          </div>
        )}
      </div>

      <Footer />
    </div>
  );
}
