/**
 * InterviewAce — Electron Main Process
 * Creates and manages the stealth overlay window.
 * FULL STEALTH: Hides backend terminal, tray, dock, and dashboard during live interviews.
 *
 * Owner: Dev 3
 * Key API: setContentProtection(true) — makes window invisible to screen share
 */

const { app, BrowserWindow, screen, Tray, Menu, globalShortcut, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let mainWindow = null;       // Prep dashboard (normal window)
let stealthWindow = null;    // Interview overlay (stealth window)
let tray = null;
let backendProcess = null;   // Python backend — runs silently, no terminal
let frontendProcess = null;  // Vite dev server — runs silently, no terminal
let isLive = false;          // Track if we're in full stealth mode
let overlayClickThrough = false;

const FRONTEND_URL = 'http://localhost:5173';
const BACKEND_PORT = 8000;
const OVERLAY_MIN_WIDTH = 340;
const OVERLAY_MIN_HEIGHT = 420;
const APP_ICON_PATH = path.join(__dirname, 'assets', 'interviewace-interview-lens.png');

function log(message, extra) {
    const timestamp = new Date().toISOString();
    if (extra === undefined) {
        console.log(`[${timestamp}] [electron] ${message}`);
        return;
    }
    console.log(`[${timestamp}] [electron] ${message}`, extra);
}

function applyAppIcon() {
    if (process.platform === 'darwin' && app.dock) {
        app.dock.setIcon(APP_ICON_PATH);
    }
}

function applyMacGlassEffect(windowInstance, { vibrancy = 'under-window' } = {}) {
    if (process.platform !== 'darwin' || !windowInstance) {
        return;
    }

    try {
        if (typeof windowInstance.setVibrancy === 'function') {
            windowInstance.setVibrancy(vibrancy);
        }
        if (typeof windowInstance.setVisualEffectState === 'function') {
            windowInstance.setVisualEffectState('active');
        }
    } catch (error) {
        log('Unable to apply macOS glass effect', error?.message || error);
    }
}

function setOverlayClickThrough(enabled) {
    overlayClickThrough = Boolean(enabled);

    if (!stealthWindow) {
        return overlayClickThrough;
    }

    stealthWindow.setIgnoreMouseEvents(overlayClickThrough, { forward: true });
    stealthWindow.setFocusable(!overlayClickThrough);

    if (!overlayClickThrough) {
        stealthWindow.focus();
    }

    stealthWindow.webContents.send('overlay-click-through', overlayClickThrough);
    log(`Overlay click-through ${overlayClickThrough ? 'enabled' : 'disabled'}`);
    return overlayClickThrough;
}

// ─── SILENT SERVER LAUNCHERS ─────────────────────
// These start the backend and frontend WITHOUT opening any terminal windows.
// The user double-clicks the app — no terminals ever appear.

function startBackendSilently() {
    /**
     * Launches the Python FastAPI server as a hidden child process.
     * No terminal window opens. No visible output.
     * When Electron quits, the backend dies with it.
     */
    const backendDir = path.join(__dirname, '..', 'backend');
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    backendProcess = spawn(
        pythonCmd,
        ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
        {
            cwd: backendDir,
            stdio: 'ignore',       // No terminal output at all
            detached: false,       // Dies when Electron closes
            windowsHide: true,     // Hide console window on Windows
            env: {
                ...process.env,
                PYTHONDONTWRITEBYTECODE: '1',
            },
        }
    );

    backendProcess.on('error', (err) => {
        log('Backend failed to start: ' + err.message);
    });

    backendProcess.on('exit', (code) => {
        log('Backend exited with code ' + code);
        backendProcess = null;
    });

    log('Backend started silently on port ' + BACKEND_PORT);
}

function startFrontendSilently() {
    /**
     * Launches the Vite dev server as a hidden child process.
     * No terminal window opens.
     */
    const frontendDir = path.join(__dirname, '..', 'frontend');
    const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';

    frontendProcess = spawn(
        npmCmd,
        ['run', 'dev'],
        {
            cwd: frontendDir,
            stdio: 'ignore',       // No terminal output
            detached: false,       // Dies when Electron closes
            windowsHide: true,     // Hide on Windows
            env: process.env,
        }
    );

    frontendProcess.on('error', (err) => {
        log('Frontend failed to start: ' + err.message);
    });

    log('Frontend started silently on port 5173');
}

function killSilentProcesses() {
    /**
     * Clean up background processes when app quits.
     */
    if (backendProcess) {
        backendProcess.kill();
        backendProcess = null;
        log('Backend process killed');
    }
    if (frontendProcess) {
        frontendProcess.kill();
        frontendProcess = null;
        log('Frontend process killed');
    }
}


// ─── Prep Dashboard Window ──────────────────────
function createMainWindow() {
    log('Creating main dashboard window');
    mainWindow = new BrowserWindow({
        width: 900,
        height: 700,
        title: 'InterviewAce',
        icon: APP_ICON_PATH,
        transparent: true,
        backgroundColor: '#00000000',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
        },
    });

    // Dashboard is ALSO invisible to screen share
    mainWindow.setContentProtection(true);
    applyMacGlassEffect(mainWindow);

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
        backgroundColor: '#00000000',
        alwaysOnTop: true,         // Stays above Zoom/Meet/Teams
        skipTaskbar: true,         // Not visible in taskbar / dock
        hasShadow: false,          // No window shadow
        focusable: true,           // Can receive keyboard input
        resizable: true,           // User can resize
        movable: true,             // User can move
        minWidth: OVERLAY_MIN_WIDTH,
        minHeight: OVERLAY_MIN_HEIGHT,
        icon: APP_ICON_PATH,

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
    // Keep the overlay visually clear instead of using tinted macOS vibrancy.
    applyMacGlassEffect(stealthWindow, { vibrancy: null });

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

// ─── FULL STEALTH MODE ──────────────────────────
// When "Go Live" is clicked, EVERYTHING disappears except the overlay.
// From the outside it looks like no app is running at all.

function enterFullStealth() {
    /**
     * Activated when the interview starts. Hides:
     * 1. Dashboard window → hidden
     * 2. Tray icon → destroyed (nothing in menu bar)
     * 3. Dock icon (Mac) → hidden
     * 4. Only the invisible overlay remains
     */
    isLive = true;

    // 1. Hide the prep dashboard
    if (mainWindow) {
        mainWindow.hide();
    }

    // 2. Destroy tray icon — nothing visible in menu bar
    if (tray) {
        tray.destroy();
        tray = null;
    }

    // 3. Mac: hide from Dock completely
    if (process.platform === 'darwin' && app.dock) {
        app.dock.hide();
    }

    // 4. Show the stealth overlay (invisible to screen share)
    if (stealthWindow) {
        stealthWindow.show();
    }

    log('FULL STEALTH MODE ACTIVE — app is completely invisible');
}

function exitFullStealth() {
    /**
     * When the interview ends, restore everything:
     * Dashboard, tray, and dock all come back.
     */
    isLive = false;

    // Restore Dock on Mac
    if (process.platform === 'darwin' && app.dock) {
        app.dock.show();
    }

    // Recreate tray icon
    createTray();

    // Hide overlay, show dashboard
    if (stealthWindow) {
        stealthWindow.hide();
    }
    if (mainWindow) {
        mainWindow.show();
        mainWindow.webContents.send('session-status-changed', { status: 'ready' });
    }

    log('Stealth mode deactivated — app restored');
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

    globalShortcut.register('Escape', () => {
        if (!stealthWindow) return;
        log('Shortcut triggered: toggle click-through');
        setOverlayClickThrough(!overlayClickThrough);
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

    // ─── FULL STEALTH: Go Live / End Session ────
    ipcMain.on('go-live', (_event, sessionId) => {
        log('IPC received: go-live — entering full stealth');
        if (stealthWindow && sessionId) {
            const overlayUrl = `${FRONTEND_URL}/overlay?session=${encodeURIComponent(sessionId)}`;
            stealthWindow.loadURL(overlayUrl);
        }
        enterFullStealth();
    });

    ipcMain.on('end-session', () => {
        log('IPC received: end-session — exiting stealth');
        exitFullStealth();
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

    ipcMain.handle('overlay:get-click-through', () => overlayClickThrough);

    ipcMain.handle('overlay:set-click-through', (_event, enabled) => {
        return setOverlayClickThrough(enabled);
    });
}

// ─── App Lifecycle ──────────────────────────────
app.whenReady().then(() => {
    applyAppIcon();

    // Start backend and frontend silently — no terminals open
    startBackendSilently();
    startFrontendSilently();

    // Wait a moment for servers to start, then create windows
    setTimeout(() => {
        createMainWindow();
        createStealthWindow();
        registerShortcuts();
        createTray();
        setupIPC();

        log('InterviewAce started — all servers running silently');
        log('Shortcut help: Esc toggle click-through');
        log('Shortcut help: Ctrl+Shift+A force answer now');
        log('Shortcut help: Ctrl+Shift+H toggle overlay');
        log('Shortcut help: Ctrl+Shift+P panic hide');
    }, 2000); // 2 second delay for servers to be ready
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
    log('Electron will quit; cleaning up');
    globalShortcut.unregisterAll();
    killSilentProcesses();
});
