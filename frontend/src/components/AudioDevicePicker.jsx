/**
 * InterviewAce — Audio Device Picker
 * Dropdown for selecting audio input devices.
 *
 * Owner: Dev 3
 */

export default function AudioDevicePicker({ label, devices, value, onChange }) {
    return (
        <div>
            <label className="mb-2 block text-[11px] uppercase tracking-[0.18em] text-gray-500">
                {label}
            </label>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full rounded-2xl border border-white/10 bg-slate-900/85 px-4 py-3
                           text-sm text-gray-100 focus:outline-none focus:border-cyan-400/60
                           focus:bg-slate-900 transition"
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
