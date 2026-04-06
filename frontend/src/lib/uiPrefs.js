export const UI_PREF_KEYS = {
    theme: 'interviewace-theme',
    dashboardOpacity: 'interviewace-dashboard-opacity',
    overlayOpacity: 'interviewace-overlay-opacity',
    overlayClickThrough: 'interviewace-overlay-click-through',
};

export function readUiPref(key, fallbackValue) {
    if (typeof window === 'undefined') {
        return fallbackValue;
    }

    try {
        const stored = window.localStorage.getItem(key);
        if (stored === null) {
            return fallbackValue;
        }
        return JSON.parse(stored);
    } catch {
        return fallbackValue;
    }
}

export function writeUiPref(key, value) {
    if (typeof window === 'undefined') {
        return;
    }

    try {
        window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
        // Ignore storage failures and keep UI responsive.
    }
}

export function backgroundAlphaFromLevel(level, minAlpha = 0.02, maxAlpha = 0.96) {
    const numeric = Number(level);
    if (Number.isNaN(numeric)) {
        return maxAlpha;
    }

    const clamped = Math.max(0, Math.min(10, numeric));
    const ratio = clamped / 10;
    return maxAlpha - ratio * (maxAlpha - minAlpha);
}
