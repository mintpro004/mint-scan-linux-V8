"""Port Scanner Screen — real local + remote port scanning"""
from widgets import C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader, ResultBox, Btn, PortBar
import tkinter as tk
import customtkinter as ctk
import threading, socket, re
from utils import run_cmd, get_open_ports, get_active_connections


WELL_KNOWN = {
    '20': 'FTP-Data', '21': 'FTP', '22': 'SSH', '23': 'Telnet',
    '25': 'SMTP', '53': 'DNS', '80': 'HTTP', '110': 'POP3',
    '143': 'IMAP', '443': 'HTTPS', '445': 'SMB', '993': 'IMAPS',
    '3306': 'MySQL', '3389': 'RDP', '5432': 'PostgreSQL',
    '5900': 'VNC', '6379': 'Redis', '8080': 'HTTP-Alt',
    '8443': 'HTTPS-Alt', '27017': 'MongoDB',
    '4444': 'Metasploit⚠', '1337': 'Suspicious⚠',
}

KNOWN_BAD_PORTS = ['4444', '1337', '31337', '666', '6667']
RISKY_PORTS = ['21', '23', '3389', '5900', '161']


class PortsScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False
        self._scanning = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._load_local, daemon=True).start()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="🔍  PORT SCANNER", font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # Local open ports
        SectionHeader(body, '01', 'LOCAL OPEN PORTS (REAL)').pack(fill='x', padx=14, pady=(14,4))
        Btn(body, "↺  REFRESH LOCAL", command=lambda: threading.Thread(
            target=self._load_local, daemon=True).start(),
            variant='ghost', width=160).pack(anchor='w', padx=14, pady=(0,6))
        self.local_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.local_frame.pack(fill='x', padx=14, pady=(0,8))

        # Remote scanner
        SectionHeader(body, '02', 'REMOTE HOST SCANNER').pack(fill='x', padx=14, pady=(10,4))
        scan_card = Card(body)
        scan_card.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(scan_card, text="Scan any IP or hostname for open ports:",
                     font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,4))
        inp_row = ctk.CTkFrame(scan_card, fg_color='transparent')
        inp_row.pack(fill='x', padx=12)
        self.host_entry = ctk.CTkEntry(inp_row, placeholder_text="192.168.1.1 or hostname",
                                        font=MONO_SM, fg_color=C['bg'],
                                        border_color=C['br'], text_color=C['tx'], height=36)
        self.host_entry.pack(side='left', fill='x', expand=True, padx=(0,8))
        self.port_range = ctk.CTkEntry(inp_row, placeholder_text="1-1000",
                                        font=MONO_SM, fg_color=C['bg'],
                                        border_color=C['br'], text_color=C['tx'],
                                        height=36, width=100)
        self.port_range.pack(side='left', padx=(0,8))
        self.scan_btn = Btn(inp_row, "SCAN", command=self._remote_scan, width=80)
        self.scan_btn.pack(side='left')

        self.scan_prog = ctk.CTkProgressBar(scan_card, height=4,
                                             progress_color=C['ac'], fg_color=C['br'])
        self.scan_prog.pack(fill='x', padx=12, pady=6)
        self.scan_prog.set(0)
        self.scan_prog_lbl = ctk.CTkLabel(scan_card, text="",
                                           font=('Courier',8), text_color=C['mu'])
        self.scan_prog_lbl.pack(anchor='w', padx=12, pady=(0,4))

        self.remote_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.remote_frame.pack(fill='x', padx=14, pady=(0,8))

        # Active connections
        SectionHeader(body, '03', 'ACTIVE CONNECTIONS').pack(fill='x', padx=14, pady=(10,4))
        self.conns_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.conns_frame.pack(fill='x', padx=14, pady=(0,14))

    def _load_local(self):
        ports = get_open_ports()
        conns = get_active_connections()
        self.after(0, self._render_local, ports, conns)

    def _render_local(self, ports, conns):
        if not hasattr(self, "local_frame"): return
        if not hasattr(self,"local_frame"): return
        for w in self.local_frame.winfo_children(): w.destroy()
        if not ports:
            ctk.CTkLabel(self.local_frame, text="No open ports detected (requires ss/netstat)",
                         font=MONO_SM, text_color=C['mu']).pack()
            return
        for p in ports[:30]:
            PortBar(self.local_frame, p['port'], p['proto'],
                    p['state'], p['process']).pack(fill='x', pady=3)

        if not hasattr(self, "conns_frame"): return
        if not hasattr(self,"conns_frame"): return
        for w in self.conns_frame.winfo_children(): w.destroy()
        if conns:
            for c in conns[:20]:
                row = ctk.CTkFrame(self.conns_frame, fg_color=C['sf'],
                                    border_color=C['br'], border_width=1, corner_radius=6)
                row.pack(fill='x', pady=2)
                ctk.CTkLabel(row, text=c['local'], font=MONO_SM,
                             text_color=C['ac']).pack(side='left', padx=8, pady=6)
                ctk.CTkLabel(row, text='→', font=MONO_SM,
                             text_color=C['mu']).pack(side='left')
                ctk.CTkLabel(row, text=c['remote'], font=MONO_SM,
                             text_color=C['am']).pack(side='left', padx=8)
                ctk.CTkLabel(row, text=c['process'], font=('Courier',8),
                             text_color=C['mu']).pack(side='right', padx=8)

    def _remote_scan(self):
        if self._scanning: return
        host = self.host_entry.get().strip()
        if not host: return
        rng  = self.port_range.get().strip() or '1-1000'
        try:
            if '-' in rng:
                start, end = map(int, rng.split('-'))
            else:
                start = end = int(rng)
        except ValueError:
            start, end = 1, 1000

        self._scanning = True
        self.scan_btn.configure(state='disabled', text='SCANNING')
        for w in self.remote_frame.winfo_children(): w.destroy()
        threading.Thread(
            target=self._do_remote_scan, args=(host, start, end), daemon=True).start()

    def _do_remote_scan(self, host, start, end):
        open_ports = []
        total = end - start + 1

        # Try nmap first (much faster)
        nmap_out, _, nmap_rc = run_cmd(
            f"nmap -T4 --open -p {start}-{end} {host} 2>/dev/null", timeout=30)
        if nmap_rc == 0 and 'open' in nmap_out:
            for line in nmap_out.split('\n'):
                m = re.match(r'(\d+)/tcp\s+open\s+(\S+)', line)
                if m:
                    open_ports.append({'port': m.group(1), 'service': m.group(2)})
            self.after(0, self._render_remote, host, open_ports, 'nmap')
            self._cleanup_scan()
            return

        # Fallback: Python socket scan
        for i, port in enumerate(range(start, end+1)):
            if not self._scanning: break
            prog = i / total
            self.after(0, lambda p=prog, port=port: (
                self.scan_prog.set(p),
                self.scan_prog_lbl.configure(
                    text=f"Scanning port {port}... ({i}/{total})")
            ))
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                if s.connect_ex((host, port)) == 0:
                    service = WELL_KNOWN.get(str(port), 'Unknown')
                    open_ports.append({'port': str(port), 'service': service})
                s.close()
            except Exception:
                pass

        self.after(0, self._render_remote, host, open_ports, 'socket')
        self._cleanup_scan()

    def _cleanup_scan(self):
        self._scanning = False
        self.after(0, lambda: (
            self.scan_btn.configure(state='normal', text='SCAN'),
            self.scan_prog.set(1),
            self.scan_prog_lbl.configure(text='✓ Scan complete')
        ))

    def _render_remote(self, host, ports, method):
        for w in self.remote_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.remote_frame,
                     text=f"Results for {host} (via {method}) — {len(ports)} open ports",
                     font=('Courier', 10, 'bold'), text_color=C['ac']
                     ).pack(anchor='w', pady=(0,6))
        if not ports:
            ResultBox(self.remote_frame, 'ok', '✓ No open ports found',
                      'Host appears to have all scanned ports closed.').pack(fill='x')
            return
        for p in ports:
            port  = p['port']
            svc   = p.get('service', WELL_KNOWN.get(port, 'Unknown'))
            col   = C['wn'] if port in KNOWN_BAD_PORTS else \
                    C['am'] if port in RISKY_PORTS else C['ac']
            row = ctk.CTkFrame(self.remote_frame, fg_color=C['sf'],
                                border_color=col, border_width=1, corner_radius=6)
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text=f":{port}", font=('Courier',13,'bold'),
                         text_color=col).pack(side='left', padx=12, pady=8)
            ctk.CTkLabel(row, text=svc, font=MONO_SM,
                         text_color=C['tx']).pack(side='left', padx=4)
            if port in KNOWN_BAD_PORTS:
                ctk.CTkLabel(row, text="⚠ CRITICAL", font=('Courier',8),
                             text_color=C['wn']).pack(side='right', padx=12)
