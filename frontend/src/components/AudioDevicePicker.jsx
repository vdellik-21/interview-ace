/**
 * InterviewAce — Audio Device Picker
 * Dropdown for selecting audio input devices.
 *
 * Owner: Dev 3
 */

export default function AudioDevicePicker({ label, devices, value, onChange }) {
    return (
        <div>
            <label className="block text-xs text-gray-400 mb-1.5">{label}</label>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5
                           text-sm text-gray-200 focus:outline-none focus:border-blue-500 transition"
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
