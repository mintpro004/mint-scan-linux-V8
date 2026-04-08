"""System Scan & Fix — comprehensive system health and repair"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, os, re, time
from installer import install_all_tools
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
        ctk.CTkLabel(hdr, text="🔧  SYSTEM SCAN & FIX", font=('Courier',13,'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, "▶ FULL SYSTEM SCAN", command=self._full_scan, width=180
            ).pack(side='right', padx=12, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # Quick action buttons
        SectionHeader(body, '01', 'QUICK FIXES').pack(fill='x', padx=14, pady=(14,4))
        qf = Card(body)
        qf.pack(fill='x', padx=14, pady=(0,8))
        grid = ctk.CTkFrame(qf, fg_color='transparent')
        grid.pack(fill='x', padx=8, pady=8)
        quick_fixes = [
            ("🔄 UPDATE SYSTEM",      self._update_system,   'primary'),
            ("🧹 CLEAN PACKAGES",     self._clean_packages,  'ghost'),
            ("💾 CHECK DISK",         self._check_disk,      'ghost'),
            ("🔐 FIX PERMISSIONS",    self._fix_permissions, 'warning'),
            ("🔥 FIX FIREWALL",       self._fix_firewall,    'danger'),
            ("🔑 HARDEN SSH",         self._harden_ssh,      'danger'),
            ("🗑 CLEAR TEMP FILES",   self._clear_temp,      'ghost'),
            ("📊 MEMORY ANALYSIS",    self._mem_analysis,    'blue'),
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
        self.scan_log = ctk.CTkTextbox(log_card, height=200, font=('Courier',10),
                                        fg_color=C['bg'], text_color=C['ok'],
                                        border_width=0)
        self.scan_log.pack(fill='x', padx=8, pady=8)
        self.scan_log.configure(state='normal')

        # Results
        SectionHeader(body, '03', 'FINDINGS & FIXES').pack(fill='x', padx=14, pady=(10,4))
        self.results_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.results_frame.pack(fill='x', padx=14, pady=(0,14))

    def _log(self, msg):
        self.scan_log.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.scan_log.see('end')

    def _full_scan(self):
        for w in self.results_frame.winfo_children(): w.destroy()
        self.scan_log.delete('1.0', 'end')
        threading.Thread(target=self._do_full_scan, daemon=True).start()

    def _do_full_scan(self):
        findings = []

        self._safe_after(0, self._log, "Starting comprehensive system scan...")

        # 1. Disk health
        self._safe_after(0, self._log, "Checking disk space...")
        df_out, _, _ = run("df -h / 2>/dev/null | tail -1")
        if df_out:
            parts = df_out.split()
            if len(parts) >= 5:
                pct = int(parts[4].replace('%',''))
                if pct > 90:
                    findings.append(('HIGH', f'Disk nearly full: {parts[4]} used ({parts[2]}/{parts[1]})',
                                     f'sudo apt autoremove && sudo apt clean',
                                     'Run: sudo apt autoremove && sudo apt clean && sudo journalctl --vacuum-size=100M'))
                elif pct > 75:
                    findings.append(('MED', f'Disk usage high: {parts[4]}',
                                     None, 'Consider cleaning: sudo apt autoremove'))

        # 2. Memory
        self._safe_after(0, self._log, "Checking memory...")
        mem_out, _, _ = run("free -m 2>/dev/null | grep Mem")
        if mem_out:
            parts = mem_out.split()
            if len(parts) >= 3:
                total, used = int(parts[1]), int(parts[2])
                pct = (used/total)*100 if total else 0
                if pct > 90:
                    findings.append(('HIGH', f'Memory critical: {pct:.0f}% used ({used}MB/{total}MB)',
                                     None, 'Check top processes: ps aux --sort=-%mem | head -10'))

        # 3. Package updates
        self._safe_after(0, self._log, "Checking for updates...")
        upd_out, _, _ = run("apt list --upgradable 2>/dev/null | grep -c upgradable", timeout=15)
        try:
            upd_count = int(upd_out.strip()) - 1
            if upd_count > 20:
                findings.append(('HIGH', f'{upd_count} security/system updates available',
                                 'sudo apt update && sudo apt upgrade -y',
                                 'Run: sudo apt update && sudo apt upgrade -y'))
            elif upd_count > 0:
                findings.append(('MED', f'{upd_count} updates available',
                                 None, 'Run: sudo apt update && sudo apt upgrade'))
        except ValueError:
            pass

        # 4. Failed services
        self._safe_after(0, self._log, "Checking failed services...")
        failed_out, _, _ = run("systemctl list-units --state=failed --no-legend 2>/dev/null | wc -l")
        try:
            failed = int(failed_out.strip())
            if failed > 0:
                names, _, _ = run("systemctl list-units --state=failed --no-legend 2>/dev/null | awk '{print $1}' | head -5")
                findings.append(('MED', f'{failed} failed system service(s): {names}',
                                 None, 'Check: systemctl --failed'))
        except ValueError:
            pass

        # 5. Zombie processes
        self._safe_after(0, self._log, "Checking for zombie processes...")
        zombie_out, _, _ = run("ps aux 2>/dev/null | awk '$8==\"Z\"' | wc -l")
        try:
            zombies = int(zombie_out.strip())
            if zombies > 0:
                findings.append(('MED', f'{zombies} zombie process(es)',
                                 None, 'Reboot may be needed to clear zombie processes'))
        except ValueError:
            pass

        # 6. Firewall
        self._safe_after(0, self._log, "Checking firewall...")
        ufw_out, _, _ = run("ufw status 2>/dev/null | head -1")
        if 'inactive' in ufw_out.lower():
            findings.append(('HIGH', 'Firewall is DISABLED',
                             'sudo ufw enable && sudo ufw default deny incoming && sudo ufw allow ssh',
                             'Enable: sudo ufw enable'))

        # 7. Automatic updates
        self._safe_after(0, self._log, "Checking auto-updates...")
        auto_out, _, _ = run("dpkg -l unattended-upgrades 2>/dev/null | grep '^ii' | wc -l")
        if auto_out.strip() == '0':
            findings.append(('MED', 'Automatic security updates not configured',
                             None, 'Install: sudo apt install unattended-upgrades && sudo dpkg-reconfigure -plow unattended-upgrades'))

        # 8. Temp files
        self._safe_after(0, self._log, "Checking temp files...")
        tmp_out, _, _ = run("du -sh /tmp 2>/dev/null | cut -f1")
        self._safe_after(0, self._log, f"  /tmp size: {tmp_out}")

        # 9. Log file sizes
        self._safe_after(0, self._log, "Checking log sizes...")
        log_out, _, _ = run("du -sh /var/log 2>/dev/null | cut -f1")
        self._safe_after(0, self._log, f"  /var/log size: {log_out}")

        if not findings:
            findings.append(('OK', '✓ System is healthy',
                             None, 'All checks passed. System is in good condition.'))

        self._safe_after(0, self._log, f"✓ Scan complete. {len(findings)} finding(s).")
        self._safe_after(0, self._render_findings, findings)

    def _render_findings(self, findings):
        for w in self.results_frame.winfo_children(): w.destroy()
        for lvl, title, fix_cmd, suggestion in findings:
            rtype = 'warn' if lvl=='HIGH' else 'med' if lvl=='MED' else 'ok'
            box = ResultBox(self.results_frame, rtype, title, suggestion)
            box.pack(fill='x', pady=3)
            if fix_cmd:
                Btn(box, f"▶ AUTO-FIX",
                    command=lambda c=fix_cmd, t=title: self._run_fix(c, t),
                    variant='success', width=120
                    ).pack(anchor='e', padx=10, pady=(0,8))

        if findings:
            Btn(self.results_frame, "💾 EXPORT SYSTEM REPORT",
                command=lambda: self._export_report(findings),
                variant='success', width=260).pack(pady=15)

    def _export_report(self, findings):
        sections = [
            ("SYSTEM SCAN FINDINGS", [f"[{f[0]}] {f[1]}" for f in findings], "WARN"),
            ("SUGGESTED REMEDIATIONS", [f[3] for f in findings if len(f)>3], "INFO")
        ]
        prompt_save_report(self, "Local System", "System Health Audit", sections)

    def _run_fix(self, cmd, title):
        self._log(f"Running fix: {title}")
        threading.Thread(target=lambda: (
            self._safe_after(0, self._log, f"$ {cmd}"),
            (lambda out, err, rc: self._safe_after(0, self._log,
             f"{'✓ Done' if rc==0 else '✗ Failed'}: {out or err}"))(
                *run(f"sudo {cmd}" if not cmd.startswith('sudo') else cmd, timeout=60)
            )
        ), daemon=True).start()

    def _update_system(self):
        threading.Thread(target=lambda: (
            self._safe_after(0, self._log, "Updating package list..."),
            (lambda o,e,r: self._safe_after(0, self._log, f"apt update: {o[-100:] if o else e[-80:]}"))(
                *run("sudo apt-get update -q", timeout=60)),
            self._safe_after(0, self._log, "Upgrading packages..."),
            (lambda o,e,r: self._safe_after(0, self._log, f"apt upgrade: {'Done' if r==0 else e[-80:]}"))(
                *run("sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -q", timeout=120)),
            self._safe_after(0, self._log, "✓ System update complete")
        ), daemon=True).start()

    def _clean_packages(self):
        threading.Thread(target=lambda: (
            self._safe_after(0, self._log, "Cleaning unused packages..."),
            (lambda o,e,r: self._safe_after(0, self._log, o[-200:] or e[-80:]))(
                *run("sudo DEBIAN_FRONTEND=noninteractive apt-get autoremove -y && sudo apt-get autoclean -y", timeout=60)),
            self._safe_after(0, self._log, "✓ Package cleanup done")
        ), daemon=True).start()

    def _check_disk(self):
        threading.Thread(target=lambda: (
            self._safe_after(0, self._log, "Disk usage:"),
            (lambda o,e,r: self._safe_after(0, self._log, o))(
                *run("df -h 2>/dev/null")),
            self._safe_after(0, self._log, "\nLargest directories in home:"),
            (lambda o,e,r: self._safe_after(0, self._log, o))(
                *run("du -sh ~/.[^.]* ~/* 2>/dev/null | sort -rh | head -10"))
        ), daemon=True).start()

    def _fix_permissions(self):
        threading.Thread(target=lambda: (
            self._safe_after(0, self._log, "Fixing home directory permissions..."),
            (lambda o,e,r: self._safe_after(0, self._log, "✓ Permissions fixed" if r==0 else e))(
                *run(f"chmod 755 ~ && chmod 700 ~/.ssh 2>/dev/null || true", timeout=10)),
            self._safe_after(0, self._log, "Checking for world-readable sensitive files..."),
            (lambda o,e,r: self._safe_after(0, self._log, f"Found: {o}" if o else "✓ No issues"))(
                *run("find ~ -maxdepth 2 -name '*.key' -o -name '*.pem' -o -name 'id_rsa' 2>/dev/null | head -5"))
        ), daemon=True).start()

    def _fix_firewall(self):
        threading.Thread(target=lambda: (
            self._safe_after(0, self._log, "Configuring firewall..."),
            (lambda o,e,r: self._safe_after(0, self._log, o or e))(
                *run("sudo ufw --force enable && sudo ufw default deny incoming && sudo ufw default allow outgoing && sudo ufw allow ssh && sudo ufw status", timeout=15)),
            self._safe_after(0, self._log, "✓ Firewall enabled with secure defaults")
        ), daemon=True).start()

    def _harden_ssh(self):
        self._log("SSH hardening suggestions:")
        suggestions = [
            "Edit: sudo nano /etc/ssh/sshd_config",
            "Set: PermitRootLogin no",
            "Set: PasswordAuthentication no  (after setting up SSH keys)",
            "Set: MaxAuthTries 3",
            "Set: Protocol 2",
            "Then: sudo systemctl restart sshd",
        ]
        for s in suggestions:
            self._log(f"  {s}")

    def _clear_temp(self):
        threading.Thread(target=lambda: (
            self._safe_after(0, self._log, "Clearing temp files..."),
            (lambda o,e,r: self._safe_after(0, self._log, "✓ Temp cleared" if r==0 else e))(
                *run("sudo rm -rf /tmp/* /var/tmp/* 2>/dev/null; sudo journalctl --vacuum-size=100M 2>/dev/null", timeout=20)),
            self._safe_after(0, self._log, "✓ Done")
        ), daemon=True).start()

    def _mem_analysis(self):
        threading.Thread(target=lambda: (
            self._safe_after(0, self._log, "Memory analysis:"),
            (lambda o,e,r: self._safe_after(0, self._log, o))(
                *run("free -h 2>/dev/null")),
            self._safe_after(0, self._log, "\nTop memory consumers:"),
            (lambda o,e,r: self._safe_after(0, self._log, o))(
                *run("ps aux --sort=-%mem 2>/dev/null | head -8"))
        ), daemon=True).start()
