"""
Threats Screen v2 — fully working scan, action buttons, smooth UI.
All heavy work runs in background threads. UI never freezes.
"""
import tkinter as tk
import customtkinter as ctk
import threading, os, re, subprocess, time, queue
from widgets import ScrollableFrame, Card, SectionHeader, ResultBox, Btn, InfoGrid, C, MONO, MONO_SM
from installer import InstallerPopup

KNOWN_BAD = {
    '23':'Telnet','4444':'Metasploit','1337':'Suspicious',
    '6667':'IRC','31337':'Back Orifice','5555':'ADB-Net',
}
RISKY = {
    '21':'FTP','25':'SMTP','3306':'MySQL','27017':'MongoDB',
    '6379':'Redis','5900':'VNC','8080':'HTTP-Alt','3389':'RDP',
}

def _r(cmd, timeout=10):
    """Run command — Chromebook-safe sudo (no GUI polkit needed)."""
    original = cmd.strip()
    if original.startswith('sudo ') and os.geteuid() != 0:
        inner = original[5:].strip()
        inner_q = inner.replace("'", "'''")
        cmd = f"sudo -n bash -c '{inner_q}' 2>/dev/null || sudo bash -c '{inner_q}'"
    env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout, env=env)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return '', str(e), 1


class ThreatsScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app       = app
        self._built    = False
        self._scanning = False
        # Queue so background thread safely posts UI updates
        self._q = queue.Queue()

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        # Start polling queue
        self._poll()

    # ── UI BUILD ──────────────────────────────────────────────────

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=52, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="⚠  THREATS & REMEDIATION",
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        self.stop_btn = Btn(hdr, "⏹ STOP", command=self._stop,
                            variant='danger', width=90)
        self.stop_btn.pack(side='right', padx=6, pady=8)
        self.stop_btn.configure(state='disabled')
        self.scan_btn = Btn(hdr, "▶ SCAN", command=self._scan, width=100)
        self.scan_btn.pack(side='right', padx=4, pady=8)

        # Progress bar (thin, always visible)
        self.prog = ctk.CTkProgressBar(self, height=3,
                                        progress_color=C['ac'],
                                        fg_color=C['br'])
        self.prog.pack(fill='x')
        self.prog.set(0)

        # Scroll area
        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── Quick actions row ─────────────────────────────────
        qa = ctk.CTkFrame(body, fg_color=C['sf'], corner_radius=10)
        qa.pack(fill='x', padx=14, pady=(12,4))
        ctk.CTkLabel(qa, text="QUICK ACTIONS",
                     font=('DejaVu Sans Mono',8,'bold'), text_color=C['mu']
                     ).pack(anchor='w', padx=12, pady=(8,4))
        qg = ctk.CTkFrame(qa, fg_color='transparent')
        qg.pack(fill='x', padx=8, pady=(0,8))
        quick = [
            ("🔥 Enable Firewall",   self._act_enable_fw,     'danger'),
            ("🔒 Harden SSH",        self._act_harden_ssh,    'danger'),
            ("🔄 Update System",     self._act_update,        'primary'),
            ("🛡 Block Bad Ports",   self._act_block_ports,   'warning'),
            ("🧹 Kill Susp Procs",  self._act_kill_susp,     'warning'),
            ("⚙ Firewall Mgr",     lambda: self.app._switch_tab('firewall'), 'blue'),
        ]
        for i,(lbl,cmd,var) in enumerate(quick):
            r2,c2 = divmod(i,3)
            Btn(qg, lbl, command=cmd, variant=var, width=182
                ).grid(row=r2, column=c2, padx=4, pady=4, sticky='ew')
        for c3 in range(3): qg.columnconfigure(c3, weight=1)

        # ── Scan log ─────────────────────────────────────────
        SectionHeader(body,'01','SCAN LOG').pack(fill='x', padx=14, pady=(10,4))
        self.scan_log = ctk.CTkTextbox(body, height=80, font=('DejaVu Sans Mono',8),
                                        fg_color=C['s2'], text_color=C['ac'],
                                        border_color=C['br'], border_width=1,
                                        corner_radius=6)
        self.scan_log.pack(fill='x', padx=14, pady=(0,6))
        self.scan_log.configure(state='disabled')

        # ── Findings ─────────────────────────────────────────
        SectionHeader(body,'02','FINDINGS & FIX OPTIONS').pack(fill='x', padx=14, pady=(8,4))
        self.findings_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.findings_frame.pack(fill='x', padx=14, pady=(0,6))
        ctk.CTkLabel(self.findings_frame,
                     text="Tap ▶ SCAN to check your system for threats",
                     font=MONO_SM, text_color=C['mu']).pack(pady=14)

        # ── Action output ─────────────────────────────────────
        SectionHeader(body,'03','ACTION OUTPUT').pack(fill='x', padx=14, pady=(8,4))
        self.action_log = ctk.CTkTextbox(body, height=100, font=('DejaVu Sans Mono',8),
                                          fg_color=C['s2'], text_color=C['ok'],
                                          border_color=C['br'], border_width=1,
                                          corner_radius=6)
        self.action_log.pack(fill='x', padx=14, pady=(0,6))
        self.action_log.configure(state='disabled')

        # ── Scam checker ─────────────────────────────────────
        SectionHeader(body,'04','SCAM / URL CHECKER').pack(fill='x', padx=14, pady=(8,4))
        sc = Card(body)
        sc.pack(fill='x', padx=14, pady=(0,14))
        ctk.CTkLabel(sc,
                     text="Check a number, URL, or message text for scam patterns:",
                     font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,4))
        sr = ctk.CTkFrame(sc, fg_color='transparent')
        sr.pack(fill='x', padx=12, pady=(0,10))
        self.scam_entry = ctk.CTkEntry(sr,
            placeholder_text="0900... or http://... or 'You won a prize'",
            font=MONO_SM, fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'], height=36)
        self.scam_entry.pack(side='left', fill='x', expand=True, padx=(0,8))
        self.scam_entry.bind('<Return>', lambda e: self._check_scam())
        Btn(sr,'ANALYSE', command=self._check_scam, variant='danger', width=90).pack(side='left')
        self.scam_result = ctk.CTkFrame(sc, fg_color='transparent')
        self.scam_result.pack(fill='x', padx=12, pady=(0,6))

    # ── Queue polling (keeps UI responsive) ───────────────────

    def _poll(self):
        """Drain the update queue — called every 50ms from main thread."""
        try:
            while True:
                fn = self._q.get_nowait()
                fn()
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _ui(self, fn):
        """Post a UI-update function to be run on main thread."""
        self._q.put(fn)

    # ── Logging ───────────────────────────────────────────────

    def _log(self, msg):
        def _do():
            self.scan_log.configure(state='normal')
            self.scan_log.insert('end', msg + '\n')
            self.scan_log.see('end')
            self.scan_log.configure(state='disabled')
        self._ui(_do)

    def _alog(self, msg):
        def _do():
            self.action_log.configure(state='normal')
            self.action_log.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.action_log.see('end')
            self.action_log.configure(state='disabled')
        self._ui(_do)

    def _set_prog(self, val):
        self._ui(lambda: self.prog.set(val))

    # ── Scan ──────────────────────────────────────────────────

    def _scan(self):
        if self._scanning:
            return
        self._scanning = True
        self._ui(lambda: self.scan_btn.configure(state='disabled', text='SCANNING...'))
        self._ui(lambda: self.stop_btn.configure(state='normal'))
        self._ui(lambda: self.prog.set(0))
        self._ui(lambda: (self.scan_log.configure(state='normal'),
                          self.scan_log.delete('1.0','end'),
                          self.scan_log.configure(state='disabled')))
        self._ui(lambda: [w.destroy() for w in self.findings_frame.winfo_children()])
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _stop(self):
        self._scanning = False
        self._ui(lambda: self.scan_btn.configure(state='normal', text='▶ SCAN'))
        self._ui(lambda: self.stop_btn.configure(state='disabled'))
        self._log("Scan stopped.")

    def _do_scan(self):
        findings = []

        def chk(label, pct):
            if not self._scanning:
                return False
            self._log(label)
            self._set_prog(pct)
            return True

        if not chk("Checking privileges...", 0.08): return
        import os
        if os.geteuid() == 0:
            findings.append(('HIGH','Running as root — elevated risk',
                'Use a regular user account for daily operations.',
                [("VIEW ADVICE",'warning',
                  lambda: self._alog("Run without sudo: source venv/bin/activate && python3 main.py"))]))

        if not chk("Scanning open ports...", 0.18): return
        out, _, _ = _r("ss -tlnp 2>/dev/null")
        for line in out.split('\n'):
            m = re.search(r':(\d+)\s', line)
            if not m: continue
            port = m.group(1)
            if port in KNOWN_BAD:
                svc = KNOWN_BAD[port]
                proc = re.search(r'users:\(\("([^"]+)"', line)
                pname = proc.group(1) if proc else '?'
                findings.append(('HIGH', f'Dangerous port :{port} ({svc}) is OPEN',
                    f'Process: {pname}. Close this immediately.',
                    [("BLOCK PORT",'danger', lambda p=port: self._block_port(p)),
                     ("KILL PROC", 'warning', lambda p=pname: self._kill_proc(p))]))
            elif port in RISKY:
                svc = RISKY[port]
                findings.append(('MED', f'Exposed port :{port} ({svc})',
                    'Ensure firewall restricts access to this port.',
                    [("BLOCK PORT",'warning', lambda p=port: self._block_port(p)),
                     ("LOCAL ONLY",'ghost',   lambda p=port: self._local_only(p))]))

        if not chk("Checking firewall...", 0.30): return
        ufw, _, rc = _r("ufw status 2>/dev/null")
        if 'inactive' in ufw.lower() or rc != 0:
            findings.append(('HIGH','Firewall (UFW) is DISABLED',
                'All incoming connections are unfiltered.',
                [("ENABLE NOW",'danger', self._act_enable_fw),
                 ("FW MANAGER",'blue', lambda: self.app._switch_tab('firewall'))]))

        if not chk("Checking SSH...", 0.42): return
        sshd = '/etc/ssh/sshd_config'
        if os.path.exists(sshd):
            try:
                cfg = open(sshd).read()
                if re.search(r'^PermitRootLogin\s+yes', cfg, re.M):
                    findings.append(('HIGH','SSH root login permitted',
                        'Brute-force attacks can gain full system access.',
                        [("DISABLE ROOT",'danger',  self._fix_ssh_root),
                         ("FULL HARDEN", 'danger', self._act_harden_ssh)]))
                if re.search(r'^PasswordAuthentication\s+yes', cfg, re.M):
                    findings.append(('MED','SSH password auth enabled',
                        'Key-based authentication is more secure.',
                        [("DISABLE PWD AUTH",'warning', self._fix_ssh_pwd)]))
            except PermissionError:
                self._log("  SSH config: needs sudo to read")

        if not chk("Checking auto-updates...", 0.52): return
        upd, _, _ = _r("dpkg -l unattended-upgrades 2>/dev/null | grep ^ii")
        if not upd:
            findings.append(('MED','Auto security updates not configured',
                'Install unattended-upgrades to apply patches automatically.',
                [("INSTALL NOW",'warning', self._fix_autoupdates)]))

        if not chk("Checking processes...", 0.62): return
        ps, _, _ = _r("ps aux 2>/dev/null")
        for name in ['netcat','ncat','socat','msfconsole','hydra','john ','hashcat']:
            if name.lower() in ps.lower():
                pids = [l.split()[1] for l in ps.split('\n')
                        if name.lower() in l.lower() and l.split()]
                pid = pids[0] if pids else '?'
                findings.append(('HIGH', f'Suspicious process: {name.strip()} (PID {pid})',
                    'Known hacking/pentest tool is running.',
                    [("KILL NOW",'danger', lambda n=name: self._kill_proc(n)),
                     ("VIEW INFO",'ghost', lambda n=name: self._alog(
                         f"Process info: {[l for l in ps.split(chr(10)) if n.lower() in l.lower()][:1]}"))]))

        if not chk("Checking /tmp...", 0.72): return
        ww, _, _ = _r("find /tmp /var/tmp -maxdepth 1 -perm -o+w -type f 2>/dev/null | wc -l")
        try:
            if int(ww.strip() or '0') > 10:
                findings.append(('MED', f'{ww.strip()} world-writable files in /tmp',
                    'Potential privilege escalation staging area.',
                    [("CLEAN /TMP",'warning', self._clean_tmp)]))
        except ValueError:
            pass

        if not chk("Checking pending updates...", 0.82): return
        upd2, _, _ = _r("apt list --upgradable 2>/dev/null | grep -c upgradable", timeout=12)
        try:
            n = max(0, int(upd2.strip()) - 1)
            if n > 20:
                findings.append(('HIGH', f'{n} security updates pending',
                    'Unpatched vulnerabilities exist in installed packages.',
                    [("UPDATE NOW",'danger', self._act_update)]))
            elif n > 0:
                findings.append(('MED', f'{n} updates available',
                    'Keep system patched for best security.',
                    [("UPDATE",'warning', self._act_update)]))
        except ValueError:
            pass

        if not self._scanning:
            return

        if not findings:
            findings.append(('OK','✓ No threats detected',
                'All security checks passed.', []))

        self._set_prog(1.0)
        self._log(f"✓ Scan complete — {len(findings)} finding(s)")
        self._scanning = False
        self._ui(lambda: self._render_findings(findings))
        self._ui(lambda: self.scan_btn.configure(state='normal', text='↺ RESCAN'))
        self._ui(lambda: self.stop_btn.configure(state='disabled'))

    # ── Render findings ───────────────────────────────────────

    def _render_findings(self, findings):
        for w in self.findings_frame.winfo_children():
            w.destroy()

        high = sum(1 for f in findings if f[0]=='HIGH')
        med  = sum(1 for f in findings if f[0]=='MED')

        if high or med:
            summary = Card(self.findings_frame,
                           accent=C['wn'] if high else C['am'])
            summary.pack(fill='x', pady=(0,8))
            InfoGrid(summary,[
                ('HIGH RISK', high, C['wn'] if high else C['ok']),
                ('MEDIUM',    med,  C['am'] if med  else C['ok']),
                ('TOTAL',     len(findings), C['ac']),
            ], columns=3).pack(fill='x', padx=6, pady=8)

        for level, title, desc, actions in findings:
            colours = {'HIGH':C['wn'],'MED':C['am'],'OK':C['ok'],'INFO':C['bl']}
            col = colours.get(level, C['mu'])

            card = ctk.CTkFrame(self.findings_frame, fg_color=C['sf'],
                                 border_color=col, border_width=1, corner_radius=8)
            card.pack(fill='x', pady=4)

            # Level badge + title
            top = ctk.CTkFrame(card, fg_color='transparent')
            top.pack(fill='x', padx=12, pady=(10,3))
            badge = ctk.CTkFrame(top, fg_color=col, corner_radius=3)
            badge.pack(side='left', padx=(0,8))
            ctk.CTkLabel(badge, text=level,
                         font=('DejaVu Sans Mono',7,'bold'),
                         text_color=C['bg']).pack(padx=7, pady=3)
            ctk.CTkLabel(top, text=title,
                         font=('DejaVu Sans Mono',10,'bold'),
                         text_color=col, wraplength=520,
                         justify='left').pack(side='left')

            # Description
            if desc:
                ctk.CTkLabel(card, text=desc,
                             font=('DejaVu Sans Mono',8), text_color=C['mu'],
                             wraplength=580, justify='left'
                             ).pack(anchor='w', padx=12, pady=(0,6))

            # Action buttons
            if actions:
                br = ctk.CTkFrame(card, fg_color='transparent')
                br.pack(anchor='w', padx=12, pady=(2,10))
                for lbl, var, cb in actions:
                    Btn(br, lbl, command=cb, variant=var,
                        width=max(100, len(lbl)*7+24)
                        ).pack(side='left', padx=3)

    # ══════════════════════════════════════════════════════════
    # REMEDIATION ACTIONS  (all run in threads, log via _alog)
    # ══════════════════════════════════════════════════════════

    def _bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _act_enable_fw(self):
        self._alog("Enabling UFW firewall...")
        def _do():
            for msg, cmd in [
                ("Enabling UFW...",          "sudo ufw --force enable"),
                ("Deny incoming by default..","sudo ufw default deny incoming"),
                ("Allow outgoing...",         "sudo ufw default allow outgoing"),
                ("Allow SSH...",              "sudo ufw allow ssh"),
            ]:
                self._alog(msg)
                out, err, rc = _r(cmd)
                self._alog(f"  {'✓' if rc==0 else '✗'} {(out or err or 'done')[:80]}")
            self._alog("✓ Firewall enabled with secure defaults")
        self._bg(_do)

    def _act_harden_ssh(self):
        InstallerPopup(self, title="Harden SSH",
            commands=[
                "sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config",
                "sudo sed -i 's/^#*MaxAuthTries.*/MaxAuthTries 3/' /etc/ssh/sshd_config",
                "sudo systemctl restart sshd 2>/dev/null || sudo service ssh restart 2>/dev/null || true",
            ],
            success_msg="SSH hardened — root login disabled, max attempts 3")

    def _act_update(self):
        InstallerPopup(self, title="Update System",
            commands=["sudo apt-get update -q","sudo apt-get upgrade -y -q",
                      "sudo apt-get autoremove -y -q"],
            success_msg="System updated successfully!")

    def _act_block_ports(self):
        self._alog("Blocking all known dangerous ports...")
        def _do():
            for port, svc in KNOWN_BAD.items():
                out, err, rc = _r(f"sudo ufw deny {port} 2>/dev/null")
                self._alog(f"  {'✓' if rc==0 else '✗'} Blocked :{port} ({svc})")
            self._alog("✓ Done")
        self._bg(_do)

    def _act_kill_susp(self):
        self._alog("Scanning for suspicious processes...")
        def _do():
            found = False
            for name in ['msfconsole','hydra','john','hashcat','netcat','ncat','socat']:
                out, _, rc = _r(f"pgrep -f {name} 2>/dev/null")
                if rc == 0 and out:
                    for pid in out.strip().split('\n'):
                        _, _, krc = _r(f"sudo kill -9 {pid} 2>/dev/null")
                        self._alog(f"  {'✓ Killed' if krc==0 else '✗ Could not kill'} {name} (PID {pid})")
                    found = True
            if not found:
                self._alog("✓ No suspicious processes running")
        self._bg(_do)

    def _block_port(self, port):
        self._alog(f"Blocking port {port}...")
        def _do(pt=port):
            out, err, rc = _r(f"sudo ufw deny {pt} 2>/dev/null")
            self._alog(f"{'✓ Blocked :'+pt if rc==0 else '✗ '+( err or out)[:60]}")
        self._bg(_do)

    def _local_only(self, port):
        def _do(pt=port):
            _r(f"sudo ufw deny {pt}")
            _r(f"sudo ufw allow from 127.0.0.1 to any port {pt}")
            self._alog(f"✓ :{pt} restricted to localhost only")
        self._bg(_do)

    def _kill_proc(self, name):
        self._alog(f"Killing {name}...")
        def _do(n=name):
            out, err, rc = _r(f"sudo pkill -f '{n}' 2>/dev/null")
            self._alog(f"{'✓ Killed '+n if rc==0 else '✗ '+( err or out)[:60]}")
        self._bg(_do)

    def _fix_ssh_root(self):
        def _do():
            _r("sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config")
            _r("sudo systemctl restart sshd 2>/dev/null || sudo service ssh restart 2>/dev/null")
            self._alog("✓ SSH root login disabled")
        self._bg(_do)

    def _fix_ssh_pwd(self):
        self._alog("WARNING: Ensure SSH keys are configured before doing this!")
        def _do():
            _r("sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config")
            _r("sudo systemctl restart sshd 2>/dev/null || sudo service ssh restart 2>/dev/null")
            self._alog("✓ SSH password auth disabled")
        self._bg(_do)

    def _fix_autoupdates(self):
        InstallerPopup(self, title="Install Auto-Updates",
            commands=["sudo apt-get install -y unattended-upgrades",
                      "sudo dpkg-reconfigure -plow unattended-upgrades"],
            success_msg="Automatic security updates configured!")

    def _clean_tmp(self):
        def _do():
            out, err, rc = _r("sudo rm -rf /tmp/* /var/tmp/* 2>/dev/null")
            self._alog("✓ /tmp cleaned" if rc==0 else f"✗ {(err or out)[:60]}")
        self._bg(_do)

    # ── Scam checker ──────────────────────────────────────────

    def _check_scam(self):
        for w in self.scam_result.winfo_children():
            w.destroy()
        val = self.scam_entry.get().strip()
        if not val:
            return
        results, risk = [], 'LOW'
        v = val.lower()
        if re.match(r'^(\+27|0)9[0-9]{8}', val.replace(' ','')):
            risk='HIGH'; results.append('Premium rate SA number (090x / +2790x)')
        if re.match(r'^https?://', val):
            if not val.startswith('https:'):
                risk='HIGH'; results.append('HTTP only — no encryption')
            if re.search(r'bit\.ly|tinyurl|t\.co|goo\.gl', val):
                results.append('Shortened URL — destination unknown')
            if re.search(r'\.(xyz|top|click|win|loan|tk|ml|ga|cf)', val):
                results.append('Suspicious domain extension')
            if re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', val):
                results.append('IP address used instead of domain')
        keywords = ['won','prize','free cash','urgent','verify account',
                    'click here','suspended','confirm details','act now','bank alert']
        hits = [w for w in keywords if w in v]
        if len(hits) >= 2:
            risk='HIGH'; results.append(f'Multiple scam keywords: {", ".join(hits[:4])}')
        elif hits:
            risk='MEDIUM'; results.append(f'Scam keyword: {hits[0]}')
        if not results:
            results.append('No obvious scam patterns detected')
        rtype = 'warn' if risk=='HIGH' else 'med' if risk=='MEDIUM' else 'ok'
        icon  = '⚠' if risk != 'LOW' else '✓'
        ResultBox(self.scam_result, rtype,
                  f'{icon} RISK: {risk}',
                  '\n'.join(results)).pack(fill='x')
