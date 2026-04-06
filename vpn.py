"""
Mint Scan v8 — Built-in VPN Client
Supports OpenVPN and WireGuard via system CLI tools.
"""
import os, threading, subprocess, time
import tkinter as tk
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, ResultBox, InfoGrid)
from utils import run_cmd
from logger import get_logger

log = get_logger('vpn')


def detect_vpn_tools() -> dict:
    import shutil
    return {
        'openvpn':  bool(shutil.which('openvpn')),
        'wg':       bool(shutil.which('wg')),
        'wg-quick': bool(shutil.which('wg-quick')),
        'nmcli':    bool(shutil.which('nmcli')),
    }


def get_vpn_status() -> dict:
    """Detect active VPN connections."""
    # WireGuard
    wg_out, _, wg_rc = run_cmd('sudo wg show 2>/dev/null')
    # OpenVPN tun/tap interfaces
    iface_out, _, _ = run_cmd('ip link show type tun 2>/dev/null')
    # nmcli VPN
    nm_out, _, nm_rc = run_cmd(
        "nmcli -t -f TYPE,STATE con show --active 2>/dev/null | grep vpn | grep activated")
    return {
        'wireguard_active': wg_rc == 0 and bool(wg_out.strip()),
        'wireguard_info':   wg_out.strip()[:300],
        'tun_active':       bool(iface_out.strip()),
        'nm_vpn_active':    nm_rc == 0 and bool(nm_out.strip()),
    }


class VPNScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app     = app
        self._built  = False
        self._proc   = None   # active VPN process

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._refresh()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text='🔒  VPN CLIENT',
                     font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, '↺ REFRESH', command=self._refresh,
            variant='ghost', width=90).pack(side='right', padx=8, pady=6)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # Status
        SectionHeader(body, '01', 'VPN STATUS').pack(
            fill='x', padx=14, pady=(14, 4))
        self._stat_card = Card(body)
        self._stat_card.pack(fill='x', padx=14, pady=(0, 8))
        self._stat_lbl = ctk.CTkLabel(
            self._stat_card, text='Checking...',
            font=('Courier', 12, 'bold'), text_color=C['mu'])
        self._stat_lbl.pack(pady=(12, 4))
        self._stat_grid = ctk.CTkFrame(self._stat_card, fg_color='transparent')
        self._stat_grid.pack(fill='x', padx=8, pady=(0, 10))

        # Installed tools
        SectionHeader(body, '02', 'INSTALLED VPN TOOLS').pack(
            fill='x', padx=14, pady=(8, 4))
        self._tools_card = Card(body)
        self._tools_card.pack(fill='x', padx=14, pady=(0, 8))

        # WireGuard
        SectionHeader(body, '03', 'WIREGUARD').pack(
            fill='x', padx=14, pady=(8, 4))
        wg_card = Card(body, accent=C['ac'])
        wg_card.pack(fill='x', padx=14, pady=(0, 8))
        ctk.CTkLabel(wg_card,
            text='WireGuard — fast, modern, secure VPN',
            font=('Courier', 10, 'bold'), text_color=C['ac']
            ).pack(anchor='w', padx=12, pady=(10, 4))
        ctk.CTkLabel(wg_card,
            text='Config file path (e.g. /etc/wireguard/wg0.conf):',
            font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12)
        self._wg_conf = ctk.CTkEntry(
            wg_card, placeholder_text='/etc/wireguard/wg0.conf',
            font=('Courier', 9), fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'])
        self._wg_conf.pack(fill='x', padx=12, pady=6)
        br = ctk.CTkFrame(wg_card, fg_color='transparent')
        br.pack(fill='x', padx=12, pady=(0, 10))
        Btn(br, '▶ WG UP',   command=self._wg_up,   width=100).pack(side='left', padx=(0,6))
        Btn(br, '⏹ WG DOWN', command=self._wg_down,
            variant='danger', width=100).pack(side='left')
        Btn(br, '📋 SHOW STATUS',
            command=self._wg_status, variant='ghost', width=130).pack(side='left', padx=6)

        # OpenVPN
        SectionHeader(body, '04', 'OPENVPN').pack(
            fill='x', padx=14, pady=(8, 4))
        ov_card = Card(body, accent=C['bl'])
        ov_card.pack(fill='x', padx=14, pady=(0, 8))
        ctk.CTkLabel(ov_card,
            text='OpenVPN — compatible with most providers',
            font=('Courier', 10, 'bold'), text_color=C['bl']
            ).pack(anchor='w', padx=12, pady=(10, 4))
        ctk.CTkLabel(ov_card,
            text='.ovpn config file path:',
            font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12)
        self._ov_conf = ctk.CTkEntry(
            ov_card, placeholder_text='/path/to/client.ovpn',
            font=('Courier', 9), fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'])
        self._ov_conf.pack(fill='x', padx=12, pady=6)
        obr = ctk.CTkFrame(ov_card, fg_color='transparent')
        obr.pack(fill='x', padx=12, pady=(0, 10))
        Btn(obr, '▶ CONNECT', command=self._ov_connect, width=110).pack(side='left', padx=(0,6))
        Btn(obr, '⏹ DISCONNECT', command=self._ov_disconnect,
            variant='danger', width=120).pack(side='left')

        # Install
        SectionHeader(body, '05', 'INSTALL VPN TOOLS').pack(
            fill='x', padx=14, pady=(8, 4))
        ic = Card(body)
        ic.pack(fill='x', padx=14, pady=(0, 8))
        ibr = ctk.CTkFrame(ic, fg_color='transparent')
        ibr.pack(fill='x', padx=12, pady=10)
        Btn(ibr, '⬇ INSTALL WIREGUARD',
            command=lambda: self._install('wireguard wireguard-tools'),
            width=180).pack(side='left', padx=(0, 8))
        Btn(ibr, '⬇ INSTALL OPENVPN',
            command=lambda: self._install('openvpn'),
            variant='blue', width=160).pack(side='left')

        # Log
        SectionHeader(body, '06', 'VPN LOG').pack(
            fill='x', padx=14, pady=(8, 4))
        lc = Card(body)
        lc.pack(fill='x', padx=14, pady=(0, 14))
        self._log = ctk.CTkTextbox(
            lc, height=130, font=('Courier', 9),
            fg_color=C['bg'], text_color=C['ok'], border_width=0)
        self._log.pack(fill='x', padx=8, pady=8)
        self._log.configure(state='disabled')

    def _ulog(self, msg):
        def _do():
            self._log.configure(state='normal')
            ts = time.strftime('%H:%M:%S')
            self._log.insert('end', f'[{ts}] {msg}\n')
            self._log.see('end')
            self._log.configure(state='disabled')
        self.after(0, _do)

    def _refresh(self):
        st    = get_vpn_status()
        tools = detect_vpn_tools()
        connected = st['wireguard_active'] or st['tun_active'] or st['nm_vpn_active']
        self._stat_lbl.configure(
            text='🔒 VPN CONNECTED' if connected else '⚠ NOT CONNECTED',
            text_color=C['ok'] if connected else C['wn'])
        for w in self._stat_grid.winfo_children(): w.destroy()
        InfoGrid(self._stat_grid, [
            ('WIREGUARD',  'Active' if st['wireguard_active'] else 'Off',
             C['ok'] if st['wireguard_active'] else C['mu']),
            ('TUN IFACE',  'Up' if st['tun_active'] else 'None',
             C['ok'] if st['tun_active'] else C['mu']),
            ('NM VPN',     'Active' if st['nm_vpn_active'] else 'None',
             C['ok'] if st['nm_vpn_active'] else C['mu']),
        ], columns=3).pack(fill='x')

        for w in self._tools_card.winfo_children(): w.destroy()
        tool_row = ctk.CTkFrame(self._tools_card, fg_color='transparent')
        tool_row.pack(fill='x', padx=12, pady=10)
        for name, ok in tools.items():
            ctk.CTkLabel(tool_row,
                text=f"{'✓' if ok else '✗'} {name}",
                font=('Courier', 9, 'bold'),
                text_color=C['ok'] if ok else C['wn']
                ).pack(side='left', padx=10)

    def _wg_up(self):
        conf = self._wg_conf.get().strip() or '/etc/wireguard/wg0.conf'
        iface = os.path.basename(conf).replace('.conf', '')
        self._ulog(f'Starting WireGuard: {iface}')
        def _bg():
            out, err, rc = run_cmd(f'sudo wg-quick up {iface}', timeout=20)
            self.after(0, self._ulog, out or err or f'Exit: {rc}')
            self.after(0, self._refresh)
        threading.Thread(target=_bg, daemon=True).start()

    def _wg_down(self):
        conf  = self._wg_conf.get().strip() or '/etc/wireguard/wg0.conf'
        iface = os.path.basename(conf).replace('.conf', '')
        def _bg():
            out, err, rc = run_cmd(f'sudo wg-quick down {iface}', timeout=10)
            self.after(0, self._ulog, out or err or 'Done')
            self.after(0, self._refresh)
        threading.Thread(target=_bg, daemon=True).start()

    def _wg_status(self):
        def _bg():
            out, _, _ = run_cmd('sudo wg show')
            self.after(0, self._ulog, out or 'No active WireGuard tunnels')
        threading.Thread(target=_bg, daemon=True).start()

    def _ov_connect(self):
        conf = self._ov_conf.get().strip()
        if not conf:
            self._ulog('Enter .ovpn config path first')
            return
        self._ulog(f'Connecting OpenVPN: {conf}')
        def _bg():
            self._proc = subprocess.Popen(
                f'sudo openvpn --config "{conf}" --daemon',
                shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True)
            time.sleep(3)
            self.after(0, self._refresh)
            self.after(0, self._ulog, 'OpenVPN started (daemon mode)')
        threading.Thread(target=_bg, daemon=True).start()

    def _ov_disconnect(self):
        run_cmd('sudo killall openvpn 2>/dev/null')
        self._ulog('OpenVPN terminated')
        self._refresh()

    def _install(self, pkg):
        from installer import InstallerPopup
        InstallerPopup(self, f'Install {pkg}',
                       [f'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}'],
                       f'{pkg} installed!')

