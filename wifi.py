"""Wi-Fi Scanner — live scan, VPN detection, saved networks, stop/start"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, re, os
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from utils import run_cmd as run, get_wifi_networks, get_current_wifi, copy_to_clipboard


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


class WifiScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built    = False
        self._scanning = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._load_current, daemon=True).start()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="📶  WI-FI SCANNER", font=('Courier',13,'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        self.status_lbl = ctk.CTkLabel(hdr, text="Idle", font=MONO_SM, text_color=C['mu'])
        self.status_lbl.pack(side='left', padx=8)
        
        btn_row = ctk.CTkFrame(hdr, fg_color='transparent')
        btn_row.pack(side='right', padx=12, pady=6)
        
        Btn(btn_row, "🚀 SPEED TEST", command=lambda: self.app._switch_tab('network'), 
            variant='blue', width=120).pack(side='left', padx=4)
        self.stop_btn = Btn(btn_row, "⏹ STOP", command=self._stop_scan, variant='danger', width=90)
        self.stop_btn.pack(side='left', padx=4)
        self.stop_btn.configure(state='disabled')
        self.scan_btn = Btn(btn_row, "▶ SCAN", command=self._start_scan, width=90)
        self.scan_btn.pack(side='left', padx=4)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        SectionHeader(body, '01', 'CURRENT CONNECTION').pack(fill='x', padx=14, pady=(14,4))
        self.curr_card = Card(body)
        self.curr_card.pack(fill='x', padx=14, pady=(0,6))
        self.curr_info = InfoGrid(self.curr_card, [
            ('STATUS','—'),('TYPE','—'),('SSID','—'),('LOCAL IP','—')], columns=4)
        self.curr_info.pack(fill='x', padx=4, pady=4)

        SectionHeader(body, '02', 'VPN / TUNNEL DETECTION').pack(fill='x', padx=14, pady=(10,4))
        self.vpn_card = Card(body)
        self.vpn_card.pack(fill='x', padx=14, pady=(0,6))
        ctk.CTkLabel(self.vpn_card, text="Tap ▶ SCAN to check for VPN interfaces",
                     font=MONO_SM, text_color=C['mu']).pack(padx=12, pady=10)

        SectionHeader(body, '03', 'YOUR SAVED NETWORKS').pack(fill='x', padx=14, pady=(10,4))
        self.saved_hdr = ctk.CTkFrame(body, fg_color='transparent')
        self.saved_hdr.pack(fill='x', padx=14)
        
        self.saved_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.saved_frame.pack(fill='x', padx=14, pady=(0,6))
        ctk.CTkLabel(self.saved_frame, text="Tap ▶ SCAN to load saved networks",
                     font=MONO_SM, text_color=C['mu']).pack(pady=8)

        SectionHeader(body, '04', 'NEARBY NETWORKS').pack(fill='x', padx=14, pady=(10,4))
        self.nearby_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.nearby_frame.pack(fill='x', padx=14, pady=(0,14))
        ctk.CTkLabel(self.nearby_frame,
                     text="Tap ▶ SCAN to discover all Wi-Fi networks in range",
                     font=MONO_SM, text_color=C['mu']).pack(pady=20)

        SectionHeader(body, '05', 'EVIL TWIN DETECTION').pack(fill='x', padx=14, pady=(10,4))
        et_card = Card(body, accent=C['wn'])
        et_card.pack(fill='x', padx=14, pady=(0,14))
        
        ctk.CTkLabel(et_card, text="Scan for duplicate SSIDs with different BSSIDs (MACs).",
                     font=MONO_SM, text_color=C['mu']).pack(pady=(12,4))
        
        self.et_res = ctk.CTkLabel(et_card, text="", font=MONO_SM, text_color=C['wn'])
        self.et_res.pack(pady=(0,8))
        
        Btn(et_card, "💀 CHECK FOR EVIL TWINS", command=self._scan_evil_twin, variant='danger', width=200).pack(pady=(0,12))

    def _scan_evil_twin(self):
        self.et_res.configure(text="Scanning BSSIDs...", text_color=C['ac'])
        threading.Thread(target=self._do_et_scan, daemon=True).start()

    def _do_et_scan(self):
        # Using nmcli to get all APs
        out, _, rc = run("nmcli -t -f SSID,BSSID,SIGNAL,CHAN device wifi list")
        if rc != 0:
            self.et_res.configure(text="Scan failed (requires nmcli)", text_color=C['wn'])
            return

        ssid_map = {} # SSID -> list of (BSSID, SIGNAL)
        for line in out.split('\n'):
            parts = line.split(':')
            if len(parts) >= 2:
                ssid = parts[0]
                bssid = ":".join(parts[1:7]) if len(parts) >= 7 else parts[1]
                if not ssid: continue
                
                if ssid not in ssid_map:
                    ssid_map[ssid] = []
                ssid_map[ssid].append(bssid)

        evil_twins = []
        for ssid, bssids in ssid_map.items():
            unique_bssids = set(bssids)
            if len(unique_bssids) > 1:
                evil_twins.append(f"{ssid} ({len(unique_bssids)} APs)")

        if evil_twins:
            msg = "POSSIBLE EVIL TWINS FOUND:\n" + "\n".join(evil_twins)
            col = C['wn']
        else:
            msg = "No duplicate SSIDs found."
            col = C['ok']
        
        self.et_res.configure(text=msg, text_color=col)

    def _load_current(self):
        out, _, _    = run("nmcli -t -f TYPE,STATE dev 2>/dev/null | head -3")
        ip_out, _, _ = run("ip route get 8.8.8.8 2>/dev/null | grep src | awk '{print $7}' | head -1")
        ssid_out = get_current_wifi()
        conn_type    = 'Wi-Fi' if 'wifi' in out.lower() else 'Ethernet' if 'ethernet' in out.lower() else 'Unknown'
        connected    = 'connected' in out.lower()
        self.after(0, self._render_current, conn_type, ssid_out, ip_out, connected)

    def _render_current(self, conn_type, ssid, ip, connected):
        self.curr_info.destroy()
        self.curr_info = InfoGrid(self.curr_card, [
            ('STATUS',  'CONNECTED' if connected else 'DISCONNECTED',
             C['ok'] if connected else C['wn']),
            ('TYPE',    conn_type,   C['ac']),
            ('SSID',    ssid or '—', C['ok'] if ssid else C['mu']),
            ('LOCAL IP',ip or '—',   C['am']),
        ], columns=4)
        self.curr_info.pack(fill='x', padx=4, pady=4)

    def _start_scan(self):
        if self._scanning: return
        self._scanning = True
        self.scan_btn.configure(state='disabled', text='SCANNING...')
        self.stop_btn.configure(state='normal')
        self.status_lbl.configure(text='Scanning...', text_color=C['ac'])
        for w in self.nearby_frame.winfo_children(): w.destroy()
        for w in self.saved_frame.winfo_children():  w.destroy()
        ctk.CTkLabel(self.nearby_frame, text="⟳ Scanning...",
                     font=MONO_SM, text_color=C['ac']).pack(pady=8)
        threading.Thread(target=self._do_full_scan, daemon=True).start()

    def _stop_scan(self):
        self._scanning = False
        self.scan_btn.configure(state='normal', text='▶ SCAN')
        self.stop_btn.configure(state='disabled')
        self.status_lbl.configure(text='Stopped', text_color=C['mu'])

    def _do_full_scan(self):
        if not self._scanning: return

        # VPN check
        vpn_ifaces, vpn_procs = [], []
        ifaces_out, _, _ = run("ip link show 2>/dev/null")
        for iface in re.findall(r'\d+: (\w+):', ifaces_out):
            if any(x in iface.lower() for x in ['tun','tap','wg','vpn','ppp','zt','tor']):
                ip_out, _, _ = run(f"ip addr show {iface} 2>/dev/null | grep 'inet ' | awk '{{print $2}}'")
                vpn_ifaces.append({'name': iface, 'ip': ip_out or '—'})
        for proc in ['openvpn','wireguard','nordvpn','expressvpn','tailscale','zerotier']:
            out, _, rc = run(f"pgrep -x {proc} 2>/dev/null")
            if rc == 0: vpn_procs.append(proc)
        self.after(0, self._render_vpn, vpn_ifaces, vpn_procs)
        if not self._scanning: return

        # Saved networks
        saved_out, _, _ = run("nmcli -t -f NAME,TYPE,TIMESTAMP-REAL connection show 2>/dev/null | grep -E '802-11-wireless|ethernet' | sort -t: -k3 -nr", timeout=8)
        saved = []
        for line in saved_out.split('\n'):
            parts = line.split(':')
            if len(parts) >= 3 and parts[0]:
                saved.append({'name': parts[0], 'last': parts[-1]})
        self.after(0, self._render_saved, saved)
        if not self._scanning: return

        # Rescan and list
        run("nmcli device wifi rescan 2>/dev/null", timeout=5)
        networks = get_wifi_networks()
        
        self.after(0, self._render_networks, networks)
        self._scanning = False
        self.after(0, lambda: (
            self.scan_btn.configure(state='normal', text='↺ RESCAN'),
            self.stop_btn.configure(state='disabled'),
            self.status_lbl.configure(text=f"Found {len(networks)} networks", text_color=C['ok'])
        ))

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
        items = [(v['name'].upper(), v['ip'], C['bl']) for v in interfaces]
        items += [(p.upper(), 'Process active', C['bl']) for p in procs]
        if items:
            InfoGrid(self.vpn_card, items, columns=3).pack(fill='x', padx=8, pady=(0,8))
        else:
            ctk.CTkLabel(self.vpn_card, text="No tun/tap/wg/ppp/zerotier interfaces active",
                         font=MONO_SM, text_color=C['mu']).pack(padx=12, pady=(0,8))

    def _render_saved(self, saved):
        for w in self.saved_hdr.winfo_children(): w.destroy()
        for w in self.saved_frame.winfo_children(): w.destroy()
        if not saved:
            ctk.CTkLabel(self.saved_frame,
                         text="No saved networks found. Connect to Wi-Fi to populate this list.",
                         font=MONO_SM, text_color=C['mu']).pack(pady=8)
            return
            
        Btn(self.saved_hdr, "📋 COPY ALL", command=lambda: self._copy_all_saved(saved),
            variant='ghost', width=120).pack(side='right', pady=(0,4))
            
        ctk.CTkLabel(self.saved_frame, text=f"{len(saved)} saved network(s):",
                     font=('Courier',9,'bold'), text_color=C['ac']).pack(anchor='w', pady=(0,4))
        for net in saved[:20]:
            row = ctk.CTkFrame(self.saved_frame, fg_color=C['sf'],
                                border_color=C['br'], border_width=1, corner_radius=8)
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text='🔒', font=('Courier',16)).pack(side='left', padx=10, pady=8)
            info = ctk.CTkFrame(row, fg_color='transparent')
            info.pack(side='left', fill='both', expand=True, pady=8)
            ctk.CTkLabel(info, text=net['name'], font=('Courier',11,'bold'),
                         text_color=C['tx']).pack(anchor='w')
            ctk.CTkLabel(info, text=f"Last: {net['last']}", font=('Courier',8),
                         text_color=C['mu']).pack(anchor='w')
            Btn(row, "SHOW PWD", command=lambda n=net['name']: self._show_password(n),
                variant='ghost', width=90).pack(side='right', padx=8)

    def _copy_all_saved(self, saved):
        text = "MINT SCAN - SAVED WI-FI NETWORKS\n" + "="*40 + "\n"
        for net in saved:
            text += f"SSID: {net['name']}  Last Used: {net['last']}\n"
        if copy_to_clipboard(text):
            self.status_lbl.configure(text="Saved networks copied to clipboard", text_color=C['ok'])

    def _show_password(self, name):
        out, _, rc = run(f"sudo nmcli -s -g 802-11-wireless-security.psk connection show '{name}' 2>/dev/null")
        popup = ctk.CTkToplevel(self)
        popup.title(f"Password: {name}")
        popup.geometry("420x200")
        popup.configure(fg_color=C['bg'])
        popup.attributes('-topmost', True)
        if rc == 0 and out.strip():
            pwd = out.strip()
            ctk.CTkLabel(popup, text=name, font=('Courier',12,'bold'),
                         text_color=C['ac']).pack(pady=(12,4))
            e = ctk.CTkEntry(popup, font=('Courier',13,'bold'),
                             fg_color=C['s2'], border_color=C['ac'], text_color=C['ok'])
            e.pack(fill='x', padx=20, pady=8)
            e.insert(0, pwd)
            Btn(popup, "📋 COPY PASSWORD", command=lambda: copy_to_clipboard(pwd),
                variant='success').pack(pady=4)
        else:
            ctk.CTkLabel(popup,
                text=f"Cannot read: {name}\n\nMake sure to ALLOW the pkexec prompt.",
                font=MONO_SM, text_color=C['mu'], justify='center').pack(expand=True, pady=10)
        Btn(popup, "CLOSE", command=popup.destroy, variant='ghost').pack(pady=4)

    def _render_networks(self, networks):
        for w in self.nearby_frame.winfo_children(): w.destroy()
        if not networks:
            ResultBox(self.nearby_frame,'warn','⚠ NO NETWORKS FOUND',
                      'Make sure Wi-Fi is on. Try: sudo nmcli device wifi rescan'
                      ).pack(fill='x')
            return
        open_nets = [n for n in networks if n['security'].upper()=='OPEN']
        wep_nets  = [n for n in networks if 'WEP' in n['security'].upper()]
        summary   = Card(self.nearby_frame, accent=C['wn'] if open_nets else C['ok'])
        summary.pack(fill='x', pady=(0,8))
        InfoGrid(summary,[('FOUND',len(networks),C['ac']),('OPEN',len(open_nets),
                C['wn'] if open_nets else C['ok']),('WEP',len(wep_nets),
                C['wn'] if wep_nets else C['ok']),
                ('SECURE',len(networks)-len(open_nets)-len(wep_nets),C['ok'])],
                columns=4).pack(fill='x', padx=4, pady=4)
        if open_nets:
            ResultBox(summary,'warn',f'⚠ {len(open_nets)} OPEN NETWORK(S) — NO ENCRYPTION',
                      'Avoid banking or sensitive data on these.'
                      ).pack(fill='x', padx=8, pady=(0,8))
        curr,_,_ = run("nmcli -t -f active,ssid dev wifi 2>/dev/null | grep '^yes' | cut -d: -f2 | head -1")
        for net in networks:
            sec  = net['security'].upper()
            col  = sec_color(sec)
            sig  = net.get('signal',0)
            sc   = sig_color(sig)
            icon = '🔓' if sec=='OPEN' else '⚠️' if 'WEP' in sec else '🔒'
            row  = ctk.CTkFrame(self.nearby_frame, fg_color=C['sf'],
                                 border_color=C['ok'] if net['ssid']==curr.strip() else col,
                                 border_width=1, corner_radius=8)
            row.pack(fill='x', pady=3)
            ctk.CTkLabel(row, text=icon, font=('Courier',18)).pack(side='left', padx=10, pady=8)
            mid = ctk.CTkFrame(row, fg_color='transparent')
            mid.pack(side='left', fill='both', expand=True, pady=8)
            ctk.CTkLabel(mid, text=net['ssid']+('' if net['ssid']!=curr.strip() else '  ✓ CONNECTED'),
                         font=('Courier',11,'bold'),
                         text_color=C['ok'] if net['ssid']==curr.strip() else C['tx']
                         ).pack(anchor='w')
            ctk.CTkLabel(mid, text=f"{sec}  ·  CH {net['channel']}  ·  {net['freq']}  ·  BSSID: {net['bssid']}",
                         font=('Courier',8), text_color=C['mu']).pack(anchor='w')
            if sec=='OPEN':
                ctk.CTkLabel(mid, text="⚠ No encryption", font=('Courier',8), text_color=C['wn']).pack(anchor='w')
            right = ctk.CTkFrame(row, fg_color='transparent')
            right.pack(side='right', padx=12, pady=8)
            badge = ctk.CTkFrame(right, fg_color=C['s2'], border_color=col, border_width=1, corner_radius=3)
            badge.pack(pady=(0,4))
            ctk.CTkLabel(badge, text=sec[:8], font=('Courier',7,'bold'), text_color=col).pack(padx=6,pady=2)
            bars = 4 if sig>=75 else 3 if sig>=50 else 2 if sig>=25 else 1
            br = ctk.CTkFrame(right, fg_color='transparent')
            br.pack()
            for b in range(4):
                ctk.CTkFrame(br, width=5, height=(b+1)*5+3,
                             fg_color=sc if b<bars else C['br'],
                             corner_radius=1).pack(side='left', padx=1, anchor='s')
            ctk.CTkLabel(right, text=f"{sig}%", font=('Courier',8), text_color=sc).pack()
