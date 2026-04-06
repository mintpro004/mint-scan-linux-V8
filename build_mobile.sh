#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║   MINT SCAN v8 — CROSS-PLATFORM MOBILE APP BUILDER          ║
# ║   Android APK · iOS PWA · Windows EXE · macOS APP           ║
# ╚══════════════════════════════════════════════════════════════╝
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
OUT="$DIR/mobile_builds"
mkdir -p "$OUT"

# Determine what to build
BUILD_ANDROID=false; BUILD_IOS=false; BUILD_WINDOWS=false; BUILD_MACOS=false
[ $# -eq 0 ] && BUILD_ANDROID=true && BUILD_IOS=true && BUILD_WINDOWS=true && BUILD_MACOS=true
for a in "$@"; do
  case $a in android) BUILD_ANDROID=true ;; ios) BUILD_IOS=true ;;
    windows) BUILD_WINDOWS=true ;; macos|mac) BUILD_MACOS=true ;;
    all) BUILD_ANDROID=true;BUILD_IOS=true;BUILD_WINDOWS=true;BUILD_MACOS=true ;;
  esac
done

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   MINT SCAN v8 — MOBILE APP BUILDER                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─────────────────────────────────────────────────────────────────
# SHARED: Generate manifest.json and service worker
# ─────────────────────────────────────────────────────────────────
make_pwa_assets() {
  local dst="$1"
  cat > "$dst/manifest.json" << 'MANIFEST'
{
  "name": "Mint Scan v8",
  "short_name": "MintScan",
  "description": "Advanced Security Auditor — Mint Projects, Pretoria",
  "start_url": "./index.html",
  "display": "standalone",
  "background_color": "#05111f",
  "theme_color": "#00ffe0",
  "orientation": "portrait-primary",
  "icons": [
    {"src": "icon-192.png","sizes": "192x192","type": "image/png","purpose": "any maskable"},
    {"src": "icon-512.png","sizes": "512x512","type": "image/png","purpose": "any maskable"}
  ],
  "categories": ["security","utilities","productivity"],
  "shortcuts": [
    {"name":"Security Scan","url":"./index.html","description":"Run full security scan"},
    {"name":"Network Monitor","url":"./index.html","description":"Monitor network"}
  ]
}
MANIFEST

  cat > "$dst/sw.js" << 'SWEOF'
const CACHE_NAME = 'mintscan-v8-cache';
const ASSETS = ['./index.html','./manifest.json'];
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)));
});
self.addEventListener('activate', e => {
  e.waitUntil(clients.claim());
});
self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).catch(() => caches.match('./index.html')))
  );
});
SWEOF
}

# ─────────────────────────────────────────────────────────────────
# ANDROID — PWA installable + ADB push method
# ─────────────────────────────────────────────────────────────────
if [ "$BUILD_ANDROID" = true ]; then
  echo -e "${YELLOW}[ANDROID] Building Android package...${NC}"
  A="$OUT/android"; mkdir -p "$A"

  # Copy and patch the mobile app
  cp "$DIR/mint_scan_android.html" "$A/index.html"
  make_pwa_assets "$A"

  # Inject SW registration + manifest link into HTML
  sed -i 's|</head>|<link rel="manifest" href="./manifest.json">\n<meta name="theme-color" content="#00ffe0">\n</head>|' "$A/index.html"
  sed -i 's|</body>|<script>if("serviceWorker"in navigator){navigator.serviceWorker.register("./sw.js").then(()=>console.log("SW ok")).catch(e=>console.warn("SW:",e));}</script>\n</body>|' "$A/index.html"

  # Create ADB push + open script
  cat > "$A/install_via_adb.sh" << 'ADBSH'
#!/bin/bash
# Push Mint Scan mobile app to phone via ADB and open it
set -e
CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=9876

echo -e "${CYAN}Mint Scan v8 — Android ADB Installer${NC}"

if ! command -v adb &>/dev/null; then
  echo -e "${RED}ADB not found. Run: sudo apt-get install adb${NC}"; exit 1
fi

DEVICES=$(adb devices 2>/dev/null | grep -v "^List\|^$\|offline" | grep -c "device$")
if [ "$DEVICES" -eq 0 ]; then
  echo -e "${RED}No Android device found.${NC}"
  echo "1. Connect USB cable"
  echo "2. Enable USB Debugging (Settings → Developer Options)"
  echo "3. Tap ALLOW on phone"
  exit 1
fi

SERIAL=$(adb devices | grep -v "^List\|^$\|offline" | grep "device$" | head -1 | awk '{print $1}')
echo -e "${GREEN}Device: $SERIAL${NC}"

# Method 1: ADB reverse + Python HTTP server (best for Android 16)
echo "Starting HTTP server on port $PORT..."
cd "$DIR"
if command -v python3 &>/dev/null; then
  python3 -m http.server $PORT --bind 127.0.0.1 &
  SERVER_PID=$!
  sleep 1
  adb -s "$SERIAL" reverse tcp:$PORT tcp:$PORT
  URL="http://localhost:$PORT/index.html"
  echo -e "${GREEN}Opening: $URL${NC}"
  # Try multiple browsers
  for pkg in com.android.chrome com.sec.android.app.sbrowser org.mozilla.firefox; do
    adb -s "$SERIAL" shell am start -a android.intent.action.VIEW -d "$URL" -p "$pkg" 2>/dev/null && break
  done
  adb -s "$SERIAL" shell am start -a android.intent.action.VIEW -d "$URL" 2>/dev/null || true
  echo ""
  echo -e "${GREEN}✓ Companion open on phone at: $URL${NC}"
  echo "Server PID: $SERVER_PID (Ctrl+C to stop)"
  echo ""
  echo "To add as app: In Chrome menu → 'Add to Home Screen'"
  wait $SERVER_PID
else
  # Fallback: push to sdcard and open via Firefox (supports file://)
  adb -s "$SERIAL" push "$DIR/index.html" /sdcard/Download/MintScan.html
  adb -s "$SERIAL" shell am start -a android.intent.action.VIEW \
    -d "file:///sdcard/Download/MintScan.html" -p org.mozilla.firefox 2>/dev/null || \
  adb -s "$SERIAL" shell am start -n com.android.htmlviewer/.HTMLViewerActivity \
    -a android.intent.action.VIEW -d "file:///sdcard/Download/MintScan.html" 2>/dev/null || \
    echo "Open file manually: Files → Download → MintScan.html (use Firefox, not Chrome)"
fi
ADBSH
  chmod +x "$A/install_via_adb.sh"

  # Create Android README
  cat > "$A/README.txt" << 'ANDREADME'
MINT SCAN v8 — ANDROID INSTALLATION
======================================

METHOD 1 — USB + ADB (Recommended, works on Android 16):
  bash install_via_adb.sh
  Then in Chrome: tap ⋮ menu → "Add to Home Screen"

METHOD 2 — Wi-Fi (No cable needed):
  1. Start Mint Scan desktop: bash run.sh
  2. Open Wireless tab → START SERVER  
  3. Note the URL (e.g. http://192.168.1.100:8765)
  4. Open that URL in your phone's Chrome browser
  5. Tap ⋮ → "Add to Home Screen" to install as app

METHOD 3 — Direct open (Firefox on Android only):
  adb push index.html /sdcard/Download/MintScan.html
  Open Firefox → type: file:///sdcard/Download/MintScan.html

FEATURES (Android):
  ✓ 8-tab security app (Dashboard, Threats, Battery, Network,
    Ports, Device, Sync, Tools)
  ✓ Real-time security score (0-100)
  ✓ Battery API monitoring
  ✓ Network speed test (Cloudflare)
  ✓ WebRTC leak detection
  ✓ Browser port scanner
  ✓ DNS/GeoIP/SSL/Threat intel tools
  ✓ Bi-directional sync with Mint Scan desktop
  ✓ Offline support via Service Worker
  ✓ Works on Android 6+, Chrome 72+

REQUIREMENTS: Android 6.0+, Chrome 72+ or Firefox 68+
ANDREADME

  echo -e "${GREEN}  ✓ Android package → $A/${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# iOS — PWA with Apple-specific meta tags
# ─────────────────────────────────────────────────────────────────
if [ "$BUILD_IOS" = true ]; then
  echo -e "${YELLOW}[iOS] Building iOS PWA package...${NC}"
  I="$OUT/ios"; mkdir -p "$I"

  cp "$DIR/mint_scan_android.html" "$I/index.html"
  make_pwa_assets "$I"

  # Inject iOS-specific meta tags
  sed -i 's|</head>|<link rel="manifest" href="./manifest.json">\n<meta name="apple-mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n<meta name="apple-mobile-web-app-title" content="Mint Scan">\n<meta name="apple-touch-fullscreen" content="yes">\n<link rel="apple-touch-icon" href="./icon-180.png">\n</head>|' "$I/index.html"
  sed -i 's|</body>|<script>if("serviceWorker"in navigator){navigator.serviceWorker.register("./sw.js");}</script>\n</body>|' "$I/index.html"

  cat > "$I/README.txt" << 'IOSREADME'
MINT SCAN v8 — iOS INSTALLATION
==================================
iOS does not allow sideloading APKs. Use the Safari PWA method:

INSTALL AS APP (Safari only):
  1. Start Mint Scan desktop: bash run.sh
  2. Open Wireless tab → START SERVER
  3. On iPhone/iPad, open Safari (NOT Chrome/Firefox)
  4. Go to: http://<your-desktop-ip>:8765
  5. Tap Share button (box with ↑ arrow)
  6. Scroll down → "Add to Home Screen"
  7. Tap ADD → Mint Scan icon appears on home screen

FEATURES (iOS):
  ✓ Full-screen standalone app experience
  ✓ Battery monitoring (iOS 16.4+ with Safari)
  ✓ Network monitor and speed test
  ✓ Security scan with scoring
  ✓ Port scanner (browser-based)
  ✓ Privacy/WebRTC check
  ✓ DNS, GeoIP, SSL tools
  ✓ Desktop sync
  ✓ Offline via Service Worker
  ✓ iOS 12.2+, iPadOS 13+

NOTE: Battery API requires iOS 16.4+ and Safari specifically.
IOSREADME

  echo -e "${GREEN}  ✓ iOS package → $I/${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# WINDOWS — Electron desktop app
# ─────────────────────────────────────────────────────────────────
if [ "$BUILD_WINDOWS" = true ]; then
  echo -e "${YELLOW}[WINDOWS] Building Windows Electron app...${NC}"
  W="$OUT/windows"; mkdir -p "$W"
  cp "$DIR/mint_scan_android.html" "$W/index.html"

  cat > "$W/package.json" << 'WINPKG'
{
  "name": "mint-scan-v8",
  "version": "8.0.0",
  "description": "Mint Scan v8 — Advanced Security Auditor by Mint Projects",
  "main": "main.js",
  "author": "Mint Projects PTY (Ltd), Pretoria, South Africa",
  "license": "Proprietary",
  "scripts": {
    "start":     "electron .",
    "build-win": "electron-packager . \"Mint Scan\" --platform=win32 --arch=x64 --out=dist --overwrite --icon=icon.ico --app-version=8.0.0 --win32metadata.ProductName=\"Mint Scan v8\" --win32metadata.CompanyName=\"Mint Projects\"",
    "build-win32":"electron-packager . \"Mint Scan\" --platform=win32 --arch=ia32 --out=dist --overwrite"
  },
  "devDependencies": {
    "electron": "^29.0.0",
    "electron-packager": "^17.1.2"
  }
}
WINPKG

  cat > "$W/main.js" << 'WINMAIN'
'use strict';
const { app, BrowserWindow, Menu, shell } = require('electron');
const path = require('path');

let mainWindow;

app.whenReady().then(() => {
  mainWindow = new BrowserWindow({
    width: 440,
    height: 920,
    minWidth: 380,
    minHeight: 700,
    title: 'Mint Scan v8',
    backgroundColor: '#05111f',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  mainWindow.once('ready-to-show', () => mainWindow.show());

  // Right-click context menu with copy/paste
  mainWindow.webContents.on('context-menu', (_, params) => {
    const menu = Menu.buildFromTemplate([
      { label: 'Copy',       role: 'copy',       enabled: params.selectionText.length > 0 },
      { label: 'Paste',      role: 'paste' },
      { label: 'Select All', role: 'selectAll' },
      { type: 'separator' },
      { label: 'Reload',     click: () => mainWindow.reload() },
      { label: 'Open DevTools', click: () => mainWindow.webContents.openDevTools() },
    ]);
    menu.popup();
  });

  // App menu
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'File', submenu: [
      { label: 'Reload', accelerator: 'F5', click: () => mainWindow.reload() },
      { type: 'separator' },
      { label: 'Quit', accelerator: 'Ctrl+Q', role: 'quit' },
    ]},
    { label: 'Edit', submenu: [
      { label: 'Copy',       role: 'copy' },
      { label: 'Paste',      role: 'paste' },
      { label: 'Select All', role: 'selectAll' },
      { label: 'Undo',       role: 'undo' },
      { label: 'Redo',       role: 'redo' },
    ]},
    { label: 'View', submenu: [
      { label: 'Zoom In',    accelerator: 'Ctrl+=', click: () => { const z = mainWindow.webContents.getZoomLevel(); mainWindow.webContents.setZoomLevel(z + 0.5); }},
      { label: 'Zoom Out',   accelerator: 'Ctrl+-', click: () => { const z = mainWindow.webContents.getZoomLevel(); mainWindow.webContents.setZoomLevel(z - 0.5); }},
      { label: 'Reset Zoom', accelerator: 'Ctrl+0', click: () => mainWindow.webContents.setZoomLevel(0) },
      { type: 'separator' },
      { label: 'DevTools',   accelerator: 'F12',    click: () => mainWindow.webContents.openDevTools() },
    ]},
  ]));
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) app.emit('ready'); });
WINMAIN

  # Windows run script
  cat > "$W/START.bat" << 'WINBAT'
@echo off
title Mint Scan v8
echo ====================================
echo   Mint Scan v8 - Starting...
echo ====================================
echo.

:: Check if Node.js is installed
where node >nul 2>&1
if %errorlevel% neq 0 (
  echo ERROR: Node.js not found.
  echo Download from: https://nodejs.org
  echo Install Node.js then run this script again.
  pause
  exit /b 1
)

:: Install dependencies if needed
if not exist "node_modules" (
  echo Installing Electron (first run takes ~2 minutes)...
  npm install --save-dev electron@29
  if %errorlevel% neq 0 (
    echo Failed to install. Check internet connection.
    pause
    exit /b 1
  )
)

echo Launching Mint Scan v8...
npx electron .
WINBAT

  cat > "$W/BUILD_EXE.bat" << 'WINBUILD'
@echo off
title Mint Scan v8 - Build Windows EXE
echo ====================================
echo   Building Mint Scan v8 Windows EXE
echo ====================================
echo.
where node >nul 2>&1
if %errorlevel% neq 0 ( echo Node.js required: https://nodejs.org && pause && exit /b 1 )
echo [1/3] Installing dependencies...
npm install
echo [2/3] Building 64-bit Windows EXE...
npm run build-win
echo [3/3] Done!
echo.
echo EXE is in: dist\Mint Scan-win32-x64\
echo Run: dist\Mint Scan-win32-x64\Mint Scan.exe
pause
WINBUILD

  cat > "$W/README.txt" << 'WINREADME'
MINT SCAN v8 — WINDOWS INSTALLATION
======================================
REQUIREMENTS: Node.js 18+ from https://nodejs.org (FREE)

METHOD 1 — Run directly (fastest):
  Double-click: START.bat
  (Installs Electron automatically on first run, ~2 min)

METHOD 2 — Build standalone .exe:
  Double-click: BUILD_EXE.bat
  EXE appears in: dist\Mint Scan-win32-x64\Mint Scan.exe
  Copy that folder anywhere — no Node.js needed after build

METHOD 3 — Browser (no install):
  Open index.html in Chrome or Edge

FEATURES:
  ✓ Native Windows window with menus
  ✓ Edit menu: Copy, Paste, Select All, Undo, Redo
  ✓ Right-click context menu
  ✓ Ctrl+C/V/A keyboard shortcuts
  ✓ Zoom controls (Ctrl +/-/0)
  ✓ All 8 mobile security tabs
  ✓ Desktop sync to Mint Scan Linux
  ✓ Offline capable
WINREADME

  echo -e "${GREEN}  ✓ Windows package → $W/${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# macOS — Electron desktop app
# ─────────────────────────────────────────────────────────────────
if [ "$BUILD_MACOS" = true ]; then
  echo -e "${YELLOW}[macOS] Building macOS Electron app...${NC}"
  M="$OUT/macos"; mkdir -p "$M"
  cp "$DIR/mint_scan_android.html" "$M/index.html"

  cat > "$M/package.json" << 'MACPKG'
{
  "name": "mint-scan-v8",
  "version": "8.0.0",
  "description": "Mint Scan v8 — Advanced Security Auditor by Mint Projects",
  "main": "main.js",
  "author": "Mint Projects PTY (Ltd)",
  "license": "Proprietary",
  "scripts": {
    "start":        "electron .",
    "build-mac":    "electron-packager . 'Mint Scan' --platform=darwin --arch=x64  --out=dist --overwrite --app-version=8.0.0",
    "build-mac-arm":"electron-packager . 'Mint Scan' --platform=darwin --arch=arm64 --out=dist --overwrite --app-version=8.0.0"
  },
  "devDependencies": {
    "electron": "^29.0.0",
    "electron-packager": "^17.1.2"
  }
}
MACPKG

  # Same main.js as Windows (Electron is cross-platform)
  cp "$W/main.js" "$M/main.js" 2>/dev/null || cat > "$M/main.js" << 'MACMAIN'
'use strict';
const { app, BrowserWindow, Menu } = require('electron');
const path = require('path');
let win;
app.whenReady().then(() => {
  win = new BrowserWindow({ width:440, height:920, minWidth:380, minHeight:700,
    title:'Mint Scan v8', backgroundColor:'#05111f', show:false,
    webPreferences:{ nodeIntegration:false, contextIsolation:true } });
  win.loadFile(path.join(__dirname,'index.html'));
  win.once('ready-to-show', () => win.show());
  win.webContents.on('context-menu', (_, p) => {
    Menu.buildFromTemplate([
      { label:'Copy', role:'copy', enabled:p.selectionText.length>0 },
      { label:'Paste', role:'paste' },
      { label:'Select All', role:'selectAll' },
      { type:'separator' },
      { label:'Reload', click:()=>win.reload() },
    ]).popup();
  });
});
app.on('window-all-closed', () => { if(process.platform!=='darwin') app.quit(); });
app.on('activate', () => { if(BrowserWindow.getAllWindows().length===0) app.emit('ready'); });
MACMAIN

  cat > "$M/build_macos.sh" << 'MACBUILD'
#!/bin/bash
set -e
echo "=== Mint Scan v8 — macOS Builder ==="
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
if ! command -v node &>/dev/null; then
  echo "Node.js required: https://nodejs.org"
  exit 1
fi
echo "[1/3] Installing dependencies..."
npm install
echo "[2/3] Building Intel (.app)..."
npm run build-mac
echo "[3/3] Building Apple Silicon (.app)..."
npm run build-mac-arm
echo ""
echo "✓ Apps in dist/"
echo "  Intel:  dist/Mint Scan-darwin-x64/Mint\ Scan.app"
echo "  Silicon:dist/Mint Scan-darwin-arm64/Mint\ Scan.app"
MACBUILD
  chmod +x "$M/build_macos.sh"

  cat > "$M/run_dev.sh" << 'MACRUN'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
if [ ! -d "node_modules" ]; then
  echo "Installing Electron (first run ~2 min)..."
  npm install --save-dev electron@29
fi
npx electron .
MACRUN
  chmod +x "$M/run_dev.sh"

  cat > "$M/README.txt" << 'MACREADME'
MINT SCAN v8 — macOS INSTALLATION
====================================
REQUIREMENTS: Node.js 18+ from https://nodejs.org (FREE)

METHOD 1 — Run directly:
  bash run_dev.sh

METHOD 2 — Build .app bundle:
  bash build_macos.sh
  Intel:   dist/Mint Scan-darwin-x64/Mint Scan.app
  Silicon: dist/Mint Scan-darwin-arm64/Mint Scan.app
  Drag to Applications folder

METHOD 3 — Browser:
  Open index.html in Safari or Chrome

APPLE SILICON: build-mac-arm produces native ARM binary
for full performance on M1/M2/M3/M4 Macs.

GATEKEEPER: If blocked, right-click the .app → Open
MACREADME

  echo -e "${GREEN}  ✓ macOS package → $M/${NC}"
fi

# ─────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   BUILD COMPLETE — Mint Scan v8 Mobile Apps                 ║"
echo "╠══════════════════════════════════════════════════════════════╣"
[ "$BUILD_ANDROID" = true ] && printf "║  %-58s║\n" "  Android  → mobile_builds/android/  (bash install_via_adb.sh)"
[ "$BUILD_IOS"     = true ] && printf "║  %-58s║\n" "  iOS      → mobile_builds/ios/       (Safari → Add to Home Screen)"
[ "$BUILD_WINDOWS" = true ] && printf "║  %-58s║\n" "  Windows  → mobile_builds/windows/   (double-click START.bat)"
[ "$BUILD_MACOS"   = true ] && printf "║  %-58s║\n" "  macOS    → mobile_builds/macos/     (bash run_dev.sh)"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Usage: bash build_mobile.sh [android|ios|windows|macos|all]║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
