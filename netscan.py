"""Network Scanner — traffic analysis, vulnerabilities, suggestions"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, re, time, os
from installer import install_nmap
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from utils import run_cmd as run, copy_to_clipboard
from reports import prompt_save_report


class NetScanScreen(ctk.CTkFrame):
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
        self.app = app
        self._built = False
        self._capturing = False
        self._cap_proc = None

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="🔬  NETWORK SCANNER", font=('DejaVu Sans Mono',13,'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)

        btn_row = ctk.CTkFrame(hdr, fg_color='transparent')
        btn_row.pack(side='right', padx=12, pady=6)
        Btn(btn_row, "▶ SCAN",    command=self._full_scan,  width=90).pack(side='left', padx=3)
        Btn(btn_row, "📡 TRAFFIC", command=self._toggle_capture, variant='warning', width=110).pack(side='left', padx=3)
        Btn(btn_row, "🛡 VULNS",  command=self._vuln_scan,  variant='danger', width=90).pack(side='left', padx=3)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # Connected devices
        SectionHeader(body, '01', 'DEVICES ON NETWORK').pack(fill='x', padx=14, pady=(14,4))
        self.devices_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.devices_frame.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self.devices_frame, text="Tap SCAN to discover all devices on your network",
                     font=MONO_SM, text_color=C['mu']).pack(pady=8)

        # Live traffic
        SectionHeader(body, '02', 'LIVE TRAFFIC CAPTURE').pack(fill='x', padx=14, pady=(10,4))
        self.traffic_card = Card(body)
        self.traffic_card.pack(fill='x', padx=14, pady=(0,8))
        
        tf_hdr = ctk.CTkFrame(self.traffic_card, fg_color='transparent')
        tf_hdr.pack(fill='x', padx=8, pady=(4,0))

        self.cap_status = ctk.CTkLabel(tf_hdr, text="● IDLE — tap 📡 TRAFFIC to start",
                                        font=MONO_SM, text_color=C['mu'])
        self.cap_status.pack(side='left', padx=4)

        # Action buttons — right side
        self.analyze_btn  = Btn(tf_hdr, "📊 ANALYZE",  command=self._analyze_traffic,    variant='blue',  width=90)
        self.save_log_btn = Btn(tf_hdr, "💾 SAVE",      command=self._save_traffic_log,   variant='ghost', width=70)
        self.copy_log_btn = Btn(tf_hdr, "📋 COPY ALL",  command=self._copy_traffic_log,   variant='ghost', width=90)
        self.paste_btn    = Btn(tf_hdr, "📌 PASTE",     command=self._paste_to_log,        variant='ghost', width=70)
        self.clear_btn    = Btn(tf_hdr, "🗑 CLEAR",     command=self._clear_traffic_log,  variant='ghost', width=70)
        for b in [self.clear_btn, self.paste_btn, self.copy_log_btn, self.save_log_btn, self.analyze_btn]:
            b.pack(side='right', padx=2)

        # Search row
        find_row = ctk.CTkFrame(self.traffic_card, fg_color='transparent')
        find_row.pack(fill='x', padx=8, pady=(2,0))
        ctk.CTkLabel(find_row, text="Find:", font=('DejaVu Sans Mono',9), text_color=C['mu']).pack(side='left')
        self.find_entry = ctk.CTkEntry(find_row, width=180, font=('DejaVu Sans Mono',9),
                                        fg_color=C['bg'], border_color=C['br'],
                                        text_color=C['tx'], height=26,
                                        placeholder_text="search traffic...")
        self.find_entry.pack(side='left', padx=4)
        Btn(find_row, "↓ FIND", command=self._find_in_log, variant='ghost', width=70).pack(side='left', padx=2)
        Btn(find_row, "↑ PREV", command=lambda: self._find_in_log(reverse=True), variant='ghost', width=70).pack(side='left', padx=2)
        self.find_count_lbl = ctk.CTkLabel(find_row, text="", font=('DejaVu Sans Mono',8), text_color=C['mu'])
        self.find_count_lbl.pack(side='left', padx=6)

        # Traffic log — always stays 'normal' so user can select, copy, paste freely
        self.traffic_log = ctk.CTkTextbox(self.traffic_card, height=220,
                                           font=('DejaVu Sans Mono',10), fg_color=C['bg'],
                                           text_color=C['ac'], border_width=0,
                                           wrap='none')
        self.traffic_log.pack(fill='both', padx=8, pady=(4,8))
        self.traffic_log.configure(state='normal')
        # Bind Ctrl+A select all, Ctrl+C copy, Ctrl+V paste
        self.traffic_log.bind("<Control-a>", lambda e: self._select_all_log())
        self.traffic_log.bind("<Control-c>", lambda e: self._copy_selection())
        self.traffic_log.bind("<Control-v>", lambda e: self._paste_to_log())
        self._find_pos = '1.0'

        # Vulnerabilities
        SectionHeader(body, '03', 'VULNERABILITIES').pack(fill='x', padx=14, pady=(10,4))
        self.vuln_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.vuln_frame.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self.vuln_frame, text="Tap 🛡 VULNS to scan for network vulnerabilities",
                     font=MONO_SM, text_color=C['mu']).pack(pady=8)

        # Suggestions
        SectionHeader(body, '04', 'FIX SUGGESTIONS').pack(fill='x', padx=14, pady=(10,4))
        self.fix_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.fix_frame.pack(fill='x', padx=14, pady=(0,14))

        # Deep Packet Inspection
        SectionHeader(body, '05', 'DEEP PACKET INSPECTION').pack(fill='x', padx=14, pady=(10,4))
        dpi_card = Card(body)
        dpi_card.pack(fill='x', padx=14, pady=(0,14))
        
        ctk.CTkLabel(dpi_card, text="Analyze HTTP headers, TLS SNI, and DNS queries for hidden threats.",
                     font=MONO_SM, text_color=C['mu']).pack(pady=(12,4))
        
        self.dpi_res = ctk.CTkTextbox(dpi_card, height=100, font=('DejaVu Sans Mono',9), fg_color=C['bg'], text_color=C['tx'], border_width=0)
        self.dpi_res.pack(fill='x', padx=8, pady=8)
        self.dpi_res.insert('1.0', "Ready to scan.")
        self.dpi_res.configure(state='disabled')
        
        Btn(dpi_card, "🔎 RUN DEEP SCAN (10s)", command=self._dpi_scan, variant='ghost', width=200).pack(pady=(0,12))

    def _dpi_scan(self):
        self.dpi_res.configure(state='normal')
        self.dpi_res.delete('1.0', 'end')
        self.dpi_res.insert('end', "Initializing tshark...\n")
        self.dpi_res.configure(state='disabled')
        threading.Thread(target=self._do_dpi, daemon=True).start()

    def _do_dpi(self):
        # Check tshark
        if subprocess.run("which tshark", shell=True).returncode != 0:
            self._log_dpi("Error: 'tshark' not found.\nRun: sudo apt install tshark")
            return

        self._log_dpi("Capturing traffic (10s)...")
        # Capture HTTP Host, TLS SNI, DNS Query
        cmd = ("tshark -i any -a duration:10 -T fields "
               "-e http.host -e ssl.handshake.extensions_server_name -e dns.qry.name "
               "-Y 'http.request or ssl.handshake.type==1 or dns.flags.response==0'")
        
        out, err, rc = run(cmd, timeout=15)
        
        if not out:
            self._log_dpi("No interesting traffic captured.")
            return

        unique_hosts = set()
        for line in out.split('\n'):
            for part in line.split('\t'):
                if part.strip():
                    unique_hosts.add(part.strip())
        
        self._log_dpi(f"Captured {len(unique_hosts)} unique domains/hosts:\n")
        for h in sorted(unique_hosts):
            self._log_dpi(f"• {h}")

    def _log_dpi(self, msg):
        self.dpi_res.configure(state='normal')
        self.dpi_res.insert('end', msg + "\n")
        self.dpi_res.see('end')
        self.dpi_res.configure(state='disabled')

    def _full_scan(self):
        for w in self.devices_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.devices_frame, text="⟳ Scanning network...",
                     font=MONO_SM, text_color=C['ac']).pack(pady=8)
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        # Get local subnet
        ip_out, _, _ = run("ip route | grep -v default | head -1 | awk '{print $1}'")
        subnet = ip_out.strip() or '192.168.1.0/24'

        # Try nmap first, fallback to arp
        nmap_out, _, nmap_rc = run(f"nmap -sn {subnet} 2>/dev/null", timeout=30)

        devices = []
        if nmap_rc == 0 and 'Nmap scan' in nmap_out:
            # Parse nmap output
            current = {}
            for line in nmap_out.split('\n'):
                if 'Nmap scan report' in line:
                    if current: devices.append(current)
                    ip_m = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    host_m = re.search(r'for (.+?) \(', line)
                    current = {
                        'ip': ip_m.group(1) if ip_m else '—',
                        'host': host_m.group(1) if host_m else '',
                        'mac': '—', 'vendor': '—'
                    }
                elif 'MAC Address' in line:
                    mac_m = re.search(r'([0-9A-F:]{17})', line)
                    vendor_m = re.search(r'\((.+)\)', line)
                    if current:
                        current['mac'] = mac_m.group(1) if mac_m else '—'
                        current['vendor'] = vendor_m.group(1) if vendor_m else '—'
            if current: devices.append(current)
        else:
            # Fallback: arp-scan or arp
            arp_out, _, _ = run("arp -n 2>/dev/null | grep -v incomplete | tail -n +2")
            for line in arp_out.split('\n'):
                parts = line.split()
                if len(parts) >= 3:
                    devices.append({'ip': parts[0], 'mac': parts[2],
                                    'host': parts[1] if len(parts)>3 else '',
                                    'vendor': '—'})

        self._safe_after(0, self._render_devices, devices, subnet)

    def _render_devices(self, devices, subnet):
        for w in self.devices_frame.winfo_children(): w.destroy()

        if not devices:
            ctk.CTkLabel(self.devices_frame,
                         text="No devices found. Try: sudo apt install nmap",
                         font=MONO_SM, text_color=C['mu']).pack()
            return

        # Summary
        InfoGrid(self.devices_frame, [
            ('SUBNET',   subnet,         C['ac']),
            ('DEVICES',  len(devices),   C['ok']),
        ], columns=2).pack(fill='x', pady=(0,8))

        for dev in devices:
            row = ctk.CTkFrame(self.devices_frame, fg_color=C['sf'],
                                border_color=C['br'], border_width=1, corner_radius=8)
            row.pack(fill='x', pady=2)
            left = ctk.CTkFrame(row, fg_color='transparent')
            left.pack(side='left', padx=12, pady=8, fill='both', expand=True)
            ctk.CTkLabel(left, text=dev['ip'], font=('DejaVu Sans Mono',11,'bold'),
                         text_color=C['ac']).pack(anchor='w')
            meta = f"MAC: {dev['mac']}"
            if dev.get('vendor') and dev['vendor'] != '—':
                meta += f"  Vendor: {dev['vendor']}"
            if dev.get('host'):
                meta += f"  Host: {dev['host']}"
            ctk.CTkLabel(left, text=meta, font=('DejaVu Sans Mono',8),
                         text_color=C['mu']).pack(anchor='w')
            # Scan ports button
            Btn(row, "SCAN PORTS",
                command=lambda ip=dev['ip']: self._scan_device(ip),
                variant='ghost', width=100
                ).pack(side='right', padx=12)

    def _scan_device(self, ip):
        threading.Thread(target=self._do_device_scan, args=(ip,), daemon=True).start()

    def _do_device_scan(self, ip):
        self._safe_after(0, lambda: self._log_traffic(f"Scanning {ip}..."))
        out, _, _ = run(f"nmap -T4 --open -p 1-1000 {ip} 2>/dev/null", timeout=30)
        self._safe_after(0, lambda: self._log_traffic(f"Results for {ip}:\n{out[:600]}"))

    def _toggle_capture(self):
        if self._capturing:
            self._stop_capture()
        else:
            self._start_capture()

    def _start_capture(self):
        self._capturing = True
        self.cap_status.configure(text="● CAPTURING TRAFFIC", text_color=C['ok'])
        threading.Thread(target=self._do_capture, daemon=True).start()

    def _stop_capture(self):
        self._capturing = False
        if self._cap_proc:
            self._cap_proc.terminate()
            self._cap_proc = None
        self.cap_status.configure(text="● STOPPED", text_color=C['mu'])

    def _do_capture(self):
        # Use tcpdump if available, otherwise ss for active connections
        tcpdump, _, rc = run("which tcpdump")
        if rc == 0:
            cmd = "sudo tcpdump -l -n -q -c 100 2>/dev/null"
        else:
            cmd = "ss -tnp 2>/dev/null"

        try:
            self._cap_proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True)
            count = 0
            for line in self._cap_proc.stdout:
                if not self._capturing: break
                if count < 200:
                    self._safe_after(0, self._log_traffic, line.strip())
                    count += 1
        except Exception as e:
            self._safe_after(0, self._log_traffic, f"Capture error: {e}")
        finally:
            self._capturing = False
            self._safe_after(0, lambda: self.cap_status.configure(
                text="● CAPTURE STOPPED", text_color=C['mu']))

    def _log_traffic(self, msg):
        self.traffic_log.insert('end', msg + '\n')
        self.traffic_log.see('end')

    def _select_all_log(self):
        """Select all text in traffic log."""
        self.traffic_log.tag_add('sel', '1.0', 'end')
        return 'break'

    def _copy_selection(self):
        """Copy selected text or all text if nothing selected."""
        try:
            txt = self.traffic_log.get('sel.first', 'sel.last')
        except Exception:
            txt = self.traffic_log.get('1.0', 'end').strip()
        if txt:
            copy_to_clipboard(txt)
            self.cap_status.configure(text=f"● COPIED ({len(txt)} chars)", text_color=C['ok'])
        return 'break'

    def _copy_traffic_log(self):
        """Copy entire log to system clipboard."""
        txt = self.traffic_log.get('1.0', 'end').strip()
        if not txt:
            self.cap_status.configure(text="● LOG IS EMPTY", text_color=C['mu'])
            return
        copy_to_clipboard(txt)
        lines = len(txt.splitlines())
        self.cap_status.configure(text=f"● COPIED {lines} lines", text_color=C['ok'])

    def _paste_to_log(self):
        """Paste from system clipboard into traffic log."""
        try:
            # Try tkinter clipboard first
            root = self.winfo_toplevel()
            txt = root.clipboard_get()
        except Exception:
            try:
                import subprocess
                r = subprocess.run('xclip -selection clipboard -o',
                                   shell=True, capture_output=True, text=True, timeout=2)
                txt = r.stdout
            except Exception:
                txt = ''
        if txt:
            self.traffic_log.insert('end', txt)
            self.traffic_log.see('end')
            self.cap_status.configure(text=f"● PASTED ({len(txt)} chars)", text_color=C['ok'])

    def _clear_traffic_log(self):
        """Clear all traffic log content."""
        self.traffic_log.delete('1.0', 'end')
        self.cap_status.configure(text="● LOG CLEARED", text_color=C['mu'])
        self._find_pos = '1.0'

    def _find_in_log(self, reverse=False):
        """Search traffic log for a term, highlight and jump."""
        query = self.find_entry.get().strip()
        if not query:
            return
        content = self.traffic_log.get('1.0', 'end')
        lines   = content.splitlines()
        # Count matches
        total = sum(1 for l in lines if query.lower() in l.lower())
        if total == 0:
            self.find_count_lbl.configure(text=f"Not found", text_color=C['wn'])
            return
        # Remove old highlights
        self.traffic_log.tag_remove('found', '1.0', 'end')
        self.traffic_log.tag_config('found', background=C['am'], foreground=C['bg'])
        # Highlight all
        idx = '1.0'
        while True:
            idx = self.traffic_log.search(query, idx, nocase=True, stopindex='end')
            if not idx:
                break
            end_idx = f"{idx}+{len(query)}c"
            self.traffic_log.tag_add('found', idx, end_idx)
            idx = end_idx
        # Navigate
        search_from = self._find_pos
        direction   = '-backwards' if reverse else ''
        nxt = self.traffic_log.search(query, search_from, nocase=True,
                                       stopindex='1.0' if reverse else 'end',
                                       backwards=reverse)
        if not nxt:
            # Wrap around
            nxt = self.traffic_log.search(query, 'end' if reverse else '1.0',
                                           nocase=True,
                                           stopindex='1.0' if reverse else 'end',
                                           backwards=reverse)
        if nxt:
            self.traffic_log.see(nxt)
            self._find_pos = f"{nxt}+{len(query)}c" if not reverse else nxt
            self.find_count_lbl.configure(text=f"{total} match(es)", text_color=C['ok'])

    def _save_traffic_log(self):
        """Save traffic log with timestamp filename, supports .txt and .pcap (raw)."""
        txt = self.traffic_log.get('1.0', 'end').strip()
        if not txt:
            self.cap_status.configure(text="● NOTHING TO SAVE", text_color=C['mu'])
            return
        import tkinter.filedialog as fd
        ts = time.strftime('%Y%m%d_%H%M%S')
        path = fd.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"traffic_{ts}.txt",
            filetypes=[
                ("Text log",    "*.txt"),
                ("CSV export",  "*.csv"),
                ("All files",   "*.*"),
            ])
        if not path:
            return
        if path.endswith('.csv'):
            # Export as structured CSV
            lines = txt.splitlines()
            import csv, io
            buf = io.StringIO()
            w   = csv.writer(buf)
            w.writerow(['timestamp', 'direction', 'protocol', 'src', 'dst', 'info'])
            for l in lines:
                parts = l.split()
                if len(parts) >= 5:
                    w.writerow([parts[0] if parts else '',
                                '', '', '', '', l])
                else:
                    w.writerow(['', '', '', '', '', l])
            with open(path, 'w', newline='') as f:
                f.write(buf.getvalue())
        else:
            with open(path, 'w') as f:
                f.write(f"# Mint Scan v8 — Traffic Log\n")
                f.write(f"# Saved: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Lines: {len(txt.splitlines())}\n\n")
                f.write(txt)
        size = os.path.getsize(path)
        self.cap_status.configure(
            text=f"● SAVED: {os.path.basename(path)} ({size//1024}KB)",
            text_color=C['ok'])

    def _analyze_traffic(self):
        txt = self.traffic_log.get('1.0', 'end').strip()
        if not txt: return
        
        self.cap_status.configure(text="● ANALYZING...", text_color=C['ac'])
        
        # Simple analysis
        lines = txt.split('\n')
        total = len(lines)
        ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', txt)
        unique_ips = set(ips)
        
        http = sum(1 for l in lines if 'HTTP' in l.upper() or '.80 ' in l or '.443 ' in l)
        dns = sum(1 for l in lines if 'DNS' in l.upper() or '.53 ' in l)
        
        report_text = [
            f"Total Packets Captured: {total}",
            f"Unique IP Addresses: {len(unique_ips)}",
            f"HTTP/HTTPS Traffic: {http} packets",
            f"DNS Queries: {dns} packets",
            "",
            "PEER LIST:"
        ]
        for ip in sorted(unique_ips)[:15]:
            report_text.append(f" • {ip}")
            
        prompt_save_report(self, "Traffic Analysis", "Packet Capture Report", [
            ("SUMMARY", report_text, "INFO"),
            ("RAW DATA SNIPPET", lines[:50], "OK")
        ])
        self.cap_status.configure(text="● ANALYSIS COMPLETE", text_color=C['ok'])

    def _vuln_scan(self):
        for w in self.vuln_frame.winfo_children(): w.destroy()
        for w in self.fix_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.vuln_frame, text="⟳ Scanning for vulnerabilities...",
                     font=MONO_SM, text_color=C['ac']).pack(pady=8)
        threading.Thread(target=self._do_vuln, daemon=True).start()

    def _do_vuln(self):
        vulns = []
        fixes = []

        # 1. Check firewall
        ufw, _, _ = run("ufw status 2>/dev/null")
        if 'inactive' in ufw.lower():
            vulns.append(('HIGH', 'Firewall (UFW) is INACTIVE',
                          'All incoming connections are unfiltered'))
            fixes.append('Enable firewall: sudo ufw enable && sudo ufw default deny incoming && sudo ufw allow ssh')

        # 2. Check open ports
        ports_out, _, _ = run("ss -tlnp 2>/dev/null")
        dangerous = {'23': 'Telnet', '21': 'FTP', '4444': 'Metasploit', '5900': 'VNC'}
        for port, svc in dangerous.items():
            if f':{port} ' in ports_out or f':{port}\n' in ports_out:
                vulns.append(('HIGH', f'Dangerous port open: {port} ({svc})',
                              f'{svc} is running and exposed'))
                fixes.append(f'Close {svc}: sudo ufw deny {port}')

        # 3. SSH hardening
        ssh_cfg, _, _ = run("grep -E 'PermitRootLogin|PasswordAuthentication|Port' /etc/ssh/sshd_config 2>/dev/null")
        if 'PermitRootLogin yes' in ssh_cfg:
            vulns.append(('HIGH', 'SSH allows root login',
                          'Root login over SSH is a major security risk'))
            fixes.append('Edit /etc/ssh/sshd_config: set PermitRootLogin no, then: sudo systemctl restart sshd')

        if 'PasswordAuthentication yes' in ssh_cfg:
            vulns.append(('MED', 'SSH password authentication enabled',
                          'Brute force attacks possible'))
            fixes.append('Use SSH keys instead: PasswordAuthentication no in sshd_config')

        # 4. Check for unencrypted DNS
        dns_out, _, _ = run("resolvectl status 2>/dev/null | grep 'DNS Server'")
        if '8.8.8.8' in dns_out or '1.1.1.1' in dns_out:
            vulns.append(('MED', 'Using plain DNS (not encrypted)',
                          'DNS queries are visible to your ISP and anyone on the network'))
            fixes.append('Enable DNS-over-HTTPS: install systemd-resolved with DoH, or use NextDNS')

        # 5. Check for running services
        svc_out, _, _ = run("ss -tlnp 2>/dev/null | grep -v '127.0.0.1' | grep -v '::1'")
        exposed = re.findall(r':(\d+)\s', svc_out)
        if len(exposed) > 5:
            vulns.append(('MED', f'{len(exposed)} ports exposed on network interfaces',
                          'Reduce attack surface by closing unused services'))
            fixes.append('Audit services: systemctl list-units --type=service --state=running')

        # 6. Wireless encryption
        wifi_out, _, _ = run("nmcli -t -f ACTIVE,SECURITY dev wifi 2>/dev/null | grep yes")
        if 'WEP' in wifi_out:
            vulns.append(('HIGH', 'Connected to WEP-encrypted network',
                          'WEP is completely broken and provides no real security'))
            fixes.append('Connect to WPA2 or WPA3 network instead')

        if not vulns:
            vulns.append(('OK', '✓ No critical vulnerabilities found',
                          'Basic security checks passed'))

        self._safe_after(0, self._render_vulns, vulns, fixes)

    def _render_vulns(self, vulns, fixes):
        for w in self.vuln_frame.winfo_children(): w.destroy()
        for w in self.fix_frame.winfo_children(): w.destroy()

        high = sum(1 for v in vulns if v[0] == 'HIGH')
        if high:
            ResultBox(self.vuln_frame, 'warn',
                      f'⚠ {high} HIGH-RISK VULNERABILITY/VULNERABILITIES',
                      'Review and apply fixes below immediately.'
                      ).pack(fill='x', pady=(0,8))

        for lvl, title, desc in vulns:
            rtype = 'warn' if lvl=='HIGH' else 'med' if lvl=='MED' else 'ok'
            ResultBox(self.vuln_frame, rtype, title, desc).pack(fill='x', pady=3)

        if fixes:
            ctk.CTkLabel(self.fix_frame, text="RECOMMENDED FIXES:",
                         font=('DejaVu Sans Mono',10,'bold'), text_color=C['ok']
                         ).pack(anchor='w', pady=(4,6))
            for i, fix in enumerate(fixes, 1):
                fix_row = ctk.CTkFrame(self.fix_frame, fg_color=C['sf'],
                                        border_color=C['ok'], border_width=1,
                                        corner_radius=6)
                fix_row.pack(fill='x', pady=2)
                ctk.CTkLabel(fix_row, text=f"{i}.", font=('DejaVu Sans Mono',9,'bold'),
                             text_color=C['ok']).pack(side='left', padx=(10,4), pady=8)
                ctk.CTkLabel(fix_row, text=fix, font=('DejaVu Sans Mono',8),
                             text_color=C['mu'], wraplength=600, justify='left'
                             ).pack(side='left', pady=8, padx=4)
                # Copy button
                Btn(fix_row, "COPY",
                    command=lambda f=fix: self._copy(f),
                    variant='ghost', width=60
                    ).pack(side='right', padx=8)

        # Global export button
        Btn(self.fix_frame, "💾 EXPORT SECURITY REPORT",
            command=lambda: self._export_report(vulns, fixes),
            variant='success', width=260).pack(pady=10)

    def _export_report(self, vulns, fixes):
        ip_out, _, _ = run("ip route | grep default | awk '{print $3}'")
        gateway = ip_out.strip() or "Network"
        sections = [
            ("VULNERABILITIES FOUND", [f"[{v[0]}] {v[1]} - {v[2]}" for v in vulns], "WARN"),
            ("RECOMMENDED FIXES", fixes, "INFO")
        ]
        prompt_save_report(self, gateway, "Network Security Audit", sections)

    def _copy(self, text):
        copy_to_clipboard(text)
