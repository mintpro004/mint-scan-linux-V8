"""
Mint Scan v8 — Plugin System
Load custom security modules from ~/.mint_scan_plugins/
Each plugin is a Python file exposing:
  PLUGIN_META = {'name':'...', 'version':'1.0', 'author':'...', 'description':'...'}
  class PluginScreen(ctk.CTkFrame): ...
"""
import os, sys, importlib.util, threading, time, traceback
import customtkinter as ctk
import tkinter as tk
from widgets import C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader, Btn, ResultBox
from logger import get_logger

log = get_logger('plugins')

PLUGIN_DIR = os.path.expanduser('~/.mint_scan_plugins/')
if not os.path.exists(PLUGIN_DIR):
    os.makedirs(PLUGIN_DIR, exist_ok=True)

_loaded = {}  # name -> module


def discover():
    """Return list of .py filenames in PLUGIN_DIR."""
    if not os.path.exists(PLUGIN_DIR):
        return []
    return sorted(
        f for f in os.listdir(PLUGIN_DIR)
        if f.endswith('.py') and not f.startswith('_'))


def load_plugin(filename: str) -> dict | None:
    """
    Load a single plugin file.
    Returns {'meta':..., 'module':..., 'screen_cls':..., 'error':...}
    """
    path = os.path.join(PLUGIN_DIR, filename)
    name = filename[:-3]
    try:
        spec = importlib.util.spec_from_file_location(f'mintscan_plugin_{name}', path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        meta = getattr(mod, 'PLUGIN_META', {
            'name': name, 'version': '?',
            'author': '?', 'description': '(no description)'})
        screen_cls = getattr(mod, 'PluginScreen', None)

        _loaded[name] = mod
        log.info(f'Plugin loaded: {meta["name"]} v{meta["version"]}')
        return {'meta': meta, 'module': mod,
                'screen_cls': screen_cls, 'filename': filename, 'error': None}
    except Exception as e:
        err = traceback.format_exc()
        log.warning(f'Plugin {filename} failed: {e}')
        return {'meta': {'name': name}, 'filename': filename,
                'screen_cls': None, 'error': str(e)}


def load_all() -> list:
    """Load all discovered plugins. Returns list of result dicts."""
    results = []
    for fn in discover():
        results.append(load_plugin(fn))
    return results


def broadcast_event(event: str, data=None):
    """Fire an event to all loaded plugins that expose on_event()."""
    for name, mod in list(_loaded.items()):
        fn = getattr(mod, 'on_event', None)
        if fn:
            try:
                fn(event, data)
            except Exception as e:
                log.warning(f'Plugin {name} on_event error: {e}')


def unload_plugin(name: str):
    """Remove a plugin from the loaded set."""
    _loaded.pop(name, None)


def get_loaded() -> dict:
    return dict(_loaded)


# ── Plugin Manager Screen ─────────────────────────────────────────

class PluginScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app    = app
        self._built = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._refresh()

    def on_blur(self):
        """Called when switching away — no background threads to stop."""
        pass

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text='🔌  PLUGIN MANAGER',
                     font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, '↺ RELOAD', command=self._refresh,
            variant='ghost', width=90).pack(side='right', padx=8, pady=6)
        Btn(hdr, '📂 OPEN FOLDER',
            command=lambda: os.system(f'xdg-open "{PLUGIN_DIR}" &'),
            variant='ghost', width=130).pack(side='right', padx=4, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)

    def _refresh(self):
        for w in self.scroll.winfo_children(): w.destroy()
        body = self.scroll

        # ── CORE MODULES ──────────────────────────────────────
        SectionHeader(body, '01', 'CORE SECURITY MODULES').pack(fill='x', padx=14, pady=(14,4))
        core_card = Card(body)
        core_card.pack(fill='x', padx=14, pady=(0,8))
        
        from app import ALL_TABS
        tab_map = {k: (lbl, icon) for k, lbl, icon in ALL_TABS}
        
        grid = ctk.CTkFrame(core_card, fg_color='transparent')
        grid.pack(fill='x', padx=12, pady=12)
        
        core_keys = ['malware', 'network', 'firewall', 'guardian', 'ids', 'auditor', 'vpn']
        for i, key in enumerate(core_keys):
            lbl, icon = tab_map.get(key, (key.upper(), '🛠'))
            r_idx, c_idx = divmod(i, 2)
            f = ctk.CTkFrame(grid, fg_color=C['s2'], corner_radius=6)
            f.grid(row=r_idx, column=c_idx, padx=4, pady=4, sticky='ew')
            ctk.CTkLabel(f, text=f"{icon} {lbl}", font=MONO, text_color=C['ac']).pack(side='left', padx=10, pady=8)
            ctk.CTkLabel(f, text="INSTALLED", font=('DejaVu Sans Mono', 8, 'bold'), text_color=C['ok']).pack(side='right', padx=10)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # ── EXTERNAL PLUGINS ──────────────────────────────────
        SectionHeader(body, '02', 'EXTERNAL PLUGINS').pack(fill='x', padx=14, pady=(10,4))
        ext_card = Card(body)
        ext_card.pack(fill='x', padx=14, pady=(0,8))
        
        results = load_all()
        if not results:
            ctk.CTkLabel(ext_card, text="No external plugins found in ~/.mint_scan_plugins/",
                         font=MONO_SM, text_color=C['mu']).pack(pady=20)
        else:
            for res in results:
                m = res.get('meta', {})
                ok = res.get('error') is None
                self._render_plugin_row(ext_card, m, ok, res.get('error'))

    def _render_plugin_row(self, parent, m, ok, err=None):
        row = ctk.CTkFrame(parent, fg_color=C['s2'], corner_radius=6)
        row.pack(fill='x', padx=10, pady=4)
        title_r = ctk.CTkFrame(row, fg_color='transparent')
        title_r.pack(fill='x', padx=10, pady=(8,2))
        ctk.CTkLabel(title_r, text=m.get('name','Unknown'), font=MONO,
                     text_color=C['ac'] if ok else C['wn']).pack(side='left')
        ctk.CTkLabel(title_r, text=f"v{m.get('version','1.0')}", font=('DejaVu Sans Mono', 8),
                     text_color=C['mu']).pack(side='left', padx=10)
        ctk.CTkLabel(title_r, text="● ACTIVE" if ok else "● ERROR",
                     font=('DejaVu Sans Mono', 8, 'bold'),
                     text_color=C['ok'] if ok else C['wn']
                     ).pack(side='right')
        ctk.CTkLabel(row,
            text=m.get('description', err or ''),
            font=('DejaVu Sans Mono', 9), text_color=C['mu'],
            wraplength=600, justify='left'
            ).pack(anchor='w', padx=10, pady=(0, 8))
