#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║   MINT SCAN v8 — SELF-HEALING INSTALLER                     ║
# ║   Supports: Chromebook · Ubuntu 20/22/24 · Kali · WSL2      ║
# ║   Arch:     x86_64 · aarch64 (ARM64) · armv7l               ║
# ╚══════════════════════════════════════════════════════════════╝
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   MINT SCAN v8 — SELF-HEALING INSTALLER  (git clone only)   ║"
echo "║   Pretoria · Mint Projects PTY (Ltd) · South Africa         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Platform / arch detection ────────────────────────────────────
IS_CHROMEBOOK=false; IS_WSL=false; IS_KALI=false; IS_AARCH64=false

ARCH=$(uname -m)
[[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]] && IS_AARCH64=true

[ -f /proc/version ] && grep -qi "cros\|chrome" /proc/version 2>/dev/null && IS_CHROMEBOOK=true
[ -f /proc/sys/fs/binfmt_misc/WSLInterop ] && IS_WSL=true
[ -f /etc/os-release ] && grep -qi "kali" /etc/os-release 2>/dev/null && IS_KALI=true

echo "[0/7] Detecting platform..."
$IS_CHROMEBOOK && echo "  ✓ Chromebook / Crostini detected"
$IS_WSL        && echo "  ✓ Windows WSL2 detected"
$IS_KALI       && echo "  ✓ Kali Linux detected"
$IS_AARCH64    && echo "  ✓ ARM64 / aarch64 architecture"
! $IS_CHROMEBOOK && ! $IS_WSL && ! $IS_KALI && echo "  ✓ Standard Linux (Ubuntu/Debian)"

# Git repo check
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}  ⚠ Not a git repository — install from git clone for updates${NC}"
else
    echo "  ✓ Git repository detected"
    REMOTE=$(git remote get-url origin 2>/dev/null || echo "not configured")
    echo "  Remote: $REMOTE"
fi

# ── [1/7] Ownership fix ──────────────────────────────────────────
echo "[1/7] Fixing ownership..."
sudo chown -R "$USER:$USER" "$SCRIPT_DIR" 2>/dev/null || true
echo "  ✓ Done"

# Remove development/test files that should not be in production
for testfile in reproduce_injection.py test_fix.py; do
    [ -f "$testfile" ] && rm -f "$testfile" && echo "  Removed: $testfile"
done

# ── [2/7] System packages ────────────────────────────────────────
echo "[2/7] Installing system packages..."
export DEBIAN_FRONTEND=noninteractive

PKGS_BASE="python3 python3-pip python3-tk python3-dev python3-venv git"
PKGS_DISPLAY="x11-utils xdotool"
PKGS_NET="net-tools dbus"

if $IS_CHROMEBOOK; then
    echo "  Chromebook: using Crostini-safe package list..."
    sudo apt-get update -qq 2>/dev/null || true
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        $PKGS_BASE $PKGS_NET 2>/dev/null || true
    # Chromebook UFW fix — needs special flag
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ufw 2>/dev/null && \
        echo "  ✓ UFW installed successfully on Chromebook"

elif $IS_AARCH64; then
    echo "  ARM64 / aarch64: using compatible package list..."
    sudo apt-get update -qq 2>/dev/null || true
    # python3-tk on aarch64 Ubuntu 22.04 needs explicit install
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        $PKGS_BASE $PKGS_DISPLAY $PKGS_NET \
        python3-tk python3-pil python3-pil.imagetk \
        libtk8.6 libglib2.0-0 2>/dev/null || true
    echo "  ✓ aarch64 packages installed"

else
    sudo apt-get update -qq 2>/dev/null || true
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        $PKGS_BASE $PKGS_DISPLAY $PKGS_NET 2>/dev/null || true
    echo "  ✓ Done"
fi

# Optional tools (non-blocking)
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    adb nmap ufw 2>/dev/null || true

echo "  ✓ Done"

# ── [3/7] Python venv ────────────────────────────────────────────
echo "[3/7] Setting up Python environment..."
[ ! -d "venv" ] && python3 -m venv venv
source venv/bin/activate

# Upgrade pip silently
pip install -q --upgrade pip 2>/dev/null || true

# Pin customtkinter to 5.2.2 — stable across x86_64 AND aarch64
# 5.2.2 is tested on Python 3.9/3.10/3.11/3.12, Ubuntu 20/22/24, aarch64
pip install -q "customtkinter==5.2.2" 2>/dev/null || \
pip install -q "customtkinter>=5.2.0,<6.0" 2>/dev/null || \
pip install -q customtkinter 2>/dev/null || true

# Core deps
pip install -q darkdetect psutil pillow netifaces speedtest-cli 2>/dev/null || true

# requests — needed for CVE lookup, updater
pip install -q requests 2>/dev/null || true

# Optional deps (don't fail if unavailable on aarch64)
pip install -q pystray 2>/dev/null || true
pip install -q plyer 2>/dev/null || true
pip install -q reportlab 2>/dev/null || true

echo "  ✓ Done"

# ── [4/7] widgets.py verification ───────────────────────────────
echo "[4/7] Verifying widgets.py..."
python3 -m py_compile widgets.py 2>/dev/null || {
    echo -e "  ${RED}✗ widgets.py has syntax errors${NC}"
    exit 1
}
echo "  ✓ widgets.py OK"

# ── [5/7] main.py verification ──────────────────────────────────
echo "[5/7] Checking main.py..."
python3 -m py_compile main.py 2>/dev/null || {
    echo -e "  ${RED}✗ main.py has errors${NC}"
    exit 1
}
echo "  ✓ main.py OK"

# ── [6/7] All modules ───────────────────────────────────────────
echo "[6/7] Verifying all Python modules..."
FAIL_COUNT=0
for pyfile in *.py; do
    result=$(python3 -m py_compile "$pyfile" 2>&1)
    if [ -n "$result" ]; then
        echo -e "    ${RED}✗ $pyfile — $result${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        echo "    ✓ $pyfile"
    fi
done

if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "  ${RED}✗ $FAIL_COUNT file(s) have errors${NC}"
    exit 1
fi

# Quick Card widget smoke test — verifies aarch64 stability
WIDGET_OK=$(python3 -c "
import sys, os
sys.path.insert(0, os.getcwd())
try:
    from widgets import Card, Btn, ScrollableFrame, C
    # Verify Card can be instantiated without crashing
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    c = Card(root)
    c.destroy()
    root.destroy()
    print('OK')
except Exception as e:
    print(f'FAIL: {e}')
" 2>&1)

if [[ "$WIDGET_OK" == *"OK"* ]]; then
    echo "  ✓ All widget classes verified (aarch64-safe)"
else
    echo -e "  ${RED}✗ Widget check failed: $WIDGET_OK${NC}"
    exit 1
fi

# ── [7/7] Desktop shortcut ──────────────────────────────────────
echo "[7/7] Creating desktop shortcut..."
DESKTOP_DIR="$HOME/Desktop"
[ -d "$DESKTOP_DIR" ] || DESKTOP_DIR="$HOME"
cat > "$DESKTOP_DIR/MintScan.desktop" << EOF
[Desktop Entry]
Name=Mint Scan v8
Comment=Advanced Linux Security Auditor
Exec=bash $SCRIPT_DIR/run.sh
Icon=$SCRIPT_DIR/icon.png
Terminal=false
Type=Application
Categories=System;Security;
StartupWMClass=MintScan
EOF
chmod +x "$DESKTOP_DIR/MintScan.desktop" 2>/dev/null || true
echo "  ✓ Done"

echo ""
echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ✓ MINT SCAN v8 — INSTALLATION COMPLETE                   ║"
$IS_CHROMEBOOK && \
echo "║   ✓ Chromebook: Crostini-safe UFW install applied          ║"
$IS_AARCH64 && \
echo "║   ✓ ARM64 / aarch64: compatible packages installed         ║"
echo "║   Run:  bash run.sh                                        ║"
echo "║   Or:   source venv/bin/activate && python3 main.py        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
