/**
 * InterviewAce — Transcript Feed
 * Scrolling display of live transcript entries with speaker labels.
 *
 * Owner: Dev 3
 */

import { useRef, useEffect } from 'react';

export default function TranscriptFeed({ entries }) {
    const bottomRef = useRef(null);
    const interviewerEntries = entries.filter((entry) => entry.speaker === 'interviewer');

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [interviewerEntries]);

    return (
        <div className="mx-3 mt-2 max-h-28 overflow-y-auto shrink-0 space-y-0.5 rounded-xl border border-white/6 bg-black/10 px-3 py-2">
            <div className="text-[9px] uppercase tracking-widest text-gray-600 mb-1">
                Live Transcript
            </div>
            {interviewerEntries.length === 0 && (
                <div className="text-[11px] text-gray-600 italic">
                    Waiting for interviewer audio...
                </div>
            )}
            {interviewerEntries.slice(-8).map((t, i) => (
                <div
                    key={i}
                    className="text-[12px] leading-snug text-blue-300"
                >
                    <span className="font-semibold">🎤</span>{' '}
                    {t.text}
                </div>
            ))}
            <div ref={bottomRef} />
        </div>
    );
}
