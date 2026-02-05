import React from 'react';
import { Sparkles } from 'lucide-react';

const MusicBars = () => (
    <div className="flex items-end gap-1 h-8 mb-2">
        <div className="w-1.5 bg-primary rounded-t-full animate-[bounce_1s_infinite] h-[60%]"></div>
        <div className="w-1.5 bg-primary-hover rounded-t-full animate-[bounce_1.2s_infinite] h-[80%]"></div>
        <div className="w-1.5 bg-green-300 rounded-t-full animate-[bounce_0.8s_infinite] h-[40%]"></div>
        <div className="w-1.5 bg-emerald-400 rounded-t-full animate-[bounce_1.5s_infinite] h-[100%]"></div>
        <div className="w-1.5 bg-emerald-500 rounded-t-full animate-[bounce_1.1s_infinite] h-[50%]"></div>
    </div>
);

export default function Header() {
    return (
        <header className="flex flex-col items-center justify-center mb-12 pt-8">
            {/* Version Badge */}
            <div className="flex items-center gap-2 mb-6 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 backdrop-blur-md shadow-lg shadow-primary/5 hover:border-primary/30 transition-colors cursor-default select-none">
                <Sparkles className="w-3.5 h-3.5 text-yellow-400" />
                <span className="text-[10px] font-bold text-gray-300 tracking-widest uppercase">Version 3.5 Stable</span>
            </div>

            {/* Todo: Add animation here later */}
            <div className="flex items-center gap-3">
                <MusicBars />
                <h1 className="text-6xl md:text-7xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-br from-white via-gray-200 to-gray-500 drop-shadow-2xl select-none">
                    Spoti<span className="text-primary">Down</span>
                </h1>
            </div>
            <p className="text-gray-400 mt-4 text-lg max-w-lg text-center font-light leading-relaxed">
                Trình tải nhạc <span className="text-primary-hover font-medium">High Quality</span> từ Spotify. <br />
                Hỗ trợ tải lẻ và Album trọn bộ.
            </p>
        </header>
    );
}
