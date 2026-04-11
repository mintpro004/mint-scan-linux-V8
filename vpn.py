"""
Mint Scan v8 — VPN Client
Scans all real config sources including nmcli, /etc/wireguard, and home dirs.
One-button connect. Shows real status. No hardcoded paths.
"""
import os, threading, subprocess, time, glob, shutil, re
import tkinter as tk
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, InfoGrid)
from utils import run_cmd
from logger import get_logger

log = get_logger('vpn')


def find_wg_configs() -> list:
    """Find WireGuard .conf files in all standard locations."""
    dirs = [
        '/etc/wireguard',
        os.path.expanduser('~'),
        os.path.expanduser('~/vpn'),
        os.path.expanduser('~/wireguard'),
        os.path.expanduser('~/Downloads'),
        '/usr/local/etc/wireguard',
    ]
    found = []
    for d in dirs:
        if os.path.isdir(d):
            try:
                for f in glob.glob(os.path.join(d, '*.conf')):
                    if os.path.isfile(f):
                        found.append(f)
            except PermissionError:
                pass
    return sorted(set(found))


def find_ovpn_configs() -> list:
    """Find OpenVPN .ovpn files in all standard locations."""
    dirs = [
        os.path.expanduser('~'),
        os.path.expanduser('~/vpn'),
        os.path.expanduser('~/openvpn'),
        os.path.expanduser('~/Downloads'),
        '/etc/openvpn/client',
        '/etc/openvpn',
    ]
    found = []
    for d in dirs:
        if os.path.isdir(d):
            try:
                for f in glob.glob(os.path.join(d, '*.ovpn')):
                    if os.path.isfile(f):
                        found.append(f)
            except PermissionError:
                pass
    return sorted(set(found))


def get_nmcli_vpn_connections() -> list:
    """Get VPN connections configured in NetworkManager."""
    out, _, rc = run_cmd(
        "nmcli -t -f NAME,TYPE con show 2>/dev/null | grep -i vpn", timeout=5)
    if rc != 0 or not out.strip():
        return []
    conns = []
    for line in out.strip().splitlines():
        parts = line.split(':')
        if parts:
            conns.append(parts[0].strip())
    return conns


def detect_vpn_tools() -> dict:
    return {
        'openvpn':  bool(shutil.which('openvpn')),
        'wg':       bool(shutil.which('wg')),
        'wg-quick': bool(shutil.which('wg-quick')),
        'nmcli':    bool(shutil.which('nmcli')),
    }


def get_vpn_status() -> dict:
    active_wg, _, _ = run_cmd('wg show interfaces 2>/dev/null', timeout=4)
    tun_out, _, _   = run_cmd('ip link show type tun 2>/dev/null', timeout=4)
    nm_active, _, _ = run_cmd(
        "nmcli -t -f NAME,TYPE,STATE con show --active 2>/dev/null | grep -i vpn | grep -i activated",
        timeout=4)
    return {
        'wireguard_active':  bool(active_wg.strip()),
        'wireguard_ifaces':  active_wg.strip().split() if active_wg.strip() else [],
        'tun_active':        bool(tun_out.strip()),
        'nm_vpn_active':     bool(nm_active.strip()),
        'nm_vpn_name':       nm_active.split(':')[0].strip() if nm_active.strip() else '',
    }


NONE_LABEL = '(none found — see instructions below)'


class VPNScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app      = app
        self._built   = False
        self._ov_proc = None

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._bg_refresh, daemon=True).start()

    def on_blur(self):
        pass

    def _safe_after(self, delay, fn, *args):
        def _g():
            try:
                if self.winfo_exists(): fn(*args)
            except Exception: pass
        try: self.after(delay, _g)
        except Exception: pass

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x'); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='🔒  VPN CLIENT',
                     font=('DejaVu Sans Mono', 13, 'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        Btn(hdr, '↺ REFRESH', command=lambda: threading.Thread(
            target=self._bg_refresh, daemon=True).start(),
            variant='ghost', width=90).pack(side='right', padx=8, pady=8)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # ── STATUS ─────────────────────────────────────────────
        SectionHeader(body, '01', 'VPN STATUS').pack(fill='x', padx=14, pady=(14,4))
        self._sc = Card(body)
        self._sc.pack(fill='x', padx=14, pady=(0,8))
        self._stat_lbl = ctk.CTkLabel(self._sc, text='Checking...',
                                       font=('DejaVu Sans Mono',13,'bold'), text_color=C['mu'])
        self._stat_lbl.pack(pady=(12,4))
        self._stat_info = ctk.CTkLabel(self._sc, text='',
                                        font=MONO_SM, text_color=C['mu'])
        self._stat_info.pack(pady=(0,4))
        self._tool_lbl = ctk.CTkLabel(self._sc, text='',
                                       font=('DejaVu Sans Mono',8), text_color=C['mu'])
        self._tool_lbl.pack(pady=(0,10))

        # ── WIREGUARD ──────────────────────────────────────────
        SectionHeader(body, '02', 'WIREGUARD').pack(fill='x', padx=14, pady=(8,4))
        wg = Card(body, accent=C['ac'])
        wg.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(wg, text='Select config:', font=MONO_SM,
                     text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,2))
        self._wg_var  = ctk.StringVar(value=NONE_LABEL)
        self._wg_menu = ctk.CTkOptionMenu(
            wg, variable=self._wg_var, values=[NONE_LABEL],
            fg_color=C['s2'], button_color=C['br2'],
            dropdown_fg_color=C['sf'], text_color=C['tx'], font=('DejaVu Sans Mono',9),
            dynamic_resizing=False)
        self._wg_menu.pack(fill='x', padx=12, pady=4)

        br = ctk.CTkFrame(wg, fg_color='transparent')
        br.pack(fill='x', padx=12, pady=(4,6))
        Btn(br, '▶ WG UP',      command=self._wg_up,     width=110).pack(side='left', padx=(0,6))
        Btn(br, '⏹ WG DOWN',    command=self._wg_down,   variant='danger', width=110).pack(side='left', padx=(0,6))
        Btn(br, '📊 STATUS',    command=self._wg_status, variant='ghost',  width=100).pack(side='left')

        self._wg_install_frame = ctk.CTkFrame(wg, fg_color='transparent')
        self._wg_install_frame.pack(fill='x', padx=12, pady=(0,4))

        ctk.CTkLabel(wg,
            text='No .conf? Place WireGuard .conf file in:\n'
                 '  /etc/wireguard/wg0.conf   OR   ~/vpn/myvpn.conf',
            font=('DejaVu Sans Mono',8), text_color=C['mu']).pack(anchor='w', padx=12, pady=(0,10))

        # ── OPENVPN ────────────────────────────────────────────
        SectionHeader(body, '03', 'OPENVPN').pack(fill='x', padx=14, pady=(8,4))
        ov = Card(body, accent=C['bl'])
        ov.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(ov, text='Select .ovpn config:', font=MONO_SM,
                     text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,2))
        self._ov_var  = ctk.StringVar(value=NONE_LABEL)
        self._ov_menu = ctk.CTkOptionMenu(
            ov, variable=self._ov_var, values=[NONE_LABEL],
            fg_color=C['s2'], button_color=C['br2'],
            dropdown_fg_color=C['sf'], text_color=C['tx'], font=('DejaVu Sans Mono',9),
            dynamic_resizing=False)
        self._ov_menu.pack(fill='x', padx=12, pady=4)

        br2 = ctk.CTkFrame(ov, fg_color='transparent')
        br2.pack(fill='x', padx=12, pady=(4,6))
        Btn(br2, '▶ CONNECT',    command=self._ov_connect,    width=120).pack(side='left', padx=(0,6))
        Btn(br2, '⏹ DISCONNECT', command=self._ov_disconnect, variant='danger', width=120).pack(side='left')

        self._ov_install_frame = ctk.CTkFrame(ov, fg_color='transparent')
        self._ov_install_frame.pack(fill='x', padx=12, pady=(0,4))

        ctk.CTkLabel(ov,
            text='No .ovpn? Download from your VPN provider and place in ~/vpn/',
            font=('DejaVu Sans Mono',8), text_color=C['mu']).pack(anchor='w', padx=12, pady=(0,10))

        # ── NETWORKMANAGER VPN ─────────────────────────────────
        SectionHeader(body, '04', 'NETWORKMANAGER VPN').pack(fill='x', padx=14, pady=(8,4))
        nm = Card(body)
        nm.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(nm, text='nmcli configured VPN connections:',
                     font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,2))
        self._nm_var  = ctk.StringVar(value=NONE_LABEL)
        self._nm_menu = ctk.CTkOptionMenu(
            nm, variable=self._nm_var, values=[NONE_LABEL],
            fg_color=C['s2'], button_color=C['br2'],
            dropdown_fg_color=C['sf'], text_color=C['tx'], font=('DejaVu Sans Mono',9),
            dynamic_resizing=False)
        self._nm_menu.pack(fill='x', padx=12, pady=4)
        br3 = ctk.CTkFrame(nm, fg_color='transparent')
        br3.pack(fill='x', padx=12, pady=(4,10))
        Btn(br3, '▶ NM CONNECT',    command=self._nm_connect,    width=150).pack(side='left', padx=(0,6))
        Btn(br3, '⏹ NM DISCONNECT', command=self._nm_disconnect, variant='danger', width=150).pack(side='left')

        # ── LOG ────────────────────────────────────────────────
        SectionHeader(body, '05', 'VPN LOG').pack(fill='x', padx=14, pady=(8,4))
        lc = Card(body)
        lc.pack(fill='x', padx=14, pady=(0,14))
        self._log_box = ctk.CTkTextbox(lc, height=130, font=('DejaVu Sans Mono',9),
                                        fg_color=C['bg'], text_color=C['ok'], border_width=0)
        self._log_box.pack(fill='x', padx=8, pady=8)
        self._log_box.configure(state='normal')

    def _ulog(self, msg):
        try:
            if not self.winfo_exists(): return
            self._log_box.configure(state='normal')
            self._log_box.insert('end', f'[{time.strftime("%H:%M:%S")}] {msg}\n')
            self._log_box.see('end')
            self._log_box.configure(state='disabled')
        except Exception: pass

    def _bg_refresh(self):
        wg_cfgs  = find_wg_configs()
        ov_cfgs  = find_ovpn_configs()
        nm_conns = get_nmcli_vpn_connections()
        tools    = detect_vpn_tools()
        st       = get_vpn_status()
        self._safe_after(0, self._apply_refresh, wg_cfgs, ov_cfgs, nm_conns, tools, st)

    def _apply_refresh(self, wg_cfgs, ov_cfgs, nm_conns, tools, st):
        try:
            if not self.winfo_exists(): return
        except Exception: return

        # WireGuard dropdown
        wg_vals = wg_cfgs if wg_cfgs else [NONE_LABEL]
        self._wg_menu.configure(values=wg_vals)
        if wg_cfgs and self._wg_var.get() == NONE_LABEL:
            self._wg_var.set(wg_cfgs[0])
        elif not wg_cfgs:
            self._wg_var.set(NONE_LABEL)

        # OpenVPN dropdown
        ov_vals = ov_cfgs if ov_cfgs else [NONE_LABEL]
        self._ov_menu.configure(values=ov_vals)
        if ov_cfgs and self._ov_var.get() == NONE_LABEL:
            self._ov_var.set(ov_cfgs[0])
        elif not ov_cfgs:
            self._ov_var.set(NONE_LABEL)

        # NM VPN dropdown
        nm_vals = nm_conns if nm_conns else [NONE_LABEL]
        self._nm_menu.configure(values=nm_vals)
        if nm_conns and self._nm_var.get() == NONE_LABEL:
            self._nm_var.set(nm_conns[0])
        elif not nm_conns:
            self._nm_var.set(NONE_LABEL)

        # Status
        connected = st['wireguard_active'] or st['tun_active'] or st['nm_vpn_active']
        if st['wireguard_active']:
            detail = f"WireGuard: {', '.join(st['wireguard_ifaces'])}"
        elif st['nm_vpn_active']:
            detail = f"NM VPN: {st['nm_vpn_name']}"
        elif st['tun_active']:
            detail = "TUN interface active (OpenVPN)"
        else:
            detail = f"WG configs: {len(wg_cfgs)}  OVPN: {len(ov_cfgs)}  NM VPNs: {len(nm_conns)}"

        self._stat_lbl.configure(
            text='🔒 CONNECTED' if connected else '⚠ NOT CONNECTED',
            text_color=C['ok'] if connected else C['wn'])
        self._stat_info.configure(text=detail)

        tool_parts = []
        for name, ok in tools.items():
            tool_parts.append(f"{'✓' if ok else '✗'} {name}")
        self._tool_lbl.configure(text='  '.join(tool_parts))

        # Show install buttons only if tool is missing
        for w in self._wg_install_frame.winfo_children(): w.destroy()
        if not tools['wg-quick']:
            Btn(self._wg_install_frame, '⬇ INSTALL WIREGUARD',
                command=lambda: self._install('wireguard wireguard-tools'), width=200
                ).pack(side='left', padx=(0,6))

        for w in self._ov_install_frame.winfo_children(): w.destroy()
        if not tools['openvpn']:
            Btn(self._ov_install_frame, '⬇ INSTALL OPENVPN',
                command=lambda: self._install('openvpn'), width=180
                ).pack(side='left')

    def _get_wg_iface(self):
        val = self._wg_var.get()
        if val == NONE_LABEL or not val:
            return None
        return os.path.basename(val).replace('.conf','')

    def _wg_up(self):
        iface = self._get_wg_iface()
        if not iface:
            self._ulog('No WireGuard config selected.')
            self._ulog('  → Place a .conf file in /etc/wireguard/ or ~/vpn/')
            self._ulog('  → Then tap ↺ REFRESH to detect it')
            return
        conf = self._wg_var.get()
        self._ulog(f'Starting WireGuard: {iface}')
        self._ulog(f'Config: {conf}')
        def _bg():
            # Check wg-quick is installed
            if not shutil.which('wg-quick'):
                self._safe_after(0, self._ulog,
                    '✗ wg-quick not installed. Tap ⬇ INSTALL WIREGUARD below.')
                return
            # Copy conf to /etc/wireguard/ if not already there
            target = f'/etc/wireguard/{iface}.conf'
            if os.path.exists(conf) and not os.path.exists(target):
                out, err, rc = run_cmd(
                    f'sudo mkdir -p /etc/wireguard && '
                    f'sudo cp "{conf}" "{target}" && sudo chmod 600 "{target}"',
                    timeout=10)
                if rc == 0:
                    self._safe_after(0, self._ulog, f'Copied config to {target}')
                else:
                    self._safe_after(0, self._ulog, f'Note: {err or out}')
            # Bring up the tunnel
            out, err, rc = run_cmd(f'sudo wg-quick up {iface}', timeout=30)
            result = out or err or f'exit={rc}'
            self._safe_after(0, self._ulog, ('✓ Connected: ' if rc==0 else '✗ Failed: ') + result[:150])
            self._safe_after(800, lambda: threading.Thread(
                target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _wg_down(self):
        st = get_vpn_status()
        ifaces = st['wireguard_ifaces'] or ([self._get_wg_iface()] if self._get_wg_iface() else [])
        if not ifaces:
            self._ulog('No active WireGuard interface.')
            return
        def _bg():
            for iface in ifaces:
                out, err, rc = run_cmd(f'sudo wg-quick down {iface}', timeout=15)
                self._safe_after(0, self._ulog, f'{iface}: {out or err or "Done"}')
            self._safe_after(500, lambda: threading.Thread(target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _wg_status(self):
        def _bg():
            out, err, _ = run_cmd('sudo wg show', timeout=8)
            self._safe_after(0, self._ulog, out or err or 'No active WireGuard tunnels')
        threading.Thread(target=_bg, daemon=True).start()

    def _ov_connect(self):
        conf = self._ov_var.get()
        if conf == NONE_LABEL or not conf:
            self._ulog('No .ovpn file selected. Download from your VPN provider and place in ~/vpn/')
            return
        self._ulog(f'Connecting OpenVPN: {os.path.basename(conf)}')
        def _bg():
            out, err, rc = run_cmd(
                f'sudo openvpn --config "{conf}" --daemon '
                f'--log /tmp/mint_scan_openvpn.log --writepid /tmp/mint_scan_ov.pid',
                timeout=20)
            time.sleep(2)
            self._safe_after(0, self._ulog, '✓ OpenVPN daemon started' if rc==0 else f'✗ {out or err}')
            self._safe_after(500, lambda: threading.Thread(target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _ov_disconnect(self):
        self._ulog('Disconnecting OpenVPN...')
        def _bg():
            if self._ov_proc:
                try: self._ov_proc.terminate()
                except Exception: pass
                self._ov_proc = None
            run_cmd('sudo killall openvpn 2>/dev/null', timeout=10)
            self._safe_after(0, self._ulog, 'OpenVPN terminated')
            self._safe_after(500, lambda: threading.Thread(target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _nm_connect(self):
        name = self._nm_var.get()
        if name == NONE_LABEL or not name:
            self._ulog('No NetworkManager VPN selected.')
            return
        self._ulog(f'Connecting NM VPN: {name}')
        def _bg():
            out, err, rc = run_cmd(f'nmcli con up "{name}"', timeout=30)
            self._safe_after(0, self._ulog, out or err or f'Exit: {rc}')
            self._safe_after(500, lambda: threading.Thread(target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _nm_disconnect(self):
        name = self._nm_var.get()
        if name == NONE_LABEL: return
        self._ulog(f'Disconnecting NM VPN: {name}')
        def _bg():
            run_cmd(f'nmcli con down "{name}"', timeout=15)
            self._safe_after(0, self._ulog, f'NM VPN disconnected: {name}')
            self._safe_after(500, lambda: threading.Thread(target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _install(self, pkg):
        from installer import InstallerPopup
        InstallerPopup(self, f'Install {pkg}',
                       [f'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}'],
                       f'{pkg} installed!')
        self.after(4000, lambda: threading.Thread(target=self._bg_refresh, daemon=True).start())
