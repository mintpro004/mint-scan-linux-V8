"""
Mint Scan v8 — VPN Client
Supports WireGuard and OpenVPN.
Auto-discovers available WireGuard configs — no path entry needed.
One-button connect with interface selector dropdown.
"""
import os, threading, subprocess, time, glob, shutil
import tkinter as tk
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, InfoGrid)
from utils import run_cmd
from logger import get_logger

log = get_logger('vpn')

WG_DIRS = ['/etc/wireguard', '/home', os.path.expanduser('~')]


def find_wg_configs() -> list:
    """Scan standard locations for .conf WireGuard config files."""
    found = []
    for d in ['/etc/wireguard', os.path.expanduser('~'),
              os.path.expanduser('~/wireguard'),
              os.path.expanduser('~/vpn')]:
        if os.path.isdir(d):
            for f in glob.glob(os.path.join(d, '*.conf')):
                found.append(f)
    return sorted(set(found))


def find_ovpn_configs() -> list:
    found = []
    for d in [os.path.expanduser('~'),
              os.path.expanduser('~/vpn'),
              os.path.expanduser('~/openvpn'),
              '/etc/openvpn']:
        if os.path.isdir(d):
            for f in glob.glob(os.path.join(d, '*.ovpn')):
                found.append(f)
    return sorted(set(found))


def detect_vpn_tools() -> dict:
    return {
        'openvpn':  bool(shutil.which('openvpn')),
        'wg':       bool(shutil.which('wg')),
        'wg-quick': bool(shutil.which('wg-quick')),
        'nmcli':    bool(shutil.which('nmcli')),
    }


def get_vpn_status() -> dict:
    wg_out, _, wg_rc = run_cmd('sudo wg show 2>/dev/null', timeout=5)
    iface_out, _, _  = run_cmd('ip link show type tun 2>/dev/null')
    nm_out, _, nm_rc = run_cmd(
        "nmcli -t -f TYPE,STATE con show --active 2>/dev/null | grep -i vpn")
    active_ifaces, _, _ = run_cmd('wg show interfaces 2>/dev/null')
    return {
        'wireguard_active':  bool(active_ifaces.strip()),
        'wireguard_ifaces':  active_ifaces.strip().split() if active_ifaces.strip() else [],
        'wireguard_info':    wg_out.strip()[:400],
        'tun_active':        bool(iface_out.strip()),
        'nm_vpn_active':     bool(nm_out.strip()),
    }


class VPNScreen(ctk.CTkFrame):
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
        self.app    = app
        self._built = False
        self._ov_proc = None

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._refresh()

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='🔒  VPN CLIENT',
                     font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, '↺ REFRESH', command=self._refresh,
            variant='ghost', width=90).pack(side='right', padx=8, pady=8)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # ── STATUS ────────────────────────────────────────────────
        SectionHeader(body, '01', 'VPN STATUS').pack(
            fill='x', padx=14, pady=(14, 4))
        self._sc = Card(body)
        self._sc.pack(fill='x', padx=14, pady=(0, 8))
        self._stat_lbl = ctk.CTkLabel(
            self._sc, text='Checking...',
            font=('Courier', 13, 'bold'), text_color=C['mu'])
        self._stat_lbl.pack(pady=(12, 4))
        self._stat_grid = ctk.CTkFrame(self._sc, fg_color='transparent')
        self._stat_grid.pack(fill='x', padx=8, pady=(0, 10))

        # ── WIREGUARD — ONE-BUTTON ────────────────────────────────
        SectionHeader(body, '02', 'WIREGUARD — ONE-BUTTON CONNECT').pack(
            fill='x', padx=14, pady=(8, 4))
        wg_card = Card(body, accent=C['ac'])
        wg_card.pack(fill='x', padx=14, pady=(0, 8))

        ctk.CTkLabel(wg_card,
            text='Auto-detected WireGuard configs:',
            font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,2))

        # Config selector dropdown (auto-populated)
        self._wg_var = ctk.StringVar(value='')
        self._wg_menu = ctk.CTkOptionMenu(
            wg_card, variable=self._wg_var,
            values=['(scanning...)'],
            fg_color=C['s2'], button_color=C['br2'],
            dropdown_fg_color=C['sf'],
            text_color=C['tx'], font=('Courier', 9))
        self._wg_menu.pack(fill='x', padx=12, pady=4)

        br = ctk.CTkFrame(wg_card, fg_color='transparent')
        br.pack(fill='x', padx=12, pady=(0, 10))
        Btn(br, '▶ WG UP',       command=self._wg_up,     width=110).pack(side='left', padx=(0,6))
        Btn(br, '⏹ WG DOWN',     command=self._wg_down,   variant='danger', width=110).pack(side='left', padx=(0,6))
        Btn(br, '📊 WG STATUS',  command=self._wg_status, variant='ghost',  width=120).pack(side='left')

        ctk.CTkLabel(wg_card,
            text='No configs? Place .conf file in /etc/wireguard/ or ~/vpn/',
            font=('Courier', 8), text_color=C['mu']).pack(anchor='w', padx=12, pady=(0,8))

        # ── OPENVPN ───────────────────────────────────────────────
        SectionHeader(body, '03', 'OPENVPN').pack(
            fill='x', padx=14, pady=(8, 4))
        ov_card = Card(body, accent=C['bl'])
        ov_card.pack(fill='x', padx=14, pady=(0, 8))

        ctk.CTkLabel(ov_card,
            text='Auto-detected .ovpn configs:',
            font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,2))

        self._ov_var = ctk.StringVar(value='')
        self._ov_menu = ctk.CTkOptionMenu(
            ov_card, variable=self._ov_var,
            values=['(scanning...)'],
            fg_color=C['s2'], button_color=C['br2'],
            dropdown_fg_color=C['sf'],
            text_color=C['tx'], font=('Courier', 9))
        self._ov_menu.pack(fill='x', padx=12, pady=4)

        ovbr = ctk.CTkFrame(ov_card, fg_color='transparent')
        ovbr.pack(fill='x', padx=12, pady=(0, 10))
        Btn(ovbr, '▶ CONNECT',    command=self._ov_connect,    width=120).pack(side='left', padx=(0,6))
        Btn(ovbr, '⏹ DISCONNECT', command=self._ov_disconnect, variant='danger', width=130).pack(side='left')

        # ── INSTALL ───────────────────────────────────────────────
        SectionHeader(body, '04', 'INSTALL VPN TOOLS').pack(
            fill='x', padx=14, pady=(8, 4))
        ic = Card(body)
        ic.pack(fill='x', padx=14, pady=(0, 8))
        self._tools_frame = ctk.CTkFrame(ic, fg_color='transparent')
        self._tools_frame.pack(fill='x', padx=12, pady=6)
        ibr = ctk.CTkFrame(ic, fg_color='transparent')
        ibr.pack(fill='x', padx=12, pady=(0,10))
        Btn(ibr, '⬇ INSTALL WIREGUARD',
            command=lambda: self._install('wireguard wireguard-tools'),
            width=190).pack(side='left', padx=(0,8))
        Btn(ibr, '⬇ INSTALL OPENVPN',
            command=lambda: self._install('openvpn'),
            variant='blue', width=160).pack(side='left')

        # ── LOG ───────────────────────────────────────────────────
        SectionHeader(body, '05', 'VPN LOG').pack(
            fill='x', padx=14, pady=(8, 4))
        lc = Card(body)
        lc.pack(fill='x', padx=14, pady=(0, 14))
        self._log_box = ctk.CTkTextbox(
            lc, height=130, font=('Courier', 9),
            fg_color=C['bg'], text_color=C['ok'], border_width=0)
        self._log_box.pack(fill='x', padx=8, pady=8)
        self._log_box.configure(state='normal')

    def _ulog(self, msg):
        def _do():
            try:
                if not self.winfo_exists(): return
                self._log_box.configure(state='normal')
                ts = time.strftime('%H:%M:%S')
                self._log_box.insert('end', f'[{ts}] {msg}\n')
                self._log_box.see('end')
                self._log_box.configure(state='disabled')
            except Exception:
                pass
        self._safe_after(0, _do)

    def _refresh(self):
        # Scan configs
        wg_cfgs  = find_wg_configs()
        ov_cfgs  = find_ovpn_configs()
        tools    = detect_vpn_tools()
        st       = get_vpn_status()

        # Update WG dropdown
        wg_names = wg_cfgs if wg_cfgs else ['(no .conf files found)']
        self._wg_menu.configure(values=wg_names)
        if wg_cfgs and (not self._wg_var.get() or self._wg_var.get() == '(scanning...)'):
            self._wg_var.set(wg_cfgs[0])
        elif not wg_cfgs:
            self._wg_var.set(wg_names[0])

        # Update OV dropdown
        ov_names = ov_cfgs if ov_cfgs else ['(no .ovpn files found)']
        self._ov_menu.configure(values=ov_names)
        if ov_cfgs and (not self._ov_var.get() or self._ov_var.get() == '(scanning...)'):
            self._ov_var.set(ov_cfgs[0])
        elif not ov_cfgs:
            self._ov_var.set(ov_names[0])

        # Status
        connected = st['wireguard_active'] or st['tun_active'] or st['nm_vpn_active']
        self._stat_lbl.configure(
            text='🔒 VPN CONNECTED' if connected else '⚠ NOT CONNECTED',
            text_color=C['ok'] if connected else C['wn'])

        for w in self._stat_grid.winfo_children(): w.destroy()
        items = [
            ('WIREGUARD',
             f"Active ({', '.join(st['wireguard_ifaces'])})" if st['wireguard_active'] else 'Inactive',
             C['ok'] if st['wireguard_active'] else C['mu']),
            ('TUN IFACE',  'Up' if st['tun_active'] else 'None',
             C['ok'] if st['tun_active'] else C['mu']),
            ('NM VPN',     'Active' if st['nm_vpn_active'] else 'None',
             C['ok'] if st['nm_vpn_active'] else C['mu']),
            ('WG CONFIGS', str(len(wg_cfgs)), C['ac']),
            ('OV CONFIGS', str(len(ov_cfgs)), C['ac']),
        ]
        InfoGrid(self._stat_grid, items, columns=5).pack(fill='x')

        # Tool status
        for w in self._tools_frame.winfo_children(): w.destroy()
        for name, ok in tools.items():
            ctk.CTkLabel(self._tools_frame,
                text=f"{'✓' if ok else '✗'} {name}",
                font=('Courier', 9, 'bold'),
                text_color=C['ok'] if ok else C['wn']
                ).pack(side='left', padx=10)

    def _get_wg_iface(self):
        conf = self._wg_var.get()
        if '(no ' in conf or not conf:
            return None
        return os.path.basename(conf).replace('.conf', '')

    def _wg_up(self):
        iface = self._get_wg_iface()
        if not iface:
            self._ulog('No WireGuard config selected or found.')
            return
        self._ulog(f'Starting WireGuard: {iface}')
        def _bg():
            out, err, rc = run_cmd(f'sudo wg-quick up {iface}', timeout=20)
            self._safe_after(0, self._ulog, out or err or f'Done (rc={rc})')
            self._safe_after(0, self._refresh)
        threading.Thread(target=_bg, daemon=True).start()

    def _wg_down(self):
        # Try active interfaces first, then selected config
        st = get_vpn_status()
        ifaces = st.get('wireguard_ifaces', []) or ([self._get_wg_iface()] if self._get_wg_iface() else [])
        if not ifaces:
            self._ulog('No active WireGuard interface to stop.')
            return
        def _bg():
            for iface in ifaces:
                out, err, rc = run_cmd(f'sudo wg-quick down {iface}', timeout=10)
                self._safe_after(0, self._ulog, f'{iface}: ' + (out or err or f'Done rc={rc}'))
            self._safe_after(0, self._refresh)
        threading.Thread(target=_bg, daemon=True).start()

    def _wg_status(self):
        def _bg():
            out, err, _ = run_cmd('sudo wg show')
            self._safe_after(0, self._ulog, out or err or 'No active WireGuard tunnels')
        threading.Thread(target=_bg, daemon=True).start()

    def _ov_connect(self):
        conf = self._ov_var.get()
        if '(no ' in conf or not conf:
            self._ulog('No .ovpn config selected or found.')
            return
        self._ulog(f'Connecting OpenVPN: {os.path.basename(conf)}')
        def _bg():
            self._ov_proc = subprocess.Popen(
                ['sudo', 'openvpn', '--config', conf, '--daemon',
                 '--log', '/tmp/mint_scan_openvpn.log'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            time.sleep(3)
            self._safe_after(0, self._ulog, 'OpenVPN daemon started')
            self._safe_after(0, self._refresh)
        threading.Thread(target=_bg, daemon=True).start()

    def _ov_disconnect(self):
        run_cmd('sudo killall openvpn 2>/dev/null')
        if self._ov_proc:
            try: self._ov_proc.terminate()
            except Exception: pass
            self._ov_proc = None
        self._ulog('OpenVPN terminated')
        self._refresh()

    def _install(self, pkg):
        from installer import InstallerPopup
        InstallerPopup(self, f'Install {pkg}',
                       [f'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}'],
                       f'{pkg} installed!')
        self.after(3000, self._refresh)
