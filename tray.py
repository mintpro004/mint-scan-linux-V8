"""
Mint Scan v8 — System Tray Icon
Uses pystray (pip install pystray pillow).
Falls back gracefully if not available.
"""
import threading, os, sys
from logger import get_logger

log = get_logger('tray')
_tray_icon = None


def _make_image(color_hex='#00ffe0', size=64):
    """Create a simple shield icon programmatically (no file dependency)."""
    try:
        from PIL import Image, ImageDraw
        img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Shield outline
        pts = [
            (size//2, 4),
            (size-4, size//4),
            (size-4, size*5//8),
            (size//2, size-4),
            (4, size*5//8),
            (4, size//4),
        ]
        r, g, b = int(color_hex[1:3],16), int(color_hex[3:5],16), int(color_hex[5:7],16)
        draw.polygon(pts, fill=(r, g, b, 220), outline=(255,255,255,180))
        # Letter M
        draw.text((size//2-6, size//3), 'M',
                  fill=(5, 17, 31, 255), font=None)
        return img
    except Exception as e:
        log.warning(f'PIL not available for tray icon: {e}')
        return None


def start_tray(app_ref, score_fn=None):
    """
    Start the system tray icon.
    app_ref   – MintScanApp instance (for show/hide)
    score_fn  – callable returning current score int
    """
    global _tray_icon
    try:
        import pystray
    except ImportError:
        log.warning('pystray not installed — system tray disabled. '
                    'Run: pip install pystray pillow --break-system-packages')
        return

    img = _make_image()
    if img is None:
        return

    def _show(icon, item):
        try:
            app_ref.root.after(0, app_ref.root.deiconify)
            app_ref.root.after(0, app_ref.root.lift)
        except Exception:
            pass

    def _hide(icon, item):
        try:
            app_ref.root.after(0, app_ref.root.withdraw)
        except Exception:
            pass

    def _quit(icon, item):
        icon.stop()
        try:
            app_ref.root.after(0, app_ref.root.destroy)
        except Exception:
            pass

    def _title():
        score = score_fn() if score_fn else '—'
        return f'Mint Scan v8  —  Score: {score}'

    menu = pystray.Menu(
        pystray.MenuItem('Show Mint Scan', _show, default=True),
        pystray.MenuItem('Hide to Tray',   _hide),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_title,           None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit',           _quit),
    )
    _tray_icon = pystray.Icon('mintscan', img, 'Mint Scan v8', menu)

    def _run():
        log.info('System tray icon started')
        _tray_icon.run()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def update_tray_tooltip(msg: str):
    """Update tray tooltip text."""
    global _tray_icon
    if _tray_icon:
        try:
            _tray_icon.title = msg
        except Exception:
            pass


def stop_tray():
    global _tray_icon
    if _tray_icon:
        try:
            _tray_icon.stop()
        except Exception:
            pass

