"""
Mint Scan v8 — System Tray Icon
Chromebook/Crostini-safe: detects missing systray manager and silently disables.
Uses AppIndicator3 on Ubuntu/Kali, falls back to pystray, then silently disables.
"""
import threading, os, sys
from logger import get_logger

log = get_logger('tray')
_tray_icon  = None
_tray_ok    = False


def _is_chromebook() -> bool:
    try:
        if os.path.exists('/proc/version'):
            v = open('/proc/version').read().lower()
            if 'cros' in v or 'chromeos' in v:
                return True
        import shutil
        return bool(shutil.which('crosh'))
    except Exception:
        return False


def _make_image(color_hex='#00ffe0', size=64):
    try:
        from PIL import Image, ImageDraw, ImageFont
        img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy = size // 2, size // 2
        # Shield shape
        pts = [
            (cx, 4), (size - 6, size // 4),
            (size - 6, size * 5 // 8),
            (cx, size - 4),
            (6, size * 5 // 8), (6, size // 4),
        ]
        r = int(color_hex[1:3], 16)
        g = int(color_hex[3:5], 16)
        b = int(color_hex[5:7], 16)
        draw.polygon(pts, fill=(r, g, b, 220), outline=(255, 255, 255, 160))
        return img
    except Exception as e:
        log.debug(f'PIL icon error: {e}')
        return None


def start_tray(app_ref, score_fn=None):
    """
    Start system tray. Silent no-op on Chromebook/Crostini where no systray
    manager exists. Also silently disables if pystray raises AssertionError.
    """
    global _tray_icon, _tray_ok

    # Chromebook Crostini has no system tray manager — skip entirely
    if _is_chromebook():
        log.info('Chromebook detected — system tray disabled (no systray manager)')
        return

    try:
        import pystray
    except ImportError:
        log.info('pystray not installed — tray disabled')
        return

    img = _make_image()
    if img is None:
        log.info('PIL unavailable — tray icon disabled')
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

    menu = pystray.Menu(
        pystray.MenuItem('Show Mint Scan', _show, default=True),
        pystray.MenuItem('Hide to Tray',   _hide),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quit',           _quit),
    )
    _tray_icon = pystray.Icon('mintscan', img, 'Mint Scan v8', menu)

    def _run():
        try:
            _tray_icon.run()
            log.info('System tray started')
        except AssertionError:
            # No systray manager running (common on minimal desktops)
            log.info('No systray manager — tray disabled silently')
        except Exception as e:
            log.info(f'Tray not available: {e}')

    threading.Thread(target=_run, daemon=True, name='tray').start()


def update_tray_tooltip(msg: str):
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
