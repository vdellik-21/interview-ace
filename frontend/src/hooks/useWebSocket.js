/**
 * InterviewAce — useWebSocket Hook
 * Manages WebSocket connection to backend with auto-reconnect.
 *
 * Owner: Dev 3
 */

import { useRef, useEffect, useCallback, useState } from 'react';

const BACKEND_WS_URL = 'ws://localhost:8000/api/copilot';

export default function useWebSocket(sessionId, onMessage) {
    const wsRef = useRef(null);
    const [isConnected, setIsConnected] = useState(false);
    const reconnectTimeout = useRef(null);
    const retryDelay = useRef(1000);

    const connect = useCallback(() => {
        if (!sessionId) return;

        const ws = new WebSocket(`${BACKEND_WS_URL}/${sessionId}`);
        wsRef.current = ws;

        ws.onopen = () => {
            setIsConnected(true);
            retryDelay.current = 1000; // Reset retry delay on success
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                onMessage(data);
            } catch (err) {
                console.error('[WS] Failed to parse message:', err);
            }
        };

        ws.onclose = () => {
            setIsConnected(false);
            // Auto-reconnect with exponential backoff
            reconnectTimeout.current = setTimeout(() => {
                retryDelay.current = Math.min(retryDelay.current * 2, 10000);
                connect();
            }, retryDelay.current);
        };

        ws.onerror = (err) => {
            console.error('[WS] Error:', err);
        };
    }, [sessionId, onMessage]);

    useEffect(() => {
        connect();
        return () => {
            if (wsRef.current) wsRef.current.close();
            if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
        };
    }, [connect]);

    const send = useCallback((data) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(data));
        }
    }, []);

    return { send, isConnected, ws: wsRef };
}
