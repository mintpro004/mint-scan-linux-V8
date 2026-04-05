"""Firewall Manager — view all rules, add/remove, configure UFW"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, re, time, shutil
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from installer import InstallerPopup
from utils import run_cmd as _run


class FirewallScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._load_status, daemon=True).start()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="🔥  FIREWALL MANAGER",
                     font=('Courier',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        Btn(hdr, "↺ REFRESH", command=lambda: threading.Thread(
            target=self._load_status, daemon=True).start(),
            variant='ghost', width=100).pack(side='right', padx=12, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── Status ────────────────────────────────────────────
        SectionHeader(body, '01', 'FIREWALL STATUS').pack(fill='x', padx=14, pady=(14,4))
        self.status_card = Card(body)
        self.status_card.pack(fill='x', padx=14, pady=(0,8))
        self.status_info = ctk.CTkLabel(self.status_card,
            text="Loading firewall status...", font=MONO_SM, text_color=C['mu'])
        self.status_info.pack(padx=12, pady=12)

        # ── Quick controls ────────────────────────────────────
        SectionHeader(body, '02', 'QUICK CONTROLS').pack(fill='x', padx=14, pady=(8,4))
        ctrl = Card(body)
        ctrl.pack(fill='x', padx=14, pady=(0,8))
        cg = ctk.CTkFrame(ctrl, fg_color='transparent')
        cg.pack(fill='x', padx=8, pady=8)
        controls = [
            ("✅ ENABLE FIREWALL",       self._enable_fw,         'success'),
            ("❌ DISABLE FIREWALL",      self._disable_fw,        'danger'),
            ("🔒 SECURE DEFAULTS",       self._secure_defaults,   'primary'),
            ("🌐 ALLOW SSH (22)",        lambda: self._allow_port('22','SSH'),    'ghost'),
            ("🌐 ALLOW HTTP (80)",       lambda: self._allow_port('80','HTTP'),   'ghost'),
            ("🌐 ALLOW HTTPS (443)",     lambda: self._allow_port('443','HTTPS'), 'ghost'),
        ]
        for i, (lbl, cmd, var) in enumerate(controls):
            r2, c2 = divmod(i, 3)
            Btn(cg, lbl, command=cmd, variant=var, width=182
                ).grid(row=r2, column=c2, padx=4, pady=4, sticky='ew')
        cg.columnconfigure(0, weight=1)
        cg.columnconfigure(1, weight=1)
        cg.columnconfigure(2, weight=1)

        # ── Add rule ──────────────────────────────────────────
        SectionHeader(body, '03', 'ADD / REMOVE RULE').pack(fill='x', padx=14, pady=(8,4))
        rule_card = Card(body)
        rule_card.pack(fill='x', padx=14, pady=(0,8))

        row1 = ctk.CTkFrame(rule_card, fg_color='transparent')
        row1.pack(fill='x', padx=12, pady=(10,4))

        ctk.CTkLabel(row1, text="PORT / SERVICE:", font=('Courier',9,'bold'),
                     text_color=C['ac'], width=140).pack(side='left')
        self.port_entry = ctk.CTkEntry(row1,
            placeholder_text="e.g. 8080  or  22  or  3306",
            font=MONO_SM, fg_color=C['bg'], border_color=C['br'],
            text_color=C['tx'], height=34, width=180)
        self.port_entry.pack(side='left', padx=8)

        ctk.CTkLabel(row1, text="PROTO:", font=('Courier',9),
                     text_color=C['mu']).pack(side='left', padx=4)
        self.proto_var = tk.StringVar(value='tcp')
        proto_menu = ctk.CTkOptionMenu(row1, variable=self.proto_var,
            values=['tcp','udp','any'],
            fg_color=C['br'], button_color=C['br2'],
            dropdown_fg_color=C['sf'], font=MONO_SM, width=80)
        proto_menu.pack(side='left', padx=4)

        row2 = ctk.CTkFrame(rule_card, fg_color='transparent')
        row2.pack(fill='x', padx=12, pady=(4,4))

        ctk.CTkLabel(row2, text="FROM IP (optional):", font=('Courier',9,'bold'),
                     text_color=C['ac'], width=140).pack(side='left')
        self.ip_entry = ctk.CTkEntry(row2,
            placeholder_text="e.g. 192.168.1.0/24  (leave blank = any)",
            font=MONO_SM, fg_color=C['bg'], border_color=C['br'],
            text_color=C['tx'], height=34, width=280)
        self.ip_entry.pack(side='left', padx=8)

        row3 = ctk.CTkFrame(rule_card, fg_color='transparent')
        row3.pack(fill='x', padx=12, pady=(4,10))
        Btn(row3, "✅ ALLOW",  command=self._add_allow, variant='success', width=120).pack(side='left', padx=4)
        Btn(row3, "❌ DENY",   command=self._add_deny,  variant='danger',  width=120).pack(side='left', padx=4)
        Btn(row3, "🗑 DELETE RULE", command=self._delete_rule, variant='warning', width=140).pack(side='left', padx=4)

        # ── All rules ─────────────────────────────────────────
        SectionHeader(body, '04', 'ALL FIREWALL RULES').pack(fill='x', padx=14, pady=(8,4))
        self.rules_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.rules_frame.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self.rules_frame, text="Loading rules...",
                     font=MONO_SM, text_color=C['mu']).pack(pady=8)

        # ── iptables view ─────────────────────────────────────
        SectionHeader(body, '05', 'RAW IPTABLES RULES').pack(fill='x', padx=14, pady=(8,4))
        ipt_card = Card(body)
        ipt_card.pack(fill='x', padx=14, pady=(0,8))
        Btn(ipt_card, "VIEW IPTABLES", command=self._view_iptables,
            variant='ghost', width=150).pack(anchor='w', padx=12, pady=(8,4))
        self.ipt_box = ctk.CTkTextbox(ipt_card, height=140, font=('Courier',10),
                                       fg_color=C['bg'], text_color=C['mu'],
                                       border_width=0)
        self.ipt_box.pack(fill='x', padx=8, pady=(0,8))
        self.ipt_box.configure(state='normal')

        # ── VPN Killswitch ────────────────────────────────────
        SectionHeader(body, '06', 'VPN KILLSWITCH').pack(fill='x', padx=14, pady=(8,4))
        ks_card = Card(body, accent=C['wn'])
        ks_card.pack(fill='x', padx=14, pady=(0,8))
        
        ctk.CTkLabel(ks_card, text="Block all traffic if VPN drops (allows tun0/wg0 only)",
                     font=MONO_SM, text_color=C['mu']).pack(pady=(12,4))
        
        self.ks_btn = Btn(ks_card, "🛡 ENABLE KILLSWITCH", command=self._toggle_killswitch, variant='primary', width=200)
        self.ks_btn.pack(pady=(0,12))

        # ── Action output ─────────────────────────────────────
        SectionHeader(body, '07', 'ACTION OUTPUT').pack(fill='x', padx=14, pady=(8,4))
        self.action_log = ctk.CTkTextbox(body, height=110, font=('Courier',10),
                                          fg_color=C['s2'], text_color=C['ok'],
                                          border_color=C['br'], border_width=1, corner_radius=6)
        self.action_log.pack(fill='x', padx=14, pady=(0,14))
        self.action_log.configure(state='normal')

    def _toggle_killswitch(self):
        # Check if ufw installed
        if shutil.which('ufw') is None:
            self._alog("Error: ufw not found.")
            return

        # Check current state (naive check)
        btn_text = self.ks_btn.cget('text')
        if "ENABLE" in btn_text:
            # Enabling
            self._alog("Enabling VPN Killswitch...")
            # Find vpn interface
            out, _, _ = _run("ip -o link show | grep -E 'tun|wg'")
            if not out:
                self._alog("Error: No VPN interface (tun/wg) found!")
                return
            
            # Simple UFW logic: default deny outgoing, allow out on vpn, allow out to vpn server (hard to know IP)
            # This is risky without knowing VPN IP.
            # Safer: just deny outgoing on physical, allow on tun.
            
            _run("ufw default deny outgoing")
            _run("ufw default deny incoming")
            _run("ufw allow out on tun0")
            _run("ufw allow out on wg0")
            _run("ufw allow out on lo") # Loopback
            # We must allow connection to the VPN server itself, but we don't know the IP.
            # This is a strict killswitch. User might get locked out of connecting to VPN.
            # Warn user.
            
            self._alog("Killswitch ENABLED. Only tun0/wg0/lo traffic allowed out.")
            self._alog("⚠ Note: If VPN is not connected, you cannot connect to it!")
            self.ks_btn.configure(text="❌ DISABLE KILLSWITCH", variant='danger')
        else:
            # Disabling
            self._alog("Disabling Killswitch (resetting to default)...")
            _run("ufw default allow outgoing")
            self._alog("Outgoing traffic allowed.")
            self.ks_btn.configure(text="🛡 ENABLE KILLSWITCH", variant='primary')

    # ── Logging ───────────────────────────────────────────────

    def _alog(self, msg):
        self.action_log.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.action_log.see('end')

    # ── Status loader ─────────────────────────────────────────

    def _load_status(self):
        ufw_out, _, rc = _run('ufw status verbose 2>/dev/null')
        active = rc == 0 and 'active' in ufw_out.lower()
        self.after(0, self._render_status, ufw_out, active)
        self.after(0, self._render_rules, ufw_out)

    def _render_status(self, ufw_out, active):
        for w in self.status_card.winfo_children():
            w.destroy()

        # Check if ufw is installed
        if not shutil.which('ufw'):
            ResultBox(self.status_card, 'warn', '🔥 UFW Firewall Not Installed',
                      'The "Uncomplicated Firewall" tool is missing from your system.'
                      ).pack(fill='x', padx=8, pady=(8,4))
            Btn(self.status_card, "⬇ INSTALL UFW FIREWALL",
                command=self._install_ufw, variant='primary', width=240
                ).pack(anchor='w', padx=12, pady=(0,10))
            return

        col = C['ok'] if active else C['wn']
        status_text = 'ACTIVE' if active else 'INACTIVE'

        ResultBox(self.status_card,
                  'ok' if active else 'warn',
                  f'UFW Firewall: {status_text}',
                  'Your firewall is protecting incoming connections.' if active
                  else 'Firewall is OFF — all ports are open to the network!'
                  ).pack(fill='x', padx=8, pady=(8,4))

        if active and ufw_out:
            # Parse default policies
            default_in  = re.search(r'Default: (\w+) \(incoming\)', ufw_out)
            default_out = re.search(r'Default: (\w+) \(outgoing\)', ufw_out)
            InfoGrid(self.status_card, [
                ('INCOMING',  default_in.group(1).upper()  if default_in  else '—',
                 C['ok'] if default_in  and 'deny' in default_in.group(1)  else C['am']),
                ('OUTGOING',  default_out.group(1).upper() if default_out else '—',
                 C['ok'] if default_out and 'allow' in default_out.group(1) else C['am']),
                ('STATUS',    'ACTIVE',  C['ok']),
                ('TOOL',      'UFW',     C['ac']),
            ], columns=4).pack(fill='x', padx=8, pady=(4,8))

    def _install_ufw(self):
        self._alog("Installing UFW Firewall (Chromebook-safe)...")
        # Chromebook Crostini: iptables-persistent may not be available.
        # Use --no-install-recommends and skip iptables-persistent if on Chromebook.
        import platform
        is_cros = shutil.which('crosh') is not None or \
                  'chromeos' in platform.uname().release.lower() or \
                  'cros' in open('/proc/version').read().lower() if \
                  os.path.exists('/proc/version') else False

        if is_cros:
            cmds = [
                'sudo apt-get update -qq',
                'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ufw',
                'sudo ufw --force enable',
                'sudo ufw default deny incoming',
                'sudo ufw default allow outgoing',
            ]
        else:
            cmds = [
                'echo "iptables-persistent iptables-persistent/autosave_v4 boolean true" | sudo debconf-set-selections',
                'echo "iptables-persistent iptables-persistent/autosave_v6 boolean true" | sudo debconf-set-selections',
                'sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq',
                'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ufw iptables-persistent',
                'sudo ufw --force enable',
                'sudo ufw default deny incoming',
                'sudo ufw default allow outgoing',
                'sudo ufw allow ssh',
            ]
        InstallerPopup(self,
            title="Install UFW Firewall",
            commands=cmds,
            success_msg="UFW Firewall installed and enabled!",
            on_done=lambda: threading.Thread(target=self._load_status, daemon=True).start()
        )

    def _render_rules(self, ufw_out):
        for w in self.rules_frame.winfo_children():
            w.destroy()

        if not ufw_out or 'inactive' in ufw_out.lower():
            ctk.CTkLabel(self.rules_frame,
                         text="Firewall is inactive — enable it to see rules",
                         font=MONO_SM, text_color=C['mu']).pack(pady=8)
            return

        # Parse rules from ufw status numbered
        rules_out, _, _ = _run('ufw status numbered 2>/dev/null')
        if not rules_out:
            ctk.CTkLabel(self.rules_frame, text="No rules defined yet",
                         font=MONO_SM, text_color=C['mu']).pack(pady=8)
            return

        rules = []
        for line in rules_out.split('\n'):
            m = re.match(r'\[\s*(\d+)\]\s+(.+)', line)
            if m:
                rules.append({'num': m.group(1), 'rule': m.group(2).strip()})

        if not rules:
            ctk.CTkLabel(self.rules_frame, text="No numbered rules found",
                         font=MONO_SM, text_color=C['mu']).pack(pady=8)
            return

        ctk.CTkLabel(self.rules_frame,
                     text=f"{len(rules)} rule(s) configured:",
                     font=('Courier',9,'bold'), text_color=C['ac']
                     ).pack(anchor='w', pady=(0,4))

        for rule in rules:
            row = ctk.CTkFrame(self.rules_frame, fg_color=C['sf'],
                                border_color=C['br'], border_width=1, corner_radius=6)
            row.pack(fill='x', pady=2)

            # Determine color based on rule content
            rule_text = rule['rule'].upper()
            if 'DENY' in rule_text or 'REJECT' in rule_text:
                col = C['wn']
            elif 'ALLOW' in rule_text:
                col = C['ok']
            else:
                col = C['mu']

            num_badge = ctk.CTkFrame(row, fg_color=C['br2'], corner_radius=3, width=32, height=28)
            num_badge.pack(side='left', padx=8, pady=8)
            num_badge.pack_propagate(False)
            ctk.CTkLabel(num_badge, text=rule['num'], font=('Courier',9,'bold'),
                         text_color=C['ac']).pack(expand=True)

            ctk.CTkLabel(row, text=rule['rule'], font=('Courier',9),
                         text_color=col, anchor='w', justify='left'
                         ).pack(side='left', padx=4, pady=8, fill='x', expand=True)

            Btn(row, "DELETE",
                command=lambda n=rule['num']: self._delete_numbered(n),
                variant='danger', width=75).pack(side='right', padx=8)

    # ── Actions ───────────────────────────────────────────────

    def _enable_fw(self):
        self._alog("Enabling firewall...")
        def _do():
            out, err, rc = _run("sudo ufw --force enable")
            self.after(0, self._alog,
                       "✓ Firewall enabled" if rc==0 else f"✗ {(err or out)[:80]}")
            self.after(500, lambda: threading.Thread(
                target=self._load_status, daemon=True).start())
        threading.Thread(target=_do, daemon=True).start()

    def _disable_fw(self):
        self._alog("WARNING: Disabling firewall — all ports will be unprotected!")
        def _do():
            out, err, rc = _run("sudo ufw disable")
            self.after(0, self._alog,
                       "Firewall disabled" if rc==0 else f"✗ {(err or out)[:80]}")
            self.after(500, lambda: threading.Thread(
                target=self._load_status, daemon=True).start())
        threading.Thread(target=_do, daemon=True).start()

    def _secure_defaults(self):
        self._alog("Applying secure default policy...")
        def _do():
            for cmd, msg in [
                ("sudo ufw --force enable",              "Enabled UFW"),
                ("sudo ufw default deny incoming",       "Default: deny incoming"),
                ("sudo ufw default allow outgoing",      "Default: allow outgoing"),
                ("sudo ufw allow ssh",                   "Allowed SSH (22)"),
            ]:
                out, err, rc = _run(cmd)
                self.after(0, self._alog,
                           f"  {'✓' if rc==0 else '✗'} {msg}: {(out or err or 'done')[:60]}")
            self.after(500, lambda: threading.Thread(
                target=self._load_status, daemon=True).start())
            self.after(0, self._alog, "✓ Secure defaults applied")
        threading.Thread(target=_do, daemon=True).start()

    def _allow_port(self, port, name=''):
        self._alog(f"Allowing port {port} ({name})...")
        def _do(pt=port, nm=name):
            out, err, rc = _run(f"sudo ufw allow {pt}")
            self.after(0, self._alog,
                       f"{'✓ Allowed port '+pt+' ('+nm+')' if rc==0 else '✗ '+( err or out)[:60]}")
            self.after(500, lambda: threading.Thread(
                target=self._load_status, daemon=True).start())
        threading.Thread(target=_do, daemon=True).start()

    def _add_allow(self):
        self._apply_rule('allow')

    def _add_deny(self):
        self._apply_rule('deny')

    def _apply_rule(self, action):
        port  = self.port_entry.get().strip()
        proto = self.proto_var.get()
        from_ip = self.ip_entry.get().strip()

        if not port:
            self._alog("Enter a port number or service name first")
            return

        if from_ip:
            cmd = f"sudo ufw {action} from {from_ip} to any port {port}"
            if proto != 'any':
                cmd += f" proto {proto}"
        else:
            if proto == 'any':
                cmd = f"sudo ufw {action} {port}"
            else:
                cmd = f"sudo ufw {action} {port}/{proto}"

        self._alog(f"Running: {cmd}")
        def _do(c=cmd):
            out, err, rc = _run(c)
            self.after(0, self._alog,
                       f"{'✓ Rule applied: '+c if rc==0 else '✗ '+( err or out)[:100]}")
            self.after(500, lambda: threading.Thread(
                target=self._load_status, daemon=True).start())
        threading.Thread(target=_do, daemon=True).start()

    def _delete_rule(self):
        port = self.port_entry.get().strip()
        if not port:
            self._alog("Enter a port to delete its rule")
            return
        self._alog(f"Deleting rule for port {port}...")
        def _do(pt=port):
            out, err, rc = _run(f"echo 'y' | sudo ufw delete allow {pt} 2>/dev/null || "
                                 f"echo 'y' | sudo ufw delete deny {pt} 2>/dev/null")
            self.after(0, self._alog,
                       f"{'✓ Rule deleted for port '+pt if rc==0 else '✗ '+( err or out)[:80]}")
            self.after(500, lambda: threading.Thread(
                target=self._load_status, daemon=True).start())
        threading.Thread(target=_do, daemon=True).start()

    def _delete_numbered(self, num):
        self._alog(f"Deleting rule #{num}...")
        def _do(n=num):
            out, err, rc = _run(f"echo 'y' | sudo ufw delete {n} 2>/dev/null")
            self.after(0, self._alog,
                       f"{'✓ Deleted rule #'+n if rc==0 else '✗ '+( err or out)[:80]}")
            self.after(800, lambda: threading.Thread(
                target=self._load_status, daemon=True).start())
        threading.Thread(target=_do, daemon=True).start()

    def _view_iptables(self):
        def _do():
            out, err, rc = _run("sudo iptables -L -n --line-numbers 2>/dev/null", timeout=8)
            if rc != 0 or not out:
                out = err or "iptables not available or needs sudo"
            self.ipt_box.delete('1.0', 'end')
            self.ipt_box.insert('1.0', out)
        threading.Thread(target=_do, daemon=True).start()
