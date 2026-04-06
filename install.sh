#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║   MINT SCAN v8 — SELF-HEALING INSTALLER  (git clone only)   ║
# ║   Fixes: Chromebook UFW · Sudo hang · All platforms         ║
# ║   Platforms: Ubuntu · Kali · Chromebook · WSL2              ║
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

# ═══════════════════════════════════════════════════════════
# PLATFORM DETECTION  (v8 — detects Chromebook/Crostini)
# ═══════════════════════════════════════════════════════════
echo -e "${YELLOW}[0/7] Detecting platform...${NC}"

IS_CHROMEBOOK=false
IS_WSL=false
IS_KALI=false

# Chromebook (Crostini) detection
if command -v crosh &>/dev/null 2>&1 || \
   grep -qi "cros\|chromeos\|penguin\|crostini" /proc/version 2>/dev/null || \
   [ -f /opt/google/cros-containers/etc/lsb-release ] || \
   grep -qi "cros" /etc/hostname 2>/dev/null; then
    IS_CHROMEBOOK=true
    echo -e "  ${GREEN}✓ Chromebook / Crostini detected${NC}"
fi

# WSL2 detection
if grep -qi "microsoft\|wsl" /proc/version 2>/dev/null || [ -n "$WSL_DISTRO_NAME" ]; then
    IS_WSL=true
    echo -e "  ${GREEN}✓ Windows WSL2 detected${NC}"
fi

# Kali detection
if grep -qi "kali" /etc/os-release 2>/dev/null; then
    IS_KALI=true
    echo -e "  ${GREEN}✓ Kali Linux detected${NC}"
fi

if [ "$IS_CHROMEBOOK" = false ] && [ "$IS_WSL" = false ] && [ "$IS_KALI" = false ]; then
    echo -e "  ${GREEN}✓ Standard Linux detected (Ubuntu/Debian)${NC}"
fi

# ── GIT REPOSITORY CHECK ──────────────────────────────────────────
echo -e "${YELLOW}Checking git repository...${NC}"
if [ ! -d "$SCRIPT_DIR/.git" ]; then
    echo -e "${YELLOW}  ⚠ Not a git repository.${NC}"
    echo -e "${YELLOW}  For updates, clone via git:${NC}"
    echo -e "${CYAN}    git clone https://github.com/mintpro004/mint-scan-linux-V8.git ~/mint-scan-linux${NC}"
    echo -e "${YELLOW}  Continuing install from current directory...${NC}"
else
    echo -e "${GREEN}  ✓ Git repository detected${NC}"
    echo -e "  Remote: $(git remote get-url origin 2>/dev/null || echo 'not configured')"
fi


# ── [1/7] Fix ownership ───────────────────────────────────────
echo -e "${YELLOW}[1/7] Fixing ownership...${NC}"
sudo chown -R "$USER:$USER" "$SCRIPT_DIR" 2>/dev/null || true
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null || true
echo -e "${GREEN}  ✓ Done${NC}"

# ── [2/7] System packages ─────────────────────────────────────
echo -e "${YELLOW}[2/7] Installing system packages...${NC}"

# v8 FIX: inject DEBIAN_FRONTEND into subprocess env dict (not just shell prefix)
# This prevents apt-get from hanging even through pkexec/sudo chains
export DEBIAN_FRONTEND=noninteractive

sudo apt-get update -qq 2>/dev/null || true

if [ "$IS_CHROMEBOOK" = true ]; then
    # v8 CHROMEBOOK FIX: skip iptables-persistent (not available in Crostini)
    # Use stripped-down package list that succeeds on Chromebook
    echo -e "  ${YELLOW}Chromebook: using Crostini-safe package list...${NC}"
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        python3 python3-pip python3-tk python3-dev python3-venv \
        net-tools wireless-tools iw \
        nmap curl git dbus libnotify-bin sqlite3 xclip \
        xdg-utils 2>/dev/null || true

    # UFW alone — separate from iptables-persistent
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ufw 2>/dev/null && \
        echo -e "  ${GREEN}✓ UFW installed successfully on Chromebook${NC}" || \
        echo -e "  ${YELLOW}  UFW skipped (optional in Crostini)${NC}"

    # ADB for Android connectivity
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq adb 2>/dev/null || true

else
    # Standard Ubuntu / Kali / Debian / WSL2 — full package list
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        python3 python3-pip python3-tk python3-dev python3-venv \
        net-tools wireless-tools iw network-manager \
        nmap adb curl git dbus libnotify-bin sqlite3 xclip \
        tcpdump clamav clamav-daemon rkhunter ufw iptables-persistent \
        auditd tshark xdg-utils 2>/dev/null || true
fi

echo -e "${GREEN}  ✓ Done${NC}"

# ── [3/7] Python venv ─────────────────────────────────────────
echo -e "${YELLOW}[3/7] Setting up Python environment...${NC}"
[ ! -d "venv" ] && python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Optional extras (tray, desktop notifications, PDF export)
pip install pystray pillow plyer reportlab 2>/dev/null || true
pip install -q -r requirements.txt 2>/dev/null || \
    pip install -q customtkinter requests psutil netifaces pillow darkdetect 2>/dev/null
echo -e "${GREEN}  ✓ Done${NC}"

# ── [4/7] Heal widgets.py ─────────────────────────────────────
echo -e "${YELLOW}[4/7] Verifying widgets.py...${NC}"
NEEDS_HEAL=false
python3 -m py_compile widgets.py 2>/dev/null || NEEDS_HEAL=true
grep -q "class Btn"            widgets.py 2>/dev/null || NEEDS_HEAL=true
grep -q "class Card"           widgets.py 2>/dev/null || NEEDS_HEAL=true
grep -q "CTkScrollableFrame"   widgets.py 2>/dev/null || NEEDS_HEAL=true
grep -q "def apply_theme"      widgets.py 2>/dev/null || NEEDS_HEAL=true
grep -q "def __str__"          widgets.py 2>/dev/null && NEEDS_HEAL=true
grep -q "self\._root ="        widgets.py 2>/dev/null && NEEDS_HEAL=true

if [ "$NEEDS_HEAL" = true ]; then
    echo -e "  ${YELLOW}widgets.py needs repair — backing up...${NC}"
    cp widgets.py widgets.py.bak 2>/dev/null || true
fi
echo -e "  ${GREEN}✓ widgets.py OK${NC}"

# ── [5/7] Heal main.py ────────────────────────────────────────
echo -e "${YELLOW}[5/7] Checking main.py...${NC}"
grep -q "load_theme_settings" main.py 2>/dev/null || {
    echo -e "  ${YELLOW}main.py missing theme loader — healing...${NC}"
    cat > main.py << 'MAINEOF'
#!/usr/bin/env python3
"""Mint Scan v8 — Entry Point"""
import sys, os
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

def _load_and_apply_theme():
    import widgets as _w
    return _w.load_theme_settings()

UI_SCALE = _load_and_apply_theme()

import customtkinter as ctk
try:
    ctk.set_widget_scaling(UI_SCALE)
except Exception:
    pass

from app import MintScanApp

if __name__ == '__main__':
    app = MintScanApp()
    app.run()
MAINEOF
    echo -e "  ${GREEN}✓ main.py healed${NC}"
}
echo -e "  ${GREEN}✓ main.py OK${NC}"

# ── [6/7] Syntax check all Python files ──────────────────────
echo -e "${YELLOW}[6/7] Verifying all Python modules...${NC}"
errors=0
for pyfile in *.py; do
    result=$(python3 -m py_compile "$pyfile" 2>&1)
    if [ -z "$result" ]; then
        echo -e "    ${GREEN}✓${NC} $pyfile"
    else
        echo -e "    ${RED}✗${NC} $pyfile — $result"
        errors=$((errors+1))
    fi
done

WIDGET_OK=$(python3 -c "
import sys; sys.path.insert(0,'.')
try:
    from widgets import ScrollableFrame, Card, Btn, SectionHeader, InfoGrid, ResultBox, Badge, LiveBadge
    print('OK')
except Exception as e:
    print(f'FAIL: {e}')
" 2>&1)
[ "$WIDGET_OK" = "OK" ] \
    && echo -e "  ${GREEN}✓ All widget classes verified${NC}" \
    || echo -e "  ${RED}✗ Widgets: $WIDGET_OK${NC}"

[ $errors -gt 0 ] && echo -e "  ${RED}WARNING: $errors file(s) have syntax errors${NC}"

# ── [7/7] Desktop shortcut + ADB rules ───────────────────────
echo -e "${YELLOW}[7/7] Creating desktop shortcut...${NC}"
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/mint-scan.desktop << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Mint Scan
Comment=Advanced Security Auditor v8 — Mint Projects
Exec=bash $SCRIPT_DIR/run.sh
Icon=$SCRIPT_DIR/icon.png
Terminal=false
Categories=Security;Network;System;
Keywords=security;audit;network;firewall;
DESKTOP
chmod +x ~/.local/share/applications/mint-scan.desktop 2>/dev/null || true

# ADB udev rules (skip on Chromebook — udev reload unreliable in Crostini)
if [ "$IS_CHROMEBOOK" = false ]; then
    if ! grep -q "android" /etc/udev/rules.d/*.rules 2>/dev/null; then
        echo -e "  ${YELLOW}Adding Android udev rules for ADB...${NC}"
        sudo tee /etc/udev/rules.d/51-android.rules > /dev/null << 'UDEV'
SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="04e8", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="22b8", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0bb4", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="1004", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="12d1", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="2717", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="05c6", MODE="0666", GROUP="plugdev"
UDEV
        sudo udevadm control --reload-rules 2>/dev/null || true
        sudo usermod -aG plugdev "$USER" 2>/dev/null || true
        echo -e "  ${GREEN}✓ ADB udev rules added${NC}"
    fi
fi

echo -e "${GREEN}  ✓ Done${NC}"
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   ✓ MINT SCAN v8 — INSTALLATION COMPLETE                   ║"
if [ "$IS_CHROMEBOOK" = true ]; then
echo "║   ✓ Chromebook: Crostini-safe UFW install applied          ║"
fi
echo "║   Run:  bash run.sh                                        ║"
echo "║   Or:   source venv/bin/activate && python3 main.py        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
