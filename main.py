#!/usr/bin/env python3
"""
Mint Scan v8 — Entry Point
Cross-platform launcher: x86_64, aarch64, Chromebook, WSL2, Wayland, X11.
"""
import sys, os

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# ── Display / Wayland setup BEFORE any tkinter import ────────────
def _configure_display():
    """
    Ensure a display is available.
    - On Wayland: force XWayland via DISPLAY=:0 unless already set
    - On WSL2: set DISPLAY=:0 if not set
    - On headless: detect early and exit cleanly
    """
    # Already configured
    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        return

    # Try to find an X display
    for d in [':0', ':1', ':10']:
        import subprocess
        r = subprocess.run(['xdpyinfo', '-display', d],
                          capture_output=True, timeout=2)
        if r.returncode == 0:
            os.environ['DISPLAY'] = d
            return

    # Chromebook Crostini default
    if os.path.exists('/proc/version'):
        v = open('/proc/version').read().lower()
        if 'cros' in v or 'chrome' in v:
            os.environ['DISPLAY'] = ':0'
            return

    # WSL2 detection
    if os.path.exists('/proc/sys/fs/binfmt_misc/WSLInterop'):
        os.environ['DISPLAY'] = ':0'
        return

_configure_display()

# ── Theme pre-load ───────────────────────────────────────────────
def _load_theme():
    import widgets as _w
    return _w.load_theme_settings()

UI_SCALE = _load_theme()

import customtkinter as ctk
try:
    ctk.set_widget_scaling(UI_SCALE)
except Exception:
    pass

# ── Wayland/HiDPI fixes ──────────────────────────────────────────
# Force XWayland mode — native Wayland has no reliable tkinter backend yet
os.environ.setdefault('GDK_BACKEND', 'x11')
os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')

from app import MintScanApp

if __name__ == '__main__':
    try:
        app = MintScanApp()
        app.run()
    except Exception as e:
        import traceback, sys as _sys
        _sys.stderr.write(f"\n[Mint Scan] Fatal startup error: {e}\n\n")
        traceback.print_exc()
        _sys.stderr.write("\nTroubleshooting:\n")
        _sys.stderr.write("  1. Make sure you ran: bash install.sh\n")
        _sys.stderr.write("  2. For Wayland: export DISPLAY=:0 && bash run.sh\n")
        _sys.stderr.write("  3. For headless: Xvfb :0 -screen 0 1280x800x24 & export DISPLAY=:0\n")
        _sys.exit(1)
