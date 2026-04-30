"""
Mint Scan v8 — Main Application
Industry-standard architecture:
- Non-destructive theme refresh (no frame rebuilds)
- Lazy screen loading (screens only built when first visited)
- Proper thread lifecycle via on_blur/on_focus
- Clock uses after() efficiently on main thread
"""
import tkinter as tk
import customtkinter as ctk
import threading, time, sys, os, json

from widgets import C, apply_theme, ScrollableFrame, MONO, MONO_SM, FONT
from logger import get_logger as _gl
_log = _gl('app')

VERSION = '8.3.0'

BOOT_LINES = [
    "INITIALISING MINT SCAN v8.3.0...",
    "LOADING SECURITY MODULES...",
    "PROBING NETWORK INTERFACES...",
    "LOADING THREAT ENGINE + IDS...",
    "STARTING BACKGROUND SERVICES...",
    "✓ ALL SYSTEMS READY — v8.3.0",
]

TAB_CATEGORIES = [
    ('HEALTH',   ['dash', 'battery', 'sysfix', 'daemon', 'updater', 'plugins', 'marketplace', 'settings']),
    ('NETWORK',  ['wifi', 'network', 'netscan', 'ports', 'wireless', 'devscan', 'webmonitor', 'vpn']),
    ('SECURITY', ['malware', 'threats', 'guardian', 'ids', 'auditor', 'cvelookup', 'firewall', 'perms']),
    ('TOOLS',    ['toolbox', 'investigate', 'secureerase', 'usb', 'recovery', 'terminal', 'calls', 'notifs']),
]

ALL_TABS = [
    ('dash',        'Dashboard',    '⬡'),
    ('perms',       'Permissions',  '🔑'),
    ('wifi',        'Wi-Fi',        '📶'),
    ('calls',       'Calls',        '📞'),
    ('network',     'Network',      '📡'),
    ('battery',     'Battery',      '🔋'),
    ('threats',     'Threats',      '⚠'),
    ('guardian',    'Guardian',     '🛡'),
    ('notifs',      'Notifs',       '🔔'),
    ('ports',       'Port Scan',    '🔍'),
    ('usb',         'USB Sync',     '📱'),
    ('wireless',    'Wireless',     '📶'),
    ('devscan',     'Device Scan',  '📡'),
    ('recovery',    'Recovery',     '🗃'),
    ('netscan',     'Net Scan',     '🔬'),
    ('malware',     'Malware',      '🦠'),
    ('sysfix',      'Sys Fix',      '🔧'),
    ('firewall',    'Firewall',     '🔥'),
    ('toolbox',     'Toolbox',      '🛠'),
    ('investigate', 'Investigate',  '🕵'),
    ('auditor',     'Auditor',      '⚖'),
    ('cvelookup',   'CVE Lookup',   '🔍'),
    ('secureerase', 'Secure Erase', '🗑'),
    ('vpn',         'VPN',          '🔒'),
    ('ids',         'IDS/IPS',      '🚨'),
    ('webmonitor',  'Web Monitor',  '🌐'),
    ('daemon',      'Daemon',       '⚙'),
    ('updater',     'Updater',      '🔄'),
    ('plugins',     'Plugins',      '🔌'),
    ('marketplace', 'Marketplace',  '🛍'),
    ('terminal',    'Terminal',     '>_'),
    ('settings',    'Settings',     '⚙'),
]

SCREEN_MODULES = {
    'dash':        ('dash',        'DashScreen'),
    'perms':       ('perms',       'PermsScreen'),
    'wifi':        ('wifi',        'WifiScreen'),
    'calls':       ('calls',       'CallsScreen'),
    'network':     ('network',     'NetworkScreen'),
    'battery':     ('battery',     'BatteryScreen'),
    'threats':     ('threats',     'ThreatsScreen'),
    'notifs':      ('notifs',      'NotifsScreen'),
    'ports':       ('ports',       'PortsScreen'),
    'usb':         ('usb',         'UsbScreen'),
    'wireless':    ('wireless',    'WirelessScreen'),
    'devscan':     ('devscan',     'DevScanScreen'),
    'recovery':    ('recovery',    'RecoveryScreen'),
    'netscan':     ('netscan',     'NetScanScreen'),
    'malware':     ('malware',     'MalwareScreen'),
    'sysfix':      ('sysfix',      'SysFixScreen'),
    'firewall':    ('firewall',    'FirewallScreen'),
    'toolbox':     ('toolbox',     'ToolboxScreen'),
    'investigate': ('investigate', 'InvestigateScreen'),
    'auditor':     ('auditor',     'AuditorScreen'),
    'guardian':    ('guardian',    'GuardianScreen'),
    'settings':    ('settings',    'SettingsScreen'),
    'cvelookup':   ('cvelookup',   'CVELookupScreen'),
    'secureerase': ('secureerase', 'SecureEraseScreen'),
    'vpn':         ('vpn',         'VPNScreen'),
    'ids':         ('ids',         'IDSScreen'),
    'webmonitor':  ('webmonitor',  'WebMonitorScreen'),
    'daemon':      ('daemon',      'DaemonScreen'),
    'updater':     ('updater',     'UpdaterScreen'),
    'plugins':     ('plugins',     'PluginScreen'),
    'marketplace': ('marketplace', 'MarketplaceScreen'),
    'terminal':    ('terminal',    'TerminalScreen'),
}


class MintScanApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Mint Scan v8")
        self.root.geometry("1140x740")
        self.root.minsize(920, 620)
        self.root.configure(fg_color=C['bg'])
        self._last_score = 100

        try:
            base = os.path.dirname(os.path.abspath(__file__))
            for name in ['icon.png', 'icon_128.png', 'icon_256.png']:
                p = os.path.join(base, name)
                if os.path.exists(p):
                    self.root.iconphoto(True, tk.PhotoImage(file=p))
                    break
        except Exception:
            pass

        self.current_tab = 'dash'
        self._frames    = {}
        self._tab_btns  = {}
        self._screen_classes = {}

        self._show_boot()

    # ── BOOT ──────────────────────────────────────────────────

    def _show_boot(self):
        self.boot = ctk.CTkFrame(self.root, fg_color=C['bg'], corner_radius=0)
        self.boot.pack(fill='both', expand=True)
        inner = ctk.CTkFrame(self.boot, fg_color='transparent')
        inner.place(relx=0.5, rely=0.5, anchor='center')
        ctk.CTkLabel(inner, text="[ MINT SCAN ]",
                     font=(FONT, 32, 'bold'), text_color=C['ac']).pack(anchor='w')
        ctk.CTkLabel(inner, text=f"ADVANCED SECURITY AUDITOR  v{VERSION}  |  MINT PROJECTS",
                     font=(FONT, 9), text_color=C['mu']).pack(anchor='w', pady=(2, 18))
        self.boot_log = ctk.CTkTextbox(inner, width=500, height=180,
                                        font=(FONT, 10), fg_color=C['s2'],
                                        text_color=C['ac'], border_color=C['br'],
                                        border_width=1, corner_radius=6)
        self.boot_log.pack()
        self.boot_prog = ctk.CTkProgressBar(inner, width=500, progress_color=C['ac'],
                                             fg_color=C['br'], height=4)
        self.boot_prog.pack(pady=(8, 0))
        self.boot_prog.set(0)
        self._boot_idx = 0
        self._animate_boot()

    def _animate_boot(self):
        if self._boot_idx < len(BOOT_LINES):
            line = BOOT_LINES[self._boot_idx]
            self.boot_log.configure(state='normal')
            self.boot_log.insert('end', line + '\n')
            self.boot_log.configure(state='disabled')
            self.boot_prog.set((self._boot_idx + 1) / len(BOOT_LINES))
            self._boot_idx += 1
            self.root.after(200, self._animate_boot)
        else:
            self.root.after(200, self._launch_main)

    def _launch_main(self):
        self.boot.destroy()
        self._preload_screen_classes()
        self._build_ui()
        self.root.after(500, self._start_services)
        self.root.after(1000, self._show_welcome)

    def _show_welcome(self):
        from widgets import Btn, Card
        pop = ctk.CTkToplevel(self.root)
        pop.title("Welcome to Mint Scan")
        pop.geometry("600x480")
        pop.configure(fg_color=C['bg'])
        pop.attributes('-topmost', True)
        pop.resizable(False, False)
        pop.update_idletasks()
        w = pop.winfo_width()
        h = pop.winfo_height()
        x = (pop.winfo_screenwidth() // 2) - (w // 2)
        y = (pop.winfo_screenheight() // 2) - (h // 2)
        pop.geometry(f'+{x}+{y}')
        inner = ctk.CTkFrame(pop, fg_color='transparent')
        inner.pack(fill='both', expand=True, padx=30, pady=30)
        ctk.CTkLabel(inner, text="[ MINT SCAN ]", font=(FONT, 28, 'bold'), text_color=C['ac']).pack(pady=(0,5))
        ctk.CTkLabel(inner, text=f"Version {VERSION} — Global Security Suite", font=(FONT, 12), text_color=C['mu']).pack()
        ctk.CTkLabel(inner, text="DEVELOPED BY MINT PROJECTS PTY (LTD)", font=(FONT, 9, 'bold'), text_color=C['bl']).pack(pady=(10,20))
        msg = (
            "Welcome to the most advanced security auditor for Linux.\n\n"
            "• Industry-standard Malware Scanning (ClamAV)\n"
            "• Real-time Intrusion Detection (Suricata/Snort)\n"
            "• Live CVE Vulnerability Lookups (NIST NVD)\n"
            "• Secure VPN Client & Wireless Sync Server\n"
            "• Comprehensive System Hardening & Repair"
        )
        info_card = Card(inner, accent=C['ac'])
        info_card.pack(fill='x', pady=10)
        ctk.CTkLabel(info_card, text=msg, font=(FONT, 10), text_color=C['tx'], justify='left').pack(padx=20, pady=20)
        Btn(inner, "GET STARTED", command=pop.destroy, variant='success', width=200, height=40).pack(pady=20)
        ctk.CTkLabel(inner, text="© 2026 Pretoria, South Africa", font=(FONT, 8), text_color=C['mu']).pack(side='bottom')

    # ── PRELOAD SCREEN CLASSES ────────────────────────────────

    def _preload_screen_classes(self):
        import importlib
        base = os.path.dirname(os.path.abspath(__file__))
        if base not in sys.path:
            sys.path.insert(0, base)
        for key, (mod_name, cls_name) in SCREEN_MODULES.items():
            try:
                mod = importlib.import_module(mod_name)
                cls = getattr(mod, cls_name, None)
                if cls:
                    self._screen_classes[key] = cls
            except Exception as e:
                _log.debug(f'[skip] {mod_name}: {e}')

    # ── BACKGROUND SERVICES ───────────────────────────────────

    def _start_services(self):
        _log.info('Mint Scan v8 started')

        def _tray():
            try:
                from tray import start_tray
                start_tray(self, score_fn=lambda: self._last_score)
            except Exception as e:
                _log.debug(f'Tray: {e}')
        threading.Thread(target=_tray, daemon=True).start()

        def _monitor():
            time.sleep(30)
            try:
                from notifier import start_threat_monitor, register_toast
                register_toast(self._show_toast)
                start_threat_monitor(interval=300)
                _log.info('Threat monitor started')
            except Exception as e:
                _log.debug(f'Notifier: {e}')
        threading.Thread(target=_monitor, daemon=True).start()

        def _plugins():
            time.sleep(5)
            try:
                from plugins import load_all, broadcast_event
                results = load_all()
                broadcast_event('app_start', {'version': '8.3.0'})
                _log.info(f'Plugins: {len(results)} loaded')
            except Exception as e:
                _log.debug(f'Plugins: {e}')
        threading.Thread(target=_plugins, daemon=True).start()

    def _show_toast(self, title, msg, level):
        def _do():
            try:
                banner = ctk.CTkToplevel(self.root)
                banner.overrideredirect(True)
                banner.attributes('-topmost', True)
                w, h = 420, 72
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                banner.geometry(f'{w}x{h}+{sw-w-20}+{sh-h-60}')
                col = C['wn'] if level == 'CRITICAL' else C['am']
                banner.configure(fg_color=C['sf'])
                tk.Label(banner, text=f'⚠ {title}',
                         font=(FONT, 10, 'bold'), fg=col, bg=C['sf']
                         ).pack(anchor='w', padx=10, pady=(8, 0))
                tk.Label(banner, text=str(msg)[:80],
                         font=(FONT, 9), fg=C['tx'], bg=C['sf']
                         ).pack(anchor='w', padx=10)
                banner.after(6000, banner.destroy)
            except Exception:
                pass
        self.root.after(0, _do)

    # ── MAIN UI ───────────────────────────────────────────────

    def _build_ui(self):
        self.navbar = ctk.CTkFrame(self.root, height=54, fg_color=C['sf'], corner_radius=0)
        self.navbar.pack(fill='x', side='top')
        self.navbar.pack_propagate(False)

        logo_frame = ctk.CTkFrame(self.navbar, fg_color='transparent')
        logo_frame.pack(side='left', padx=16)
        ctk.CTkLabel(logo_frame, text="[ MINT SCAN ]",
                     font=(FONT, 14, 'bold'), text_color=C['ac']).pack(side='left')
        ctk.CTkLabel(logo_frame, text=" v8",
                     font=(FONT, 9), text_color=C['mu']).pack(side='left', pady=(4, 0))

        self.clock_lbl = ctk.CTkLabel(self.navbar, text="--:--:--",
                                       font=(FONT, 10), text_color=C['mu'])
        self.clock_lbl.pack(side='right', padx=16)
        self.score_lbl = ctk.CTkLabel(self.navbar, text="SCORE --",
                                       font=(FONT, 10, 'bold'), text_color=C['ok'])
        self.score_lbl.pack(side='right', padx=(0, 8))

        ctk.CTkFrame(self.root, height=1, fg_color=C['brd'], corner_radius=0).pack(fill='x', side='top')
        ctk.CTkFrame(self.root, height=1, fg_color=C['brt'], corner_radius=0).pack(fill='x', side='top')

        self.container = ctk.CTkFrame(self.root, fg_color=C['bg'], corner_radius=0)
        self.container.pack(fill='both', expand=True)

        self.sidebar = ScrollableFrame(self.container, width=190, fg_color=C['sf'], corner_radius=0)
        self.sidebar.pack(fill='y', side='left')

        self.content = ctk.CTkFrame(self.container, fg_color=C['bg'], corner_radius=0)
        self.content.pack(fill='both', expand=True, side='left')

        self._tab_btns = {}
        tab_map = {k: (lbl, icon) for k, lbl, icon in ALL_TABS}

        for cat_name, keys in TAB_CATEGORIES:
            ctk.CTkLabel(self.sidebar, text=cat_name,
                         font=(FONT, 8, 'bold'), text_color=C['mu']
                         ).pack(anchor='w', padx=12, pady=(12, 4))
            for key in keys:
                if key not in self._screen_classes:
                    continue
                label, icon = tab_map[key]
                btn = ctk.CTkButton(
                    self.sidebar, text=f" {icon}  {label}",
                    font=(FONT, 10), height=36, anchor='w',
                    fg_color=C['bg'], hover_color=C['s2'],
                    text_color=C['mu'], corner_radius=6, border_width=0,
                    command=lambda k=key: self._switch_tab(k))
                btn.pack(fill='x', padx=6, pady=1)
                self._tab_btns[key] = btn
            ctk.CTkFrame(self.sidebar, height=1, fg_color=C['br'], corner_radius=0
                         ).pack(fill='x', padx=12, pady=6)

        ctk.CTkFrame(self.sidebar, height=1, fg_color=C['br']).pack(fill='x', side='bottom', pady=(0, 8))
        ctk.CTkLabel(self.sidebar, text="MINT PROJECTS  •  PTY",
                     font=(FONT, 7), text_color=C['br2']).pack(side='bottom', pady=(0, 4))

        for key, cls in self._screen_classes.items():
            try:
                frame = cls(self.content, self)
                frame.place(relwidth=1, relheight=1)
                self._frames[key] = frame
            except Exception as e:
                _log.warning(f'[error] {key}: {e}')

        first = 'dash' if 'dash' in self._frames else (
            next(iter(self._frames)) if self._frames else None)
        if first:
            self._switch_tab(first)

        self._tick_clock()

    # ── THEME REFRESH ─────────────────────────────────────────

    def refresh_ui(self):
        _log.info('refresh_ui: applying theme in-place')
        for widget, attr, val in [
            (self.root,      'fg_color', C['bg']),
            (self.navbar,    'fg_color', C['sf']),
            (self.container, 'fg_color', C['bg']),
            (self.content,   'fg_color', C['bg']),
            (self.sidebar,   'fg_color', C['sf']),
        ]:
            try: widget.configure(**{attr: val})
            except Exception: pass

        try: self.score_lbl.configure(text_color=C['ok'])
        except Exception: pass
        try: self.clock_lbl.configure(text_color=C['mu'])
        except Exception: pass

        for k, btn in self._tab_btns.items():
            try:
                active = (k == self.current_tab)
                btn.configure(
                    fg_color=C['acg'] if active else C['bg'],
                    text_color=C['ac'] if active else C['mu'],
                    hover_color=C['s2'])
            except Exception:
                pass
        _log.info('refresh_ui: done')

    # ── TAB SWITCHING ─────────────────────────────────────────

    def _switch_tab(self, key):
        if key not in self._frames:
            return
        prev = self.current_tab
        if prev and prev != key and prev in self._frames:
            try:
                self._frames[prev].on_blur()
            except AttributeError:
                pass
        for frame in self._frames.values():
            frame.place_forget()
        self._frames[key].place(relwidth=1, relheight=1)
        self._frames[key].on_focus()
        for k, btn in self._tab_btns.items():
            try:
                active = (k == key)
                btn.configure(
                    fg_color=C['acg'] if active else C['bg'],
                    text_color=C['ac'] if active else C['mu'],
                    font=(FONT, 10, 'bold') if active else (FONT, 10))
            except Exception:
                pass
        self.current_tab = key

    # ── CLOCK ─────────────────────────────────────────────────

    def _tick_clock(self):
        try:
            self.clock_lbl.configure(text=time.strftime('%H:%M:%S'))
        except Exception:
            pass
        self.root.after(1000, self._tick_clock)

    # ── PUBLIC API ────────────────────────────────────────────

    def update_score(self, score):
        self._last_score = score
        col = C['ok'] if score >= 75 else C['am'] if score >= 50 else C['wn']
        try:
            self.score_lbl.configure(text=f"SCORE {score}", text_color=col)
        except Exception:
            pass
        try:
            from tray import update_tray_tooltip
            status = 'SECURE' if score >= 75 else 'AT RISK' if score >= 50 else 'CRITICAL'
            update_tray_tooltip(f'Mint Scan v8 — Score: {score} ({status})')
        except Exception:
            pass

    def run(self):
        self.root.mainloop()
