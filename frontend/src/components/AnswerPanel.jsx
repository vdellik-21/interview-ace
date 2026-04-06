/**
 * InterviewAce — Answer Panel
 * Displays streaming AI-generated answer with auto-scroll.
 *
 * Owner: Dev 3
 */

import { forwardRef, useImperativeHandle, useLayoutEffect, useMemo, useRef } from 'react';

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

const AnswerPanel = forwardRef(function AnswerPanel(
    {
        answer,
        previousAnswers = [],
        answerSource,
        isStreaming,
        autoFollow = true,
        showManualNextButton = false,
        theme = 'dark',
        surfaceAlpha = 0.2,
    },
    ref,
) {
    const scrollRef = useRef(null);
    const bottomRef = useRef(null);
    const answerRefs = useRef([]);
    const activeAnswerIndexRef = useRef(-1);
    const pinnedToLatestRef = useRef(true);
    const ultraTransparent = theme === 'dark' && surfaceAlpha <= 0.02;

    const answerSections = useMemo(() => {
        const earlier = previousAnswers.map((item, idx) => ({
            ...item,
            key: `${item.question}-${idx}`,
            label: 'Earlier Answer',
            isCurrent: false,
        }));

        if (!answer) {
            return earlier;
        }

        return [
            ...earlier,
            {
                key: '__current__',
                question: '',
                answer,
                source: answerSource,
                label: 'Current Answer',
                isCurrent: true,
            },
        ];
    }, [answer, answerSource, previousAnswers]);

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

    const headerTextClass = theme === 'light' ? 'text-slate-500' : 'text-white/80';
    const containerClass =
        theme === 'light'
            ? 'border-slate-300/80 text-slate-800'
            : 'border-white/10 text-gray-100';
    const currentCardClass =
        theme === 'light'
            ? 'border-slate-300/80'
            : ultraTransparent
                ? 'border-white/6'
                : 'border-white/8';
    const earlierCardClass =
        theme === 'light'
            ? 'border-slate-300/70'
            : ultraTransparent
                ? 'border-white/5'
                : 'border-white/6';
    const secondaryTextClass = theme === 'light' ? 'text-slate-500' : 'text-white/60';
    const waitingTextClass = theme === 'light' ? 'text-slate-500' : 'text-white/70';
    const sharedTextShadow =
        theme === 'light' ? '0 1px 4px rgba(255, 255, 255, 0.35)' : '0 1px 8px rgba(0, 0, 0, 0.95)';

    useLayoutEffect(() => {
        const latestIndex = answerSections.length - 1;
        if (latestIndex < 0) {
            activeAnswerIndexRef.current = -1;
            pinnedToLatestRef.current = true;
            return;
        }

        if (autoFollow || activeAnswerIndexRef.current < 0) {
            bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
            activeAnswerIndexRef.current = latestIndex;
            pinnedToLatestRef.current = true;
        }
    }, [answer, answerSections.length, autoFollow, isStreaming, previousAnswers.length]);

    const syncActiveAnswerIndex = () => {
        const container = scrollRef.current;
        const answerElements = answerRefs.current.filter(Boolean);

        if (!container || answerElements.length === 0) {
            activeAnswerIndexRef.current = -1;
            return;
        }

        const top = container.scrollTop;
        let activeIndex = 0;

        for (let index = 0; index < answerElements.length; index += 1) {
            const element = answerElements[index];
            if (element.offsetTop <= top + 8) {
                activeIndex = index;
            } else {
                break;
            }
        }

        activeAnswerIndexRef.current = activeIndex;
        const distanceFromBottom =
            container.scrollHeight - container.clientHeight - container.scrollTop;
        pinnedToLatestRef.current =
            distanceFromBottom <= 16 || activeIndex >= answerElements.length - 1;
    };

    const jumpToNextAnswer = () => {
        const container = scrollRef.current;
        const answerElements = answerRefs.current.filter(Boolean);

        if (!container || answerElements.length === 0) {
            return;
        }

        if (activeAnswerIndexRef.current < 0) {
            syncActiveAnswerIndex();
        }

        const currentIndex =
            activeAnswerIndexRef.current < 0
                ? 0
                : activeAnswerIndexRef.current;
        const targetIndex = Math.min(currentIndex + 1, answerElements.length - 1);
        const target = answerElements[targetIndex];

        activeAnswerIndexRef.current = targetIndex;
        pinnedToLatestRef.current = targetIndex >= answerElements.length - 1;

        container.scrollTo({
            top: Math.max(target.offsetTop - 8, 0),
            behavior: 'smooth',
        });
    };

    useImperativeHandle(ref, () => ({
        jumpToNextAnswer,
        scrollToLatest: () => {
            const latestIndex = answerSections.length - 1;
            if (latestIndex < 0) {
                return;
            }

            bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
            activeAnswerIndexRef.current = latestIndex;
            pinnedToLatestRef.current = true;
        },
    }), [answerSections.length]);

    return (
        <div className="relative z-10 flex-1 flex flex-col overflow-hidden min-h-0">
            <div className={`mb-1 flex items-center gap-2 shrink-0 text-[9px] uppercase tracking-widest ${headerTextClass}`}>
                <span>💡 Suggested Answer</span>
                {renderSourceLabel()}
                {isStreaming && (
                    <span className="text-yellow-400 animate-pulse text-[10px]">● generating...</span>
                )}
            </div>
            <div className="relative flex-1 min-h-0">
                <div
                    ref={scrollRef}
                    onScroll={syncActiveAnswerIndex}
                    className={`h-full overflow-y-auto rounded-[24px] border p-4 text-[13px] leading-relaxed ${containerClass}`}
                    style={{
                        backgroundColor:
                            theme === 'light'
                                ? `rgba(255,255,255,${Math.min(surfaceAlpha + 0.04, 0.82)})`
                                : ultraTransparent
                                    ? `rgba(10,10,15,${Math.max(surfaceAlpha * 6.6, 0.52)})`
                                    : `rgba(10,10,15,${Math.max(surfaceAlpha * 7.1, 0.6)})`,
                        backdropFilter: 'blur(20px) saturate(140%)',
                        WebkitBackdropFilter: 'blur(20px) saturate(140%)',
                        boxShadow:
                            '0 18px 42px rgba(0, 0, 0, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.08), inset 0 -1px 0 rgba(0, 0, 0, 0.28)',
                        textShadow: sharedTextShadow,
                    }}
                >
                    {answerSections.map((item, idx) => (
                        <div
                            key={item.key}
                            ref={(element) => {
                                answerRefs.current[idx] = element;
                            }}
                            className={`mb-4 rounded-[20px] border p-4 ${item.isCurrent ? currentCardClass : earlierCardClass}`}
                            style={{
                                backgroundColor: item.isCurrent
                                    ? theme === 'light'
                                        ? `rgba(255,255,255,${Math.min(surfaceAlpha + 0.06, 0.88)})`
                                        : ultraTransparent
                                            ? `rgba(10,10,15,${Math.max(surfaceAlpha * 7.2, 0.58)})`
                                            : `rgba(10,10,15,${Math.max(surfaceAlpha * 7.8, 0.66)})`
                                    : theme === 'light'
                                        ? `rgba(241,245,249,${Math.min(surfaceAlpha + 0.05, 0.78)})`
                                        : ultraTransparent
                                            ? `rgba(12,12,18,${Math.max(surfaceAlpha * 5.8, 0.42)})`
                                            : `rgba(12,12,18,${Math.max(surfaceAlpha * 6.3, 0.5)})`,
                                backdropFilter: 'blur(18px) saturate(135%)',
                                WebkitBackdropFilter: 'blur(18px) saturate(135%)',
                                boxShadow: item.isCurrent
                                    ? 'inset 0 1px 0 rgba(255, 255, 255, 0.07), inset 0 -1px 0 rgba(0, 0, 0, 0.26), 0 12px 28px rgba(0, 0, 0, 0.18)'
                                    : 'inset 0 1px 0 rgba(255, 255, 255, 0.05), inset 0 -1px 0 rgba(0, 0, 0, 0.22), 0 8px 20px rgba(0, 0, 0, 0.14)',
                            }}
                        >
                            <div className={`mb-2 text-[9px] uppercase tracking-[0.22em] ${secondaryTextClass}`}>
                                {item.label}
                            </div>
                            {!item.isCurrent && (
                                <div className={`mb-2 text-[11px] ${theme === 'light' ? 'text-slate-600' : 'text-gray-400'}`}>
                                    {item.question}
                                </div>
                            )}
                            {item.answer.split('\n').filter((line) => line.trim().length > 0).map((line, index) => {
                                const trimmed = line.trim();
                                let lineClass =
                                    item.isCurrent
                                        ? theme === 'light'
                                            ? 'text-slate-800'
                                            : 'text-gray-200'
                                        : theme === 'light'
                                            ? 'text-slate-700 opacity-95'
                                            : 'text-gray-300 opacity-90';

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
                    ))}

                    {!answer && previousAnswers.length === 0 && (
                        <span className={`italic ${waitingTextClass}`}>
                            Waiting for interviewer's question...
                        </span>
                    )}
                    <div ref={bottomRef} />
                </div>
                {showManualNextButton && (
                    <button
                        type="button"
                        onClick={jumpToNextAnswer}
                        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md border border-blue-400/25
                                   bg-black/20 px-2 py-2 text-[11px] text-blue-50 shadow-lg transition
                                   hover:bg-black/28"
                        style={{ textShadow: sharedTextShadow }}
                        title="Jump to next answer"
                    >
                        ↓ Next
                    </button>
                )}
            </div>
        </div>
    );
});

export default AnswerPanel;
