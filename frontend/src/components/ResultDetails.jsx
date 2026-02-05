import React from 'react';
import { Music, FileArchive, Loader2, Download } from 'lucide-react';
import { cn } from '../lib/utils';
import { toast } from 'sonner';

export default function ResultDetails({
    result,
    downloadTrack,
    downloadZip,
    isZipping,
    zipProgress,
    zipStatusText,
    trackStatuses
}) {
    const isTrack = result.type === 'track';

    const handleDownloadTrack = () => {
        toast.info(`Đang bắt đầu tải: ${result.name}`);
        downloadTrack(result.url, result.id);
    };

    const handleDownloadZip = () => {
        toast.info("Đang khởi tạo quá trình nén file...");
        downloadZip();
    }

    return (
        <div className="h-fit lg:sticky lg:top-8">
            <div className="bg-surface/80 backdrop-blur-2xl border border-white/10 rounded-[32px] p-6 lg:p-8 shadow-2xl relative overflow-hidden group">
                {/* Background Blur Effect */}
                <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none group-hover:from-primary/10 transition-colors duration-500" />

                <div className="relative z-10 flex flex-col items-center text-center">
                    <div className="relative group/image">
                        <img
                            src={result.cover}
                            alt="Cover"
                            className="w-64 h-64 rounded-2xl shadow-2xl mb-6 object-cover transform group-hover/image:scale-105 transition-transform duration-500"
                        />
                        <div className="absolute inset-0 rounded-2xl ring-1 ring-inset ring-white/10 pointer-events-none" />
                    </div>

                    <h2 className="text-2xl font-bold text-white mb-2 leading-tight">{result.name}</h2>
                    <p className="text-lg text-gray-400 mb-6 flex items-center justify-center gap-2">
                        <Music className="w-5 h-5 text-primary" /> {result.artist}
                    </p>

                    {isTrack ? (
                        <button
                            onClick={handleDownloadTrack}
                            className={cn(
                                "w-full font-bold py-4 rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-primary/20",
                                "bg-primary hover:bg-primary-hover text-surface-dark active:scale-[0.98]",
                                trackStatuses[result.id] === 'loading' && "opacity-80 cursor-wait"
                            )}
                            disabled={trackStatuses[result.id] === 'loading'}
                        >
                            {trackStatuses[result.id] === 'loading' ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" /> Đang xử lý...
                                </>
                            ) : (
                                <>
                                    <Download className="w-5 h-5" /> Tải Ngay
                                </>
                            )}
                        </button>
                    ) : (
                        <div className="w-full space-y-4">
                            <button
                                onClick={handleDownloadZip}
                                disabled={isZipping}
                                className={cn(
                                    "w-full py-4 rounded-xl font-bold flex items-center justify-center gap-3 transition-all active:scale-[0.98]",
                                    isZipping
                                        ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 cursor-wait'
                                        : 'bg-primary hover:bg-primary-hover text-surface-dark shadow-lg shadow-primary/20'
                                )}
                            >
                                {isZipping ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileArchive className="w-5 h-5" />}
                                {isZipping ? "Đang xử lý..." : "Tải trọn bộ (.zip)"}
                            </button>

                            {isZipping && (
                                <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                                    <div className="h-2 bg-surface-light rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-primary transition-all duration-300 ease-out"
                                            style={{ width: `${zipProgress}%` }}
                                        ></div>
                                    </div>
                                    <p className="text-xs text-yellow-200 text-center animate-pulse font-mono flex items-center justify-center gap-2">
                                        <Loader2 className="w-3 h-3 animate-spin" /> {zipStatusText}
                                    </p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
