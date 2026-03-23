/**
 * InterviewAce — Answer Panel
 * Displays streaming AI-generated answer with auto-scroll.
 *
 * Owner: Dev 3
 */

import { useRef, useEffect } from 'react';

export default function AnswerPanel({ answer, isStreaming }) {
    const scrollRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [answer]);

    return (
        <div className="flex-1 mx-3 mt-2 flex flex-col overflow-hidden min-h-0">
            <div className="text-[9px] uppercase tracking-widest text-gray-600 mb-1 flex items-center gap-2 shrink-0">
                💡 Suggested Answer
                {isStreaming && (
                    <span className="text-yellow-400 animate-pulse text-[10px]">● generating...</span>
                )}
            </div>
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto bg-white/[0.03] rounded-lg p-3
                           text-[13px] leading-relaxed whitespace-pre-wrap text-gray-200"
            >
                {answer || (
                    <span className="text-gray-600 italic">
                        Waiting for interviewer's question...
                    </span>
                )}
            </div>
        </div>
    );
}
