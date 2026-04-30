#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║   MINT SCAN v8 — LAUNCHER                                   ║
# ║   Supports: x86_64 · aarch64 · Chromebook · WSL2            ║
# ╚══════════════════════════════════════════════════════════════╝
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'
YELLOW='\033[1;33m'; NC='\033[0m'

# Block sudo run (breaks display)
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}[ MINT SCAN ]${NC} ERROR: Do NOT run as root / sudo."
    echo -e "  Use: ${GREEN}bash run.sh${NC}  (without sudo)"
    exit 1
fi

# ── Display detection ────────────────────────────────────────────
# Wayland: force XWayland compatibility mode
if [ -n "$WAYLAND_DISPLAY" ] && [ -z "$DISPLAY" ]; then
    echo -e "${YELLOW}[ MINT SCAN ]${NC} Wayland detected — using XWayland"
    export DISPLAY=:0
    export GDK_BACKEND=x11
    export QT_QPA_PLATFORM=xcb
fi

# WSL2: set DISPLAY if not set
if [ -f /proc/sys/fs/binfmt_misc/WSLInterop ] && [ -z "$DISPLAY" ]; then
    echo -e "${YELLOW}[ MINT SCAN ]${NC} WSL2 detected — setting DISPLAY=:0"
    export DISPLAY=:0
fi

# Check display is available
if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
    # Try :0 as a last resort
    if xdpyinfo -display :0 &>/dev/null 2>&1; then
        export DISPLAY=:0
    else
        echo -e "${RED}[ MINT SCAN ]${NC} No display found."
        echo "  If you're on Wayland:  export DISPLAY=:0 && bash run.sh"
        echo "  If you're headless:    Xvfb :0 -screen 0 1280x800x24 &"
        echo "                         export DISPLAY=:0 && bash run.sh"
        exit 1
    fi
fi

# ── Self-heal check ──────────────────────────────────────────────
HEAL=false
[ ! -d "venv" ] && HEAL=true
python3 -m py_compile widgets.py 2>/dev/null || HEAL=true
! grep -q "class Card" widgets.py 2>/dev/null && HEAL=true
# Detect broken Card implementations that cause runtime crashes:
# Pattern 1: plain object Card with def _w(self) method → TypeError: method + str
grep -q "def _w(self)" widgets.py 2>/dev/null && HEAL=true
# Pattern 2: Card calls super().pack() in __init__ → AttributeError: property has no setter  
grep -A 30 "class Card" widgets.py 2>/dev/null | grep -q "super().pack()" && HEAL=true

if [ "$HEAL" = true ]; then
    echo -e "${CYAN}[ MINT SCAN ]${NC} Self-healing — running installer..."
    sudo chown -R "$USER:$USER" "$SCRIPT_DIR" 2>/dev/null || true
    bash install.sh
fi

# ── Activate venv ────────────────────────────────────────────────
source venv/bin/activate 2>/dev/null || {
    echo -e "${RED}[ MINT SCAN ]${NC} venv broken — reinstalling..."
    bash install.sh
    source venv/bin/activate
}

# ── aarch64: ensure python3-tk is in venv ────────────────────────
ARCH=$(uname -m)
if [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
    python3 -c "import tkinter" 2>/dev/null || {
        echo -e "${YELLOW}[ MINT SCAN ]${NC} tkinter missing on ARM64 — fixing..."
        sudo apt-get install -y python3-tk libtk8.6 2>/dev/null || true
    }
fi

echo -e "${GREEN}[ MINT SCAN ]${NC} Launching v8..."
exec python3 main.py "$@"
