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

export default function ModelSelector({ value, onChange, theme = 'dark' }) {
    const labelClass = theme === 'light' ? 'text-slate-500' : 'text-gray-500';
    const selectClass =
        theme === 'light'
            ? 'border-slate-300 bg-white/80 text-slate-900 focus:border-cyan-500/60 focus:bg-white'
            : 'border-white/10 bg-slate-900/85 text-gray-100 focus:border-cyan-400/60 focus:bg-slate-900';

    return (
        <div>
            <label className={`mb-2 block text-[11px] uppercase tracking-[0.18em] ${labelClass}`}>
                Interview Model
            </label>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className={`w-full rounded-2xl border px-4 py-3 text-sm transition focus:outline-none ${selectClass}`}
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
