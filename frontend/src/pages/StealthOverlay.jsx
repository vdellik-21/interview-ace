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
    const [answerHistory, setAnswerHistory] = useState([]);
    const [answerSource, setAnswerSource] = useState('');
    const [isStreaming, setIsStreaming] = useState(false);
    const [fontSize, setFontSize] = useState(14);
    const [isResizing, setIsResizing] = useState(false);
    const wsRef = useRef(null);
    const resizeSessionRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const shouldReconnectRef = useRef(true);
    const isEndingSessionRef = useRef(false);
    const currentAnswerRef = useRef('');
    const detectedQuestionRef = useRef('');
    const answerSourceRef = useRef('');

    const sendAction = useCallback((type, payload = {}) => {
        if (type === 'force_answer') {
            setStatus('⚡ Forcing answer now...');
        } else if (type === 'regenerate') {
            setStatus('🔄 Regenerating answer...');
        }

        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type, ...payload }));
        }
    }, []);

    const hideOverlay = useCallback(() => {
        if (window.electronAPI?.hideOverlay) {
            window.electronAPI.hideOverlay();
        }
    }, []);

    useEffect(() => {
        currentAnswerRef.current = currentAnswer;
        detectedQuestionRef.current = detectedQuestion;
        answerSourceRef.current = answerSource;
    }, [answerSource, currentAnswer, detectedQuestion]);

    const handleEndSession = useCallback(() => {
        shouldReconnectRef.current = false;
        isEndingSessionRef.current = true;
        setIsStreaming(false);
        setStatus('🔴 Ending session...');

        if (reconnectTimerRef.current) {
            window.clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }

        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'stop_session' }));
            return;
        }

        if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
            wsRef.current.close();
        }

        hideOverlay();
    }, [hideOverlay]);

    const archiveCurrentAnswer = useCallback((nextQuestion = '') => {
        setAnswerHistory((prev) => {
            const lastAnswer = currentAnswerRef.current.trim();
            const lastQuestion = detectedQuestionRef.current.trim();
            const lastSource = answerSourceRef.current;
            const nextQuestionText = nextQuestion.trim();

            if (!lastAnswer || !lastQuestion || lastSource === 'error') {
                return prev;
            }
            if (lastQuestion === nextQuestionText) {
                return prev;
            }
            if (prev.some((item) => item.question === lastQuestion && item.answer === lastAnswer)) {
                return prev;
            }

            return [
                {
                    question: lastQuestion,
                    answer: lastAnswer,
                    source: lastSource,
                },
                ...prev,
            ].slice(0, 3);
        });
    }, []);

    const buildManualQuestionText = useCallback(() => {
        const recentInterviewerEntries = [];

        for (let index = transcript.length - 1; index >= 0; index -= 1) {
            const entry = transcript[index];
            if (entry.speaker !== 'interviewer') {
                if (recentInterviewerEntries.length > 0) {
                    break;
                }
                continue;
            }

            const text = entry.text?.trim();
            if (!text) {
                continue;
            }

            recentInterviewerEntries.push(text);
            if (recentInterviewerEntries.length >= 3) {
                break;
            }
        }

        const manualText = recentInterviewerEntries.reverse().join(' ').trim();
        return manualText || detectedQuestion.trim();
    }, [detectedQuestion, transcript]);

    const requestManualAnswer = useCallback(() => {
        const manualQuestionText = buildManualQuestionText();
        if (!manualQuestionText) {
            setStatus('⚪ No interviewer question heard yet.');
            return;
        }

        archiveCurrentAnswer(manualQuestionText);
        setDetectedQuestion(manualQuestionText);
        setCurrentAnswer('');
        setAnswerSource('');
        setIsStreaming(true);
        setStatus('⚡ Generating answer from latest interviewer transcript...');
        sendAction('force_answer', { question_text: manualQuestionText });
    }, [archiveCurrentAnswer, buildManualQuestionText, sendAction]);

    // ─── Handle WebSocket Messages ──────────────
    const handleMessage = useCallback((data) => {
        switch (data.type) {
            case 'status':
                setStatus(data.text);
                if (isEndingSessionRef.current && data.text?.includes('Session ended')) {
                    setIsStreaming(false);
                    hideOverlay();
                }
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
                archiveCurrentAnswer(data.text || '');
                setDetectedQuestion(data.text);
                setCurrentAnswer('');
                setAnswerSource('');
                setIsStreaming(true);
                break;

            case 'answer_replace':
                setCurrentAnswer(data.text || '');
                setAnswerSource(data.source || '');
                break;

            case 'answer_token':
                setAnswerSource(data.source || answerSourceRef.current || '');
                setCurrentAnswer((prev) => prev + data.token);
                break;

            case 'answer_complete':
                setIsStreaming(false);
                break;

            case 'error':
                setStatus(`⚠️ ${data.message}`);
                setIsStreaming(false);
                if (data.message) {
                    setCurrentAnswer(data.message);
                    setAnswerSource('error');
                }
                break;
        }
    }, [archiveCurrentAnswer, hideOverlay]);

    // ─── WebSocket Connection ───────────────────
    useEffect(() => {
        // Get session ID from URL params or localStorage
        const params = new URLSearchParams(window.location.search);
        const sessionId = params.get('session');

        if (!sessionId) {
            setStatus('⚪ Waiting for session');
            return undefined;
        }

        shouldReconnectRef.current = true;
        isEndingSessionRef.current = false;

        const connect = () => {
            const ws = new WebSocket(`ws://localhost:8000/api/copilot/${sessionId}`);
            wsRef.current = ws;

            ws.onopen = () => {
                if (!shouldReconnectRef.current || isEndingSessionRef.current) {
                    ws.close();
                    return;
                }
                setStatus('🟢 Connected');
                ws.send(JSON.stringify({ type: 'start_session', session_id: sessionId }));
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };

            ws.onclose = () => {
                wsRef.current = null;

                if (isEndingSessionRef.current) {
                    setIsStreaming(false);
                    setStatus('🔴 Session ended');
                    hideOverlay();
                    return;
                }

                setStatus('🔴 Disconnected');
                if (!shouldReconnectRef.current) {
                    return;
                }

                reconnectTimerRef.current = window.setTimeout(connect, 2000);
            };

            ws.onerror = () => {
                setStatus('⚠️ Connection error');
            };
        };

        connect();

        return () => {
            shouldReconnectRef.current = false;
            isEndingSessionRef.current = false;
            if (reconnectTimerRef.current) {
                window.clearTimeout(reconnectTimerRef.current);
                reconnectTimerRef.current = null;
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [handleMessage, hideOverlay]);

    // ─── Electron IPC Listeners ─────────────────
    useEffect(() => {
        if (window.electronAPI) {
            // Keyboard shortcut actions
            window.electronAPI.onAction((action) => {
                if (action === 'force_answer') {
                    requestManualAnswer();
                    return;
                }

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
    }, [requestManualAnswer, sendAction]);

    // ─── Overlay Keyboard Shortcuts ─────────────
    useEffect(() => {
        const handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                event.preventDefault();
                hideOverlay();
                return;
            }

            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'w') {
                event.preventDefault();
                hideOverlay();
                return;
            }

            if (event.metaKey || event.ctrlKey || event.altKey) {
                return;
            }

            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                requestManualAnswer();
            }

            if (event.key.toLowerCase() === 'r') {
                event.preventDefault();
                sendAction('regenerate');
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [hideOverlay, requestManualAnswer, sendAction]);

    const startResize = useCallback(async (event) => {
        if (!window.electronAPI?.getOverlayBounds || !window.electronAPI?.setOverlayBounds) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        const initialBounds = await window.electronAPI.getOverlayBounds();
        if (!initialBounds) {
            return;
        }

        resizeSessionRef.current = {
            startX: event.screenX,
            startY: event.screenY,
            bounds: initialBounds,
        };
        setIsResizing(true);
    }, []);

    useEffect(() => {
        if (!isResizing) {
            return undefined;
        }

        const handleMouseMove = (event) => {
            const session = resizeSessionRef.current;
            if (!session || !window.electronAPI?.setOverlayBounds) {
                return;
            }

            const nextWidth = session.bounds.width + (event.screenX - session.startX);
            const nextHeight = session.bounds.height + (event.screenY - session.startY);

            window.electronAPI.setOverlayBounds({
                width: nextWidth,
                height: nextHeight,
            });
        };

        const handleMouseUp = () => {
            resizeSessionRef.current = null;
            setIsResizing(false);
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isResizing]);

    const showEmptyState = transcript.length === 0 && !detectedQuestion && !currentAnswer;

    return (
        <div
            className="h-screen flex flex-col select-none overflow-hidden rounded-xl"
            style={{
                fontSize: `${fontSize}px`,
                background: 'linear-gradient(180deg, rgba(2, 6, 23, 0.44), rgba(2, 6, 23, 0.30))',
                backdropFilter: 'blur(6px)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif',
            }}
        >
            {/* ─── Header ──────────────────────── */}
            <div
                className="flex items-center justify-between px-4 py-2 shrink-0 border-b border-white/10"
                style={{ WebkitAppRegion: 'drag' }}
            >
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
                <div
                    className="flex items-center gap-2"
                    style={{ WebkitAppRegion: 'no-drag' }}
                >
                    <span className="text-[10px] text-gray-600">
                        drag header to move • drag corner to resize • esc hides
                    </span>
                    <button
                        type="button"
                        onClick={hideOverlay}
                        className="text-[11px] bg-white/8 hover:bg-white/15 text-gray-300 px-2 py-1 rounded-md transition"
                    >
                        Hide
                    </button>
                </div>
            </div>

            {/* ─── Live Transcript ─────────────── */}
            <TranscriptFeed entries={transcript} />

            {showEmptyState && (
                <div className="mx-3 mt-2 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-4">
                    <div className="text-[11px] uppercase tracking-[0.24em] text-gray-500 mb-2">
                        Live Status
                    </div>
                    <div className="text-[15px] text-white font-medium mb-1">
                        {status}
                    </div>
                    <div className="text-[12px] text-gray-400 leading-relaxed">
                        Waiting for interviewer system audio. Once interviewer speech is detected,
                        transcript and answer suggestions will appear here.
                    </div>
                </div>
            )}

            {/* ─── Detected Question ──────────── */}
            {detectedQuestion && (
                <div className="mx-3 mt-2 p-3 bg-blue-500/10 border border-blue-500/25 rounded-lg shrink-0">
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
                previousAnswers={answerHistory}
                answerSource={answerSource}
                isStreaming={isStreaming}
            />

            {/* ─── Action Buttons ────────────── */}
            <div className="flex gap-2 px-3 py-2 shrink-0 border-t border-white/10">
                <button
                    onClick={requestManualAnswer}
                    className="text-[11px] bg-blue-900/40 hover:bg-blue-900/60 text-blue-200
                               px-3 py-1.5 rounded-md transition"
                >
                    ⚡ Generate Now
                </button>
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
                    onClick={handleEndSession}
                    className="text-[11px] bg-red-900/40 hover:bg-red-900/60 text-red-300
                               px-3 py-1.5 rounded-md transition"
                >
                    ⏹ End
                </button>
                <button
                    onClick={hideOverlay}
                    className="text-[11px] bg-white/8 hover:bg-white/15 text-gray-300
                               px-3 py-1.5 rounded-md transition"
                >
                    ✕ Hide
                </button>
            </div>

            <div
                role="presentation"
                aria-label="Resize overlay"
                onMouseDown={startResize}
                className="absolute bottom-0 right-0 h-5 w-5 cursor-se-resize rounded-tl-md bg-white/10 hover:bg-white/20"
                style={{ WebkitAppRegion: 'no-drag' }}
            >
                <div className="pointer-events-none absolute bottom-1 right-1 text-[10px] leading-none text-white/60">
                    ◢
                </div>
            </div>
        </div>
    );
}
