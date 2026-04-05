#!/usr/bin/env python3
"""
Mint Scan v8 — Entry Point
Loads saved theme before window opens, then launches app.
"""
import sys, os

# Add this directory to path first
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# Apply saved theme BEFORE importing ctk or creating window
def _load_and_apply_theme():
    import widgets as _w
    scale = _w.load_theme_settings()
    return scale

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
