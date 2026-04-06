/**
 * InterviewAce — Electron Preload Script
 * Secure bridge between main process and renderer.
 * Exposes IPC channels to the React app.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Overlay controls
    showOverlay: (sessionId) => ipcRenderer.send('show-overlay', sessionId),
    goLive: (sessionId) => ipcRenderer.send('go-live', sessionId),
    endSession: () => ipcRenderer.send('end-session'),
    hideOverlay: () => ipcRenderer.send('hide-overlay'),
    getOverlayBounds: () => ipcRenderer.invoke('overlay:get-bounds'),
    setOverlayBounds: (bounds) => ipcRenderer.invoke('overlay:set-bounds', bounds),
    getOverlayClickThrough: () => ipcRenderer.invoke('overlay:get-click-through'),
    setOverlayClickThrough: (enabled) => ipcRenderer.invoke('overlay:set-click-through', enabled),

    // Listen for actions from keyboard shortcuts
    onAction: (callback) => {
        ipcRenderer.on('action', (_event, action) => callback(action));
    },

    // Listen for font size changes
    onFontSize: (callback) => {
        ipcRenderer.on('font-size', (_event, direction) => callback(direction));
    },

    onOverlayClickThrough: (callback) => {
        ipcRenderer.on('overlay-click-through', (_event, enabled) => callback(enabled));
    },

    onSessionStatusChanged: (callback) => {
        ipcRenderer.on('session-status-changed', (_event, payload) => callback(payload));
    },

    // Check if running inside Electron
    isElectron: true,
});
