/**
 * InterviewAce — Status Indicator
 * Shows the current session status with a colored dot.
 *
 * Owner: Dev 3
 */

const STATUS_CONFIG = {
    idle: { color: 'bg-gray-500/80', label: 'Ready to prep' },
    preparing: { color: 'bg-amber-400 animate-pulse', label: 'Preparing' },
    ready: { color: 'bg-emerald-400', label: 'Ready' },
    live: { color: 'bg-red-400 animate-pulse', label: 'Live' },
};

export default function StatusIndicator({ status, theme = 'dark' }) {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.idle;
    const containerClass =
        theme === 'light'
            ? 'border-slate-300 bg-white/75'
            : 'border-white/8 bg-black/20';
    const textClass = theme === 'light' ? 'text-slate-500' : 'text-gray-400';

    return (
        <div className={`flex items-center gap-2 rounded-full border px-3 py-1.5 ${containerClass}`}>
            <div className={`w-2 h-2 rounded-full ${config.color}`} />
            <span className={`text-[11px] uppercase tracking-[0.18em] ${textClass}`}>{config.label}</span>
        </div>
    );
}
