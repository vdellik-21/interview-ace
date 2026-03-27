/**
 * InterviewAce — App Icon
 * Apple Health-inspired rounded tile used in the dashboard header.
 */

export default function AppIcon({ className = 'h-10 w-10' }) {
    return (
        <div
            className={`relative overflow-hidden rounded-[22px] border border-white/50 bg-white shadow-[0_16px_40px_rgba(255,255,255,0.18)] ${className}`}
            aria-hidden="true"
        >
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_25%,rgba(255,255,255,0.95),rgba(255,255,255,0.78)_45%,rgba(255,255,255,0.55)_100%)]" />
            <svg
                viewBox="0 0 64 64"
                className="absolute inset-0 h-full w-full drop-shadow-[0_8px_16px_rgba(236,72,153,0.28)]"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
            >
                <defs>
                    <linearGradient id="health-heart-fill" x1="16" y1="12" x2="48" y2="52" gradientUnits="userSpaceOnUse">
                        <stop stopColor="#FF7AA8" />
                        <stop offset="0.55" stopColor="#FF4F8C" />
                        <stop offset="1" stopColor="#FF2D55" />
                    </linearGradient>
                    <linearGradient id="health-glow-fill" x1="12" y1="8" x2="56" y2="60" gradientUnits="userSpaceOnUse">
                        <stop stopColor="#FFD7E5" stopOpacity="0.85" />
                        <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
                    </linearGradient>
                </defs>
                <path
                    d="M32 52C28.1 48.7 24.9 45.8 22.4 43.2C19.9 40.6 17.8 38.3 16.2 36.2C14.7 34.2 13.6 32.2 12.9 30.3C12.3 28.5 12 26.6 12 24.7C12 20.9 13.3 17.8 15.8 15.5C18.4 13.2 21.6 12 25.4 12C27.6 12 29.7 12.5 31.6 13.6C33.5 14.7 35 16.2 36 18.1C37.1 16.2 38.6 14.7 40.5 13.6C42.4 12.5 44.5 12 46.7 12C50.5 12 53.7 13.2 56.2 15.5C58.8 17.8 60 20.9 60 24.7C60 26.6 59.7 28.5 59.1 30.3C58.5 32.2 57.4 34.2 55.8 36.2C54.3 38.3 52.2 40.6 49.7 43.2C47.2 45.8 44 48.7 40 52L36 55.4C34.9 56.3 33.6 56.8 32 56.8C30.4 56.8 29.1 56.3 28 55.4L32 52Z"
                    fill="url(#health-heart-fill)"
                />
                <path
                    d="M22 16.5C24 14.6 26.6 13.6 29.5 13.6C31.1 13.6 32.8 14 34.3 14.8C32.9 15.8 31.8 17 30.9 18.5C29.8 17.1 28.5 16 27 15.4C25.5 14.8 23.7 14.7 22 15.1V16.5Z"
                    fill="url(#health-glow-fill)"
                />
            </svg>
        </div>
    );
}
