/**
 * InterviewAce — Model Selector Component
 * Dropdown to pick which model powers both prep and live answers.
 *
 * Owner: Dev 3
 */

const MODELS = [
    {
        id: 'gpt-5-mini',
        name: 'GPT-5 mini',
        desc: 'OpenAI model used for prep and live answers',
    },
    {
        id: 'claude-haiku-4-5',
        name: 'Claude Haiku 4.5',
        desc: 'Anthropic model used for prep and live answers',
    },
];

export default function ModelSelector({ value, onChange }) {
    return (
        <div>
            <label className="mb-2 block text-[11px] uppercase tracking-[0.18em] text-gray-500">
                Interview Model
            </label>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full rounded-2xl border border-white/10 bg-slate-900/85 px-4 py-3
                           text-sm text-gray-100 focus:outline-none focus:border-cyan-400/60
                           focus:bg-slate-900 transition"
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
