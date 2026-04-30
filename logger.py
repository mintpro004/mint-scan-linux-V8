"""
Mint Scan v8 — Centralised Logging
Replaces all print() statements with structured logging to file + GUI.
All modules import: from logger import log, LOG_FILE
"""
import logging, os, sys, threading
from datetime import datetime

LOG_FILE = os.path.expanduser('~/.mint_scan_v8.log')
_gui_callbacks = []          # functions to call with (level, msg)
_lock = threading.Lock()

# ── File + stream handler ─────────────────────────────────────────
_fmt = logging.Formatter(
    '%(asctime)s [%(levelname)-8s] %(name)s — %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

_file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
_file_handler.setFormatter(_fmt)

_root = logging.getLogger('mintscan')
_root.setLevel(logging.DEBUG)
_root.addHandler(_file_handler)

# Suppress noisy third-party libs
for _noisy in ('urllib3', 'requests', 'speedtest'):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


class _GuiHandler(logging.Handler):
    """Forward log records to registered GUI callbacks."""
    def emit(self, record):
        msg = self.format(record)
        with _lock:
            for cb in list(_gui_callbacks):
                try:
                    cb(record.levelname, msg)
                except Exception:
                    pass

_gui_h = _GuiHandler()
_gui_h.setFormatter(_fmt)
_root.addHandler(_gui_h)


def get_logger(name: str) -> logging.Logger:
    """Get a named child logger — use in every module."""
    return _root.getChild(name)

def register_gui_callback(fn):
    """Register a function(level, msg) to receive log lines in the GUI."""
    with _lock:
        _gui_callbacks.append(fn)

def unregister_gui_callback(fn):
    with _lock:
        if fn in _gui_callbacks:
            _gui_callbacks.remove(fn)

def log(level: str, msg: str, name: str = 'app'):
    """Convenience wrapper: log(\'INFO\', \'message\')"""
    lgr = get_logger(name)
    getattr(lgr, level.lower(), lgr.info)(msg)

def get_log_tail(n: int = 200) -> str:
    """Return the last n lines of the log file."""
    try:
        with open(LOG_FILE, encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        return ''.join(lines[-n:])
    except Exception:
        return ''

def clear_log():
    """Truncate the log file."""
    try:
        open(LOG_FILE, 'w').close()
    except Exception:
        pass

