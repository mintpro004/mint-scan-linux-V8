"""
Investigation Screen — deep dive into threats.
Source IP geolocation, WHOIS, reverse DNS, port scan, process tree,
attack pattern analysis, full timeline. For understanding threats only.
"""
import tkinter as tk
import customtkinter as ctk
import subprocess, threading, re, time, os, json
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from utils import run_cmd as _run
from reports import prompt_save_report


def _is_private_ip(ip):
    """Check if IP is RFC1918 private (not routable on internet)"""
    import ipaddress
    try:
        a = ipaddress.ip_address(ip)
        return a.is_private or a.is_loopback or a.is_link_local
    except Exception:
        return False


class InvestigateScreen(ctk.CTkFrame):
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
        self._investigating = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def investigate_ip(self, ip, reason=''):
        """Called from other screens to investigate a specific IP"""
        self.app._switch_tab('investigate')
        self.target_entry.delete(0, 'end')
        self.target_entry.insert(0, ip)
        if reason:
            self._log(f"Investigation requested: {reason}")
        self._start_investigation()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="🔬  THREAT INVESTIGATOR",
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        self.stop_btn = Btn(hdr, "⏹ STOP", command=self._stop,
                            variant='danger', width=80)
        self.stop_btn.pack(side='right', padx=4, pady=6)
        self.stop_btn.configure(state='disabled')

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── Target input ──────────────────────────────────────
        SectionHeader(body, '01', 'INVESTIGATION TARGET').pack(
            fill='x', padx=14, pady=(14,4))
        inp_card = Card(body)
        inp_card.pack(fill='x', padx=14, pady=(0,8))

        ctk.CTkLabel(inp_card,
            text="Enter an IP address, domain, process name, or port number to investigate:",
            font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,4))

        row = ctk.CTkFrame(inp_card, fg_color='transparent')
        row.pack(fill='x', padx=12, pady=(0,10))
        self.target_entry = ctk.CTkEntry(row,
            placeholder_text="e.g.  185.220.101.5  or  evil.ru  or  nc  or  :4444",
            font=('DejaVu Sans Mono',11), fg_color=C['bg'],
            border_color=C['ac'], text_color=C['ac'], height=40)
        self.target_entry.pack(side='left', fill='x', expand=True, padx=(0,8))
        self.target_entry.bind('<Return>', lambda e: self._start_investigation())
        Btn(row, "🔬 INVESTIGATE", command=self._start_investigation,
            variant='primary', width=150).pack(side='left')

        # Quick targets from live system
        ctk.CTkLabel(inp_card, text="Quick targets from live system:",
                     font=('DejaVu Sans Mono',8), text_color=C['mu']).pack(anchor='w', padx=12, pady=(0,4))
        q_row = ctk.CTkFrame(inp_card, fg_color='transparent')
        q_row.pack(fill='x', padx=12, pady=(0,10))
        Btn(q_row, "PUBLIC IP",    command=self._investigate_public_ip,  variant='ghost', width=110).pack(side='left', padx=3)
        Btn(q_row, "CONNECTIONS",  command=self._investigate_connections, variant='ghost', width=110).pack(side='left', padx=3)
        Btn(q_row, "OPEN PORTS",   command=self._investigate_ports,       variant='ghost', width=110).pack(side='left', padx=3)
        Btn(q_row, "PROCESSES",    command=self._investigate_processes,   variant='ghost', width=110).pack(side='left', padx=3)

        # ── Progress ──────────────────────────────────────────
        self.progress = ctk.CTkProgressBar(body, height=4,
                                            progress_color=C['ac'], fg_color=C['br'])
        self.progress.pack(fill='x', padx=14, pady=(0,4))
        self.progress.set(0)

        # ── Summary ───────────────────────────────────────────
        SectionHeader(body, '02', 'INVESTIGATION SUMMARY').pack(
            fill='x', padx=14, pady=(8,4))
        self.summary_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.summary_frame.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self.summary_frame,
                     text="Enter a target above and tap 🔬 INVESTIGATE",
                     font=MONO_SM, text_color=C['mu']).pack(pady=12)

        # ── Geolocation ───────────────────────────────────────
        SectionHeader(body, '03', 'LOCATION & IDENTITY').pack(
            fill='x', padx=14, pady=(8,4))
        self.geo_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.geo_frame.pack(fill='x', padx=14, pady=(0,8))

        # ── Network intelligence ──────────────────────────────
        SectionHeader(body, '04', 'NETWORK INTELLIGENCE').pack(
            fill='x', padx=14, pady=(8,4))
        self.net_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.net_frame.pack(fill='x', padx=14, pady=(0,8))

        # ── WHOIS / Registration ──────────────────────────────
        SectionHeader(body, '05', 'WHOIS / REGISTRATION').pack(
            fill='x', padx=14, pady=(8,4))
        self.whois_card = Card(body)
        self.whois_card.pack(fill='x', padx=14, pady=(0,8))
        self.whois_box = ctk.CTkTextbox(
            self.whois_card, height=140, font=('DejaVu Sans Mono',8),
            fg_color=C['bg'], text_color=C['tx'], border_width=0)
        self.whois_box.pack(fill='x', padx=8, pady=8)
        self.whois_box.configure(state='disabled')

        # ── Attack analysis ───────────────────────────────────
        SectionHeader(body, '06', 'THREAT ANALYSIS & ROOT CAUSE').pack(
            fill='x', padx=14, pady=(8,4))
        self.analysis_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.analysis_frame.pack(fill='x', padx=14, pady=(0,8))

        # ── Full log ──────────────────────────────────────────
        SectionHeader(body, '07', 'FULL INVESTIGATION LOG').pack(
            fill='x', padx=14, pady=(8,4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0,14))
        self.inv_log = ctk.CTkTextbox(
            log_card, height=200, font=('DejaVu Sans Mono',8),
            fg_color=C['bg'], text_color=C['ac'],
            border_width=0)
        self.inv_log.pack(fill='x', padx=8, pady=8)
        self.inv_log.configure(state='disabled')

    # ── Logging ───────────────────────────────────────────────

    def _log(self, msg):
        self.inv_log.configure(state='normal')
        self.inv_log.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.inv_log.see('end')
        self.inv_log.configure(state='disabled')

    def _prog(self, val):
        self._safe_after(0, lambda: self.progress.set(val))

    # ── Quick investigation launchers ─────────────────────────

    def _investigate_public_ip(self):
        def _do():
            ip, _, _ = _run("curl -s --max-time 5 https://api.ipify.org 2>/dev/null")
            if ip:
                self._safe_after(0, lambda: self.target_entry.delete(0, 'end'))
                self._safe_after(0, lambda: self.target_entry.insert(0, ip.strip()))
                self._safe_after(0, self._start_investigation)
        threading.Thread(target=_do, daemon=True).start()

    def _investigate_connections(self):
        self.target_entry.delete(0, 'end')
        self.target_entry.insert(0, 'connections')
        self._start_investigation()

    def _investigate_ports(self):
        self.target_entry.delete(0, 'end')
        self.target_entry.insert(0, 'ports')
        self._start_investigation()

    def _investigate_processes(self):
        self.target_entry.delete(0, 'end')
        self.target_entry.insert(0, 'processes')
        self._start_investigation()

    # ── Main investigation ────────────────────────────────────

    def _start_investigation(self):
        if self._investigating:
            return
        target = self.target_entry.get().strip()
        if not target:
            return

        self._investigating = True
        self.stop_btn.configure(state='normal')
        self.progress.set(0)

        # Clear results
        for frame in [self.summary_frame, self.geo_frame,
                      self.net_frame, self.analysis_frame]:
            for w in frame.winfo_children():
                w.destroy()
        self.inv_log.configure(state='normal')
        self.inv_log.delete('1.0', 'end')
        self.inv_log.configure(state='disabled')
        self.whois_box.configure(state='normal')
        self.whois_box.delete('1.0', 'end')
        self.whois_box.configure(state='disabled')

        ctk.CTkLabel(self.summary_frame, text=f"⟳ Investigating: {target}...",
                     font=MONO_SM, text_color=C['ac']).pack(pady=8)

        threading.Thread(target=self._do_investigate, args=(target,), daemon=True).start()

    def _stop(self):
        self._investigating = False
        self.stop_btn.configure(state='disabled')
        self._log("Investigation stopped by user.")

    def _do_investigate(self, target):
        self._log(f"Starting investigation: {target}")
        self._prog(0.05)

        # Detect target type
        ip_pattern = re.match(r'^(\d{1,3}\.){3}\d{1,3}$', target)
        domain_pattern = re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', target)
        port_pattern = re.match(r'^:?(\d+)$', target)

        findings = []
        geo_data = {}
        net_data = {}

        if target in ('connections', 'ports', 'processes'):
            self._investigate_system(target, findings)
        elif ip_pattern:
            ip = target
            self._log(f"Target type: IP address ({ip})")
            self._prog(0.1)
            geo_data = self._geolocate_ip(ip, findings)
            self._prog(0.35)
            net_data = self._network_intel(ip, findings)
            self._prog(0.6)
            self._do_whois(ip)
            self._prog(0.75)
            self._reverse_dns(ip, findings)
            self._prog(0.85)
            self._port_scan_target(ip, findings)
        elif domain_pattern:
            self._log(f"Target type: Domain ({target})")
            self._prog(0.1)
            # Resolve to IP first
            ip_out, _, _ = _run(f"dig +short {target} A 2>/dev/null | head -1")
            ip = ip_out.strip() if ip_out else ''
            if ip:
                self._log(f"Resolved to IP: {ip}")
                geo_data = self._geolocate_ip(ip, findings)
                self._prog(0.4)
                net_data = self._network_intel(ip, findings)
                self._prog(0.6)
                self._do_whois(target)
                self._prog(0.75)
                self._port_scan_target(ip, findings)
            else:
                self._log("Could not resolve domain to IP")
                findings.append({'level':'INFO','title':f'Domain: {target}',
                                  'desc':'Could not resolve — may be offline or blocked'})
        elif port_pattern:
            port = port_pattern.group(1)
            self._log(f"Target type: Port {port}")
            self._investigate_port(port, findings)
        else:
            # Treat as process name
            self._log(f"Target type: Process/keyword '{target}'")
            self._investigate_process(target, findings)

        self._prog(0.95)
        if not self._investigating:
            return

        analysis = self._build_analysis(target, findings, geo_data, net_data)
        self._prog(1.0)
        self._investigating = False

        self._safe_after(0, self._render_results, target, findings, geo_data, net_data, analysis)
        self._safe_after(0, lambda: self.stop_btn.configure(state='disabled'))

    # ── Geolocation ───────────────────────────────────────────

    def _geolocate_ip(self, ip, findings):
        self._log(f"Geolocating {ip}...")
        data = {}

        if _is_private_ip(ip):
            self._log(f"  {ip} is a private/local IP address")
            data = {'ip': ip, 'private': True, 'country': 'Local Network',
                    'org': 'Private', 'city': '—', 'isp': 'Internal'}
            return data

        # Try ipapi.co
        out, _, rc = _run(f"curl -s --max-time 6 https://ipapi.co/{ip}/json/ 2>/dev/null")
        if rc == 0 and out:
            try:
                j = json.loads(out)
                data = {
                    'ip':       j.get('ip', ip),
                    'country':  j.get('country_name', '—'),
                    'country_code': j.get('country_code', '—'),
                    'region':   j.get('region', '—'),
                    'city':     j.get('city', '—'),
                    'isp':      j.get('org', '—'),
                    'asn':      j.get('asn', '—'),
                    'timezone': j.get('timezone', '—'),
                    'lat':      j.get('latitude', '—'),
                    'lon':      j.get('longitude', '—'),
                    'private':  False,
                }
                self._log(f"  Location: {data['city']}, {data['country']}")
                self._log(f"  ISP/Org: {data['isp']}")
                self._log(f"  ASN: {data['asn']}")

                # Flag suspicious ISPs
                isp_lower = str(data['isp']).lower()
                suspicious_isps = [
                    'tor', 'vpn', 'proxy', 'anonymous', 'hosting',
                    'digitalocean', 'linode', 'vultr', 'ovh', 'hetzner',
                    'choopa', 'frantech', 'psychz', 'serverius'
                ]
                for sus in suspicious_isps:
                    if sus in isp_lower:
                        findings.append({
                            'level': 'HIGH',
                            'title': f'Suspicious hosting provider: {data["isp"]}',
                            'desc':  f'This IP is hosted by a provider commonly used for VPNs, '
                                     f'proxies, or anonymous services. Country: {data["country"]}',
                        })
                        break
            except Exception as e:
                self._log(f"  Geo parse error: {e}")
                data = {'ip': ip, 'country': '—', 'city': '—', 'isp': '—'}
        else:
            self._log("  Could not reach geolocation API (no internet?)")
            data = {'ip': ip, 'country': 'Unknown', 'city': '—', 'isp': '—'}

        return data

    # ── Network intelligence ──────────────────────────────────

    def _network_intel(self, ip, findings):
        self._log(f"Gathering network intelligence for {ip}...")
        data = {}

        # Reverse DNS
        rdns, _, _ = _run(f"dig +short -x {ip} 2>/dev/null | head -1")
        if not rdns:
            rdns, _, _ = _run(f"host {ip} 2>/dev/null | head -1")
        data['rdns'] = rdns.strip().rstrip('.') if rdns else '(no reverse DNS)'
        self._log(f"  Reverse DNS: {data['rdns']}")

        # Ping reachability
        _, _, rc = _run(f"ping -c 1 -W 2 {ip} 2>/dev/null")
        data['reachable'] = rc == 0
        self._log(f"  Reachable: {'Yes' if data['reachable'] else 'No (filtered/offline)'}")

        # Traceroute (fast, 5 hops max)
        trace, _, _ = _run(f"traceroute -m 5 -w 1 {ip} 2>/dev/null | tail -5")
        data['traceroute'] = trace
        if trace:
            self._log(f"  Traceroute (last 5 hops):\n{trace}")

        return data

    def _reverse_dns(self, ip, findings):
        rdns, _, _ = _run(f"dig +short -x {ip} 2>/dev/null | head -3")
        if rdns:
            self._log(f"  PTR records: {rdns}")
            # Check for suspicious hostnames
            rdns_lower = rdns.lower()
            if any(x in rdns_lower for x in ['tor', 'exit', 'relay', 'vpn', 'proxy']):
                findings.append({
                    'level': 'HIGH',
                    'title': f'Reverse DNS suggests TOR/VPN exit node',
                    'desc':  f'PTR record: {rdns.strip()} — this IP appears to be an anonymisation node',
                })

    def _do_whois(self, target):
        self._log(f"Running WHOIS for {target}...")
        whois_out, _, rc = _run(f"whois {target} 2>/dev/null", timeout=12)
        if rc == 0 and whois_out:
            # Filter to most useful lines
            useful = []
            keys = ['netname','country','orgname','org-name','organisation',
                    'descr','abuse','notify','route','cidr','netrange',
                    'originas','inetnum','created','last-modified',
                    'registrar','creation date','updated date']
            for line in whois_out.split('\n'):
                ll = line.lower()
                if any(k in ll for k in keys) and ':' in line:
                    useful.append(line.strip())
            output = '\n'.join(useful[:30]) if useful else whois_out[:800]
        else:
            output = 'whois not available — install with: sudo apt install whois'

        self._safe_after(0, self._show_whois, output)

    def _show_whois(self, text):
        self.whois_box.configure(state='normal')
        self.whois_box.delete('1.0', 'end')
        self.whois_box.insert('1.0', text)
        self.whois_box.configure(state='disabled')

    def _port_scan_target(self, ip, findings):
        if _is_private_ip(ip):
            return
        self._log(f"Quick port scan of {ip} (top ports)...")
        nmap, _, rc = _run(f"nmap -T4 --open -F {ip} 2>/dev/null", timeout=30)
        if rc == 0 and nmap:
            open_ports = re.findall(r'(\d+)/tcp\s+open\s+(\S+)', nmap)
            if open_ports:
                self._log(f"  Open ports: {', '.join(f'{p}/{s}' for p,s in open_ports[:10])}")
                dangerous = {'23':'Telnet','4444':'Metasploit','1337':'Hacker',
                             '3389':'RDP','5900':'VNC','6667':'IRC'}
                for port, svc in open_ports:
                    if port in dangerous:
                        findings.append({
                            'level': 'HIGH',
                            'title': f'Dangerous service on remote host: port {port} ({svc})',
                            'desc':  f'Port {port} ({dangerous[port]}) is open on {ip} — '
                                     f'this service is commonly exploited',
                        })
            else:
                self._log("  No open ports found (may be firewalled)")
        else:
            self._log("  Port scan unavailable (install nmap: sudo apt install nmap)")

    # ── System investigation modes ────────────────────────────

    def _investigate_system(self, mode, findings):
        if mode == 'connections':
            self._log("Analysing all active network connections...")
            out, _, _ = _run("ss -tnp state established 2>/dev/null")
            self._log(f"Active connections:\n{out}")
            # Extract external IPs
            ips = re.findall(r'(\d+\.\d+\.\d+\.\d+):\d+\s+users', out)
            external = [ip for ip in set(ips) if not _is_private_ip(ip)]
            if external:
                self._log(f"External IPs to investigate: {', '.join(external[:5])}")
                for ip in external[:3]:
                    findings.append({
                        'level': 'INFO',
                        'title': f'Active connection to external IP: {ip}',
                        'desc':  f'Tap the field above and enter {ip} to investigate this IP',
                    })
            self._safe_after(0, self._show_whois,
                       f"Active connections:\n{out}\n\nExternal IPs: {', '.join(external)}")

        elif mode == 'ports':
            self._log("Analysing all open ports...")
            out, _, _ = _run("ss -tlnp 2>/dev/null")
            self._log(f"Open ports:\n{out}")
            dangerous = {'23':'Telnet','4444':'Metasploit','1337':'Hacker','5555':'ADB-Net'}
            ports = re.findall(r':(\d+)\s', out)
            for port in set(ports):
                if port in dangerous:
                    findings.append({
                        'level': 'HIGH',
                        'title': f'Dangerous port open locally: :{port} ({dangerous[port]})',
                        'desc':  f'This port is associated with {dangerous[port]}. Close it immediately.',
                    })
            self._safe_after(0, self._show_whois, f"Open ports:\n{out}")

        elif mode == 'processes':
            self._log("Analysing running processes for threats...")
            out, _, _ = _run("ps aux --sort=-%cpu 2>/dev/null | head -20")
            self._log(f"Top processes:\n{out}")
            suspicious = ['nc ','netcat','ncat','socat','msfconsole','hydra',
                          'john ','hashcat','mimikatz','empire','cobaltstrike']
            for name in suspicious:
                if name.lower() in out.lower():
                    pid_line = [l for l in out.split('\n') if name.lower() in l.lower()]
                    findings.append({
                        'level': 'HIGH',
                        'title': f'Suspicious process: {name.strip()}',
                        'desc':  f'Known hacking tool is running: {pid_line[0][:100] if pid_line else ""}',
                    })
            self._safe_after(0, self._show_whois, f"Running processes:\n{out}")

    def _investigate_port(self, port, findings):
        self._log(f"Investigating port {port}...")
        # Who is listening on this port?
        out, _, _ = _run(f"ss -tlnp 2>/dev/null | grep :{port}")
        if out:
            self._log(f"  Process on :{port}: {out}")
            findings.append({
                'level': 'INFO',
                'title': f'Port :{port} is open locally',
                'desc':  out[:200],
            })
        # What connections exist on this port?
        conns, _, _ = _run(f"ss -tnp 2>/dev/null | grep :{port}")
        if conns:
            self._log(f"  Active connections on :{port}:\n{conns}")
        self._safe_after(0, self._show_whois,
                   f"Port :{port} analysis:\n\nListening:\n{out}\n\nConnections:\n{conns}")

    def _investigate_process(self, name, findings):
        self._log(f"Investigating process: {name}")
        out, _, _ = _run(f"ps aux | grep -i {name} | grep -v grep")
        if out:
            self._log(f"  Process found:\n{out}")
            # Get open files/connections for this process
            pid_match = re.search(r'\S+\s+(\d+)', out)
            if pid_match:
                pid = pid_match.group(1)
                lsof, _, _ = _run(f"lsof -p {pid} -i 2>/dev/null | head -10")
                if lsof:
                    self._log(f"  Network connections:\n{lsof}")
                findings.append({
                    'level': 'INFO',
                    'title': f'Process found: {name} (PID {pid})',
                    'desc':  out[:200],
                })
        else:
            self._log(f"  No process named '{name}' found")
        self._safe_after(0, self._show_whois, f"Process analysis: {name}\n\n{out}")

    # ── Threat analysis ───────────────────────────────────────

    def _build_analysis(self, target, findings, geo_data, net_data):
        analysis = []

        high = [f for f in findings if f.get('level') == 'HIGH']
        med  = [f for f in findings if f.get('level') in ('MED','MEDIUM')]

        # Overall risk score
        score = len(high) * 30 + len(med) * 10
        if score >= 60:
            risk_level = 'HIGH'
            risk_color = C['wn']
        elif score >= 20:
            risk_level = 'MEDIUM'
            risk_color = C['am']
        else:
            risk_level = 'LOW'
            risk_color = C['ok']

        analysis.append({
            'type': 'summary',
            'risk': risk_level,
            'color': risk_color,
            'high': len(high),
            'med': len(med),
            'score': min(score, 100),
        })

        # Root cause assessment
        if geo_data:
            country = geo_data.get('country','Unknown')
            isp = geo_data.get('isp', '')
            if geo_data.get('private'):
                analysis.append({
                    'type': 'root_cause',
                    'text': 'This is a PRIVATE/LOCAL IP address — traffic from within your own network or device.',
                    'level': 'INFO',
                })
            else:
                analysis.append({
                    'type': 'root_cause',
                    'text': f'Traffic originates from {country} via {isp}. '
                            f'ISP/hosting provider controls this IP block.',
                    'level': 'INFO' if risk_level == 'LOW' else risk_level,
                })

        # Recommendations
        recs = []
        if high:
            recs.append("Block this IP immediately using UFW: sudo ufw deny from <ip>")
            recs.append("Check firewall rules in the FIREWALL tab")
            recs.append("Run a malware scan in the MALWARE tab")
        if any('tor' in str(f).lower() or 'vpn' in str(f).lower() for f in findings):
            recs.append("This IP uses anonymisation — origin is intentionally hidden")
            recs.append("Consider blocking the entire ASN/ISP subnet")
        if net_data.get('reachable') and not _is_private_ip(target) if re.match(r'^(\d+\.){3}\d+$', target) else False:
            recs.append(f"Run full port scan: nmap -sV -A {target}")

        if recs:
            analysis.append({'type': 'recommendations', 'items': recs})

        return analysis

    # ── Render results ────────────────────────────────────────

    def _render_results(self, target, findings, geo_data, net_data, analysis):
        # Summary
        for w in self.summary_frame.winfo_children():
            w.destroy()

        an = next((a for a in analysis if a['type'] == 'summary'), None)
        if an:
            risk_col = an['color']
            header = ResultBox(
                self.summary_frame,
                rtype='warn' if an['risk']=='HIGH' else 'med' if an['risk']=='MEDIUM' else 'ok',
                title=f"RISK LEVEL: {an['risk']}  —  Target: {target}",
                body=f"High-risk findings: {an['high']}  |  Medium: {an['med']}"
            )
            header.pack(fill='x', pady=(0,6))

            # Action buttons on the summary
            act_row = ctk.CTkFrame(self.summary_frame, fg_color='transparent')
            act_row.pack(fill='x', pady=(0,8))
            if re.match(r'^(\d+\.){3}\d+$', target):
                Btn(act_row, f"🔥 BLOCK {target}",
                    command=lambda ip=target: self._block_ip(ip),
                    variant='danger', width=160).pack(side='left', padx=4)
                Btn(act_row, "📋 COPY IP",
                    command=lambda ip=target: self._copy(ip),
                    variant='ghost', width=100).pack(side='left', padx=4)

            Btn(act_row, "💾 EXPORT REPORT",
                command=lambda: self._export_report(target, findings, geo_data, net_data, analysis),
                variant='success', width=160).pack(side='left', padx=4)

            Btn(act_row, "⚙ OPEN FIREWALL",
                command=lambda: self.app._switch_tab('firewall'),
                variant='blue', width=140).pack(side='left', padx=4)

    def _export_report(self, target, findings, geo, net, analysis):
        sections = [
            ("INVESTIGATION SUMMARY", f"Target: {target}\nRisk: {next((a['risk'] for a in analysis if a['type']=='summary'), 'Unknown')}", "INFO"),
            ("FINDINGS", findings, "WARN"),
        ]
        if geo: sections.append(("GEOLOCATION", geo, "INFO"))
        if net: sections.append(("NETWORK INTEL", net, "INFO"))
        
        recs = next((a['items'] for a in analysis if a['type']=='recommendations'), [])
        if recs: sections.append(("RECOMMENDATIONS", recs, "INFO"))
        
        prompt_save_report(self, target, "Threat Investigation", sections)

    # ── Geolocation ───────────────────────────────────────────

        for w in self.geo_frame.winfo_children():
            w.destroy()
        if geo_data:
            if geo_data.get('private'):
                ResultBox(self.geo_frame, 'info',
                          '🏠 Private / Local IP Address',
                          'This IP is within your local network (RFC1918). '
                          'Not routable on the internet.'
                          ).pack(fill='x')
            else:
                items = [
                    ('IP ADDRESS',  geo_data.get('ip','—'),      C['ac']),
                    ('COUNTRY',     geo_data.get('country','—'),  C['tx']),
                    ('CITY',        geo_data.get('city','—'),     C['tx']),
                    ('REGION',      geo_data.get('region','—'),   C['mu']),
                    ('ISP / ORG',   geo_data.get('isp','—'),      C['am']),
                    ('ASN',         geo_data.get('asn','—'),      C['mu']),
                    ('TIMEZONE',    geo_data.get('timezone','—'), C['mu']),
                    ('COORDINATES', f"{geo_data.get('lat','—')}, {geo_data.get('lon','—')}", C['mu']),
                ]
                InfoGrid(self.geo_frame, items, columns=4).pack(fill='x')
                if net_data:
                    ctk.CTkLabel(
                        self.geo_frame,
                        text=f"Reverse DNS: {net_data.get('rdns','—')}  |  "
                             f"Reachable: {'Yes' if net_data.get('reachable') else 'No'}",
                        font=('DejaVu Sans Mono',8), text_color=C['mu']
                    ).pack(anchor='w', pady=(4,0))

        # Network intel
        for w in self.net_frame.winfo_children():
            w.destroy()
        if net_data.get('traceroute'):
            trace_card = Card(self.net_frame)
            trace_card.pack(fill='x', pady=(0,4))
            ctk.CTkLabel(trace_card, text="TRACEROUTE (last 5 hops):",
                         font=('DejaVu Sans Mono',8,'bold'), text_color=C['ac']
                         ).pack(anchor='w', padx=10, pady=(8,2))
            ctk.CTkLabel(trace_card, text=net_data['traceroute'],
                         font=('DejaVu Sans Mono',8), text_color=C['mu'],
                         justify='left', wraplength=700
                         ).pack(anchor='w', padx=10, pady=(0,8))

        # Analysis & recommendations
        for w in self.analysis_frame.winfo_children():
            w.destroy()

        # Root cause
        for item in analysis:
            if item['type'] == 'root_cause':
                rc_level = item.get('level','INFO')
                rtype = 'warn' if rc_level=='HIGH' else 'med' if rc_level=='MEDIUM' else 'info'
                ResultBox(self.analysis_frame, rtype,
                          'ROOT CAUSE ASSESSMENT', item['text']
                          ).pack(fill='x', pady=3)

        # All findings
        for f in findings:
            lvl = f.get('level','INFO')
            rtype = 'warn' if lvl=='HIGH' else 'med' if lvl in ('MED','MEDIUM') else 'info'
            ResultBox(self.analysis_frame, rtype,
                      f['title'], f.get('desc','')
                      ).pack(fill='x', pady=3)

        # Recommendations
        for item in analysis:
            if item['type'] == 'recommendations':
                rec_card = Card(self.analysis_frame, accent=C['bl'])
                rec_card.pack(fill='x', pady=(6,3))
                ctk.CTkLabel(rec_card, text="RECOMMENDED ACTIONS:",
                             font=('DejaVu Sans Mono',9,'bold'), text_color=C['bl']
                             ).pack(anchor='w', padx=10, pady=(8,4))
                for i, rec in enumerate(item['items'], 1):
                    ctk.CTkLabel(rec_card, text=f"{i}. {rec}",
                                 font=('DejaVu Sans Mono',8), text_color=C['tx'],
                                 justify='left', wraplength=680
                                 ).pack(anchor='w', padx=14, pady=2)
                ctk.CTkLabel(rec_card, text="", height=6).pack()

        if not findings and not geo_data:
            ResultBox(self.analysis_frame, 'ok',
                      '✓ No threats detected for this target',
                      'Investigation complete — no indicators of compromise found.'
                      ).pack(fill='x')

        self._log("✓ Investigation complete.")

    # ── Actions ───────────────────────────────────────────────

    def _block_ip(self, ip):
        self._log(f"Blocking {ip} with UFW...")
        def _do():
            out, err, rc = _run(f"sudo ufw deny from {ip} 2>/dev/null")
            msg = f"✓ Blocked {ip}" if rc == 0 else f"✗ Failed: {err[:60]}"
            self._safe_after(0, self._log, msg)
        threading.Thread(target=_do, daemon=True).start()

    def _copy(self, text):
        try:
            subprocess.run(f"echo '{text}' | xclip -selection clipboard",
                           shell=True, timeout=3)
            self._log(f"Copied: {text}")
        except Exception:
            self._log(f"Copy: {text}")
