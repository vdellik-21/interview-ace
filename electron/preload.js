/**
 * InterviewAce — Electron Preload Script
 * Secure bridge between main process and renderer.
 * Exposes IPC channels to the React app.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Overlay controls
    showOverlay: () => ipcRenderer.send('show-overlay'),
    hideOverlay: () => ipcRenderer.send('hide-overlay'),

    // Listen for actions from keyboard shortcuts
    onAction: (callback) => {
        ipcRenderer.on('action', (_event, action) => callback(action));
    },

    // Listen for font size changes
    onFontSize: (callback) => {
        ipcRenderer.on('font-size', (_event, direction) => callback(direction));
    },

    // Check if running inside Electron
    isElectron: true,
});
