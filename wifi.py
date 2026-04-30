"""
Wi-Fi Scanner — Live scan · Saved networks · VPN detection · Evil-twin check
Robust nmcli/iwlist/iw parser — handles BSSIDs with colons correctly.
"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, re, os, time
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from utils import (run_cmd as run, get_wifi_networks, get_current_wifi,
                   get_saved_wifi_networks, copy_to_clipboard, connect_to_wifi)

def sig_color(sig):
    if sig >= 75: return C['ok']
    if sig >= 50: return C['ac']
    if sig >= 25: return C['am']
    return C['wn']

def sec_color(sec):
    s = sec.upper()
    if 'WPA3' in s: return C['ok']
    if 'WPA2' in s: return C['ac']
    if 'WPA'  in s: return C['am']
    if 'WEP'  in s: return C['wn']
    return C['wn']

class SignalBars(ctk.CTkFrame):
    def __init__(self, parent, signal=0, **kw):
        super().__init__(parent, fg_color='transparent', **kw)
        col  = sig_color(signal)
        bars = 4 if signal>=75 else 3 if signal>=50 else 2 if signal>=25 else 1
        for b in range(4):
            h = (b+1)*6+2
            ctk.CTkFrame(self, width=5, height=h,
                         fg_color=col if b<bars else C['br'],
                         corner_radius=1).pack(side='left', padx=1, anchor='s')
        ctk.CTkLabel(self, text=f'{signal}%',
                     font=('DejaVu Sans Mono',8), text_color=col
                     ).pack(side='left', padx=(4,0))

class PulseDot(ctk.CTkFrame):
    def __init__(self, parent, color=None, **kw):
        super().__init__(parent, fg_color='transparent', width=16, height=16, **kw)
        self._color = color or C['ok']
        self._on    = True
        self._dot   = ctk.CTkFrame(self, width=10, height=10,
                                   fg_color=self._color, corner_radius=5)
        self._dot.place(relx=0.5, rely=0.5, anchor='center')
        self._pulse()

    def set_color(self, c):
        self._color = c
        self._dot.configure(fg_color=c)

    def _pulse(self):
        try:
            if not self.winfo_exists(): return
            self._on = not self._on
            self._dot.configure(fg_color=self._color if self._on else C['br'])
            self.after(700, self._pulse)
        except Exception: pass


class WifiScreen(ctk.CTkFrame):
    def _safe_after(self, delay, fn, *args):
        def _g():
            try:
                if self.winfo_exists(): fn(*args)
            except Exception: pass
        try: self.after(delay, _g)
        except Exception: pass

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app       = app
        self._built    = False
        self._scanning = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._load_current, daemon=True).start()

    def on_blur(self): pass

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=52, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        left = ctk.CTkFrame(hdr, fg_color='transparent')
        left.pack(side='left', padx=12, pady=6)
        ctk.CTkLabel(left, text='📶  WI-FI SCANNER',
                     font=('DejaVu Sans Mono',13,'bold'),
                     text_color=C['ac']).pack(side='left')
        self._pulse_dot = PulseDot(left, color=C['mu'])
        self._pulse_dot.pack(side='left', padx=8)
        self.status_lbl = ctk.CTkLabel(left, text='Not scanning',
                                        font=MONO_SM, text_color=C['mu'])
        self.status_lbl.pack(side='left')
        btn_row = ctk.CTkFrame(hdr, fg_color='transparent')
        btn_row.pack(side='right', padx=12, pady=6)
        Btn(btn_row, '🚀 SPEED TEST',
            command=lambda: self.app._switch_tab('network'),
            variant='blue', width=120).pack(side='left', padx=4)
        self.stop_btn = Btn(btn_row, '⏹ STOP', command=self._stop_scan,
                            variant='danger', width=90)
        self.stop_btn.pack(side='left', padx=4)
        self.stop_btn.configure(state='disabled')
        self.scan_btn = Btn(btn_row, '▶ SCAN', command=self._start_scan, width=90)
        self.scan_btn.pack(side='left', padx=4)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        SectionHeader(body,'01','CURRENT CONNECTION').pack(fill='x',padx=14,pady=(14,4))
        self.curr_card = Card(body, accent=C['ac'])
        self.curr_card.pack(fill='x', padx=14, pady=(0,6))
        self._curr_loading = ctk.CTkLabel(self.curr_card,
            text='⟳  Detecting connection…', font=MONO_SM, text_color=C['mu'])
        self._curr_loading.pack(padx=12, pady=10)

        SectionHeader(body,'02','VPN / TUNNEL DETECTION').pack(fill='x',padx=14,pady=(10,4))
        self.vpn_card = Card(body)
        self.vpn_card.pack(fill='x', padx=14, pady=(0,6))
        ctk.CTkLabel(self.vpn_card,
                     text='Tap ▶ SCAN to check for VPN interfaces',
                     font=MONO_SM, text_color=C['mu']).pack(padx=12, pady=10)

        SectionHeader(body,'03','PREVIOUSLY CONNECTED NETWORKS').pack(fill='x',padx=14,pady=(10,4))
        self._saved_hdr   = ctk.CTkFrame(body, fg_color='transparent')
        self._saved_hdr.pack(fill='x', padx=14)
        self._saved_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._saved_frame.pack(fill='x', padx=14, pady=(0,6))
        ctk.CTkLabel(self._saved_frame,
                     text='Tap ▶ SCAN to load previously connected networks',
                     font=MONO_SM, text_color=C['mu']).pack(pady=8)

        SectionHeader(body,'04','NEARBY NETWORKS').pack(fill='x',padx=14,pady=(10,4))
        self.nearby_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.nearby_frame.pack(fill='x', padx=14, pady=(0,14))
        ctk.CTkLabel(self.nearby_frame,
                     text='Tap ▶ SCAN to discover all Wi-Fi networks in range',
                     font=MONO_SM, text_color=C['mu']).pack(pady=20)

        SectionHeader(body,'05','EVIL TWIN DETECTION').pack(fill='x',padx=14,pady=(10,4))
        et_card = Card(body, accent=C['wn'])
        et_card.pack(fill='x', padx=14, pady=(0,14))
        ctk.CTkLabel(et_card,
                     text='Scans for duplicate SSIDs with different BSSIDs (MACs).',
                     font=MONO_SM, text_color=C['mu']).pack(pady=(12,4))
        self.et_res = ctk.CTkLabel(et_card, text='', font=MONO_SM, text_color=C['wn'])
        self.et_res.pack(pady=(0,4))
        Btn(et_card, '💀 CHECK FOR EVIL TWINS', command=self._scan_evil_twin,
            variant='danger', width=200).pack(pady=(0,12))

    # ── Current connection ──────────────────────────────────────

    def _load_current(self):
        out, _, _    = run('nmcli -t -f TYPE,STATE dev 2>/dev/null | head -5')
        ip_out, _, _ = run(
            "ip route get 8.8.8.8 2>/dev/null | grep -oP 'src \\K[\\d.]+' | head -1")
        ssid         = get_current_wifi()
        connected    = 'connected' in out.lower()
        conn_type    = ('Wi-Fi'    if 'wifi'     in out.lower() else
                        'Ethernet' if 'ethernet' in out.lower() else 'Unknown')
        signal = 0
        if connected:
            # nmcli -t format is "ACTIVE:SIGNAL" per line e.g. "yes:72"
            sig_out, _, _ = run(
                "nmcli -t -f ACTIVE,SIGNAL device wifi list 2>/dev/null")
            for line in sig_out.splitlines():
                if line.startswith('yes:') or line.startswith('*:'):
                    try:
                        signal = int(line.split(':', 1)[1].strip())
                    except Exception:
                        pass
                    break
        self._safe_after(0, self._render_current,
                         conn_type, ssid, ip_out.strip(), connected, signal)

    def _render_current(self, conn_type, ssid, ip, connected, signal=0):
        for w in self.curr_card.winfo_children(): w.destroy()
        col = C['ok'] if connected else C['wn']
        top = ctk.CTkFrame(self.curr_card, fg_color='transparent')
        top.pack(fill='x', padx=12, pady=(10,4))
        badge = ctk.CTkFrame(top, fg_color=C['okg'] if connected else C['wng'],
                             border_color=col, border_width=1, corner_radius=6)
        badge.pack(side='left')
        ctk.CTkLabel(badge,
                     text=f'  {"✓ CONNECTED" if connected else "✗ OFFLINE"}  ',
                     font=('DejaVu Sans Mono',10,'bold'), text_color=col
                     ).pack(padx=4, pady=4)
        if signal and connected:
            SignalBars(top, signal=signal).pack(side='left', padx=12)
        grid = ctk.CTkFrame(self.curr_card, fg_color='transparent')
        grid.pack(fill='x', padx=12, pady=(0,10))
        for label, value, vc in [
            ('TYPE',     conn_type,   C['ac']),
            ('SSID',     ssid or '—', C['ok'] if ssid else C['mu']),
            ('LOCAL IP', ip   or '—', C['am']),
        ]:
            c2 = ctk.CTkFrame(grid, fg_color='transparent')
            c2.pack(side='left', padx=14)
            ctk.CTkLabel(c2, text=label,
                         font=('DejaVu Sans Mono',7,'bold'),
                         text_color=C['mu']).pack(anchor='w')
            ctk.CTkLabel(c2, text=value,
                         font=('DejaVu Sans Mono',11,'bold'),
                         text_color=vc).pack(anchor='w')

    # ── Scan control ────────────────────────────────────────────

    def _start_scan(self):
        if self._scanning: return
        self._scanning = True
        self.scan_btn.configure(state='disabled', text='SCANNING…')
        self.stop_btn.configure(state='normal')
        self.status_lbl.configure(text='Scanning…', text_color=C['ac'])
        self._pulse_dot.set_color(C['ac'])
        for w in self.nearby_frame.winfo_children(): w.destroy()
        for w in self._saved_frame.winfo_children():  w.destroy()
        ctk.CTkLabel(self.nearby_frame, text='⟳  Scanning nearby networks…',
                     font=MONO_SM, text_color=C['ac']).pack(pady=8)
        ctk.CTkLabel(self._saved_frame, text='⟳  Loading saved networks…',
                     font=MONO_SM, text_color=C['ac']).pack(pady=8)
        threading.Thread(target=self._do_full_scan, daemon=True).start()

    def _stop_scan(self):
        self._scanning = False
        self.scan_btn.configure(state='normal', text='▶ SCAN')
        self.stop_btn.configure(state='disabled')
        self.status_lbl.configure(text='Stopped', text_color=C['mu'])
        self._pulse_dot.set_color(C['mu'])

    def _do_full_scan(self):
        # VPN
        vpn_ifaces, vpn_procs = [], []
        ifaces_out, _, _ = run('ip link show 2>/dev/null')
        for iface in re.findall(r'\d+: (\w+):', ifaces_out):
            if any(x in iface.lower() for x in ['tun','tap','wg','vpn','ppp','zt','tor']):
                ip_out, _, _ = run(
                    f"ip addr show {iface} 2>/dev/null | grep 'inet ' | awk '{{print $2}}'")
                vpn_ifaces.append({'name': iface, 'ip': ip_out or '—'})
        for proc in ['openvpn','wireguard','nordvpn','expressvpn','tailscale','zerotier']:
            out, _, rc = run(f'pgrep -x {proc} 2>/dev/null')
            if rc == 0: vpn_procs.append(proc)
        self._safe_after(0, self._render_vpn, vpn_ifaces, vpn_procs)
        if not self._scanning: return

        # Saved
        saved = get_saved_wifi_networks()
        self._safe_after(0, self._render_saved, saved)
        if not self._scanning: return

        # Nearby
        networks = get_wifi_networks()
        self._safe_after(0, self._render_networks, networks)
        self._scanning = False
        count = len(networks)
        self._safe_after(0, lambda: (
            self.scan_btn.configure(state='normal', text='↺ RESCAN'),
            self.stop_btn.configure(state='disabled'),
            self.status_lbl.configure(
                text=f'Found {count} networks  ·  {len(saved)} saved',
                text_color=C['ok']),
            self._pulse_dot.set_color(C['ok']),
        ))

    # ── Render VPN ──────────────────────────────────────────────

    def _render_vpn(self, interfaces, procs):
        for w in self.vpn_card.winfo_children(): w.destroy()
        active = bool(interfaces or procs)
        if active:
            ResultBox(self.vpn_card,'info','🔒 VPN / TUNNEL ACTIVE',
                      'Traffic is being routed through a VPN or tunnel.'
                      ).pack(fill='x', padx=8, pady=(8,4))
        else:
            ResultBox(self.vpn_card,'ok','✓ NO VPN DETECTED',
                      'No VPN, tunnel or proxy interfaces found.'
                      ).pack(fill='x', padx=8, pady=(8,4))
        items  = [(v['name'].upper(), v['ip'],       C['bl']) for v in interfaces]
        items += [(p.upper(),         'Process active', C['bl']) for p in procs]
        if items:
            InfoGrid(self.vpn_card, items, columns=3).pack(fill='x', padx=8, pady=(0,8))
        else:
            ctk.CTkLabel(self.vpn_card,
                         text='No tun/tap/wg/ppp/zerotier interfaces active',
                         font=MONO_SM, text_color=C['mu']).pack(padx=12, pady=(0,8))

    # ── Render saved ─────────────────────────────────────────────

    def _render_saved(self, saved):
        for w in self._saved_hdr.winfo_children(): w.destroy()
        for w in self._saved_frame.winfo_children(): w.destroy()
        if not saved:
            ctk.CTkLabel(self._saved_frame,
                         text='No saved Wi-Fi profiles found.\n'
                              'Connect to a network first, or run as root for full access.',
                         font=MONO_SM, text_color=C['mu'], justify='center').pack(pady=10)
            return
        Btn(self._saved_hdr, '📋 COPY ALL',
            command=lambda: self._copy_all_saved(saved),
            variant='ghost', width=120).pack(side='right', pady=(0,4))
        ctk.CTkLabel(self._saved_frame,
                     text=f'{len(saved)} previously connected network(s):',
                     font=('DejaVu Sans Mono',9,'bold'),
                     text_color=C['ac']).pack(anchor='w', pady=(0,6))
        for net in saved[:30]:
            row = ctk.CTkFrame(self._saved_frame, fg_color=C['sf'],
                               border_color=C['br'], border_width=1, corner_radius=8)
            row.pack(fill='x', pady=3)
            ctk.CTkLabel(row, text='🔒', font=('DejaVu Sans Mono',16)
                         ).pack(side='left', padx=10, pady=8)
            info = ctk.CTkFrame(row, fg_color='transparent')
            info.pack(side='left', fill='both', expand=True, pady=8)
            ctk.CTkLabel(info, text=net['name'],
                         font=('DejaVu Sans Mono',11,'bold'),
                         text_color=C['tx']).pack(anchor='w')
            ctk.CTkLabel(info, text=f"Last used: {net['last']}",
                         font=('DejaVu Sans Mono',8),
                         text_color=C['mu']).pack(anchor='w')
            Btn(row, 'SHOW PWD',
                command=lambda n=net['name']: self._show_password(n),
                variant='ghost', width=90).pack(side='right', padx=8)

    def _copy_all_saved(self, saved):
        text = 'MINT SCAN — SAVED WI-FI NETWORKS\n' + '='*40 + '\n'
        for net in saved:
            text += f"SSID: {net['name']}  Last Used: {net['last']}\n"
        if copy_to_clipboard(text):
            self.status_lbl.configure(
                text='Copied to clipboard', text_color=C['ok'])

    def _show_password(self, name):
        out, _, rc = run(
            f"sudo nmcli -s -g 802-11-wireless-security.psk "
            f"connection show '{name}' 2>/dev/null")
        popup = ctk.CTkToplevel(self)
        popup.title(f'Password: {name}')
        popup.geometry('420x200')
        popup.configure(fg_color=C['bg'])
        popup.attributes('-topmost', True)
        if rc == 0 and out.strip():
            pwd = out.strip()
            ctk.CTkLabel(popup, text=name,
                         font=('DejaVu Sans Mono',12,'bold'),
                         text_color=C['ac']).pack(pady=(12,4))
            e = ctk.CTkEntry(popup, font=('DejaVu Sans Mono',13,'bold'),
                             fg_color=C['s2'], border_color=C['ac'],
                             text_color=C['ok'])
            e.pack(fill='x', padx=20, pady=8)
            e.insert(0, pwd)
            Btn(popup, '📋 COPY PASSWORD',
                command=lambda: copy_to_clipboard(pwd),
                variant='success').pack(pady=4)
        else:
            ctk.CTkLabel(popup,
                         text=f'Cannot read: {name}\n\n'
                              'Run: sudo bash run.sh, or check sudo permissions.',
                         font=MONO_SM, text_color=C['mu'],
                         justify='center').pack(expand=True, pady=10)
        Btn(popup, 'CLOSE', command=popup.destroy, variant='ghost').pack(pady=4)

    def _on_connect_click(self, ssid, security):
        if 'OPEN' in security.upper():
            self._do_connect(ssid, None)
            return

        # Prompt for password
        popup = ctk.CTkToplevel(self)
        popup.title(f'Connect to {ssid}')
        popup.geometry('400x200')
        popup.configure(fg_color=C['bg'])
        popup.attributes('-topmost', True)
        popup.grab_set()

        ctk.CTkLabel(popup, text=f'Enter password for "{ssid}":',
                     font=('DejaVu Sans Mono',11,'bold'), text_color=C['ac']).pack(pady=(20,10))
        
        pwd_entry = ctk.CTkEntry(popup, show='*', width=300, font=MONO)
        pwd_entry.pack(pady=10)
        pwd_entry.focus_set()

        def _submit():
            pwd = pwd_entry.get()
            popup.destroy()
            self._do_connect(ssid, pwd)

        btn_row = ctk.CTkFrame(popup, fg_color='transparent')
        btn_row.pack(pady=10)
        Btn(btn_row, 'CANCEL', command=popup.destroy, variant='ghost', width=100).pack(side='left', padx=10)
        Btn(btn_row, 'CONNECT', command=_submit, variant='success', width=100).pack(side='left', padx=10)
        
        popup.bind('<Return>', lambda e: _submit())

    def _do_connect(self, ssid, password):
        self.status_lbl.configure(text=f'Connecting to {ssid}…', text_color=C['ac'])
        self._pulse_dot.set_color(C['ac'])
        
        def _bg():
            ok, msg = connect_to_wifi(ssid, password)
            if ok:
                self._safe_after(0, lambda s=ssid: self.status_lbl.configure(text=f'✓ Connected to {s}', text_color=C['ok']))
                self._safe_after(0, self._pulse_dot.set_color, C['ok'])
                self._safe_after(1000, self._load_current)
            else:
                self._safe_after(0, lambda m=msg: self.status_lbl.configure(text=f'✗ Connection failed: {m[:40]}…', text_color=C['wn']))
                self._safe_after(0, self._pulse_dot.set_color, C['wn'])

        threading.Thread(target=_bg, daemon=True).start()

    # ── Render nearby ────────────────────────────────────────────

    def _render_networks(self, networks):
        for w in self.nearby_frame.winfo_children(): w.destroy()
        if not networks:
            ResultBox(self.nearby_frame,'warn','⚠ NO NETWORKS FOUND',
                      'Ensure Wi-Fi is enabled:\n'
                      '  nmcli radio wifi on\n'
                      '  nmcli device wifi rescan').pack(fill='x')
            return

        # Chromebook/Crostini: show a friendly info card instead of a broken scan
        if networks and networks[0].get('_crostini'):
            net = networks[0]
            note = net.get('_note', '')
            ssid = net.get('ssid', 'Unknown')
            sig  = net.get('signal', 0)
            info_card = Card(self.nearby_frame, accent=C['ac'])
            info_card.pack(fill='x', pady=(0,8))
            InfoGrid(info_card, [
                ('STATUS',    'Connected' if sig > 0 else 'Unknown', C['ok'] if sig > 0 else C['mu']),
                ('NETWORK',   ssid,  C['ac']),
                ('SIGNAL',    f'{sig}%' if sig else '—', C['ok'] if sig > 50 else C['am']),
                ('MANAGED BY', 'Chrome OS', C['mu']),
            ], columns=2).pack(fill='x', padx=4, pady=4)
            ResultBox(info_card, 'info', 'ℹ  CHROMEBOOK LIMITATION', note
                      ).pack(fill='x', padx=8, pady=(0,8))
            ctk.CTkLabel(self.nearby_frame,
                text='To manage Wi-Fi: Chrome OS Settings → Network → Wi-Fi',
                font=MONO_SM, text_color=C['mu']).pack(pady=12)
            return

        open_nets = [n for n in networks if n['security'].upper()=='OPEN']
        wep_nets  = [n for n in networks if 'WEP' in n['security'].upper()]
        summary = Card(self.nearby_frame, accent=C['wn'] if open_nets else C['ok'])
        summary.pack(fill='x', pady=(0,8))
        InfoGrid(summary,[
            ('FOUND',  str(len(networks)),                                    C['ac']),
            ('OPEN',   str(len(open_nets)),  C['wn'] if open_nets else C['ok']),
            ('WEP',    str(len(wep_nets)),   C['wn'] if wep_nets  else C['ok']),
            ('SECURE', str(len(networks)-len(open_nets)-len(wep_nets)),        C['ok']),
        ], columns=4).pack(fill='x', padx=4, pady=4)
        if open_nets:
            ResultBox(summary,'warn',f'⚠ {len(open_nets)} OPEN NETWORK(S)',
                      'Avoid sensitive data on open networks.'
                      ).pack(fill='x', padx=8, pady=(0,8))
        curr_out,_,_ = run(
            "nmcli -t -f ACTIVE,SSID device wifi list 2>/dev/null")
        curr = ''
        for _ln in curr_out.splitlines():
            if _ln.startswith('yes:') or _ln.startswith('*:'):
                curr = _ln.split(':',1)[1].strip()
                break
        for net in networks:
            sec  = net['security'].upper()
            col  = sec_color(sec)
            sig  = net.get('signal',0)
            sc   = sig_color(sig)
            icon = '🔓' if sec=='OPEN' else '⚠️' if 'WEP' in sec else '🔒'
            is_me = (net['ssid']==curr)
            row = ctk.CTkFrame(self.nearby_frame, fg_color=C['sf'],
                               border_color=C['ok'] if is_me else col,
                               border_width=2 if is_me else 1, corner_radius=8)
            row.pack(fill='x', pady=3)
            ctk.CTkLabel(row, text=icon,
                         font=('DejaVu Sans Mono',18)).pack(side='left', padx=10, pady=8)
            mid = ctk.CTkFrame(row, fg_color='transparent')
            mid.pack(side='left', fill='both', expand=True, pady=8)
            ctk.CTkLabel(mid,
                         text=net['ssid']+('  ✓ CONNECTED' if is_me else ''),
                         font=('DejaVu Sans Mono',11,'bold'),
                         text_color=C['ok'] if is_me else C['tx']).pack(anchor='w')
            ctk.CTkLabel(mid,
                         text=f"{sec}  ·  CH {net['channel']}  ·  {net['freq']}  ·  {net['bssid']}",
                         font=('DejaVu Sans Mono',8), text_color=C['mu']).pack(anchor='w')
            if sec=='OPEN':
                ctk.CTkLabel(mid, text='⚠ No encryption',
                             font=('DejaVu Sans Mono',8), text_color=C['wn']).pack(anchor='w')
            right = ctk.CTkFrame(row, fg_color='transparent')
            right.pack(side='right', padx=12, pady=8)
            
            if not is_me:
                Btn(right, 'CONNECT', 
                    command=lambda s=net['ssid'], sc=sec: self._on_connect_click(s, sc),
                    variant='success', width=80).pack(pady=(0,4))
            
            badge = ctk.CTkFrame(right, fg_color=C['s2'],
                                 border_color=col, border_width=1, corner_radius=3)
            badge.pack(pady=(0,6))
            ctk.CTkLabel(badge, text=sec[:8],
                         font=('DejaVu Sans Mono',7,'bold'), text_color=col).pack(padx=6,pady=2)
            SignalBars(right, signal=sig).pack()

    # ── Evil-twin ────────────────────────────────────────────────

    def _scan_evil_twin(self):
        self.et_res.configure(text='Scanning BSSIDs…', text_color=C['ac'])
        threading.Thread(target=self._do_et_scan, daemon=True).start()

    def _do_et_scan(self):
        out, _, rc = run('nmcli --escape no -g SSID,BSSID device wifi list 2>/dev/null')
        if rc != 0 or not out:
            self._safe_after(0, lambda: self.et_res.configure(
                text='Scan failed — nmcli unavailable', text_color=C['wn']))
            return
        ssid_map: dict = {}
        for line in out.split('\n'):
            line = line.strip()
            if not line: continue
            bm = re.search(r'([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})', line)
            if not bm: continue
            ssid  = line[:bm.start()].rstrip(':').strip() or '(hidden)'
            bssid = bm.group(1).upper()
            ssid_map.setdefault(ssid, set()).add(bssid)
        evil = [f'{s}  ({len(b)} APs)' for s,b in ssid_map.items() if len(b)>1]
        if evil:
            msg = '⚠ POSSIBLE EVIL TWINS:\n' + '\n'.join(evil)
            col = C['wn']
        else:
            msg = f'✓ No duplicate SSIDs found across {len(ssid_map)} networks.'
            col = C['ok']
        self._safe_after(0, lambda: self.et_res.configure(text=msg, text_color=col))
