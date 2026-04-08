"""
Mint Scan v8 — Plugin System
Load custom security modules from ~/.mint_scan_plugins/
Each plugin is a Python file exposing:
  PLUGIN_META = {'name':'...', 'version':'1.0', 'author':'...', 'description':'...'}
  class PluginScreen(ctk.CTkFrame): ...   (optional — adds a tab)
  def on_event(event, data): ...         (optional — receives app events)
"""
import os, sys, importlib.util, traceback, json
from logger import get_logger

log = get_logger('plugins')

PLUGIN_DIR  = os.path.expanduser('~/.mint_scan_plugins')
_loaded     = {}   # name → module


def ensure_dir():
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    readme = os.path.join(PLUGIN_DIR, 'README.txt')
    if not os.path.exists(readme):
        with open(readme, 'w') as f:
            f.write("""MINT SCAN v8 — PLUGIN DIRECTORY
=================================
Drop .py files here to add custom modules.

Each plugin must contain:
  PLUGIN_META = {
      'name':        'My Plugin',
      'version':     '1.0',
      'author':      'Your Name',
      'description': 'What it does',
  }

Optional:
  class PluginScreen(ctk.CTkFrame):  # adds a sidebar tab
      def __init__(self, parent, app): ...
      def on_focus(self): ...

  def on_event(event, data): ...     # receives 'threat_found', 'scan_complete' etc.

Example plugins: https://github.com/mintpro004/mint-scan-linux-V8/tree/main/plugins
""")


def discover():
    """Scan PLUGIN_DIR for .py files. Returns list of paths."""
    ensure_dir()
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
import tkinter as tk
import customtkinter as ctk
from widgets import C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader, Btn, ResultBox


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

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)
        self._body = body

        SectionHeader(body, '01', 'PLUGIN DIRECTORY').pack(
            fill='x', padx=14, pady=(14, 4))
        dc = Card(body)
        dc.pack(fill='x', padx=14, pady=(0, 8))
        ctk.CTkLabel(dc, text=PLUGIN_DIR,
                     font=('DejaVu Sans Mono', 9), text_color=C['ac']
                     ).pack(anchor='w', padx=12, pady=8)
        ctk.CTkLabel(dc,
            text='Drop .py plugin files here. Each plugin can add a sidebar tab\n'
                 'or react to security events (threats, scans, port opens).',
            font=('DejaVu Sans Mono', 9), text_color=C['mu'], justify='left'
            ).pack(anchor='w', padx=12, pady=(0, 10))

        SectionHeader(body, '02', 'INSTALLED PLUGINS').pack(
            fill='x', padx=14, pady=(8, 4))
        self._list_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._list_frame.pack(fill='x', padx=14, pady=(0, 14))

    def _refresh(self):
        for w in self._list_frame.winfo_children():
            w.destroy()
        results = load_all()
        if not results:
            ctk.CTkLabel(self._list_frame,
                text='No plugins found.\nDrop .py files into: ' + PLUGIN_DIR,
                font=MONO_SM, text_color=C['mu']
                ).pack(pady=12)
            return
        for r in results:
            m   = r['meta']
            err = r['error']
            row = ctk.CTkFrame(
                self._list_frame, fg_color=C['sf'],
                border_color=C['ok'] if not err else C['wn'],
                border_width=1, corner_radius=6)
            row.pack(fill='x', pady=3)
            lc = ctk.CTkFrame(row, fg_color='transparent')
            lc.pack(fill='x', padx=10, pady=8)
            ctk.CTkLabel(lc,
                text=f"{'✓' if not err else '✗'}  {m.get('name','?')}  v{m.get('version','?')}",
                font=('DejaVu Sans Mono', 10, 'bold'),
                text_color=C['ok'] if not err else C['wn']
                ).pack(side='left')
            ctk.CTkLabel(lc,
                text=f"  by {m.get('author','?')}",
                font=('DejaVu Sans Mono', 8), text_color=C['mu']
                ).pack(side='left')
            ctk.CTkLabel(row,
                text=m.get('description', err or ''),
                font=('DejaVu Sans Mono', 9), text_color=C['mu']
                ).pack(anchor='w', padx=10, pady=(0, 8))

