"""
Device Scanner — IoT, CCTV, Smart Appliances, Infected Device Detection.
Fingerprints every device on the network by MAC vendor, open ports, banners,
and known IoT signatures. Flags infected or compromised devices.
"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, re, time, os, socket, json
from widgets import (ScrollableFrame, Card, SectionHeader, InfoGrid,
                     ResultBox, Btn, Badge, C, MONO, MONO_SM)
from utils import run_cmd as _run

# ── Device type fingerprint DB ────────────────────────────────────
# (vendor keyword → device type, icon, risk_ports)
VENDOR_TYPES = {
    'hikvision':  ('CCTV Camera',    '📷', ['80','443','554','8000','8080']),
    'dahua':      ('CCTV Camera',    '📷', ['80','443','554','37777']),
    'axis':       ('IP Camera',      '📷', ['80','443','554']),
    'reolink':    ('IP Camera',      '📷', ['80','554','9000']),
    'foscam':     ('IP Camera',      '📷', ['80','88','443']),
    'amcrest':    ('CCTV/NVR',       '📹', ['80','443','554','37777']),
    'hanwha':     ('CCTV Camera',    '📷', ['80','443','554']),
    'vivotek':    ('IP Camera',      '📷', ['80','443','554']),
    'tp-link':    ('Router/Switch',  '🌐', ['80','443','22','23']),
    'tplink':     ('Router/Switch',  '🌐', ['80','443','22','23']),
    'netgear':    ('Router',         '🌐', ['80','443','22']),
    'asus':       ('Router',         '🌐', ['80','443','22','8080']),
    'cisco':      ('Network Equip',  '🔌', ['22','23','80','443','161']),
    'ubiquiti':   ('Network Equip',  '🔌', ['22','80','443','8080','8443']),
    'mikrotik':   ('Router',         '🌐', ['21','22','23','80','8291']),
    'd-link':     ('Router/Camera',  '🌐', ['80','443','23','8080']),
    'dlink':      ('Router/Camera',  '🌐', ['80','443','23','8080']),
    'samsung':    ('Smart Device',   '📱', ['80','443','7676','9197']),
    'lg':         ('Smart TV/Appl',  '📺', ['80','443','1926','3000']),
    'sony':       ('Smart TV',       '📺', ['80','443','10000']),
    'philips':    ('Smart Light/TV', '💡', ['80','443','1900']),
    'amazon':     ('Smart Speaker',  '🔊', ['80','443','4070','55442']),
    'google':     ('Smart Speaker',  '🔊', ['80','443','8008','8009']),
    'apple':      ('Apple Device',   '🍎', ['80','443','548','5353']),
    'raspberry':  ('Raspberry Pi',   '🍓', ['22','80','443']),
    'espressif':  ('IoT Module',     '🔧', ['80','443','8266']),
    'tuya':       ('Smart Plug/IoT', '🔌', ['6668','6669','6670']),
    'shelly':     ('Smart Plug',     '🔌', ['80','443']),
    'synology':   ('NAS',            '💾', ['22','80','443','5000','5001']),
    'qnap':       ('NAS',            '💾', ['22','80','443','8080','8081']),
    'western':    ('NAS/Drive',      '💾', ['22','80','443','9000']),
    'seagate':    ('NAS',            '💾', ['22','80','443']),
    'canon':      ('Printer',        '🖨',  ['80','443','515','631','9100']),
    'hp':         ('Printer',        '🖨',  ['80','443','515','631','9100']),
    'epson':      ('Printer',        '🖨',  ['80','443','515','631']),
    'brother':    ('Printer',        '🖨',  ['80','443','515','631','9100']),
    'xbox':       ('Gaming Console', '🎮', ['80','443','3074','3075']),
    'playstation':('Gaming Console', '🎮', ['80','443','3478','3479']),
    'nintendo':   ('Gaming Console', '🎮', ['80','443']),
    'intel':      ('PC/NUC',         '💻', ['22','80','443']),
    'vmware':     ('Virtual Machine', '🖥', ['22','80','443','902']),
}

# ── Infection/malware indicators ──────────────────────────────────
INFECTED_PORTS = {
    '23':    ('Telnet open',       'HIGH',  'Credentials transmitted in plaintext. Common malware C2 channel.'),
    '4444':  ('Metasploit port',   'CRIT',  'Classic Metasploit/Meterpreter reverse shell port.'),
    '5555':  ('ADB over network',  'HIGH',  'Android Debug Bridge exposed. Full device compromise possible.'),
    '1337':  ('Leet/Backdoor',     'HIGH',  'Port 1337 associated with backdoor and hacker tools.'),
    '31337': ('Back Orifice',      'CRIT',  'Back Orifice RAT port. Device likely compromised.'),
    '6667':  ('IRC C2',            'HIGH',  'IRC port used by botnet command-and-control.'),
    '9001':  ('Tor ORPort',        'MED',   'Tor relay or hidden service running.'),
    '9050':  ('Tor SOCKSPort',     'MED',   'Tor SOCKS proxy — anonymized traffic routing.'),
    '1080':  ('SOCKS Proxy',       'MED',   'SOCKS proxy may indicate traffic tunnelling.'),
    '3389':  ('RDP Exposed',       'HIGH',  'Remote Desktop exposed to network. Ransomware entry point.'),
    '5900':  ('VNC Exposed',       'HIGH',  'VNC remote desktop exposed. Often unencrypted.'),
    '8443':  ('Alt-HTTPS/C2',      'MED',   'Alternate HTTPS sometimes used by malware C2.'),
    '2323':  ('Alt-Telnet',        'HIGH',  'Alternate Telnet port. Used by Mirai botnet.'),
    '7547':  ('TR-069/Mirai',      'CRIT',  'TR-069 management port. Targeted by Mirai and Satori botnets.'),
    '37215': ('Huawei Exploit',    'CRIT',  'CVE-2017-17215 — Huawei router RCE exploit port.'),
    '52869': ('UPnP/Reaper',       'HIGH',  'UPnP port targeted by IoT Reaper botnet.'),
    '6379':  ('Redis Exposed',     'HIGH',  'Redis with no auth — full data access and RCE possible.'),
    '27017': ('MongoDB Exposed',   'HIGH',  'MongoDB with no auth — full database access.'),
    '2375':  ('Docker API',        'CRIT',  'Docker daemon exposed — container escape and host takeover.'),
}

KNOWN_MALWARE_BANNERS = [
    'mirai', 'satori', 'reaper', 'bashlite', 'mozi',
    'gafgyt', 'hajime', 'brickerbot', 'aidra',
]

# ── Color helpers ────────────────────────────────────────────────
RISK_COLOR = {'CRIT': C['wn'], 'HIGH': C['wn'], 'MED': C['am'], 'LOW': C['ok'], 'OK': C['ok']}


class DevScanScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app       = app
        self._built    = False
        self._scanning = False
        self._devices  = []

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True

    # ── UI BUILD ─────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=52, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📡  DEVICE SCANNER — IoT · CCTV · APPLIANCES",
                     font=('Courier',12,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        self.stop_btn = Btn(hdr, "⏹ STOP", command=self._stop,
                            variant='danger', width=80)
        self.stop_btn.pack(side='right', padx=4, pady=8)
        self.stop_btn.configure(state='disabled')
        Btn(hdr, "💾 EXPORT", command=self._export,
            variant='ghost', width=90).pack(side='right', padx=4, pady=8)
        self.scan_btn = Btn(hdr, "▶ SCAN NETWORK", command=self._start_scan, width=140)
        self.scan_btn.pack(side='right', padx=4, pady=8)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # Subnet input
        SectionHeader(body, '01', 'SCAN TARGET').pack(fill='x', padx=14, pady=(14,4))
        tgt = Card(body)
        tgt.pack(fill='x', padx=14, pady=(0,8))

        tgt_row = ctk.CTkFrame(tgt, fg_color='transparent')
        tgt_row.pack(fill='x', padx=10, pady=10)
        ctk.CTkLabel(tgt_row, text="Subnet:", font=MONO_SM,
                     text_color=C['mu']).pack(side='left', padx=(0,8))
        self.subnet_entry = ctk.CTkEntry(tgt_row,
            placeholder_text="Auto-detect",
            font=MONO_SM, fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'],
            width=200, height=34)
        self.subnet_entry.pack(side='left')

        opt_row = ctk.CTkFrame(tgt, fg_color='transparent')
        opt_row.pack(fill='x', padx=10, pady=(0,10))
        self.opt_deep    = ctk.BooleanVar(value=True)
        self.opt_infect  = ctk.BooleanVar(value=True)
        self.opt_banner  = ctk.BooleanVar(value=True)
        for var, lbl in [(self.opt_deep,   'Deep port scan'),
                         (self.opt_infect, 'Infection check'),
                         (self.opt_banner, 'Banner grab')]:
            ctk.CTkCheckBox(opt_row, text=lbl, variable=var,
                font=('Courier',8), text_color=C['tx'],
                fg_color=C['ac'], checkmark_color=C['bg'],
                border_color=C['br'], hover_color=C['br2']
            ).pack(side='left', padx=(0,14))

        # Progress / status
        SectionHeader(body, '02', 'SCAN PROGRESS').pack(fill='x', padx=14, pady=(8,4))
        prog_card = Card(body)
        prog_card.pack(fill='x', padx=14, pady=(0,8))
        self.prog_bar = ctk.CTkProgressBar(prog_card, height=5,
            progress_color=C['ac'], fg_color=C['br'])
        self.prog_bar.pack(fill='x', padx=10, pady=(10,4))
        self.prog_bar.set(0)
        self.prog_lbl = ctk.CTkLabel(prog_card, text="Idle — tap ▶ SCAN NETWORK",
            font=MONO_SM, text_color=C['mu'])
        self.prog_lbl.pack(anchor='w', padx=10, pady=(0,10))

        # Summary
        SectionHeader(body, '03', 'NETWORK SUMMARY').pack(fill='x', padx=14, pady=(8,4))
        self.summary_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.summary_frame.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self.summary_frame, text="No scan yet.",
                     font=MONO_SM, text_color=C['mu']).pack(pady=6)

        # Infected devices
        SectionHeader(body, '04', 'INFECTED / COMPROMISED DEVICES').pack(fill='x', padx=14, pady=(8,4))
        self.infected_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.infected_frame.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self.infected_frame, text="Infection check results will appear here.",
                     font=MONO_SM, text_color=C['mu']).pack(pady=6)

        # All devices
        SectionHeader(body, '05', 'ALL DISCOVERED DEVICES').pack(fill='x', padx=14, pady=(8,4))
        self.devices_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.devices_frame.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self.devices_frame, text="Devices will appear after scan.",
                     font=MONO_SM, text_color=C['mu']).pack(pady=6)

        # Log
        SectionHeader(body, '06', 'SCAN LOG').pack(fill='x', padx=14, pady=(8,4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0,14))
        self.log_box = ctk.CTkTextbox(log_card, height=130,
            font=('Courier',9), fg_color=C['bg'],
            text_color=C['ok'], border_width=0)
        self.log_box.pack(fill='x', padx=8, pady=8)

    # ── SCAN ENGINE ───────────────────────────────────────────────

    def _start_scan(self):
        if self._scanning:
            return
        self._scanning = True
        self._devices  = []
        self.scan_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.prog_bar.set(0)
        self._clear(self.summary_frame)
        self._clear(self.infected_frame)
        self._clear(self.devices_frame)
        self.log_box.delete('1.0', 'end')
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _stop(self):
        self._scanning = False
        self._set_prog(0, "Scan stopped.")
        self.scan_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self._log("⏹ Scan stopped by user.")

    def _do_scan(self):
        # Step 1: Detect subnet
        subnet = self.subnet_entry.get().strip()
        if not subnet:
            out, _, _ = _run("ip route | grep -v default | grep '/' | head -1 | awk '{print $1}'")
            subnet = out.strip() or '192.168.1.0/24'
        self._log(f"Target subnet: {subnet}")
        self._set_prog(0.05, f"Discovering devices on {subnet}...")

        # Step 2: Host discovery
        devices = self._discover_hosts(subnet)
        if not self._scanning:
            return

        total = len(devices)
        self._log(f"Found {total} active hosts")
        self._set_prog(0.2, f"Found {total} hosts — fingerprinting...")

        # Step 3: Fingerprint each device
        for i, dev in enumerate(devices):
            if not self._scanning:
                break
            pct = 0.2 + (0.7 * (i / max(total, 1)))
            self._set_prog(pct, f"Scanning {dev['ip']} ({i+1}/{total})...")
            self._fingerprint(dev)
            self._devices.append(dev)

        if not self._scanning:
            return

        self._set_prog(0.95, "Building report...")
        self.after(0, self._render_all)
        self._set_prog(1.0, f"✓ Scan complete — {total} devices found.")
        self._scanning = False
        self.after(0, lambda: self.scan_btn.configure(state='normal'))
        self.after(0, lambda: self.stop_btn.configure(state='disabled'))

    def _discover_hosts(self, subnet):
        devices = []
        # Try nmap -sn (ping scan)
        out, _, rc = _run(f"nmap -sn --host-timeout 3s {subnet} 2>/dev/null", timeout=60)
        if rc == 0 and 'Nmap scan report' in out:
            cur = {}
            for line in out.split('\n'):
                if 'Nmap scan report' in line:
                    if cur:
                        devices.append(cur)
                    ip_m    = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    host_m  = re.search(r'for (.+?) \(', line)
                    cur = {
                        'ip':     ip_m.group(1) if ip_m else '',
                        'host':   host_m.group(1) if host_m else '',
                        'mac':    '', 'vendor': '', 'type': 'Unknown',
                        'icon':   '❓', 'ports': [], 'risks': [],
                        'infected': False, 'infect_reasons': [],
                    }
                elif 'MAC Address' in line and cur:
                    mac_m    = re.search(r'([0-9A-F:]{17})', line)
                    vendor_m = re.search(r'\((.+)\)', line)
                    cur['mac']    = mac_m.group(1) if mac_m else ''
                    cur['vendor'] = vendor_m.group(1) if vendor_m else ''
            if cur:
                devices.append(cur)
        else:
            # Fallback: arp table
            out, _, _ = _run("arp -n 2>/dev/null | grep -v incomplete | tail -n +2")
            for line in out.split('\n'):
                parts = line.split()
                if len(parts) >= 3 and re.match(r'\d+\.\d+\.\d+\.\d+', parts[0]):
                    devices.append({
                        'ip': parts[0], 'mac': parts[2],
                        'vendor': '', 'host': '',
                        'type': 'Unknown', 'icon': '❓',
                        'ports': [], 'risks': [],
                        'infected': False, 'infect_reasons': [],
                    })
        return devices

    def _fingerprint(self, dev):
        ip     = dev['ip']
        vendor = (dev['vendor'] or '').lower()

        # Identify device type from vendor
        for kw, (dtype, icon, _) in VENDOR_TYPES.items():
            if kw in vendor:
                dev['type'] = dtype
                dev['icon'] = icon
                break

        # Port scan
        if self.opt_deep.get():
            ports = self._port_scan(ip)
        else:
            ports = self._quick_port_scan(ip)
        dev['ports'] = ports

        # Refine type from ports if still unknown
        if dev['type'] == 'Unknown':
            dev['type'], dev['icon'] = self._type_from_ports(ports)

        # Infection check
        if self.opt_infect.get():
            self._infection_check(dev)

        # Banner grab
        if self.opt_banner.get() and ports:
            banner = self._grab_banner(ip, ports)
            if banner:
                dev['banner'] = banner
                blo = banner.lower()
                for sig in KNOWN_MALWARE_BANNERS:
                    if sig in blo:
                        dev['infected']  = True
                        dev['infect_reasons'].append(
                            f"CRIT: Malware signature in banner: '{sig}'")

        self._log(f"  {dev['icon']} {ip:16s} {dev['type']:20s} ports:{len(dev['ports'])} "
                  f"{'⚠INFECTED' if dev['infected'] else ''}")

    def _port_scan(self, ip):
        """Full port scan using nmap, fallback to socket probe."""
        open_ports = []
        # CCTV + IoT + malware ports list
        port_list = ('21,22,23,25,53,80,81,88,110,443,445,554,1080,1337,'
                     '1883,1900,2323,2375,3306,3389,4444,5000,5001,5555,'
                     '5900,6379,6667,6668,6670,7547,8000,8008,8080,8081,'
                     '8088,8443,8888,9000,9001,9050,9100,9197,27017,37215,'
                     '37777,52869')
        out, _, rc = _run(
            f"nmap -T4 --open -p {port_list} --host-timeout 8s {ip} 2>/dev/null",
            timeout=20)
        if rc == 0:
            for line in out.split('\n'):
                m = re.match(r'(\d+)/(tcp|udp)\s+open', line)
                if m:
                    open_ports.append(m.group(1))
        else:
            open_ports = self._quick_port_scan(ip)
        return open_ports

    def _quick_port_scan(self, ip):
        """Fast socket-based scan of key ports."""
        check = [80, 443, 554, 22, 23, 8080, 8000, 4444, 5555, 7547]
        open_p = []
        for port in check:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.8)
                if s.connect_ex((ip, port)) == 0:
                    open_p.append(str(port))
                s.close()
            except Exception:
                pass
        return open_p

    def _type_from_ports(self, ports):
        port_set = set(ports)
        if '554' in port_set:
            return 'IP Camera/DVR', '📷'
        if '9100' in port_set or '631' in port_set or '515' in port_set:
            return 'Printer', '🖨'
        if '3389' in port_set:
            return 'Windows PC', '💻'
        if '548' in port_set:
            return 'Mac/Apple', '🍎'
        if '1883' in port_set:
            return 'IoT (MQTT)', '🔧'
        if '6379' in port_set or '27017' in port_set:
            return 'Database Server', '💾'
        if '2375' in port_set:
            return 'Docker Host', '🐳'
        if '22' in port_set and '80' in port_set:
            return 'Linux Server', '🖥'
        if '80' in port_set or '443' in port_set:
            return 'Web Device', '🌐'
        return 'Unknown Device', '❓'

    def _infection_check(self, dev):
        ip    = dev['ip']
        ports = set(dev['ports'])

        for port, (name, level, desc) in INFECTED_PORTS.items():
            if port in ports:
                dev['risks'].append((level, name, desc, port))
                if level in ('CRIT', 'HIGH'):
                    dev['infected'] = True
                    dev['infect_reasons'].append(f"{level}: {name} (port {port})")

        # Check for default credentials on common IoT ports
        if '23' in ports:
            result = self._test_telnet_default(ip)
            if result:
                dev['infected'] = True
                dev['infect_reasons'].append(f"CRIT: Default Telnet credentials accepted — {result}")
                dev['risks'].append(('CRIT', 'Default credentials', result, '23'))

        # RTSP stream check (CCTV without auth)
        if '554' in ports:
            rtsp_open = self._test_rtsp(ip)
            if rtsp_open:
                dev['risks'].append(('HIGH', 'RTSP stream open (no auth)',
                    'Camera stream publicly accessible on network', '554'))
                dev['infect_reasons'].append("HIGH: RTSP stream unauthenticated")

    def _test_telnet_default(self, ip):
        """Try a handful of default IoT credentials over Telnet."""
        defaults = [('admin','admin'),('root',''),('admin',''),
                    ('root','root'),('admin','1234'),('admin','password')]
        try:
            import telnetlib
            for user, pwd in defaults[:3]:  # Only try 3 to stay fast
                try:
                    t = telnetlib.Telnet(ip, 23, timeout=2)
                    t.read_until(b'login:', timeout=2)
                    t.write(user.encode() + b'\n')
                    t.read_until(b'Password:', timeout=2)
                    t.write(pwd.encode() + b'\n')
                    time.sleep(0.5)
                    resp = t.read_very_eager().decode(errors='ignore')
                    t.close()
                    if '$' in resp or '#' in resp or '>' in resp:
                        return f"user='{user}' pwd='{pwd}'"
                except Exception:
                    pass
        except ImportError:
            pass
        return None

    def _test_rtsp(self, ip):
        """Check if RTSP port responds without auth."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((ip, 554))
            s.send(b'OPTIONS rtsp://' + ip.encode() + b'/ RTSP/1.0\r\nCSeq: 1\r\n\r\n')
            resp = s.recv(256).decode(errors='ignore')
            s.close()
            return 'RTSP/1.0 200' in resp or 'RTSP/1.0 401' not in resp
        except Exception:
            return False

    def _grab_banner(self, ip, ports):
        """Grab HTTP or raw banner from first open port."""
        for port in ports[:3]:
            try:
                p = int(port)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.5)
                s.connect((ip, p))
                if p in (80, 8080, 8000, 8088, 81):
                    s.send(b'HEAD / HTTP/1.0\r\nHost: ' + ip.encode() + b'\r\n\r\n')
                else:
                    s.send(b'\r\n')
                banner = s.recv(512).decode(errors='ignore').strip()
                s.close()
                if banner:
                    return banner[:200]
            except Exception:
                pass
        return ''

    # ── RENDER ────────────────────────────────────────────────────

    def _render_all(self):
        devices  = self._devices
        infected = [d for d in devices if d['infected']]
        risky    = [d for d in devices if d['risks'] and not d['infected']]

        # Summary
        self._clear(self.summary_frame)
        types = {}
        for d in devices:
            types[d['type']] = types.get(d['type'], 0) + 1

        InfoGrid(self.summary_frame, [
            ('TOTAL DEVICES',   len(devices),         C['ac']),
            ('INFECTED/RISKY',  len(infected)+len(risky),
             C['wn'] if infected else C['am'] if risky else C['ok']),
            ('DEVICE TYPES',    len(types),            C['bl']),
            ('OPEN PORTS TOTAL',sum(len(d['ports']) for d in devices), C['mu']),
        ], columns=4).pack(fill='x', pady=(0,8))

        # Type breakdown
        type_row = ctk.CTkFrame(self.summary_frame, fg_color='transparent')
        type_row.pack(fill='x', pady=(0,4))
        for dtype, count in sorted(types.items(), key=lambda x: -x[1])[:6]:
            icon = next((d['icon'] for d in devices if d['type']==dtype), '❓')
            card = ctk.CTkFrame(type_row, fg_color=C['sf'],
                                border_color=C['br'], border_width=1, corner_radius=6)
            card.pack(side='left', padx=3, pady=2)
            ctk.CTkLabel(card, text=f"{icon} {dtype}\n×{count}",
                         font=('Courier',8), text_color=C['tx'], justify='center'
                         ).pack(padx=10, pady=6)

        # Infected section
        self._clear(self.infected_frame)
        if not infected and not risky:
            ResultBox(self.infected_frame, 'ok',
                      '✓ No infected devices detected',
                      'All scanned devices appear clean.'
                      ).pack(fill='x')
        else:
            if infected:
                ResultBox(self.infected_frame, 'warn',
                          f'⚠ {len(infected)} INFECTED / COMPROMISED DEVICE(S)',
                          'These devices show signs of compromise or active infection.'
                          ).pack(fill='x', pady=(0,6))
                for dev in infected:
                    self._render_infected_card(dev)
            if risky:
                ResultBox(self.infected_frame, 'med',
                          f'⚡ {len(risky)} DEVICE(S) WITH RISKS',
                          'These devices have suspicious ports or weak configurations.'
                          ).pack(fill='x', pady=(4,6))
                for dev in risky:
                    self._render_infected_card(dev)

        # All devices
        self._clear(self.devices_frame)
        for dev in sorted(devices, key=lambda d: (not d['infected'], d['ip'])):
            self._render_device_card(dev)

    def _render_infected_card(self, dev):
        col = C['wn'] if dev['infected'] else C['am']
        card = ctk.CTkFrame(self.infected_frame, fg_color=C['s2'],
                            border_color=col, border_width=1, corner_radius=8)
        card.pack(fill='x', pady=3)

        top = ctk.CTkFrame(card, fg_color='transparent')
        top.pack(fill='x', padx=12, pady=(10,4))
        ctk.CTkLabel(top, text=f"{dev['icon']} {dev['ip']}",
                     font=('Courier',12,'bold'), text_color=col).pack(side='left')
        ctk.CTkLabel(top, text=dev['type'],
                     font=('Courier',9), text_color=C['mu']).pack(side='left', padx=8)
        if dev.get('vendor'):
            ctk.CTkLabel(top, text=dev['vendor'],
                         font=('Courier',8), text_color=C['br2']).pack(side='left')

        for reason in dev['infect_reasons']:
            lvl_col = C['wn'] if 'CRIT' in reason or 'HIGH' in reason else C['am']
            ctk.CTkLabel(card, text=f"  ⚠ {reason}",
                         font=('Courier',9), text_color=lvl_col,
                         justify='left').pack(anchor='w', padx=12)

        if dev['ports']:
            ctk.CTkLabel(card,
                         text="  Ports: " + ', '.join(dev['ports'][:12]),
                         font=('Courier',8), text_color=C['mu']
                         ).pack(anchor='w', padx=12, pady=(2,8))

    def _render_device_card(self, dev):
        if dev['infected']:
            border = C['wn']
        elif dev['risks']:
            border = C['am']
        else:
            border = C['br']

        card = ctk.CTkFrame(self.devices_frame, fg_color=C['sf'],
                            border_color=border, border_width=1, corner_radius=8)
        card.pack(fill='x', pady=3)

        top = ctk.CTkFrame(card, fg_color='transparent')
        top.pack(fill='x', padx=12, pady=(8,2))

        # Icon + IP + type
        ctk.CTkLabel(top, text=dev['icon'],
                     font=('Courier',16), text_color=border).pack(side='left', padx=(0,8))
        info = ctk.CTkFrame(top, fg_color='transparent')
        info.pack(side='left', fill='both', expand=True)
        ip_row = ctk.CTkFrame(info, fg_color='transparent')
        ip_row.pack(anchor='w')
        ctk.CTkLabel(ip_row, text=dev['ip'],
                     font=('Courier',11,'bold'), text_color=C['ac']).pack(side='left')
        if dev['host']:
            ctk.CTkLabel(ip_row, text=f"  ({dev['host']})",
                         font=('Courier',9), text_color=C['mu']).pack(side='left')
        if dev['infected']:
            ctk.CTkLabel(ip_row, text=" ⚠ INFECTED",
                         font=('Courier',9,'bold'), text_color=C['wn']).pack(side='left', padx=6)
        elif dev['risks']:
            ctk.CTkLabel(ip_row, text=" ⚡ RISKY",
                         font=('Courier',9,'bold'), text_color=C['am']).pack(side='left', padx=6)

        meta = dev['type']
        if dev.get('vendor'):
            meta += f"  ·  {dev['vendor']}"
        if dev.get('mac'):
            meta += f"  ·  {dev['mac']}"
        ctk.CTkLabel(info, text=meta, font=('Courier',8),
                     text_color=C['mu']).pack(anchor='w')

        # Ports
        if dev['ports']:
            ports_str = '  Ports: ' + '  '.join(
                f":{p}" + (' ⚠' if p in INFECTED_PORTS else '')
                for p in dev['ports'][:10])
            ctk.CTkLabel(card, text=ports_str,
                         font=('Courier',8), text_color=C['mu']
                         ).pack(anchor='w', padx=12, pady=(0,4))

        # Risks
        for lvl, name, desc, port in dev.get('risks', [])[:3]:
            col = RISK_COLOR.get(lvl, C['am'])
            ctk.CTkLabel(card,
                text=f"  [{lvl}] {name} :{port}",
                font=('Courier',8), text_color=col
            ).pack(anchor='w', padx=12)

        # Banner
        if dev.get('banner'):
            short = dev['banner'][:100].replace('\r','').replace('\n',' ')
            ctk.CTkLabel(card, text=f"  Banner: {short}",
                         font=('Courier',7), text_color=C['br2']
                         ).pack(anchor='w', padx=12, pady=(0,6))
        else:
            card.pack_configure(pady=(0, 4))

        # Action buttons
        btn_row = ctk.CTkFrame(card, fg_color='transparent')
        btn_row.pack(anchor='e', padx=12, pady=(4,8))
        Btn(btn_row, "🔍 PORT SCAN",
            command=lambda ip=dev['ip']: self._deep_scan_device(ip),
            variant='ghost', width=110).pack(side='left', padx=3)
        if dev['infected'] or dev['risks']:
            Btn(btn_row, "⚠ DETAILS",
                command=lambda d=dev: self._show_details(d),
                variant='warning', width=100).pack(side='left', padx=3)

    # ── ACTIONS ──────────────────────────────────────────────────

    def _deep_scan_device(self, ip):
        self._log(f"Deep scan: {ip}")
        def _do():
            out, _, _ = _run(
                f"nmap -T4 -sV --open -p- --host-timeout 30s {ip} 2>/dev/null",
                timeout=60)
            self._log(f"\n── Deep scan {ip} ──\n{out[:800]}")
        threading.Thread(target=_do, daemon=True).start()

    def _show_details(self, dev):
        """Show popup with full details of an infected/risky device."""
        popup = ctk.CTkToplevel(self)
        popup.title(f"Device Details — {dev['ip']}")
        popup.geometry("640x480")
        popup.configure(fg_color=C['bg'])
        popup.lift()
        popup.focus_force()

        ctk.CTkLabel(popup,
            text=f"{dev['icon']}  {dev['ip']}  —  {dev['type']}",
            font=('Courier',14,'bold'), text_color=C['ac']
        ).pack(pady=(16,4))

        box = ctk.CTkTextbox(popup, font=('Courier',10),
                             fg_color=C['s2'], text_color=C['tx'],
                             border_color=C['br'], border_width=1)
        box.pack(fill='both', expand=True, padx=14, pady=(0,14))

        lines = []
        lines.append(f"IP:      {dev['ip']}")
        lines.append(f"Host:    {dev.get('host','—')}")
        lines.append(f"MAC:     {dev.get('mac','—')}")
        lines.append(f"Vendor:  {dev.get('vendor','—')}")
        lines.append(f"Type:    {dev['type']}")
        lines.append(f"Ports:   {', '.join(dev['ports']) or '—'}")
        lines.append(f"Infected:{dev['infected']}")
        lines.append("")
        if dev['infect_reasons']:
            lines.append("INFECTION INDICATORS:")
            for r in dev['infect_reasons']:
                lines.append(f"  ⚠ {r}")
            lines.append("")
        if dev['risks']:
            lines.append("RISK DETAILS:")
            for lvl, name, desc, port in dev['risks']:
                lines.append(f"  [{lvl}] :{port}  {name}")
                lines.append(f"         {desc}")
            lines.append("")
        if dev.get('banner'):
            lines.append("BANNER:")
            lines.append(f"  {dev['banner'][:300]}")

        box.insert('1.0', '\n'.join(lines))
        box.configure(state='disabled')

    def _export(self):
        if not self._devices:
            self._log("No scan data to export.")
            return
        import tkinter.filedialog as fd
        path = fd.asksaveasfilename(
            defaultextension='.txt',
            initialfile='mint_scan_devices.txt',
            filetypes=[('Text','*.txt'),('JSON','*.json')])
        if not path:
            return
        if path.endswith('.json'):
            # Export as JSON
            safe = []
            for d in self._devices:
                safe.append({k: v for k, v in d.items()
                              if isinstance(v, (str, bool, list, int))})
            with open(path, 'w') as f:
                json.dump({'devices': safe, 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')}, f, indent=2)
        else:
            lines = [
                "MINT SCAN v7 — DEVICE SCAN REPORT",
                f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Devices found: {len(self._devices)}",
                "=" * 60, ""
            ]
            for d in self._devices:
                lines.append(f"{d['icon']} {d['ip']:16s} {d['type']:22s} "
                             f"{'⚠ INFECTED' if d['infected'] else ''}")
                lines.append(f"   Vendor: {d.get('vendor','—')}  MAC: {d.get('mac','—')}")
                if d['ports']:
                    lines.append(f"   Ports:  {', '.join(d['ports'])}")
                if d['infect_reasons']:
                    for r in d['infect_reasons']:
                        lines.append(f"   ⚠ {r}")
                lines.append("")
            with open(path, 'w') as f:
                f.write('\n'.join(lines))
        self._log(f"✓ Exported to {os.path.basename(path)}")

    # ── HELPERS ──────────────────────────────────────────────────

    def _log(self, msg):
        def _do():
            self.log_box.insert('end', msg + '\n')
            self.log_box.see('end')
        self.after(0, _do)

    def _set_prog(self, val, msg=''):
        def _do():
            self.prog_bar.set(val)
            if msg:
                self.prog_lbl.configure(text=msg)
        self.after(0, _do)

    def _clear(self, frame):
        def _do():
            for w in frame.winfo_children():
                w.destroy()
        self.after(0, _do)
