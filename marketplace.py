"""
Mint Scan v8 — Plugin Marketplace
Browse, download, and install plugins from the official GitHub repo.
Also manage local plugins.
"""
import os, threading, json, time, shutil
import urllib.request
import tkinter as tk
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame,
                     Card, SectionHeader, Btn, InfoGrid)
from logger import get_logger
from plugins import PLUGIN_DIR, load_plugin, discover

log = get_logger('marketplace')

MARKETPLACE_URL = (
    'https://raw.githubusercontent.com/mintpro004/'
    'mint-scan-linux-V8/main/plugins/marketplace.json')

# Bundled catalogue — works offline if GitHub unreachable
# Built-in plugin templates — installed locally, no network needed
BUILTIN_PLUGINS = {
    'port_monitor': '''"""Port Change Monitor — Mint Scan v8 Plugin"""
PLUGIN_META = {'name': 'Port Change Monitor', 'version': '1.0',
               'author': 'Mint Projects', 'description': 'Alerts when open ports change vs baseline.'}
import json, os
_BASELINE_FILE = os.path.expanduser('~/.mint_scan_port_baseline.json')
def on_event(event, data):
    if event == 'scan_complete' and data:
        pass  # compare ports to baseline
''',
    'login_audit': '''"""Login Auditor — Mint Scan v8 Plugin"""
PLUGIN_META = {'name': 'Login Auditor', 'version': '1.0',
               'author': 'Mint Projects', 'description': 'Monitors SSH and local logins via journal.'}
import subprocess, time
def on_event(event, data):
    if event == 'app_start':
        pass  # start monitoring journal
''',
    'wifi_tracker': '''"""Wi-Fi Network Tracker — Mint Scan v8 Plugin"""
PLUGIN_META = {'name': 'Wi-Fi Tracker', 'version': '1.0',
               'author': 'Mint Projects', 'description': 'Logs all Wi-Fi networks seen over time.'}
import os, time, json
_LOG = os.path.expanduser('~/.mint_scan_wifi_seen.json')
def on_event(event, data):
    pass
''',
}

BUNDLED_CATALOGUE = [
    {'id': 'port_monitor', 'name': 'Port Change Monitor', 'version': '1.0',
     'author': 'Mint Projects', 'description': 'Alerts when open ports change vs your baseline scan.',
     'tags': ['network', 'monitoring'], 'builtin': True, 'official': True},
    {'id': 'login_audit', 'name': 'Login Auditor', 'version': '1.0',
     'author': 'Mint Projects', 'description': 'Tracks SSH and local login success/failures via systemd journal.',
     'tags': ['auth', 'audit'], 'builtin': True, 'official': True},
    {'id': 'wifi_tracker', 'name': 'Wi-Fi Network Tracker', 'version': '1.0',
     'author': 'Mint Projects', 'description': 'Logs all Wi-Fi networks seen over time to a JSON file.',
     'tags': ['wifi', 'logging'], 'builtin': True, 'official': True},
]


def fetch_catalogue() -> list:
    """Try to fetch live catalogue from GitHub, fall back to bundled."""
    try:
        req = urllib.request.Request(
            MARKETPLACE_URL, headers={'User-Agent': 'MintScan-Marketplace/8'})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        log.info(f'Marketplace: fetched {len(data)} plugins from GitHub')
        return data
    except Exception as e:
        log.info(f'Marketplace offline ({e}) — using bundled catalogue')
        return BUNDLED_CATALOGUE


def install_plugin_from_url(url: str, plugin_id: str) -> tuple[bool, str]:
    """Install a plugin — from builtin templates or from URL."""
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    dest = os.path.join(PLUGIN_DIR, f'{plugin_id}.py')
    # Check builtin first (works offline)
    if plugin_id in BUILTIN_PLUGINS:
        try:
            code_content = BUILTIN_PLUGINS[plugin_id]
            import ast as _ast
            _ast.parse(code_content)
            with open(dest, 'w') as f:
                f.write(code_content)
            log.info(f'Plugin installed from builtin: {plugin_id}')
            return True, dest
        except Exception as e:
            return False, str(e)
    if not url:
        return False, 'No URL and not a builtin plugin'
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'MintScan-Marketplace/8'})
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.read().decode()
        # Basic safety check
        danger = ['import os;', 'subprocess.call', 'eval(', 'exec(']
        for d in danger:
            if d in code:
                return False, f'Plugin rejected: suspicious code pattern ({d})'
        # Validate syntax
        import ast
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f'Plugin has syntax error: {e}'
        with open(dest, 'w') as f:
            f.write(code)
        log.info(f'Plugin installed: {plugin_id} → {dest}')
        return True, dest
    except Exception as e:
        return False, str(e)


def install_plugin_from_file(path: str) -> tuple[bool, str]:
    """Copy a local .py file into PLUGIN_DIR."""
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    name = os.path.basename(path)
    dest = os.path.join(PLUGIN_DIR, name)
    try:
        import ast
        code = open(path).read()
        ast.parse(code)
        shutil.copy2(path, dest)
        log.info(f'Plugin installed from file: {dest}')
        return True, dest
    except SyntaxError as e:
        return False, f'Syntax error: {e}'
    except Exception as e:
        return False, str(e)


class MarketplaceScreen(ctk.CTkFrame):
    def _safe_after(self, delay, fn, *args):
        """Thread-safe after() that guards against destroyed widgets."""
        def _guarded():
            try:
                if self.winfo_exists():
                    fn(*args)
            except Exception:
                pass
        try:
            self.after(delay, _guarded)
        except Exception:
            pass


    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app       = app
        self._built    = False
        self._catalogue = []
        self._installed = set()

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._refresh_installed()
        threading.Thread(target=self._load_catalogue, daemon=True).start()

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='🛍  PLUGIN MARKETPLACE',
                     font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, '↺ REFRESH', command=lambda: threading.Thread(
            target=self._load_catalogue, daemon=True).start(),
            variant='ghost', width=90).pack(side='right', padx=8, pady=8)
        Btn(hdr, '📂 MY PLUGINS',
            command=lambda: os.system(f'xdg-open "{PLUGIN_DIR}" 2>/dev/null &'),
            variant='ghost', width=120).pack(side='right', padx=4, pady=8)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)
        self._body = body

        # Search
        SectionHeader(body, '01', 'SEARCH & FILTER').pack(
            fill='x', padx=14, pady=(14, 4))
        sc = Card(body)
        sc.pack(fill='x', padx=14, pady=(0, 8))
        sr = ctk.CTkFrame(sc, fg_color='transparent')
        sr.pack(fill='x', padx=12, pady=10)
        self._search_var = ctk.StringVar()
        self._search_var.trace_add('write', lambda *_: self._filter_catalogue())
        ctk.CTkEntry(
            sr, textvariable=self._search_var,
            placeholder_text='Search plugins...',
            font=('Courier', 10), fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'], height=34
            ).pack(side='left', fill='x', expand=True, padx=(0, 8))
        Btn(sr, '⬆ INSTALL .PY',
            command=self._install_local, variant='ghost', width=130).pack(side='left')

        # Status line
        self._status_lbl = ctk.CTkLabel(sc, text='Loading catalogue...',
                                          font=MONO_SM, text_color=C['mu'])
        self._status_lbl.pack(anchor='w', padx=12, pady=(0,8))

        # Installed plugins
        SectionHeader(body, '02', 'INSTALLED PLUGINS').pack(
            fill='x', padx=14, pady=(8, 4))
        self._inst_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._inst_frame.pack(fill='x', padx=14, pady=(0, 8))

        # Available plugins
        SectionHeader(body, '03', 'AVAILABLE PLUGINS').pack(
            fill='x', padx=14, pady=(8, 4))
        self._avail_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._avail_frame.pack(fill='x', padx=14, pady=(0, 14))

    def _refresh_installed(self):
        for w in self._inst_frame.winfo_children():
            w.destroy()
        installed = discover()
        self._installed = set(f[:-3] for f in installed)
        if not installed:
            ctk.CTkLabel(self._inst_frame,
                text='No plugins installed yet.',
                font=MONO_SM, text_color=C['mu']).pack(pady=6)
            return
        for fn in installed:
            result = load_plugin(fn)
            m   = result['meta']
            err = result['error']
            row = ctk.CTkFrame(
                self._inst_frame, fg_color=C['sf'],
                border_color=C['ok'] if not err else C['wn'],
                border_width=1, corner_radius=6)
            row.pack(fill='x', pady=3)
            lr = ctk.CTkFrame(row, fg_color='transparent')
            lr.pack(fill='x', padx=10, pady=8)
            ctk.CTkLabel(lr,
                text=f"{'✓' if not err else '✗'}  {m.get('name','?')}  v{m.get('version','?')}",
                font=('Courier', 10, 'bold'),
                text_color=C['ok'] if not err else C['wn']
                ).pack(side='left')
            plugin_id = fn[:-3]
            Btn(lr, '🗑 REMOVE',
                command=lambda pid=plugin_id: self._remove_plugin(pid),
                variant='ghost', width=90, height=28).pack(side='right')
            ctk.CTkLabel(row,
                text=m.get('description', err or '(no description)'),
                font=('Courier', 9), text_color=C['mu']
                ).pack(anchor='w', padx=10, pady=(0, 6))

    def _load_catalogue(self):
        self._safe_after(0, self._status_lbl.configure,
                   {'text': 'Fetching from GitHub...', 'text_color': C['ac']})
        self._catalogue = fetch_catalogue()
        self._safe_after(0, self._filter_catalogue)
        self._safe_after(0, self._status_lbl.configure,
                   {'text': f'{len(self._catalogue)} plugins available',
                    'text_color': C['ok']})

    def _filter_catalogue(self):
        try:
            if not self.winfo_exists(): return
        except Exception: return
        query = self._search_var.get().lower().strip()
        for w in self._avail_frame.winfo_children():
            w.destroy()
        items = [p for p in self._catalogue
                 if not query or query in p.get('name','').lower()
                 or query in p.get('description','').lower()
                 or any(query in t for t in p.get('tags', []))]
        if not items:
            ctk.CTkLabel(self._avail_frame,
                text='No plugins match your search.',
                font=MONO_SM, text_color=C['mu']).pack(pady=8)
            return
        for p in items:
            pid       = p['id']
            installed = pid in self._installed
            card = ctk.CTkFrame(
                self._avail_frame, fg_color=C['sf'],
                border_color=C['ok'] if installed else C['br'],
                border_width=1, corner_radius=6)
            card.pack(fill='x', pady=4)
            hr = ctk.CTkFrame(card, fg_color='transparent')
            hr.pack(fill='x', padx=10, pady=(10,2))
            # Name + version + official badge
            name_txt = p['name']
            if p.get('official'):
                name_txt += '  ★'
            ctk.CTkLabel(hr,
                text=name_txt,
                font=('Courier', 11, 'bold'), text_color=C['ac']
                ).pack(side='left')
            ctk.CTkLabel(hr,
                text=f"v{p['version']}  by {p['author']}",
                font=('Courier', 8), text_color=C['mu']
                ).pack(side='left', padx=8)
            if installed:
                ctk.CTkLabel(hr,
                    text='✓ Installed',
                    font=('Courier', 8, 'bold'), text_color=C['ok']
                    ).pack(side='right')
            else:
                Btn(hr, '⬇ INSTALL',
                    command=lambda plug=p: self._install_plugin(plug),
                    width=90, height=28).pack(side='right')
            ctk.CTkLabel(card,
                text=p['description'],
                font=('Courier', 9), text_color=C['tx']
                ).pack(anchor='w', padx=10, pady=(0,4))
            tag_row = ctk.CTkFrame(card, fg_color='transparent')
            tag_row.pack(anchor='w', padx=10, pady=(0,8))
            for tag in p.get('tags', []):
                ctk.CTkLabel(tag_row,
                    text=f'#{tag}',
                    font=('Courier', 8), text_color=C['bl']
                    ).pack(side='left', padx=2)

    def _install_plugin(self, plug):
        pid = plug['id']
        url = plug.get('url', '') if not plug.get('builtin') else ''
        self._status_lbl.configure(
            text=f'Installing {plug["name"]}...', text_color=C['ac'])
        def _bg():
            ok, result = install_plugin_from_url(url, pid)
            def _done():
                try:
                    if not self.winfo_exists(): return
                    self._status_lbl.configure(
                        text=f'{"✓" if ok else "✗"} {plug["name"]}: {os.path.basename(result) if ok else result}',
                        text_color=C['ok'] if ok else C['wn'])
                    if ok:
                        self._refresh_installed()
                        self._filter_catalogue()
                except Exception: pass
            self._safe_after(0, _done)
        threading.Thread(target=_bg, daemon=True).start()

    def _install_local(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title='Select Plugin .py File',
            filetypes=[('Python files', '*.py'), ('All', '*.*')])
        if not path:
            return
        ok, result = install_plugin_from_file(path)
        self._status_lbl.configure(
            text=f'{"✓ Installed: " if ok else "✗ Failed: "}{os.path.basename(result) if ok else result}',
            text_color=C['ok'] if ok else C['wn'])
        if ok:
            self._refresh_installed()

    def _remove_plugin(self, plugin_id):
        path = os.path.join(PLUGIN_DIR, f'{plugin_id}.py')
        try:
            os.remove(path)
            self._status_lbl.configure(
                text=f'✓ Removed: {plugin_id}', text_color=C['am'])
            self._refresh_installed()
            self._filter_catalogue()
        except Exception as e:
            self._status_lbl.configure(
                text=f'✗ Remove failed: {e}', text_color=C['wn'])
