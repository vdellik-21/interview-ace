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
    const [clickThrough, setClickThrough] = useState(false);
    const [status, setStatus] = useState('connecting');
    const [transcript, setTranscript] = useState([]);
    const [detectedQuestion, setDetectedQuestion] = useState('');
    const [currentAnswer, setCurrentAnswer] = useState('');
    const [answerHistory, setAnswerHistory] = useState([]);
    const [answerSource, setAnswerSource] = useState('');
    const [isStreaming, setIsStreaming] = useState(false);
    const [autoFollowAnswers, setAutoFollowAnswers] = useState(true);
    const [fontSize, setFontSize] = useState(14);
    const [isResizing, setIsResizing] = useState(false);
    const answerPanelRef = useRef(null);
    const wsRef = useRef(null);
    const dragSessionRef = useRef(null);
    const resizeSessionRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const shouldReconnectRef = useRef(true);
    const isEndingSessionRef = useRef(false);
    const hasFinalizedEndRef = useRef(false);
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

    const finalizeEndedSession = useCallback(() => {
        if (hasFinalizedEndRef.current) {
            return;
        }

        hasFinalizedEndRef.current = true;

        if (window.electronAPI?.endSession) {
            window.electronAPI.endSession();
            return;
        }

        hideOverlay();
    }, [hideOverlay]);

    useEffect(() => {
        currentAnswerRef.current = currentAnswer;
        detectedQuestionRef.current = detectedQuestion;
        answerSourceRef.current = answerSource;
    }, [answerSource, currentAnswer, detectedQuestion]);

    const handleEndSession = useCallback(() => {
        shouldReconnectRef.current = false;
        isEndingSessionRef.current = true;
        hasFinalizedEndRef.current = false;
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

        finalizeEndedSession();
    }, [finalizeEndedSession]);

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
                ...prev,
                {
                    question: lastQuestion,
                    answer: lastAnswer,
                    source: lastSource,
                },
            ].slice(-3);
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

    const handleAutoFollowChange = useCallback((enabled) => {
        setAutoFollowAnswers(enabled);
        if (enabled) {
            answerPanelRef.current?.scrollToLatest?.();
        }
    }, []);

    const applyClickThrough = useCallback(async (enabled) => {
        if (!window.electronAPI?.setOverlayClickThrough) {
            setClickThrough(enabled);
            return;
        }

        try {
            const nextValue = await window.electronAPI.setOverlayClickThrough(enabled);
            setClickThrough(Boolean(nextValue));
            setStatus(Boolean(nextValue) ? '🟡 Click-through enabled' : '🟢 Overlay interactive');
        } catch {
            setClickThrough(enabled);
        }
    }, []);

    // ─── Handle WebSocket Messages ──────────────
    const handleMessage = useCallback((data) => {
        switch (data.type) {
            case 'status':
                setStatus(data.text);
                if (isEndingSessionRef.current && data.text?.includes('Session ended')) {
                    setIsStreaming(false);
                    finalizeEndedSession();
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
                    finalizeEndedSession();
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
    }, [finalizeEndedSession, handleMessage]);

    // ─── Electron IPC Listeners ─────────────────
    useEffect(() => {
        if (window.electronAPI) {
            window.electronAPI.getOverlayClickThrough?.().then((enabled) => {
                if (typeof enabled === 'boolean') {
                    setClickThrough(enabled);
                }
            });

            window.electronAPI.onOverlayClickThrough?.((enabled) => {
                setClickThrough(Boolean(enabled));
                setStatus(Boolean(enabled) ? '🟡 Click-through enabled' : '🟢 Overlay interactive');
            });

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

    const startDragAnywhere = useCallback(async (event) => {
        if (event.button !== 0 || isResizing) {
            return;
        }

        if (!window.electronAPI?.getOverlayBounds || !window.electronAPI?.setOverlayBounds) {
            return;
        }

        const target = event.target instanceof Element ? event.target : null;
        if (
            target?.closest(
                '[data-overlay-interactive="true"], button, input, textarea, select, a',
            )
        ) {
            return;
        }

        const initialBounds = await window.electronAPI.getOverlayBounds();
        if (!initialBounds) {
            return;
        }

        dragSessionRef.current = {
            startX: event.screenX,
            startY: event.screenY,
            bounds: initialBounds,
        };
    }, [isResizing]);

    useEffect(() => {
        const handleMouseMove = (event) => {
            const session = dragSessionRef.current;
            if (!session || !window.electronAPI?.setOverlayBounds) {
                return;
            }

            const nextX = session.bounds.x + (event.screenX - session.startX);
            const nextY = session.bounds.y + (event.screenY - session.startY);

            window.electronAPI.setOverlayBounds({
                x: nextX,
                y: nextY,
            });
        };

        const handleMouseUp = () => {
            dragSessionRef.current = null;
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
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
    const surfaceAlpha = 0.09;
    const overlayBackground = 'transparent';
    const headerTextClass = 'text-gray-200';
    const statusTextClass = 'text-gray-50';
    const emptyCardClass = 'border-white/12 bg-black/[0.12]';
    const emptyTitleClass = 'text-white/80';
    const emptyBodyClass = 'text-white/90';
    const questionCardClass = 'border-white/12 bg-black/[0.16]';
    const questionTextClass = 'text-white';
    const glassCardStyle = {
        backgroundColor: 'rgba(10, 10, 15, 0.58)',
        backdropFilter: 'blur(20px) saturate(140%)',
        WebkitBackdropFilter: 'blur(20px) saturate(140%)',
        boxShadow:
            '0 18px 42px rgba(0, 0, 0, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(0, 0, 0, 0.28)',
        textShadow: '0 1px 8px rgba(0, 0, 0, 0.95)',
    };
    const glassStripStyle = {
        backgroundColor: 'rgba(10, 10, 15, 0.62)',
        backdropFilter: 'blur(20px) saturate(140%)',
        WebkitBackdropFilter: 'blur(20px) saturate(140%)',
        boxShadow:
            '0 16px 36px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(0, 0, 0, 0.24)',
        textShadow: '0 1px 6px rgba(0, 0, 0, 0.9)',
    };

    return (
        <div
            onMouseDown={startDragAnywhere}
            className="relative h-screen flex flex-col gap-2 select-none overflow-hidden bg-transparent px-3 py-3"
            style={{
                fontSize: `${fontSize}px`,
                background: overlayBackground,
                backdropFilter: 'none',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif',
                transition: 'background 200ms ease',
            }}
        >
            <div className="pointer-events-none absolute inset-0 overflow-hidden">
                <div
                    className="absolute inset-0 rounded-[28px]"
                    style={{
                        background: 'rgba(10, 10, 15, 0.18)',
                        backdropFilter: 'blur(20px) saturate(140%)',
                        WebkitBackdropFilter: 'blur(20px) saturate(140%)',
                    }}
                />
                <div
                    className="absolute -left-12 top-8 h-32 w-32 rounded-full blur-3xl"
                    style={{ background: 'radial-gradient(circle, rgba(56,189,248,0.12) 0%, rgba(56,189,248,0) 72%)' }}
                />
                <div
                    className="absolute right-4 top-16 h-36 w-36 rounded-full blur-3xl"
                    style={{ background: 'radial-gradient(circle, rgba(192,132,252,0.1) 0%, rgba(192,132,252,0) 74%)' }}
                />
                <div
                    className="absolute bottom-16 left-1/3 h-40 w-40 rounded-full blur-3xl"
                    style={{ background: 'radial-gradient(circle, rgba(45,212,191,0.08) 0%, rgba(45,212,191,0) 76%)' }}
                />
                <div
                    className="absolute inset-0 rounded-[28px]"
                    style={{
                        background:
                            'radial-gradient(circle at center, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0.01) 28%, rgba(7,10,18,0.18) 62%, rgba(4,6,12,0.46) 100%)',
                    }}
                />
            </div>

            {/* ─── Header ──────────────────────── */}
            <div
                className="relative z-10 flex items-center justify-between rounded-[22px] border border-white/15 px-4 py-3 shrink-0"
                style={glassStripStyle}
            >
                <div className="flex items-center gap-3">
                    <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] tracking-[0.28em] text-white/80">
                        INTERVIEWACE
                    </div>
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
                        <span className={`text-[10px] ${statusTextClass}`}>{status}</span>
                    </div>
                </div>
                <div
                    data-overlay-interactive="true"
                    className="flex items-center gap-2"
                >
                    <span className={`text-[10px] ${headerTextClass}`}>
                        drag anywhere to move • esc toggles click-through
                    </span>
                    <button
                        type="button"
                        onClick={() => handleAutoFollowChange(!autoFollowAnswers)}
                        className={`text-[11px] px-3 py-1.5 rounded-full border transition ${
                            autoFollowAnswers
                                ? 'text-emerald-200 border-emerald-400/30'
                                : 'text-gray-300 border-white/10'
                        }`}
                        style={{
                            backgroundColor: autoFollowAnswers
                                ? 'rgba(16,185,129,0.14)'
                                : 'rgba(255,255,255,0.08)',
                            boxShadow: autoFollowAnswers
                                ? '0 0 18px rgba(16, 185, 129, 0.18)'
                                : 'none',
                        }}
                    >
                        {autoFollowAnswers ? 'Auto-scroll On' : 'Auto-scroll Off'}
                    </button>
                    <button
                        type="button"
                        onClick={hideOverlay}
                        className="text-[11px] text-gray-300 px-3 py-1.5 rounded-full border border-white/10 transition"
                        style={{ backgroundColor: 'rgba(255,255,255,0.08)' }}
                    >
                        Hide
                    </button>
                </div>
            </div>

            {/* ─── Live Transcript ─────────────── */}
            <TranscriptFeed entries={transcript} surfaceAlpha={surfaceAlpha} />

            {showEmptyState && (
                <div
                    className={`relative z-10 rounded-[22px] border px-4 py-4 ${emptyCardClass}`}
                    style={{
                        ...glassCardStyle,
                        backgroundColor: 'rgba(10, 10, 15, 0.56)',
                    }}
                >
                    <div className={`mb-2 text-[11px] uppercase tracking-[0.24em] ${emptyTitleClass}`}>
                        Live Status
                    </div>
                    <div className="mb-1 text-[15px] font-medium text-white">
                        {status}
                    </div>
                    <div className={`text-[12px] leading-relaxed ${emptyBodyClass}`}>
                        Waiting for interviewer system audio. Once interviewer speech is detected,
                        transcript and answer suggestions will appear here.
                    </div>
                </div>
            )}

            {/* ─── Detected Question ──────────── */}
            {detectedQuestion && (
                <div
                    className={`relative z-10 rounded-[22px] border p-3 shrink-0 ${questionCardClass}`}
                    style={{
                        ...glassCardStyle,
                        backgroundColor: 'rgba(10, 10, 15, 0.62)',
                    }}
                >
                    <div className="text-[10px] uppercase tracking-wider text-blue-200 mb-1">
                        ❓ Question Detected
                    </div>
                    <div className={`text-[13px] leading-relaxed ${questionTextClass}`}>
                        {detectedQuestion}
                    </div>
                </div>
            )}

            {/* ─── AI Answer ─────────────────── */}
            <AnswerPanel
                ref={answerPanelRef}
                answer={currentAnswer}
                previousAnswers={answerHistory}
                answerSource={answerSource}
                isStreaming={isStreaming}
                autoFollow={autoFollowAnswers}
                showManualNextButton={!autoFollowAnswers}
                surfaceAlpha={surfaceAlpha}
            />

            {/* ─── Action Buttons ────────────── */}
            <div
                data-overlay-interactive="true"
                className="relative z-10 flex gap-2 px-3 py-2 shrink-0 rounded-[22px] border border-white/15"
                style={glassStripStyle}
            >
                <button
                    onClick={requestManualAnswer}
                    className="rounded-full bg-blue-900/12 px-3 py-1.5 text-[11px] text-blue-100 transition hover:bg-blue-900/22"
                >
                    ⚡ Generate Now
                </button>
                <button
                    onClick={() => sendAction('regenerate')}
                    className="rounded-full bg-white/[0.025] px-3 py-1.5 text-[11px] text-gray-200 transition hover:bg-white/[0.06]"
                >
                    🔄 Regen
                </button>
                <button
                    onClick={() => sendAction('shorter')}
                    className="rounded-full bg-white/[0.025] px-3 py-1.5 text-[11px] text-gray-200 transition hover:bg-white/[0.06]"
                >
                    ✂️ Shorter
                </button>
                <button
                    onClick={() => sendAction('more_detail')}
                    className="rounded-full bg-white/[0.025] px-3 py-1.5 text-[11px] text-gray-200 transition hover:bg-white/[0.06]"
                >
                    📝 Detail
                </button>
                <div className="flex-1" />
                <button
                    onClick={handleEndSession}
                    className="rounded-full bg-red-900/12 px-3 py-1.5 text-[11px] text-red-200 transition hover:bg-red-900/22"
                >
                    ⏹ End
                </button>
                <button
                    onClick={hideOverlay}
                    className="rounded-full bg-white/[0.025] px-3 py-1.5 text-[11px] text-gray-200 transition hover:bg-white/[0.06]"
                >
                    ✕ Hide
                </button>
            </div>

            <div
                role="presentation"
                aria-label="Resize overlay"
                onMouseDown={startResize}
                data-overlay-interactive="true"
                className="absolute bottom-0 right-0 h-5 w-5 cursor-se-resize rounded-tl-md bg-white/[0.025] hover:bg-white/[0.06]"
            >
                <div className="pointer-events-none absolute bottom-1 right-1 text-[10px] leading-none text-white/60">
                    ◢
                </div>
            </div>
        </div>
    );
}
