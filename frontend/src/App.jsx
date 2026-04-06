/**
 * InterviewAce — App Root
 *
 * Two routes:
 *   / → PrepDashboard (upload files, configure, start session)
 *   /overlay → StealthOverlay (live interview panel)
 *
 * Owner: Dev 3
 */

import { useState, useEffect } from 'react';
import PrepDashboard from './pages/PrepDashboard';
import StealthOverlay from './pages/StealthOverlay';

export default function App() {
    const [route, setRoute] = useState('/');

    useEffect(() => {
        // Simple hash-based routing
        const handleRoute = () => {
            const path = window.location.pathname;
            setRoute(path);
        };
        handleRoute();
        window.addEventListener('popstate', handleRoute);
        return () => window.removeEventListener('popstate', handleRoute);
    }, []);

    useEffect(() => {
        const isOverlayRoute = route === '/overlay';
        document.documentElement.classList.toggle('overlay-mode', isOverlayRoute);
        document.body.classList.toggle('overlay-mode', isOverlayRoute);

        return () => {
            document.documentElement.classList.remove('overlay-mode');
            document.body.classList.remove('overlay-mode');
        };
    }, [route]);

    if (route === '/overlay') {
        return <StealthOverlay />;
    }

    return <PrepDashboard />;
}
