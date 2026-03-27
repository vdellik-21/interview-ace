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

export default function StatusIndicator({ status }) {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.idle;

    return (
        <div className="flex items-center gap-2 rounded-full border border-white/8 bg-black/20 px-3 py-1.5">
            <div className={`w-2 h-2 rounded-full ${config.color}`} />
            <span className="text-[11px] uppercase tracking-[0.18em] text-gray-400">{config.label}</span>
        </div>
    );
}
