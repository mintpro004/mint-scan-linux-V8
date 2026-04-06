"""
Toolbox Screen — shows installed/missing tools, launches them, no redundant installs.
"""
import tkinter as tk
import customtkinter as ctk
import subprocess, threading, shutil, time, os
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from installer import InstallerPopup
from utils import run_cmd as _run


# ── Tool definitions ──────────────────────────────────────────────
TOOLS = [
    {
        'id':      'nmap',
        'name':    'nmap',
        'label':   '🔍 nmap',
        'desc':    'Network scanner — discovers devices, open ports, services',
        'check':   'nmap',          # binary to check with shutil.which
        'version': 'nmap --version 2>/dev/null | head -1',
        'install': ['sudo apt-get install -y nmap'],
        'launch':  None,            # CLI only
        'docs':    'sudo nmap -sV <ip>',
    },
    {
        'id':      'adb',
        'name':    'adb',
        'label':   '📱 adb',
        'desc':    'Android Debug Bridge — phone sync, APK install',
        'check':   'adb',
        'version': 'adb version 2>/dev/null | head -1',
        'install': ['sudo apt-get install -y adb'],
        'launch':  None,
        'docs':    'adb devices',
    },
    {
        'id':      'tcpdump',
        'name':    'tcpdump',
        'label':   '📡 tcpdump',
        'desc':    'Network traffic capture and analysis',
        'check':   'tcpdump',
        'version': 'tcpdump --version 2>/dev/null | head -1',
        'install': ['sudo apt-get install -y tcpdump'],
        'launch':  None,
        'docs':    'sudo tcpdump -i any -n',
    },
    {
        'id':      'clamav',
        'name':    'clamscan',
        'label':   '🦠 ClamAV',
        'desc':    'Antivirus — scans for malware and viruses',
        'check':   'clamscan',
        'version': 'clamscan --version 2>/dev/null | head -1',
        'install': [
            'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y clamav clamav-daemon',
            'sudo systemctl stop clamav-freshclam 2>/dev/null || true',
            'sudo freshclam || echo "freshclam: busy or offline, skipping for now"',
            'sudo systemctl start clamav-freshclam 2>/dev/null || true',
        ],
        'launch':  None,
        'docs':    'clamscan -r ~/  (home scan)',
    },
    {
        'id':      'rkhunter',
        'name':    'rkhunter',
        'label':   '🔒 rkhunter',
        'desc':    'Rootkit hunter — detects hidden malware, backdoors',
        'check':   'rkhunter',
        'version': 'rkhunter --version 2>/dev/null | head -1',
        'install': ['sudo apt-get install -y rkhunter'],
        'launch':  None,
        'docs':    'sudo rkhunter --check',
    },
    {
        'id':      'kdeconnect',
        'name':    'kdeconnect-cli',
        'label':   '📲 KDE Connect',
        'desc':    'Wireless phone bridge — calls, SMS, notifications',
        'check':   'kdeconnect-cli',
        'version': 'kdeconnect-cli --version 2>/dev/null | head -1',
        'install': ['sudo apt-get install -y kdeconnect'],
        'launch':  'kdeconnect-app',
        'docs':    'kdeconnect-cli -l  (list devices)',
    },
    {
        'id':      'wireshark',
        'name':    'wireshark',
        'label':   '🦈 Wireshark',
        'desc':    'Deep packet inspection and network analysis GUI',
        'check':   'wireshark',
        'version': 'wireshark --version 2>/dev/null | head -1',
        'install': ['sudo apt-get install -y wireshark'],
        'launch':  'wireshark',
        'docs':    'wireshark  (GUI)',
    },
    {
        'id':      'netstat',
        'name':    'netstat',
        'label':   '🌐 netstat',
        'desc':    'Network connections and routing table viewer',
        'check':   'netstat',
        'version': 'netstat --version 2>/dev/null | head -1',
        'install': ['sudo apt-get install -y net-tools'],
        'launch':  None,
        'docs':    'netstat -tulpn  (listening ports)',
    },
    {
        'id':      'ufw',
        'name':    'ufw',
        'label':   '🔥 UFW Firewall',
        'desc':    'Uncomplicated Firewall — manage incoming/outgoing rules',
        'check':   'ufw',
        'version': 'ufw version 2>/dev/null | head -1',
        'install': [
            'echo "iptables-persistent iptables-persistent/autosave_v4 boolean true" | sudo debconf-set-selections',
            'echo "iptables-persistent iptables-persistent/autosave_v6 boolean true" | sudo debconf-set-selections',
            'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables iptables-persistent nftables 2>/dev/null || true',
            'sudo apt-get install -y ufw',
            'sudo ufw --force enable',
            'sudo ufw default deny incoming',
            'sudo ufw default allow outgoing',
            'sudo ufw allow ssh',
        ],
        'launch':  None,
        'docs':    'sudo ufw status verbose',
    },
    {
        'id':      'whois',
        'name':    'whois',
        'label':   '🔎 whois',
        'desc':    'Domain and IP registration lookup',
        'check':   'whois',
        'version': 'whois --version 2>/dev/null | head -1',
        'install': ['sudo apt-get install -y whois'],
        'launch':  None,
        'docs':    'whois <ip or domain>',
    },
    {
        'id':      'dig',
        'name':    'dig',
        'label':   '🔭 dig / DNS',
        'desc':    'DNS lookup tool — resolve hostnames, trace DNS',
        'check':   'dig',
        'version': 'dig -v 2>&1 | head -1',
        'install': ['sudo apt-get install -y dnsutils'],
        'launch':  None,
        'docs':    'dig +short <hostname>',
    },
    {
        'id':      'traceroute',
        'name':    'traceroute',
        'label':   '🗺 traceroute',
        'desc':    'Trace network path to a host — find routing issues',
        'check':   'traceroute',
        'version': 'traceroute --version 2>/dev/null | head -1',
        'install': ['sudo apt-get install -y traceroute'],
        'launch':  None,
        'docs':    'traceroute <host>',
    },
]


def check_installed(tool_id):
    """Check if a tool binary exists. Returns (installed: bool, version: str)"""
    tool = next((t for t in TOOLS if t['id'] == tool_id), None)
    if not tool:
        return False, ''
    binary = tool.get('check', tool['name'])
    if shutil.which(binary):
        ver, _, _ = _run(tool.get('version', f'{binary} --version 2>/dev/null | head -1'))
        return True, ver.split('\n')[0][:60] if ver else 'installed'
    return False, ''


class ToolboxScreen(ctk.CTkFrame):
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
        self._tool_rows = {}   # tool_id -> dict of widgets

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._check_all, daemon=True).start()

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="🛠  SECURITY TOOLBOX",
                     font=('Courier',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        Btn(hdr, "↺ REFRESH",
            command=lambda: threading.Thread(target=self._check_all, daemon=True).start(),
            variant='ghost', width=100).pack(side='right', padx=4, pady=6)
        Btn(hdr, "⬇ INSTALL MISSING",
            command=self._install_missing,
            variant='primary', width=160).pack(side='right', padx=4, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # Summary row
        SectionHeader(body, '01', 'TOOL STATUS').pack(fill='x', padx=14, pady=(14,4))
        self.summary_card = Card(body)
        self.summary_card.pack(fill='x', padx=14, pady=(0,8))
        self.summary_lbl = ctk.CTkLabel(
            self.summary_card, text="Checking tools...",
            font=MONO_SM, text_color=C['mu'])
        self.summary_lbl.pack(padx=12, pady=10)

        # Tool cards
        SectionHeader(body, '02', 'ALL TOOLS').pack(fill='x', padx=14, pady=(8,4))
        self.tools_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.tools_frame.pack(fill='x', padx=14, pady=(0,8))

        for tool in TOOLS:
            self._make_tool_row(tool)

        # Action log
        SectionHeader(body, '03', 'ACTION LOG').pack(fill='x', padx=14, pady=(8,4))
        self.action_log = ctk.CTkTextbox(
            body, height=120, font=('Courier',8),
            fg_color=C['s2'], text_color=C['ok'],
            border_color=C['br'], border_width=1, corner_radius=6)
        self.action_log.pack(fill='x', padx=14, pady=(0,14))
        self.action_log.configure(state='disabled')

    def _make_tool_row(self, tool):
        row = ctk.CTkFrame(
            self.tools_frame, fg_color=C['sf'],
            border_color=C['br'], border_width=1, corner_radius=8)
        row.pack(fill='x', pady=3)

        # Icon + name
        left = ctk.CTkFrame(row, fg_color='transparent')
        left.pack(side='left', padx=12, pady=8, fill='both', expand=True)

        name_row = ctk.CTkFrame(left, fg_color='transparent')
        name_row.pack(fill='x')

        status_dot = ctk.CTkLabel(name_row, text='●', font=('Courier',12),
                                   text_color=C['mu'])
        status_dot.pack(side='left', padx=(0,6))

        ctk.CTkLabel(name_row, text=tool['label'],
                     font=('Courier',10,'bold'), text_color=C['tx']
                     ).pack(side='left')

        ver_lbl = ctk.CTkLabel(left, text=tool['desc'],
                                font=('Courier',8), text_color=C['mu'])
        ver_lbl.pack(anchor='w')

        docs_lbl = ctk.CTkLabel(left, text=f"Usage: {tool['docs']}",
                                 font=('Courier',7), text_color=C['br2'])
        docs_lbl.pack(anchor='w')

        # Buttons
        btns = ctk.CTkFrame(row, fg_color='transparent')
        btns.pack(side='right', padx=8, pady=8)

        install_btn = Btn(btns, "⬇ INSTALL", variant='ghost', width=100,
                          command=lambda t=tool: self._install_one(t))
        install_btn.pack(pady=2)

        launch_btn = Btn(btns, "▶ LAUNCH", variant='blue', width=100,
                         command=lambda t=tool: self._launch_tool(t))
        launch_btn.pack(pady=2)

        self._tool_rows[tool['id']] = {
            'row':         row,
            'status_dot':  status_dot,
            'ver_lbl':     ver_lbl,
            'install_btn': install_btn,
            'launch_btn':  launch_btn,
        }

    def _check_all(self):
        installed_count = 0
        total = len(TOOLS)
        for tool in TOOLS:
            installed, version = check_installed(tool['id'])
            if installed:
                installed_count += 1
            self._safe_after(0, self._update_tool_row, tool['id'], installed, version)
        self._safe_after(0, self._update_summary, installed_count, total)

    def _update_tool_row(self, tool_id, installed, version):
        w = self._tool_rows.get(tool_id)
        if not w:
            return
        if installed:
            w['status_dot'].configure(text_color=C['ok'])
            w['ver_lbl'].configure(text=f"✓ {version}", text_color=C['ok'])
            w['install_btn'].configure(state='disabled', text='✓ INSTALLED')
            # Only show launch if tool has a GUI launch command
            tool = next(t for t in TOOLS if t['id'] == tool_id)
            if not tool.get('launch'):
                w['launch_btn'].configure(state='disabled', text='CLI ONLY')
        else:
            w['status_dot'].configure(text_color=C['wn'])
            w['ver_lbl'].configure(text='✗ NOT INSTALLED', text_color=C['wn'])
            w['install_btn'].configure(state='normal', text='⬇ INSTALL')
            w['launch_btn'].configure(state='disabled', text='NOT INSTALLED')

    def _update_summary(self, installed, total):
        for w in self.summary_card.winfo_children():
            w.destroy()
        missing = total - installed
        InfoGrid(self.summary_card, [
            ('INSTALLED', installed, C['ok']),
            ('MISSING',   missing,   C['wn'] if missing else C['ok']),
            ('TOTAL',     total,     C['ac']),
        ], columns=3).pack(fill='x', padx=4, pady=6)
        if missing == 0:
            ctk.CTkLabel(self.summary_card,
                         text="✓ All security tools are installed",
                         font=MONO_SM, text_color=C['ok']
                         ).pack(pady=(0,8))
        else:
            ctk.CTkLabel(self.summary_card,
                         text=f"Tap ⬇ INSTALL MISSING to install {missing} tool(s) automatically",
                         font=MONO_SM, text_color=C['am']
                         ).pack(pady=(0,8))

    def _install_one(self, tool):
        installed, _ = check_installed(tool['id'])
        if installed:
            self._log(f"✓ {tool['name']} is already installed — skipping")
            return
        self._log(f"Installing {tool['name']}...")
        InstallerPopup(self,
            title=f"Install {tool['label']}",
            commands=['sudo apt-get update -qq'] + tool['install'],
            success_msg=f"{tool['name']} installed successfully!",
            on_done=lambda: threading.Thread(target=self._check_all, daemon=True).start()
        )

    def _install_missing(self):
        missing = []
        for tool in TOOLS:
            installed, _ = check_installed(tool['id'])
            if not installed:
                missing.append(tool)

        if not missing:
            self._log("✓ All tools already installed — nothing to do")
            return

        self._log(f"Installing {len(missing)} missing tool(s)...")
        all_cmds = ['sudo apt-get update -qq']
        for tool in missing:
            all_cmds.extend(tool['install'])
            # Deduplicate
        all_cmds = list(dict.fromkeys(all_cmds))

        InstallerPopup(self,
            title=f"Install {len(missing)} Missing Tools",
            commands=all_cmds,
            success_msg="All missing tools installed!",
            on_done=lambda: threading.Thread(target=self._check_all, daemon=True).start()
        )

    def _launch_tool(self, tool):
        launch_cmd = tool.get('launch')
        if not launch_cmd:
            self._log(f"{tool['name']} is a command-line tool. Usage: {tool['docs']}")
            return
        installed, _ = check_installed(tool['id'])
        if not installed:
            self._log(f"✗ {tool['name']} is not installed. Tap INSTALL first.")
            return
        self._log(f"Launching {tool['name']}...")
        try:
            subprocess.Popen([launch_cmd], start_new_session=True)
            self._log(f"✓ {tool['name']} launched")
        except Exception as e:
            self._log(f"✗ Could not launch: {e}")

    def _log(self, msg):
        self.action_log.configure(state='normal')
        self.action_log.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.action_log.see('end')
        self.action_log.configure(state='disabled')
