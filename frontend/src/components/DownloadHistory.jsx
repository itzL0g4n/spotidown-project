import React, { useState, useEffect } from 'react';
import { History, X, Music2, ExternalLink, Trash2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

export default function DownloadHistory({ isOpen, onClose }) {
    const [history, setHistory] = useState([]);

    useEffect(() => {
        if (isOpen) {
            const saved = JSON.parse(localStorage.getItem('spotidown_history') || '[]');
            setHistory(saved);
        }
    }, [isOpen]);

    const clearHistory = () => {
        localStorage.removeItem('spotidown_history');
        setHistory([]);
    }

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
                    />

                    {/* Panel */}
                    <motion.div
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        transition={{ type: "spring", damping: 20 }}
                        className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-surface border-l border-white/10 z-50 shadow-2xl flex flex-col"
                    >
                        <div className="p-6 border-b border-white/10 flex items-center justify-between bg-surface-light/50">
                            <h2 className="text-xl font-bold flex items-center gap-2">
                                <History className="w-5 h-5 text-primary" /> Lịch sử tải về
                            </h2>
                            <div className="flex items-center gap-2">
                                {history.length > 0 && (
                                    <button
                                        onClick={clearHistory}
                                        className="p-2 hover:bg-red-500/10 hover:text-red-500 rounded-lg transition-colors text-gray-500"
                                        title="Xóa lịch sử"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                )}
                                <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                                    <X className="w-5 h-5" />
                                </button>
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto p-4 space-y-3">
                            {history.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-4">
                                    <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                                        <History className="w-8 h-8 opacity-20" />
                                    </div>
                                    <p>Chưa có lịch sử tải xuống gần đây.</p>
                                </div>
                            ) : (
                                history.map((item, idx) => (
                                    <div key={idx} className="bg-white/5 p-4 rounded-xl border border-white/5 flex items-center gap-4 hover:border-primary/30 transition-colors group">
                                        <div className="w-12 h-12 bg-surface-dark rounded-lg flex items-center justify-center">
                                            {item.cover ? (
                                                <img src={item.cover} className="w-full h-full object-cover rounded-lg" alt="" />
                                            ) : (
                                                <Music2 className="w-6 h-6 text-gray-600" />
                                            )}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <h4 className="font-medium text-white truncate">{item.name}</h4>
                                            <p className="text-xs text-gray-500 truncate">{item.artist}</p>
                                            <p className="text-[10px] text-gray-600 mt-1">{new Date(item.timestamp).toLocaleString()}</p>
                                        </div>
                                        <a href={item.url} target="_blank" rel="noreferrer" className="p-2 bg-white/5 rounded-full hover:bg-primary hover:text-black transition-colors opacity-0 group-hover:opacity-100">
                                            <ExternalLink className="w-4 h-4" />
                                        </a>
                                    </div>
                                ))
                            )}
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
