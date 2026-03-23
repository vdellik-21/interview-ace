/**
 * InterviewAce — Status Indicator
 * Shows the current session status with a colored dot.
 *
 * Owner: Dev 3
 */

const STATUS_CONFIG = {
    idle: { color: 'bg-gray-500', label: 'Ready to set up' },
    preparing: { color: 'bg-yellow-500 animate-pulse', label: 'Preparing...' },
    ready: { color: 'bg-green-500', label: 'Session ready' },
    live: { color: 'bg-red-500 animate-pulse', label: 'LIVE' },
};

export default function StatusIndicator({ status }) {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.idle;

    return (
        <div className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${config.color}`} />
            <span className="text-xs text-gray-400">{config.label}</span>
        </div>
    );
}
