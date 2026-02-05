import React from 'react';
import { List, Loader2, CheckCircle2, Download } from 'lucide-react';
import { cn } from '../lib/utils';
import { toast } from 'sonner';

export default function TrackList({ tracks, trackStatuses, downloadTrack, cover }) {

    const handleDownload = (track) => {
        if (trackStatuses[track.id] === 'loading') return;
        toast.success(`Đã thêm vào hàng đợi: ${track.name}`);
        downloadTrack(track.url, track.id);
    }

    return (
        <div className="bg-surface/50 backdrop-blur-xl border border-white/5 rounded-[32px] overflow-hidden flex flex-col shadow-2xl h-fit min-h-[500px] animate-in fade-in slide-in-from-bottom-8 duration-700 delay-100">
            <div className="p-6 border-b border-white/5 bg-white/5 flex items-center justify-between sticky top-0 z-20 backdrop-blur-md">
                <h3 className="font-bold text-lg flex items-center gap-2 text-white">
                    <List className="w-5 h-5 text-primary" /> Danh sách phát
                </h3>
                <span className="text-xs font-mono text-gray-400 bg-black/20 px-2 py-1 rounded border border-white/5">
                    {tracks.length} items
                </span>
            </div>

            <div className="divide-y divide-white/5">
                {tracks.map((track, idx) => {
                    const status = trackStatuses[track.id];
                    return (
                        <div key={idx} className="group p-4 hover:bg-white/5 transition-colors flex items-center gap-4 relative">
                            <span className="text-gray-600 font-mono w-6 text-center text-sm">{idx + 1}</span>
                            <img
                                src={track.cover || cover}
                                className="w-12 h-12 rounded-lg bg-surface-light object-cover shadow-md group-hover:scale-110 transition-transform"
                                alt=""
                            />

                            <div className="flex-1 min-w-0">
                                <h4 className={cn(
                                    "font-bold truncate transition-colors",
                                    status === 'success' ? "text-primary" : "text-gray-200"
                                )}>{track.name}</h4>
                                <p className="text-xs text-gray-500 truncate">{track.artist}</p>
                            </div>

                            <button
                                onClick={() => handleDownload(track)}
                                className={cn(
                                    "w-10 h-10 rounded-full flex items-center justify-center transition-all",
                                    !status && "bg-white/5 hover:bg-primary hover:text-black hover:scale-110 active:scale-90",
                                    status === 'loading' && "bg-yellow-500/10 text-yellow-500",
                                    status === 'success' && "bg-primary/10 text-primary cursor-default"
                                )}
                                disabled={status === 'loading' || status === 'success'}
                                title={status === 'success' ? 'Đã tải xong' : 'Tải bài này'}
                            >
                                {status === 'loading' && <Loader2 className="w-5 h-5 animate-spin" />}
                                {status === 'success' && <CheckCircle2 className="w-5 h-5" />}
                                {!status && <Download className="w-5 h-5" />}
                            </button>
                        </div>
                    )
                })}
            </div>
        </div>
    );
}
