/**
 * InterviewAce — Stealth Overlay
 * The live interview panel rendered inside the Electron stealth window.
 * Shows real-time transcript, detected questions, and streaming AI answers.
 *
 * Owner: Dev 3
 * Status: STUB — UI implemented, WebSocket integration needed
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import TranscriptFeed from '../components/TranscriptFeed';
import AnswerPanel from '../components/AnswerPanel';

export default function StealthOverlay() {
    const [status, setStatus] = useState('connecting');
    const [transcript, setTranscript] = useState([]);
    const [detectedQuestion, setDetectedQuestion] = useState('');
    const [currentAnswer, setCurrentAnswer] = useState('');
    const [isStreaming, setIsStreaming] = useState(false);
    const [fontSize, setFontSize] = useState(14);
    const wsRef = useRef(null);

    // ─── WebSocket Connection ───────────────────
    useEffect(() => {
        // Get session ID from URL params or localStorage
        const params = new URLSearchParams(window.location.search);
        const sessionId = params.get('session') || 'default';

        const connect = () => {
            const ws = new WebSocket(`ws://localhost:8000/api/copilot/${sessionId}`);
            wsRef.current = ws;

            ws.onopen = () => {
                setStatus('🟢 Connected');
                ws.send(JSON.stringify({ type: 'start_session', session_id: sessionId }));
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };

            ws.onclose = () => {
                setStatus('🔴 Disconnected');
                // Auto-reconnect after 2 seconds
                setTimeout(connect, 2000);
            };

            ws.onerror = () => {
                setStatus('⚠️ Connection error');
            };
        };

        connect();

        return () => {
            if (wsRef.current) wsRef.current.close();
        };
    }, []);

    // ─── Handle WebSocket Messages ──────────────
    const handleMessage = useCallback((data) => {
        switch (data.type) {
            case 'status':
                setStatus(data.text);
                break;

            case 'transcript':
                setTranscript((prev) => [
                    ...prev.slice(-30), // Keep last 30 entries
                    {
                        speaker: data.speaker,
                        text: data.text,
                        timestamp: data.timestamp || new Date().toLocaleTimeString(),
                    },
                ]);
                break;

            case 'question_detected':
                setDetectedQuestion(data.text);
                setCurrentAnswer('');
                setIsStreaming(true);
                break;

            case 'answer_token':
                setCurrentAnswer((prev) => prev + data.token);
                break;

            case 'answer_complete':
                setIsStreaming(false);
                break;

            case 'error':
                setStatus(`⚠️ ${data.message}`);
                break;
        }
    }, []);

    // ─── Electron IPC Listeners ─────────────────
    useEffect(() => {
        if (window.electronAPI) {
            // Keyboard shortcut actions
            window.electronAPI.onAction((action) => {
                sendAction(action);
            });

            // Font size changes
            window.electronAPI.onFontSize((direction) => {
                setFontSize((prev) =>
                    direction === 'increase'
                        ? Math.min(prev + 2, 24)
                        : Math.max(prev - 2, 10)
                );
            });
        }
    }, []);

    // ─── Send Action to Backend ─────────────────
    const sendAction = (type) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type }));
        }
    };

    return (
        <div
            className="h-screen flex flex-col select-none overflow-hidden rounded-xl"
            style={{
                fontSize: `${fontSize}px`,
                background: 'rgba(0, 0, 0, 0.88)',
                backdropFilter: 'blur(12px)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif',
            }}
        >
            {/* ─── Header ──────────────────────── */}
            <div className="flex items-center justify-between px-4 py-2 shrink-0 border-b border-white/10">
                <div className="flex items-center gap-2">
                    <div
                        className={`w-2 h-2 rounded-full ${
                            status.includes('🟢')
                                ? 'bg-red-500 animate-pulse'
                                : status.includes('🔴')
                                ? 'bg-gray-500'
                                : 'bg-yellow-500'
                        }`}
                    />
                    <span className="text-[10px] text-gray-400">{status}</span>
                </div>
                <span className="text-[10px] text-gray-600">
                    ⌘⇧P panic • ⌘⇧H toggle
                </span>
            </div>

            {/* ─── Live Transcript ─────────────── */}
            <TranscriptFeed entries={transcript} />

            {/* ─── Detected Question ──────────── */}
            {detectedQuestion && (
                <div className="mx-3 mt-2 p-3 bg-blue-500/15 border border-blue-500/30 rounded-lg shrink-0">
                    <div className="text-[10px] uppercase tracking-wider text-blue-400 mb-1">
                        ❓ Question Detected
                    </div>
                    <div className="text-[13px] text-blue-100 leading-relaxed">
                        {detectedQuestion}
                    </div>
                </div>
            )}

            {/* ─── AI Answer ─────────────────── */}
            <AnswerPanel
                answer={currentAnswer}
                isStreaming={isStreaming}
            />

            {/* ─── Action Buttons ────────────── */}
            <div className="flex gap-2 px-3 py-2 shrink-0 border-t border-white/10">
                <button
                    onClick={() => sendAction('regenerate')}
                    className="text-[11px] bg-white/8 hover:bg-white/15 text-gray-300
                               px-3 py-1.5 rounded-md transition"
                >
                    🔄 Regen
                </button>
                <button
                    onClick={() => sendAction('shorter')}
                    className="text-[11px] bg-white/8 hover:bg-white/15 text-gray-300
                               px-3 py-1.5 rounded-md transition"
                >
                    ✂️ Shorter
                </button>
                <button
                    onClick={() => sendAction('more_detail')}
                    className="text-[11px] bg-white/8 hover:bg-white/15 text-gray-300
                               px-3 py-1.5 rounded-md transition"
                >
                    📝 Detail
                </button>
                <div className="flex-1" />
                <button
                    onClick={() => sendAction('stop_session')}
                    className="text-[11px] bg-red-900/40 hover:bg-red-900/60 text-red-300
                               px-3 py-1.5 rounded-md transition"
                >
                    ⏹ End
                </button>
            </div>
        </div>
    );
}
