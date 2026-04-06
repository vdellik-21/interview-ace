/**
 * InterviewAce — Transcript Feed
 * Scrolling display of live transcript entries with speaker labels.
 *
 * Owner: Dev 3
 */

import { useRef, useEffect } from 'react';

export default function TranscriptFeed({ entries, theme = 'dark', surfaceAlpha = 0.2 }) {
    const bottomRef = useRef(null);
    const interviewerEntries = entries.filter((entry) => entry.speaker === 'interviewer');
    const ultraTransparent = theme === 'dark' && surfaceAlpha <= 0.02;

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [interviewerEntries]);

    const containerClass =
        theme === 'light'
            ? 'border-slate-300/80 bg-white/70'
            : ultraTransparent
                ? 'border-white/15 bg-transparent'
                : 'border-white/8 bg-black/10';
    const titleClass = theme === 'light' ? 'text-slate-500' : 'text-white/80';
    const emptyClass = theme === 'light' ? 'text-slate-500' : 'text-white/85';
    const entryClass = theme === 'light' ? 'text-blue-700' : 'text-blue-50';

    return (
        <div
            className={`relative z-10 max-h-28 overflow-y-auto shrink-0 space-y-0.5 rounded-[22px] border px-3 py-2 ${containerClass}`}
            style={{
                backgroundColor:
                    theme === 'light'
                        ? `rgba(255,255,255,${Math.min(surfaceAlpha + 0.04, 0.78)})`
                        : ultraTransparent
                            ? `rgba(10,10,15,${Math.max(surfaceAlpha * 6.2, 0.5)})`
                            : `rgba(10,10,15,${Math.max(surfaceAlpha * 6.8, 0.58)})`,
                backdropFilter: 'blur(20px) saturate(140%)',
                WebkitBackdropFilter: 'blur(20px) saturate(140%)',
                boxShadow:
                    '0 18px 42px rgba(0, 0, 0, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(0, 0, 0, 0.28)',
                textShadow:
                    theme === 'light'
                        ? '0 1px 4px rgba(255, 255, 255, 0.35)'
                        : '0 1px 8px rgba(0, 0, 0, 0.95)',
            }}
        >
            <div className={`mb-1 text-[9px] uppercase tracking-widest ${titleClass}`}>
                Live Transcript
            </div>
            {interviewerEntries.length === 0 && (
                <div className={`text-[11px] italic ${emptyClass}`}>
                    Waiting for interviewer audio...
                </div>
            )}
            {interviewerEntries.slice(-8).map((t, i) => (
                <div
                    key={i}
                    className={`text-[12px] leading-snug ${entryClass}`}
                >
                    <span className="font-semibold">🎤</span>{' '}
                    {t.text}
                </div>
            ))}
            <div ref={bottomRef} />
        </div>
    );
}
