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
const OVERLAY_MIN_WIDTH = 340;
const OVERLAY_MIN_HEIGHT = 420;

function log(message, extra) {
    const timestamp = new Date().toISOString();
    if (extra === undefined) {
        console.log(`[${timestamp}] [electron] ${message}`);
        return;
    }
    console.log(`[${timestamp}] [electron] ${message}`, extra);
}

// ─── Prep Dashboard Window ──────────────────────
function createMainWindow() {
    log('Creating main dashboard window');
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
    log(`Main dashboard loading ${FRONTEND_URL}`);

    mainWindow.on('closed', () => {
        log('Main dashboard window closed');
        mainWindow = null;
    });
}

// ─── Stealth Overlay Window ─────────────────────
function createStealthWindow() {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;
    log('Creating stealth overlay window', { width, height });

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
        movable: true,             // User can move
        minWidth: OVERLAY_MIN_WIDTH,
        minHeight: OVERLAY_MIN_HEIGHT,

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
    mainWindow.setContentProtection(true);

    // Not visible in Mission Control / Alt-Tab / App Switcher
    stealthWindow.setVisibleOnAllWorkspaces(true, {
        visibleOnFullScreen: true,
    });

    // Load the overlay page
    stealthWindow.loadURL(`${FRONTEND_URL}/overlay`);
    log(`Stealth overlay loading ${FRONTEND_URL}/overlay`);

    // Start hidden — user launches from prep dashboard
    stealthWindow.hide();
    log('Stealth overlay created hidden');

    stealthWindow.on('closed', () => {
        log('Stealth overlay window closed');
        stealthWindow = null;
    });
}

function clampOverlayBounds(bounds) {
    const display = stealthWindow
        ? screen.getDisplayMatching(stealthWindow.getBounds())
        : screen.getPrimaryDisplay();
    const workArea = display.workArea;

    const width = Math.max(
        OVERLAY_MIN_WIDTH,
        Math.min(Number(bounds.width) || OVERLAY_MIN_WIDTH, workArea.width),
    );
    const height = Math.max(
        OVERLAY_MIN_HEIGHT,
        Math.min(Number(bounds.height) || OVERLAY_MIN_HEIGHT, workArea.height),
    );

    const maxX = workArea.x + workArea.width - width;
    const maxY = workArea.y + workArea.height - height;
    const x = Math.max(
        workArea.x,
        Math.min(Number(bounds.x) || workArea.x, maxX),
    );
    const y = Math.max(
        workArea.y,
        Math.min(Number(bounds.y) || workArea.y, maxY),
    );

    return { x, y, width, height };
}

// ─── Keyboard Shortcuts ─────────────────────────
function registerShortcuts() {
    const { width } = screen.getPrimaryDisplay().workAreaSize;
    log('Registering global shortcuts');

    // Toggle overlay visibility
    globalShortcut.register('CommandOrControl+Shift+H', () => {
        if (!stealthWindow) return;
        if (stealthWindow.isVisible()) {
            log('Shortcut triggered: hide overlay');
            stealthWindow.hide();
        } else {
            log('Shortcut triggered: show overlay');
            stealthWindow.show();
        }
    });

    // PANIC — instantly hide overlay
    globalShortcut.register('CommandOrControl+Shift+P', () => {
        log('Shortcut triggered: panic hide');
        if (stealthWindow) stealthWindow.hide();
    });

    // Move overlay left ↔ right
    globalShortcut.register('CommandOrControl+Shift+L', () => {
        if (!stealthWindow) return;
        const bounds = stealthWindow.getBounds();
        if (bounds.x > width / 2) {
            log('Shortcut triggered: move overlay to left');
            stealthWindow.setPosition(10, 50);      // Move to left
        } else {
            log('Shortcut triggered: move overlay to right');
            stealthWindow.setPosition(width - 430, 50); // Move to right
        }
    });

    // Font size controls
    globalShortcut.register('CommandOrControl+Shift+=', () => {
        if (stealthWindow) {
            log('Shortcut triggered: increase font size');
            stealthWindow.webContents.send('font-size', 'increase');
        }
    });
    globalShortcut.register('CommandOrControl+Shift+-', () => {
        if (stealthWindow) {
            log('Shortcut triggered: decrease font size');
            stealthWindow.webContents.send('font-size', 'decrease');
        }
    });

    // Regenerate answer
    globalShortcut.register('CommandOrControl+Shift+R', () => {
        if (stealthWindow) {
            log('Shortcut triggered: regenerate answer');
            stealthWindow.webContents.send('action', 'regenerate');
        }
    });

    // Force answer immediately
    globalShortcut.register('CommandOrControl+Shift+A', () => {
        if (stealthWindow) {
            log('Shortcut triggered: force answer');
            stealthWindow.webContents.send('action', 'force_answer');
        }
    });

    // Shorter answer
    globalShortcut.register('CommandOrControl+Shift+S', () => {
        if (stealthWindow) {
            log('Shortcut triggered: shorter answer');
            stealthWindow.webContents.send('action', 'shorter');
        }
    });

    // More detail
    globalShortcut.register('CommandOrControl+Shift+D', () => {
        if (stealthWindow) {
            log('Shortcut triggered: more detail');
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
        log('No tray icon found, skipping tray');
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
        log('Tray clicked: showing dashboard');
        if (mainWindow) mainWindow.show();
    });
}

// ─── IPC Handlers ───────────────────────────────
function setupIPC() {
    // Main window requests to show the stealth overlay
    ipcMain.on('show-overlay', (_event, sessionId) => {
        log('IPC received: show-overlay');
        if (!stealthWindow) return;

        if (sessionId) {
            const overlayUrl = `${FRONTEND_URL}/overlay?session=${encodeURIComponent(sessionId)}`;
            log(`Loading overlay session ${sessionId}`);
            stealthWindow.loadURL(overlayUrl);
        }

        stealthWindow.show();
    });

    // Main window requests to hide the stealth overlay
    ipcMain.on('hide-overlay', () => {
        log('IPC received: hide-overlay');
        if (stealthWindow) stealthWindow.hide();
    });

    ipcMain.handle('overlay:get-bounds', () => {
        if (!stealthWindow) return null;
        return stealthWindow.getBounds();
    });

    ipcMain.handle('overlay:set-bounds', (_event, nextBounds) => {
        if (!stealthWindow || !nextBounds || typeof nextBounds !== 'object') {
            return null;
        }

        const currentBounds = stealthWindow.getBounds();
        const mergedBounds = {
            x: nextBounds.x ?? currentBounds.x,
            y: nextBounds.y ?? currentBounds.y,
            width: nextBounds.width ?? currentBounds.width,
            height: nextBounds.height ?? currentBounds.height,
        };
        const clampedBounds = clampOverlayBounds(mergedBounds);

        stealthWindow.setBounds(clampedBounds);
        return stealthWindow.getBounds();
    });
}

// ─── App Lifecycle ──────────────────────────────
app.whenReady().then(() => {
    createMainWindow();
    createStealthWindow();
    registerShortcuts();
    createTray();
    setupIPC();

    log('InterviewAce Electron app started');
    log('Shortcut help: Ctrl+Shift+A force answer now');
    log('Shortcut help: Ctrl+Shift+H toggle overlay');
    log('Shortcut help: Ctrl+Shift+P panic hide');
});

app.on('window-all-closed', () => {
    // On macOS, don't quit when all windows close
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    log('Electron activate event received');
    if (mainWindow === null) {
        createMainWindow();
    }
});

app.on('will-quit', () => {
    log('Electron will quit; unregistering shortcuts');
    globalShortcut.unregisterAll();
});
