/**
 * InterviewAce — App Icon
 * Interview Lens mark used in the dashboard header.
 */

export default function AppIcon({ className = 'h-10 w-10' }) {
    return (
        <div
            className={`relative overflow-hidden rounded-[22px] border border-white/20 bg-[#060913] shadow-[0_18px_42px_rgba(15,23,42,0.38)] ${className}`}
            aria-hidden="true"
        >
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_28%_22%,rgba(56,189,248,0.22),transparent_34%),radial-gradient(circle_at_72%_24%,rgba(129,140,248,0.22),transparent_30%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(3,7,18,0.94))]" />
            <div className="absolute inset-[1px] rounded-[21px] bg-[linear-gradient(180deg,rgba(255,255,255,0.10),rgba(255,255,255,0.02))]" />
            <svg
                viewBox="0 0 64 64"
                className="absolute inset-0 h-full w-full"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
            >
                <defs>
                    <linearGradient id="lens-ring" x1="16" y1="14" x2="48" y2="50" gradientUnits="userSpaceOnUse">
                        <stop stopColor="#67E8F9" />
                        <stop offset="0.5" stopColor="#60A5FA" />
                        <stop offset="1" stopColor="#A78BFA" />
                    </linearGradient>
                    <radialGradient id="lens-core" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(32 31) rotate(90) scale(17)">
                        <stop stopColor="#F8FAFC" stopOpacity="0.92" />
                        <stop offset="0.45" stopColor="#C4B5FD" stopOpacity="0.78" />
                        <stop offset="1" stopColor="#0F172A" stopOpacity="0" />
                    </radialGradient>
                    <linearGradient id="lens-bubble" x1="20" y1="18" x2="48" y2="46" gradientUnits="userSpaceOnUse">
                        <stop stopColor="#FFFFFF" stopOpacity="0.18" />
                        <stop offset="1" stopColor="#FFFFFF" stopOpacity="0.04" />
                    </linearGradient>
                </defs>

                <path
                    d="M18 20.5C18 17.4624 20.4624 15 23.5 15H40.5C43.5376 15 46 17.4624 46 20.5V34.5C46 37.5376 43.5376 40 40.5 40H32.8L26.6 45.7C25.6 46.62 24 45.9 24 44.53V40H23.5C20.4624 40 18 37.5376 18 34.5V20.5Z"
                    fill="url(#lens-bubble)"
                    stroke="rgba(255,255,255,0.14)"
                />

                <circle cx="32" cy="28" r="12.5" stroke="url(#lens-ring)" strokeWidth="2.4" />
                <circle cx="32" cy="28" r="7.5" stroke="rgba(255,255,255,0.75)" strokeWidth="1.3" />
                <circle cx="32" cy="28" r="3.2" fill="url(#lens-core)" />

                <path d="M32 11.5V17" stroke="rgba(255,255,255,0.66)" strokeWidth="1.6" strokeLinecap="round" />
                <path d="M32 39V44.5" stroke="rgba(255,255,255,0.66)" strokeWidth="1.6" strokeLinecap="round" />
                <path d="M15.5 28H21" stroke="rgba(255,255,255,0.66)" strokeWidth="1.6" strokeLinecap="round" />
                <path d="M43 28H48.5" stroke="rgba(255,255,255,0.66)" strokeWidth="1.6" strokeLinecap="round" />

                <circle cx="47.5" cy="18.5" r="2.5" fill="#22D3EE" fillOpacity="0.95" />
                <circle cx="47.5" cy="18.5" r="5.2" stroke="#22D3EE" strokeOpacity="0.18" />
            </svg>
        </div>
    );
}
