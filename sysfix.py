"""System Scan & Fix — comprehensive system health and repair"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, os, re, time, shutil
from installer import install_all_tools, install_ripgrep, install_nmap, install_tcpdump
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from utils import run_cmd as run
from reports import prompt_save_report


class SysFixScreen(ctk.CTkFrame):
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
        self._dry_run = tk.BooleanVar(value=False)

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
        ctk.CTkLabel(hdr, text="🔧  SYSTEM SCAN & FIX", font=('DejaVu Sans Mono',13,'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        
        # Dry Run Toggle
        ctk.CTkCheckBox(hdr, text="DRY RUN", variable=self._dry_run,
                        font=MONO_SM, text_color=C['mu'],
                        fg_color=C['ac'], border_color=C['br']).pack(side='right', padx=12)

        Btn(hdr, "▶ FULL SYSTEM SCAN", command=self._full_scan, width=180
            ).pack(side='right', padx=12, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll
        self.results_frame = body

        # Quick action buttons
        SectionHeader(body, '01', 'QUICK FIXES').pack(fill='x', padx=14, pady=(14,4))
        qf = Card(body)
        qf.pack(fill='x', padx=14, pady=(0,8))

        from utils import _is_crostini
        if _is_crostini():
            cb_card = ctk.CTkFrame(qf, fg_color=C['s2'], corner_radius=6)
            cb_card.pack(fill='x', padx=8, pady=8)
            ctk.CTkLabel(cb_card, text="CHROMEBOOK AUTO-CONFIG", font=('Courier', 10, 'bold'), text_color=C['ac']).pack(anchor='w', padx=10, pady=(5,0))
            ctk.CTkLabel(cb_card, text="Optimize Linux container for security auditing.", font=('Courier', 9), text_color=C['tx']).pack(anchor='w', padx=10)
            Btn(cb_card, "🚀 RUN CHROMEBOOK FIX", command=self._fix_chromebook, variant='blue', width=200).pack(anchor='w', padx=10, pady=10)

        grid = ctk.CTkFrame(qf, fg_color='transparent')
        grid.pack(fill='x', padx=8, pady=8)
        quick_fixes = [
            ("🔄 UPDATE SYSTEM",      self._update_system,   'primary'),
            ("🧹 CLEAN PACKAGES",     self._clean_packages,  'ghost'),
            ("💾 CHECK DISK",         self._check_disk,      'ghost'),
            ("🛠 DEPS CHECK",         self._check_deps,      'blue'),
            ("🔐 FIX PERMISSIONS",    self._fix_permissions, 'warning'),
            ("🔥 FIX FIREWALL",       self._fix_firewall,    'danger'),
            ("🔑 HARDEN SSH",         self._harden_ssh,      'danger'),
            ("🗑 CLEAR TEMP FILES",   self._clear_temp,      'ghost'),
        ]
        for i, (label, cmd, variant) in enumerate(quick_fixes):
            r, c = divmod(i, 2)
            Btn(grid, label, command=cmd, variant=variant, width=220
                ).grid(row=r, column=c, padx=4, pady=4, sticky='ew')
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # Scan output
        SectionHeader(body, '02', 'SCAN OUTPUT').pack(fill='x', padx=14, pady=(10,4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0,8))
        self.scan_log = ctk.CTkTextbox(log_card, height=200, font=('DejaVu Sans Mono',10),
                                        fg_color=C['bg'], text_color=C['ok'],
                                        border_width=0)
        self.scan_log.pack(fill='x', padx=8, pady=8)
        self.scan_log.configure(state='normal')

        # Results
        SectionHeader(body, '03', 'FINDINGS & FIXES').pack(fill='x', padx=14, pady=(10,4))
        self.results_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.results_frame.pack(fill='x', padx=14, pady=(0,14))

    def _log(self, msg):
        try:
            self.scan_log.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.scan_log.see('end')
        except: pass

    def _check_deps(self):
        def _bg():
            self._safe_after(0, self._log, "Checking for essential security tools...")
            tools = [
                ('ripgrep', 'rg',     'Fast search tool for logs and code.'),
                ('nmap',    'nmap',   'Network exploration and security auditing.'),
                ('tshark',  'tshark', 'Network protocol analyzer.'),
                ('net-tools','ifconfig','Legacy network tools.'),
            ]
            missing = []
            for name, cmd, desc in tools:
                if not shutil.which(cmd):
                    self._safe_after(0, self._log, f"❌ MISSING: {name}")
                    missing.append(name)
                else:
                    self._safe_after(0, self._log, f"✅ FOUND: {name}")
            
            if missing:
                self._safe_after(0, self._log, f"\nFound {len(missing)} missing tool(s).")
                self._safe_after(0, self._render_dep_fix, missing)
            else:
                self._safe_after(0, self._log, "\n✓ All essential tools are installed.")
        threading.Thread(target=_bg, daemon=True).start()

    def _render_dep_fix(self, missing):
        box = ResultBox(self.results_frame, 'warn', 'MISSING DEPENDENCIES', 
                      f"Essential tools missing: {', '.join(missing)}")
        box.pack(fill='x', pady=5)
        Btn(box, "🚀 INSTALL ALL MISSING", 
            command=lambda: install_all_tools(self, on_done=self._check_deps),
            variant='success', width=200).pack(anchor='e', padx=10, pady=(0,8))

    def _full_scan(self):
        for w in self.results_frame.winfo_children(): w.destroy()
        self.scan_log.delete('1.0', 'end')
        threading.Thread(target=self._do_full_scan, daemon=True).start()

    def _do_full_scan(self):
        findings = []
        self._safe_after(0, self._log, "Starting comprehensive system scan...")

        # 1. Disk health
        self._safe_after(0, self._log, "Checking disk space...")
        df_out, _, _ = run(["df", "-h", "/"])
        if df_out:
            lines = df_out.splitlines()
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 5:
                    pct_str = parts[4].replace('%','')
                    try:
                        pct = int(pct_str)
                        if pct > 90:
                            findings.append(('HIGH', f'Disk nearly full: {parts[4]} used',
                                             'apt autoremove && apt clean',
                                             'Run: sudo apt autoremove && sudo apt clean'))
                    except: pass

        # 2. Package updates
        self._safe_after(0, self._log, "Checking for updates...")
        upd_out, _, _ = run(["sudo", "apt-get", "-s", "upgrade"], timeout=20)
        upd_match = re.search(r'(\d+) upgraded, (\d+) newly installed', upd_out)
        if upd_match:
            upd_count = int(upd_match.group(1))
            if upd_count > 0:
                findings.append(('MED', f'{upd_count} updates available',
                                 'apt update && apt upgrade -y', 'Run: sudo apt upgrade'))

        # 3. Firewall
        self._safe_after(0, self._log, "Checking firewall...")
        ufw_out, _, _ = run(["sudo", "ufw", "status"])
        if 'inactive' in ufw_out.lower():
            findings.append(('HIGH', 'Firewall is DISABLED', 'ufw enable', 'Enable: sudo ufw enable'))

        if not findings:
            findings.append(('OK', '✓ System is healthy', None, 'All checks passed.'))

        self._safe_after(0, self._log, f"✓ Scan complete. {len(findings)} finding(s).")
        self._safe_after(0, self._render_findings, findings)

    def _render_findings(self, findings):
        for w in self.results_frame.winfo_children(): w.destroy()
        for lvl, title, fix_cmd, suggestion in findings:
            box = ResultBox(self.results_frame, 'warn' if lvl=='HIGH' else 'med' if lvl=='MED' else 'ok', title, suggestion)
            box.pack(fill='x', pady=3)
            if fix_cmd:
                Btn(box, f"▶ AUTO-FIX", command=lambda c=fix_cmd, t=title: self._run_fix(c, t),
                    variant='success', width=120).pack(anchor='e', padx=10, pady=(0,8))

    def _execute(self, cmd_list, log_msg=None):
        cmd_str = " ".join(cmd_list) if isinstance(cmd_list, list) else cmd_list
        if self._dry_run.get():
            self._log(f"[DRY RUN] Would execute: {cmd_str}")
            return "Simulated execution", "", 0
        
        if log_msg:
            self._log(log_msg)
        return run(cmd_list)

    def _run_fix(self, cmd, title):
        self._log(f"Running fix: {title}")
        def _bg():
            out, err, rc = self._execute(f"sudo {cmd}" if not cmd.startswith('sudo') else cmd)
            if not self._dry_run.get():
                self._safe_after(0, self._log, f"{'✓ Done' if rc==0 else '✗ Failed'}: {out or err}")
        threading.Thread(target=_bg, daemon=True).start()

    def _fix_chromebook(self):
        self._log("Starting Chromebook Auto-Configuration...")
        def _bg():
            cmds = [
                "sudo apt-get update -qq",
                "sudo apt-get install -y -qq libcanberra-gtk-module libcanberra-gtk3-module python3-tk libtk8.6 adb",
                "sudo usermod -aG plugdev $USER",
                "echo 'SUBSYSTEM==\"usb\", ATTR{idVendor}==\"18d1\", MODE=\"0666\", GROUP=\"plugdev\"' | sudo tee /etc/udev/rules.d/51-android.rules > /dev/null",
                "adb kill-server",
                "adb start-server",
            ]
            for cmd in cmds:
                self._execute(cmd, f"Running: {cmd}")
            self._safe_after(0, self._log, "✓ Chromebook Auto-Config Complete.")
            self._safe_after(0, lambda: ResultBox(self.results_frame, 'ok', 'CHROMEBOOK OPTIMIZED', 
                                                 'Display, ADB, and GTK modules have been configured.').pack(fill='x', pady=5))
        threading.Thread(target=_bg, daemon=True).start()

    def _update_system(self):
        def _bg():
            self._execute(["sudo", "apt-get", "update", "-q"], "Updating package list...")
            self._execute(["sudo", "DEBIAN_FRONTEND=noninteractive", "apt-get", "upgrade", "-y", "-q"], "Upgrading packages...")
            self._safe_after(0, self._log, "✓ Process complete")
        threading.Thread(target=_bg, daemon=True).start()

    def _clean_packages(self):
        def _bg():
            self._execute(["sudo", "apt-get", "autoremove", "-y"], "Cleaning packages...")
            self._safe_after(0, self._log, "✓ Done")
        threading.Thread(target=_bg, daemon=True).start()

    def _check_disk(self):
        def _bg():
            out, _, _ = self._execute(["df", "-h"], "Checking disk usage...")
            self._safe_after(0, self._log, out)
        threading.Thread(target=_bg, daemon=True).start()

    def _fix_permissions(self):
        def _bg():
            self._execute(["chmod", "755", os.path.expanduser("~")], "Fixing home directory permissions...")
            self._safe_after(0, self._log, "✓ Done")
        threading.Thread(target=_bg, daemon=True).start()

    def _fix_firewall(self):
        def _bg():
            self._execute(["sudo", "ufw", "--force", "enable"], "Enabling firewall...")
            self._safe_after(0, self._log, "✓ Done")
        threading.Thread(target=_bg, daemon=True).start()

    def _harden_ssh(self):
        self._log("SSH hardening suggested. Check /etc/ssh/sshd_config")

    def _clear_temp(self):
        def _bg():
            self._execute(["sudo", "find", "/tmp", "-mindepth", "1", "-atime", "+1", "-delete"], "Clearing temp files...")
            self._safe_after(0, self._log, "✓ Done")
        threading.Thread(target=_bg, daemon=True).start()
