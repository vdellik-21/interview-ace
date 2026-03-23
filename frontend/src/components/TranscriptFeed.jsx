/**
 * InterviewAce — Transcript Feed
 * Scrolling display of live transcript entries with speaker labels.
 *
 * Owner: Dev 3
 */

import { useRef, useEffect } from 'react';

export default function TranscriptFeed({ entries }) {
    const bottomRef = useRef(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [entries]);

    return (
        <div className="mx-3 mt-2 max-h-28 overflow-y-auto shrink-0 space-y-0.5">
            <div className="text-[9px] uppercase tracking-widest text-gray-600 mb-1">
                Live Transcript
            </div>
            {entries.length === 0 && (
                <div className="text-[11px] text-gray-600 italic">
                    Waiting for speech...
                </div>
            )}
            {entries.slice(-8).map((t, i) => (
                <div
                    key={i}
                    className={`text-[12px] leading-snug ${
                        t.speaker === 'interviewer' ? 'text-blue-300' : 'text-green-300'
                    }`}
                >
                    <span className="font-semibold">
                        {t.speaker === 'interviewer' ? '🎤' : '🗣️'}
                    </span>{' '}
                    {t.text}
                </div>
            ))}
            <div ref={bottomRef} />
        </div>
    );
}
