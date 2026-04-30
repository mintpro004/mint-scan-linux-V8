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
        ctk.CTkLabel(hdr, text="🔧  SYSTEM SCAN & FIX", font=('DejaVu Sans Mono',13,'bold'),
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
                            findings.append(('HIGH', f'Disk nearly full: {parts[4]} used ({parts[2]}/{parts[1]})',
                                             'apt autoremove && apt clean',
                                             'Run: sudo apt autoremove && sudo apt clean && sudo journalctl --vacuum-size=100M'))
                        elif pct > 75:
                            findings.append(('MED', f'Disk usage high: {parts[4]}',
                                             None, 'Consider cleaning: sudo apt autoremove'))
                    except ValueError: pass

        # 2. Memory
        self._safe_after(0, self._log, "Checking memory...")
        mem_out, _, _ = run(["free", "-m"])
        if mem_out:
            for line in mem_out.splitlines():
                if 'Mem:' in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        total, used = int(parts[1]), int(parts[2])
                        pct = (used/total)*100 if total else 0
                        if pct > 90:
                            findings.append(('HIGH', f'Memory critical: {pct:.0f}% used ({used}MB/{total}MB)',
                                             None, 'Check top processes: ps aux --sort=-%mem | head -10'))
                    break

        # 3. Package updates
        self._safe_after(0, self._log, "Checking for updates...")
        # We use a simple check; full 'apt list' is slow
        upd_out, _, _ = run(["sudo", "apt-get", "-s", "upgrade"], timeout=20)
        upd_match = re.search(r'(\d+) upgraded, (\d+) newly installed', upd_out)
        if upd_match:
            upd_count = int(upd_match.group(1))
            if upd_count > 20:
                findings.append(('HIGH', f'{upd_count} security/system updates available',
                                 'apt update && apt upgrade -y',
                                 'Run: sudo apt update && sudo apt upgrade -y'))
            elif upd_count > 0:
                findings.append(('MED', f'{upd_count} updates available',
                                 None, 'Run: sudo apt update && sudo apt upgrade'))

        # 4. Failed services
        self._safe_after(0, self._log, "Checking failed services...")
        failed_out, _, _ = run(["systemctl", "list-units", "--state=failed", "--no-legend"])
        if failed_out:
            failed_count = len(failed_out.splitlines())
            if failed_count > 0:
                findings.append(('MED', f'{failed_count} failed system service(s)',
                                 None, 'Check: systemctl --failed'))

        # 5. Zombie processes
        self._safe_after(0, self._log, "Checking for zombie processes...")
        z_out, _, _ = run(["ps", "aux"])
        zombies = z_out.count(" <defunct>")
        if zombies > 0:
            findings.append(('MED', f'{zombies} zombie process(es)',
                             None, 'Reboot may be needed to clear zombie processes'))

        # 6. Firewall
        self._safe_after(0, self._log, "Checking firewall...")
        ufw_out, _, _ = run(["sudo", "ufw", "status"])
        if 'inactive' in ufw_out.lower():
            findings.append(('HIGH', 'Firewall is DISABLED',
                             'ufw enable',
                             'Enable: sudo ufw enable'))

        # 7. Automatic updates
        self._safe_after(0, self._log, "Checking auto-updates...")
        auto_out, _, _ = run(["dpkg", "-l", "unattended-upgrades"])
        if 'ii' not in auto_out:
            findings.append(('MED', 'Automatic security updates not configured',
                             None, 'Install: sudo apt install unattended-upgrades'))

        # 8. Temp files
        self._safe_after(0, self._log, "Checking temp files...")
        tmp_out, _, _ = run(["du", "-sh", "/tmp"])
        self._safe_after(0, self._log, f"  /tmp size: {tmp_out.split()[0] if tmp_out else '?'}")

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
        def _bg():
            self._safe_after(0, self._log, "Updating package list...")
            run(["sudo", "apt-get", "update", "-q"], timeout=60)
            self._safe_after(0, self._log, "Upgrading packages...")
            out, err, rc = run(["sudo", "DEBIAN_FRONTEND=noninteractive", "apt-get", "upgrade", "-y", "-q"], timeout=120)
            self._safe_after(0, self._log, "✓ System update complete" if rc==0 else f"✗ Update failed: {err}")
        threading.Thread(target=_bg, daemon=True).start()

    def _clean_packages(self):
        def _bg():
            self._safe_after(0, self._log, "Cleaning unused packages...")
            run(["sudo", "apt-get", "autoremove", "-y"], timeout=60)
            run(["sudo", "apt-get", "autoclean", "-y"], timeout=60)
            self._safe_after(0, self._log, "✓ Package cleanup done")
        threading.Thread(target=_bg, daemon=True).start()

    def _check_disk(self):
        def _bg():
            self._safe_after(0, self._log, "Disk usage:")
            out, _, _ = run(["df", "-h"])
            self._safe_after(0, self._log, out)
            self._safe_after(0, self._log, "\nLargest files in home:")
            # We use a limited find to avoid long waits
            out, _, _ = run(["find", os.path.expanduser("~"), "-maxdepth", "2", "-type", "f", "-size", "+100M"])
            self._safe_after(0, self._log, out or "No files > 100MB found in home root.")
        threading.Thread(target=_bg, daemon=True).start()

    def _fix_permissions(self):
        def _bg():
            self._safe_after(0, self._log, "Fixing home directory permissions...")
            run(["chmod", "755", os.path.expanduser("~")])
            ssh_dir = os.path.expanduser("~/.ssh")
            if os.path.exists(ssh_dir):
                run(["chmod", "700", ssh_dir])
            self._safe_after(0, self._log, "✓ Permissions fixed")
        threading.Thread(target=_bg, daemon=True).start()

    def _fix_firewall(self):
        def _bg():
            self._safe_after(0, self._log, "Configuring firewall...")
            run(["sudo", "ufw", "--force", "enable"])
            run(["sudo", "ufw", "default", "deny", "incoming"])
            run(["sudo", "ufw", "default", "allow", "outgoing"])
            run(["sudo", "ufw", "allow", "ssh"])
            self._safe_after(0, self._log, "✓ Firewall enabled with secure defaults")
        threading.Thread(target=_bg, daemon=True).start()

    def _harden_ssh(self):
        self._log("SSH hardening suggestions:")
        suggestions = [
            "1. Disable root login: PermitRootLogin no",
            "2. Disable password auth: PasswordAuthentication no",
            "3. Use protocol 2 only: Protocol 2",
            "4. Limit auth attempts: MaxAuthTries 3",
            "Location: /etc/ssh/sshd_config"
        ]
        for s in suggestions:
            self._log(f"  {s}")

    def _clear_temp(self):
        def _bg():
            self._safe_after(0, self._log, "Clearing temp files...")
            # Selective clear to avoid breaking running procs
            run(["sudo", "find", "/tmp", "-mindepth", "1", "-atime", "+1", "-delete"])
            run(["sudo", "journalctl", "--vacuum-size=100M"])
            self._safe_after(0, self._log, "✓ Done")
        threading.Thread(target=_bg, daemon=True).start()

    def _mem_analysis(self):
        def _bg():
            self._safe_after(0, self._log, "Memory analysis:")
            out, _, _ = run(["free", "-h"])
            self._safe_after(0, self._log, out)
            self._safe_after(0, self._log, "\nTop memory consumers:")
            out, _, _ = run(["ps", "aux", "--sort=-%mem"])
            self._safe_after(0, self._log, "\n".join(out.splitlines()[:8]))
        threading.Thread(target=_bg, daemon=True).start()
