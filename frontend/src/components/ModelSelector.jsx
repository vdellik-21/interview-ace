/**
 * InterviewAce — Model Selector Component
 * Dropdown to pick which Claude model to use.
 *
 * Owner: Dev 3
 */

const MODELS = [
    {
        id: 'claude-sonnet-4-20250514',
        name: 'Sonnet 4',
        desc: 'Fast + Smart (recommended)',
    },
    {
        id: 'claude-opus-4-20250514',
        name: 'Opus 4',
        desc: 'Smartest (slightly slower)',
    },
    {
        id: 'claude-haiku-4-5-20251001',
        name: 'Haiku 4.5',
        desc: 'Fastest (lighter answers)',
    },
];

export default function ModelSelector({ value, onChange }) {
    return (
        <div>
            <label className="block text-xs text-gray-400 mb-1.5">Claude Model</label>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5
                           text-sm text-gray-200 focus:outline-none focus:border-blue-500 transition"
            >
                {MODELS.map((m) => (
                    <option key={m.id} value={m.id}>
                        {m.name} — {m.desc}
                    </option>
                ))}
            </select>
        </div>
    );
}
