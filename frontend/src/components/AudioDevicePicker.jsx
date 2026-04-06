/**
 * InterviewAce — Audio Device Picker
 * Dropdown for selecting audio input devices.
 *
 * Owner: Dev 3
 */

export default function AudioDevicePicker({ label, devices, value, onChange, theme = 'dark' }) {
    const labelClass = theme === 'light' ? 'text-slate-500' : 'text-gray-500';
    const selectClass =
        theme === 'light'
            ? 'border-slate-300 bg-white/80 text-slate-900 focus:border-cyan-500/60 focus:bg-white'
            : 'border-white/10 bg-slate-900/85 text-gray-100 focus:border-cyan-400/60 focus:bg-slate-900';

    return (
        <div>
            <label className={`mb-2 block text-[11px] uppercase tracking-[0.18em] ${labelClass}`}>
                {label}
            </label>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className={`w-full rounded-2xl border px-4 py-3 text-sm transition focus:outline-none ${selectClass}`}
            >
                {devices.length === 0 && (
                    <option value="">No devices found</option>
                )}
                {devices.map((d) => (
                    <option key={d} value={d}>
                        {d}
                    </option>
                ))}
            </select>
        </div>
    );
}
