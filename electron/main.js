/**
 * InterviewAce — Electron Main Process
 * Creates and manages the stealth overlay window.
 *
 * Owner: Dev 3
 * Key API: setContentProtection(true) — makes window invisible to screen share
 */

const { app, BrowserWindow, screen, Tray, Menu, globalShortcut, ipcMain } = require('electron');
const path = require('path');

let mainWindow = null;     // Prep dashboard (normal window)
let stealthWindow = null;  // Interview overlay (stealth window)
let tray = null;

const FRONTEND_URL = 'http://localhost:5173';

// ─── Prep Dashboard Window ──────────────────────
function createMainWindow() {
    mainWindow = new BrowserWindow({
        width: 900,
        height: 700,
        title: 'InterviewAce',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
        },
    });

    mainWindow.loadURL(FRONTEND_URL);

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// ─── Stealth Overlay Window ─────────────────────
function createStealthWindow() {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;

    stealthWindow = new BrowserWindow({
        // Position: right side of screen
        width: 420,
        height: height - 100,
        x: width - 430,
        y: 50,

        // ═══ STEALTH PROPERTIES ═══
        frame: false,              // No window chrome / title bar
        transparent: true,         // Transparent background
        alwaysOnTop: true,         // Stays above Zoom/Meet/Teams
        skipTaskbar: true,         // Not visible in taskbar / dock
        hasShadow: false,          // No window shadow
        focusable: true,           // Can receive keyboard input
        resizable: true,           // User can resize

        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
        },
    });

    // ═══════════════════════════════════════════════════
    // THIS IS THE KEY LINE — makes the overlay INVISIBLE
    // to screen share, screenshots, and screen recording
    // ═══════════════════════════════════════════════════
    stealthWindow.setContentProtection(true);

    // Not visible in Mission Control / Alt-Tab / App Switcher
    stealthWindow.setVisibleOnAllWorkspaces(true, {
        visibleOnFullScreen: true,
    });

    // Load the overlay page
    stealthWindow.loadURL(`${FRONTEND_URL}/overlay`);

    // Start hidden — user launches from prep dashboard
    stealthWindow.hide();

    stealthWindow.on('closed', () => {
        stealthWindow = null;
    });
}

// ─── Keyboard Shortcuts ─────────────────────────
function registerShortcuts() {
    const { width } = screen.getPrimaryDisplay().workAreaSize;

    // Toggle overlay visibility
    globalShortcut.register('CommandOrControl+Shift+H', () => {
        if (!stealthWindow) return;
        if (stealthWindow.isVisible()) {
            stealthWindow.hide();
        } else {
            stealthWindow.show();
        }
    });

    // PANIC — instantly hide overlay
    globalShortcut.register('CommandOrControl+Shift+P', () => {
        if (stealthWindow) stealthWindow.hide();
    });

    // Move overlay left ↔ right
    globalShortcut.register('CommandOrControl+Shift+L', () => {
        if (!stealthWindow) return;
        const bounds = stealthWindow.getBounds();
        if (bounds.x > width / 2) {
            stealthWindow.setPosition(10, 50);      // Move to left
        } else {
            stealthWindow.setPosition(width - 430, 50); // Move to right
        }
    });

    // Font size controls
    globalShortcut.register('CommandOrControl+Shift+=', () => {
        if (stealthWindow) {
            stealthWindow.webContents.send('font-size', 'increase');
        }
    });
    globalShortcut.register('CommandOrControl+Shift+-', () => {
        if (stealthWindow) {
            stealthWindow.webContents.send('font-size', 'decrease');
        }
    });

    // Regenerate answer
    globalShortcut.register('CommandOrControl+Shift+R', () => {
        if (stealthWindow) {
            stealthWindow.webContents.send('action', 'regenerate');
        }
    });

    // Shorter answer
    globalShortcut.register('CommandOrControl+Shift+S', () => {
        if (stealthWindow) {
            stealthWindow.webContents.send('action', 'shorter');
        }
    });

    // More detail
    globalShortcut.register('CommandOrControl+Shift+D', () => {
        if (stealthWindow) {
            stealthWindow.webContents.send('action', 'more_detail');
        }
    });
}

// ─── System Tray ────────────────────────────────
function createTray() {
    // TODO (Dev 3): Create a proper 16x16 tray icon
    // For now, use a placeholder
    try {
        tray = new Tray(path.join(__dirname, 'assets', 'tray-icon.png'));
    } catch {
        // If no icon file, skip tray
        console.log('[Electron] No tray icon found, skipping tray');
        return;
    }

    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Show Dashboard',
            click: () => {
                if (mainWindow) mainWindow.show();
            },
        },
        {
            label: 'Toggle Overlay',
            accelerator: 'CmdOrCtrl+Shift+H',
            click: () => {
                if (stealthWindow) {
                    stealthWindow.isVisible()
                        ? stealthWindow.hide()
                        : stealthWindow.show();
                }
            },
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => app.quit(),
        },
    ]);

    tray.setToolTip('InterviewAce');
    tray.setContextMenu(contextMenu);

    tray.on('click', () => {
        if (mainWindow) mainWindow.show();
    });
}

// ─── IPC Handlers ───────────────────────────────
function setupIPC() {
    // Main window requests to show the stealth overlay
    ipcMain.on('show-overlay', () => {
        if (stealthWindow) stealthWindow.show();
    });

    // Main window requests to hide the stealth overlay
    ipcMain.on('hide-overlay', () => {
        if (stealthWindow) stealthWindow.hide();
    });
}

// ─── App Lifecycle ──────────────────────────────
app.whenReady().then(() => {
    createMainWindow();
    createStealthWindow();
    registerShortcuts();
    createTray();
    setupIPC();

    console.log('🎯 InterviewAce Electron app started');
    console.log('   Ctrl+Shift+H → Toggle overlay');
    console.log('   Ctrl+Shift+P → Panic hide');
});

app.on('window-all-closed', () => {
    // On macOS, don't quit when all windows close
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createMainWindow();
    }
});

app.on('will-quit', () => {
    globalShortcut.unregisterAll();
});
