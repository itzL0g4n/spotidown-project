import React from 'react';
import { Search, Loader2, ChevronRight, CheckCircle2, AlertCircle } from 'lucide-react';
import { cn } from '../lib/utils';

export default function SearchBar({
    url,
    setUrl,
    handleFetchInfo,
    status,
    progress,
    message,
    isTakingLong
}) {
    const isProcessing = status === 'processing';

    return (
        <div className="w-full flex flex-col items-center justify-start pt-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="w-full max-w-2xl transform transition-all hover:scale-[1.01] duration-300">
                {/* Input Wrapper */}
                <div className={cn(
                    "relative group rounded-3xl p-[1px] transition-all duration-500 shadow-2xl shadow-black/50",
                    "bg-gradient-to-r from-surface-light via-surface-light to-surface-light",
                    "hover:from-primary hover:via-primary-hover hover:to-emerald-500",
                    isProcessing && "from-primary/50 via-primary/50 to-primary/50 cursor-wait"
                )}>
                    <div className="relative flex items-center bg-surface rounded-[23px] h-16 md:h-20 px-2 overflow-hidden">
                        <div className="pl-6 text-gray-400 group-focus-within:text-primary transition-colors">
                            <Search className="w-6 h-6 md:w-8 md:h-8" />
                        </div>
                        <input
                            type="text"
                            placeholder="Dán link Spotify vào đây..."
                            className="w-full h-full bg-transparent border-none text-white px-4 md:px-6 text-lg md:text-xl outline-none placeholder:text-gray-600 font-medium"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            disabled={isProcessing}
                            onKeyDown={(e) => e.key === 'Enter' && handleFetchInfo()}
                            autoFocus
                        />
                        <button
                            onClick={handleFetchInfo}
                            disabled={!url || isProcessing}
                            className={cn(
                                "m-2 h-12 w-12 md:h-14 md:w-14 rounded-2xl flex items-center justify-center transition-all shadow-lg shadow-white/5",
                                "bg-white text-black hover:bg-primary hover:text-white disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white disabled:hover:text-black",
                                "active:scale-95"
                            )}
                        >
                            {isProcessing ? <Loader2 className="w-6 h-6 animate-spin" /> : <ChevronRight className="w-7 h-7" />}
                        </button>
                    </div>
                </div>

                {/* Hint / Status */}
                <div className="mt-8 text-center min-h-[60px]">
                    {status === 'processing' ? (
                        <div className="space-y-3 w-2/3 mx-auto">
                            <div className="h-1 bg-surface-light rounded-full overflow-hidden">
                                <div className="h-full bg-primary animate-[loading_1s_ease-in-out_infinite]" style={{ width: `${progress}%` }}></div>
                            </div>
                            <p className="text-primary font-mono text-sm animate-pulse">CONNECTING TO SERVER...</p>

                            {isTakingLong && (
                                <div className="mt-2 text-yellow-300 text-xs bg-yellow-500/10 border border-yellow-500/20 p-2 rounded-lg animate-in fade-in">
                                    Server đang khởi động (Cold Start). Vui lòng đợi...
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
                            <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-primary" /> No Login Required</span>
                            <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-primary" /> 320kbps MP3</span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
