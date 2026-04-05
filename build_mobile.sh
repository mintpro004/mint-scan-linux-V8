#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║   MINT SCAN v8 — CROSS-PLATFORM MOBILE APP BUILDER          ║
# ║   Builds: Android APK · iOS PWA · Windows App · macOS App   ║
# ╚══════════════════════════════════════════════════════════════╝
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   MINT SCAN v8 — MOBILE APP BUILDER                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── What to build ────────────────────────────────────────────────
BUILD_ANDROID=false
BUILD_IOS=false
BUILD_WINDOWS=false
BUILD_MACOS=false
BUILD_ALL=false

if [ $# -eq 0 ]; then BUILD_ALL=true; fi
for arg in "$@"; do
  case $arg in
    android) BUILD_ANDROID=true ;;
    ios)     BUILD_IOS=true ;;
    windows) BUILD_WINDOWS=true ;;
    macos)   BUILD_MACOS=true ;;
    all)     BUILD_ALL=true ;;
  esac
done
[ "$BUILD_ALL" = true ] && BUILD_ANDROID=true BUILD_IOS=true BUILD_WINDOWS=true BUILD_MACOS=true

OUT="$DIR/mobile_builds"
mkdir -p "$OUT"

# ════════════════════════════════════════════════════════════════
# ANDROID APK  (using TWA / WebView wrapper via aapt/dx OR
#               simple signed zip for sideloading)
# ════════════════════════════════════════════════════════════════
if [ "$BUILD_ANDROID" = true ]; then
  echo -e "${YELLOW}[ANDROID] Building APK...${NC}"
  ANDROID_OUT="$OUT/android"
  mkdir -p "$ANDROID_OUT"

  # Step 1: Copy the mobile HTML app
  cp "$DIR/mint_scan_android.html" "$ANDROID_OUT/index.html"

  # Step 2: Generate manifest.json for TWA/PWA
  cat > "$ANDROID_OUT/manifest.json" << 'MANIFEST'
{
  "name": "Mint Scan v8",
  "short_name": "MintScan",
  "description": "Advanced Security Auditor — Mint Projects",
  "start_url": "/index.html",
  "display": "standalone",
  "background_color": "#05111f",
  "theme_color": "#00ffe0",
  "orientation": "portrait",
  "icons": [
    { "src": "icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png" }
  ],
  "categories": ["security", "utilities"],
  "shortcuts": [
    { "name": "Security Scan", "url": "/index.html#threats", "description": "Run security scan" },
    { "name": "Network", "url": "/index.html#network", "description": "Network monitor" }
  ]
}
MANIFEST

  # Step 3: Generate service worker for offline support
  cat > "$ANDROID_OUT/sw.js" << 'SWEOF'
const CACHE = 'mintscan-v8';
const ASSETS = ['/', '/index.html', '/manifest.json'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
});
self.addEventListener('fetch', e => {
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
SWEOF

  # Step 4: Add SW registration to HTML
  sed -i 's|</body>|<script>if("serviceWorker"in navigator){navigator.serviceWorker.register("/sw.js").then(r=>console.log("SW registered")).catch(e=>console.log("SW error",e));}</script>\n</body>|' "$ANDROID_OUT/index.html"

  # Step 5: Try to build real APK using bubblewrap (TWA) if available
  if command -v bubblewrap &>/dev/null || npm list -g @bubblewrap/cli &>/dev/null 2>&1; then
    echo -e "  ${GREEN}bubblewrap found — building TWA APK...${NC}"
    cd "$ANDROID_OUT"
    bubblewrap init --manifest=manifest.json --directory=. 2>/dev/null || true
    bubblewrap build 2>/dev/null && echo -e "  ${GREEN}✓ APK built${NC}" || echo -e "  ${YELLOW}TWA build needs Android SDK setup${NC}"
    cd "$DIR"
  else
    echo -e "  ${YELLOW}bubblewrap not found — creating installable PWA package instead${NC}"
    echo -e "  ${CYAN}Install bubblewrap: npm install -g @bubblewrap/cli${NC}"
    # Create a self-contained ZIP that can be installed via ADB WebView
    zip -q "$ANDROID_OUT/MintScan_v8_android.zip" -j "$ANDROID_OUT/index.html" "$ANDROID_OUT/manifest.json" "$ANDROID_OUT/sw.js"
    echo -e "  ${GREEN}✓ Android PWA package: $ANDROID_OUT/MintScan_v8_android.zip${NC}"
  fi

  # Step 6: ADB install instructions
  cat > "$ANDROID_OUT/INSTALL.txt" << 'INSTEOF'
MINT SCAN v8 — ANDROID INSTALLATION
=====================================

METHOD 1 — PWA (Recommended, no APK needed):
  1. Start Mint Scan desktop: bash run.sh
  2. Open Wireless tab → START SERVER
  3. On phone browser, open the URL shown (e.g. http://192.168.1.100:8765)
  4. Tap browser menu → "Add to Home Screen"
  5. Mint Scan installs as a full-screen app with icon

METHOD 2 — ADB (USB, works offline):
  1. Connect phone via USB with USB Debugging ON
  2. In Mint Scan → USB Sync tab → tap 🚀 OPEN COMPANION ON PHONE
  3. The app opens via ADB port-forward — no internet needed

METHOD 3 — Direct file:
  adb push index.html /sdcard/Download/MintScan.html
  Then open via a file manager that supports HTML (not Chrome — use Firefox)

REQUIREMENTS: Android 6.0+, Chrome 72+ or Firefox 68+
INSTEOF

  echo -e "${GREEN}  ✓ Android build complete → $ANDROID_OUT${NC}"
fi

# ════════════════════════════════════════════════════════════════
# iOS PWA
# ════════════════════════════════════════════════════════════════
if [ "$BUILD_IOS" = true ]; then
  echo -e "${YELLOW}[iOS] Building iOS PWA package...${NC}"
  IOS_OUT="$OUT/ios"
  mkdir -p "$IOS_OUT"

  # iOS-optimised HTML — adds apple-specific meta tags
  cp "$DIR/mint_scan_android.html" "$IOS_OUT/index.html"

  # Inject iOS meta tags
  IOS_META='<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="Mint Scan">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="apple-touch-startup-image" href="splash.png">'
  sed -i "s|</head>|${IOS_META}\n</head>|" "$IOS_OUT/index.html"

  cat > "$IOS_OUT/manifest.json" << 'IOS_MANIFEST'
{
  "name": "Mint Scan v8",
  "short_name": "MintScan",
  "display": "standalone",
  "background_color": "#05111f",
  "theme_color": "#00ffe0",
  "start_url": "/index.html",
  "icons": [
    { "src": "icon-180.png", "sizes": "180x180", "type": "image/png" }
  ]
}
IOS_MANIFEST

  cat > "$IOS_OUT/INSTALL.txt" << 'IOS_INST'
MINT SCAN v8 — iOS INSTALLATION
=================================

iOS does not allow sideloading APKs. Use the PWA method:

METHOD — Safari PWA (Full App Experience):
  1. Start Mint Scan desktop: bash run.sh
  2. Open Wireless tab → START SERVER
  3. On iPhone/iPad Safari, open: http://<your-desktop-ip>:8765
  4. Tap the Share button (box with arrow) → "Add to Home Screen"
  5. Tap ADD — Mint Scan appears as a native-feeling app

FEATURES ON iOS:
  ✓ Dashboard with security score
  ✓ Battery monitoring (via Battery Status API — iOS 16.4+)
  ✓ Network monitoring and speed test
  ✓ Port scanner (browser-based)
  ✓ Device info and permissions check
  ✓ Privacy/WebRTC leak check
  ✓ Security tools (Ping, DNS, GeoIP, SSL check)
  ✓ Bi-directional sync with desktop
  ✓ Offline support via Service Worker
  ✓ Works on iOS 12.2+, iPadOS 13+

LIMITATIONS (iOS browser restrictions):
  ~ ADB not available on iOS
  ~ No USB cable connection method
  ~ Call log / SMS access not available in browser
  ~ File system access limited
IOS_INST

  echo -e "${GREEN}  ✓ iOS PWA package → $IOS_OUT${NC}"
fi

# ════════════════════════════════════════════════════════════════
# WINDOWS DESKTOP APP (using Electron-packager if available,
#                       otherwise portable HTML launcher)
# ════════════════════════════════════════════════════════════════
if [ "$BUILD_WINDOWS" = true ]; then
  echo -e "${YELLOW}[WINDOWS] Building Windows app...${NC}"
  WIN_OUT="$OUT/windows"
  mkdir -p "$WIN_OUT/app"

  cp "$DIR/mint_scan_android.html" "$WIN_OUT/app/index.html"

  # Electron main.js
  cat > "$WIN_OUT/app/main.js" << 'ELECTRON'
const { app, BrowserWindow, Menu, shell, dialog } = require('electron');
const path = require('path');

let win;

function createWindow() {
  win = new BrowserWindow({
    width: 430,
    height: 900,
    minWidth: 380,
    minHeight: 700,
    title: 'Mint Scan v8 — Mobile Security',
    backgroundColor: '#05111f',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
    }
  });

  win.loadFile('index.html');

  // Custom menu
  const menu = Menu.buildFromTemplate([
    { label: 'Mint Scan', submenu: [
      { label: 'Reload', accelerator: 'F5', click: () => win.reload() },
      { label: 'DevTools', accelerator: 'F12', click: () => win.webContents.openDevTools() },
      { type: 'separator' },
      { label: 'Quit', accelerator: 'Ctrl+Q', click: () => app.quit() },
    ]},
    { label: 'View', submenu: [
      { label: 'Zoom In',  accelerator: 'Ctrl+=', click: () => { const z = win.webContents.getZoomLevel(); win.webContents.setZoomLevel(z + 0.5); }},
      { label: 'Zoom Out', accelerator: 'Ctrl+-', click: () => { const z = win.webContents.getZoomLevel(); win.webContents.setZoomLevel(z - 0.5); }},
      { label: 'Reset Zoom', accelerator: 'Ctrl+0', click: () => win.webContents.setZoomLevel(0) },
    ]},
  ]);
  Menu.setApplicationMenu(menu);
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
ELECTRON

  cat > "$WIN_OUT/app/package.json" << 'WINPKG'
{
  "name": "mint-scan-mobile",
  "version": "8.0.0",
  "description": "Mint Scan v8 — Mobile Security App",
  "main": "main.js",
  "author": "Mint Projects",
  "license": "Proprietary",
  "scripts": {
    "start": "electron .",
    "build-win": "electron-packager . MintScan --platform=win32 --arch=x64 --out=dist --overwrite --icon=icon.ico",
    "build-win32": "electron-packager . MintScan --platform=win32 --arch=ia32 --out=dist --overwrite"
  },
  "devDependencies": {
    "electron": "^28.0.0",
    "electron-packager": "^17.0.0"
  }
}
WINPKG

  cat > "$WIN_OUT/BUILD_WINDOWS.bat" << 'WINBAT'
@echo off
echo ============================================
echo   MINT SCAN v8 - Windows App Builder
echo ============================================
echo.
echo [1] Installing Node.js dependencies...
cd app
npm install
echo.
echo [2] Building Windows .exe...
npm run build-win
echo.
echo [3] Done! Executable in app\dist\
pause
WINBAT

  cat > "$WIN_OUT/RUN_PORTABLE.bat" << 'WINRUN'
@echo off
echo Starting Mint Scan v8 (portable)...
cd app
npx electron . 2>nul || (
  echo Installing Electron...
  npm install electron --no-save
  npx electron .
)
WINRUN

  cat > "$WIN_OUT/INSTALL.txt" << 'WIN_INST'
MINT SCAN v8 — WINDOWS INSTALLATION
======================================

REQUIREMENTS: Node.js 18+ (nodejs.org)

METHOD 1 — Run Portable (Fastest):
  1. Install Node.js from https://nodejs.org
  2. Double-click RUN_PORTABLE.bat
  3. Mint Scan opens in its own window

METHOD 2 — Build Windows .exe:
  1. Install Node.js
  2. Double-click BUILD_WINDOWS.bat
  3. .exe in app\dist\MintScan-win32-x64\MintScan.exe

METHOD 3 — Browser (No install):
  1. Open app\index.html in any modern browser

FEATURES ON WINDOWS:
  ✓ All mobile security features
  ✓ Real-time battery monitoring
  ✓ Network speed test
  ✓ Port scanner
  ✓ Security threat scan
  ✓ Privacy check
  ✓ Sync to Mint Scan Linux desktop
  ✓ Full clipboard support
WIN_INST

  echo -e "${GREEN}  ✓ Windows app → $WIN_OUT${NC}"
fi

# ════════════════════════════════════════════════════════════════
# macOS APP (Electron-based)
# ════════════════════════════════════════════════════════════════
if [ "$BUILD_MACOS" = true ]; then
  echo -e "${YELLOW}[macOS] Building macOS app...${NC}"
  MAC_OUT="$OUT/macos"
  mkdir -p "$MAC_OUT/app"

  cp "$DIR/mint_scan_android.html" "$MAC_OUT/app/index.html"

  # Reuse Electron main.js (same as Windows, cross-platform)
  cp "$WIN_OUT/app/main.js" "$MAC_OUT/app/main.js" 2>/dev/null || cat > "$MAC_OUT/app/main.js" << 'MACELECTRON'
const { app, BrowserWindow, Menu } = require('electron');
const path = require('path');
let win;
function createWindow() {
  win = new BrowserWindow({
    width: 430, height: 900, minWidth: 380, minHeight: 700,
    title: 'Mint Scan v8', backgroundColor: '#05111f',
    webPreferences: { nodeIntegration: false, contextIsolation: true }
  });
  win.loadFile('index.html');
}
app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
MACELECTRON

  cat > "$MAC_OUT/app/package.json" << 'MACPKG'
{
  "name": "mint-scan-mobile",
  "version": "8.0.0",
  "description": "Mint Scan v8 — Mobile Security App",
  "main": "main.js",
  "author": "Mint Projects",
  "scripts": {
    "start": "electron .",
    "build-mac": "electron-packager . MintScan --platform=darwin --arch=x64 --out=dist --overwrite",
    "build-mac-arm": "electron-packager . MintScan --platform=darwin --arch=arm64 --out=dist --overwrite"
  },
  "devDependencies": {
    "electron": "^28.0.0",
    "electron-packager": "^17.0.0"
  }
}
MACPKG

  cat > "$MAC_OUT/build_macos.sh" << 'MACBUILD'
#!/bin/bash
echo "=== Mint Scan v8 macOS Builder ==="
cd "$(dirname "$0")/app"
echo "[1] Installing dependencies..."
npm install
echo "[2] Building macOS .app..."
npm run build-mac
echo "[3] ARM (Apple Silicon)..."
npm run build-mac-arm
echo "Done! .app bundles in dist/"
MACBUILD
chmod +x "$MAC_OUT/build_macos.sh"

  cat > "$MAC_OUT/INSTALL.txt" << 'MAC_INST'
MINT SCAN v8 — macOS INSTALLATION
====================================

REQUIREMENTS: Node.js 18+ (nodejs.org), macOS 10.13+

METHOD 1 — Run directly:
  cd app && npm install && npm start

METHOD 2 — Build .app bundle:
  bash build_macos.sh
  Then drag MintScan.app to Applications

METHOD 3 — Browser:
  Open app/index.html in Safari or Chrome

APPLE SILICON: Use build-mac-arm for native M1/M2/M3 performance.
MAC_INST

  echo -e "${GREEN}  ✓ macOS app → $MAC_OUT${NC}"
fi

# ════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   BUILD COMPLETE                                             ║"
echo "╠══════════════════════════════════════════════════════════════╣"
[ "$BUILD_ANDROID" = true ] && echo "║   Android  → mobile_builds/android/                         ║"
[ "$BUILD_IOS"     = true ] && echo "║   iOS      → mobile_builds/ios/                             ║"
[ "$BUILD_WINDOWS" = true ] && echo "║   Windows  → mobile_builds/windows/                         ║"
[ "$BUILD_MACOS"   = true ] && echo "║   macOS    → mobile_builds/macos/                           ║"
echo "║                                                              ║"
echo "║   Run:  bash build_mobile.sh android|ios|windows|macos|all  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
