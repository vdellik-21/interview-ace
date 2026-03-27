/**
 * InterviewAce — Answer Panel
 * Displays streaming AI-generated answer with auto-scroll.
 *
 * Owner: Dev 3
 */

import { useRef, useLayoutEffect } from 'react';

function renderInlineFormatting(text) {
    const segments = text.split(/(\*\*.*?\*\*)/g);
    return segments.map((segment, index) => {
        const isBold = segment.startsWith('**') && segment.endsWith('**') && segment.length > 4;
        if (isBold) {
            return (
                <strong key={`${segment}-${index}`} className="font-semibold text-white">
                    {segment.slice(2, -2)}
                </strong>
            );
        }
        return <span key={`${segment}-${index}`}>{segment}</span>;
    });
}

export default function AnswerPanel({ answer, previousAnswers = [], answerSource, isStreaming }) {
    const scrollRef = useRef(null);
    const bottomRef = useRef(null);

    const renderSourceLabel = () => {
        if (!answerSource) return null;
        if (answerSource === 'error') {
            return <span className="text-rose-300 text-[10px]">error</span>;
        }
        if (answerSource === 'gpt-5-mini') {
            return <span className="text-emerald-300 text-[10px]">GPT-5 mini</span>;
        }
        if (answerSource === 'claude-haiku-4-5') {
            return <span className="text-orange-300 text-[10px]">Claude Haiku 4.5</span>;
        }
        if (answerSource === 'openai') {
            return <span className="text-emerald-300 text-[10px]">OpenAI</span>;
        }
        return <span className="text-emerald-300 text-[10px]">{answerSource}</span>;
    };

    useLayoutEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, [answer, isStreaming, previousAnswers.length]);

    return (
        <div className="flex-1 mx-3 mt-2 flex flex-col overflow-hidden min-h-0">
            <div className="text-[9px] uppercase tracking-widest text-gray-600 mb-1 flex items-center gap-2 shrink-0">
                💡 Suggested Answer
                {renderSourceLabel()}
                {isStreaming && (
                    <span className="text-yellow-400 animate-pulse text-[10px]">● generating...</span>
                )}
            </div>
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto rounded-xl border border-white/8 bg-black/20 p-3
                           text-[13px] leading-relaxed text-gray-200"
            >
                {previousAnswers.map((item, idx) => (
                    <div
                        key={`${item.question}-${idx}`}
                        className="mb-4 rounded-xl border border-white/6 bg-black/12 p-3"
                    >
                        <div className="mb-2 text-[9px] uppercase tracking-[0.22em] text-gray-500">
                            Earlier Answer
                        </div>
                        <div className="mb-2 text-[11px] text-gray-400">
                            {item.question}
                        </div>
                        <div className="space-y-1.5 text-[12px] leading-relaxed text-gray-300 opacity-90">
                            {item.answer
                                .split('\n')
                                .filter((line) => line.trim().length > 0)
                                .map((line, index) => (
                                    <div key={`${item.question}-${index}`}>
                                        {renderInlineFormatting(line)}
                                    </div>
                                ))}
                        </div>
                    </div>
                ))}

                {!answer && (
                    <span className="text-gray-600 italic">
                        Waiting for interviewer's question...
                    </span>
                )}
                {answer && (
                    <div className="space-y-2 rounded-xl border border-white/8 bg-black/16 p-3">
                        <div className="text-[9px] uppercase tracking-[0.22em] text-gray-500">
                            Current Answer
                        </div>
                        {answer.split('\n').filter((line) => line.trim().length > 0).map((line, index) => {
                            const trimmed = line.trim();
                            let lineClass = 'text-gray-200';

                            if (trimmed.startsWith('🎯')) {
                                lineClass = 'text-emerald-300 font-medium';
                            } else if (trimmed.startsWith('💬')) {
                                lineClass = 'text-sky-300 font-medium';
                            } else if (trimmed.startsWith('🔗')) {
                                lineClass = 'text-violet-300 font-medium';
                            } else if (trimmed.startsWith('😊') || trimmed.startsWith('⚠️')) {
                                lineClass = 'text-amber-200 font-medium';
                            }

                            return (
                                <div key={`${trimmed}-${index}`} className={lineClass}>
                                    {renderInlineFormatting(line)}
                                </div>
                            );
                        })}
                    </div>
                )}
                <div ref={bottomRef} />
            </div>
        </div>
    );
}
