"""System Auditor — Live Kernel Audit, Log Analysis, Binary Integrity"""
import customtkinter as ctk
import threading, subprocess, time, os, hashlib, json
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from utils import run_cmd as run

# Critical binaries to monitor
CRITICAL_BINS = [
    '/bin/ls', '/bin/ps', '/bin/netstat', '/bin/ss', '/usr/bin/sudo',
    '/usr/bin/passwd', '/usr/sbin/sshd', '/bin/bash', '/usr/bin/top'
]

class AuditorScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False
        self._monitoring = False
        self._baseline_file = os.path.expanduser('~/.mint_scan_integrity.json')

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True

    def on_blur(self):
        """Called when switching away — no background threads to stop."""
        pass

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="🕵  SYSTEM AUDITOR", font=('DejaVu Sans Mono',13,'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── 01 Live Kernel Audit ──────────────────────────────
        SectionHeader(body, '01', 'LIVE KERNEL AUDIT (auditd)').pack(fill='x', padx=14, pady=(14,4))
        audit_card = Card(body)
        audit_card.pack(fill='x', padx=14, pady=(0,8))
        
        self.audit_log = ctk.CTkTextbox(audit_card, height=120, font=('DejaVu Sans Mono',9),
                                         fg_color=C['bg'], text_color=C['tx'], border_width=0)
        self.audit_log.pack(fill='x', padx=8, pady=8)
        self.audit_log.insert('1.0', "Waiting for audit events...\n")
        
        btn_row = ctk.CTkFrame(audit_card, fg_color='transparent')
        btn_row.pack(fill='x', padx=8, pady=(0,8))
        self.audit_btn = Btn(btn_row, "▶ START MONITOR", command=self._toggle_audit, width=140)
        self.audit_btn.pack(side='left')
        ctk.CTkLabel(btn_row, text="Requires 'auditd' package", font=MONO_SM, text_color=C['mu']).pack(side='left', padx=12)

        # ── 02 Log Analysis ───────────────────────────────────
        SectionHeader(body, '02', 'AUTH LOG ANALYSIS').pack(fill='x', padx=14, pady=(10,4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0,8))
        
        self.log_res = ctk.CTkLabel(log_card, text="Tap ANALYSE to scan /var/log/auth.log",
                                     font=MONO_SM, text_color=C['mu'], justify='left')
        self.log_res.pack(anchor='w', padx=12, pady=12)
        Btn(log_card, "🔍 ANALYSE LOGS", command=self._analyse_logs, variant='primary', width=140).pack(anchor='w', padx=12, pady=(0,12))

        # ── 03 Binary Integrity ───────────────────────────────
        SectionHeader(body, '03', 'BINARY INTEGRITY CHECK').pack(fill='x', padx=14, pady=(10,4))
        int_card = Card(body)
        int_card.pack(fill='x', padx=14, pady=(0,8))
        
        self.int_res = ResultBox(int_card, 'info', 'INTEGRITY STATUS', 'No baseline found. Create one first.')
        self.int_res.pack(fill='x', padx=8, pady=8)
        self._int_card = int_card  # store ref for later updates
        
        b_row = ctk.CTkFrame(int_card, fg_color='transparent')
        b_row.pack(fill='x', padx=8, pady=(0,8))
        Btn(b_row, "💾 CREATE BASELINE", command=self._create_baseline, variant='ghost', width=160).pack(side='left', padx=4)
        Btn(b_row, "🛡 VERIFY BINARIES", command=self._verify_integrity, variant='warning', width=160).pack(side='left', padx=4)

    def _toggle_audit(self):
        if self._monitoring:
            self._monitoring = False
            self.audit_btn.configure(text="▶ START MONITOR", variant='primary')
            self.audit_log.insert('end', "\n[Stopped]\n")
        else:
            self._monitoring = True
            self.audit_btn.configure(text="⏹ STOP MONITOR", variant='danger')
            self.audit_log.delete('1.0', 'end')
            threading.Thread(target=self._monitor_audit, daemon=True).start()

    def _monitor_audit(self):
        # Tail audit.log or run ausearch -m USER_AUTH,EXECVE -ts recent -w
        # Fallback to tailing /var/log/auth.log if auditd missing
        cmd = "tail -f /var/log/audit/audit.log 2>/dev/null"
        if not os.path.exists('/var/log/audit/audit.log'):
             cmd = "tail -f /var/log/auth.log"
        
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        while self._monitoring:
            line = proc.stdout.readline()
            if line:
                (self.audit_log.insert('end', line) if self.winfo_exists() else None)
                self.audit_log.see('end')
            else:
                time.sleep(0.1)
        proc.terminate()

    def _analyse_logs(self):
        self.log_res.configure(text="Scanning logs...", text_color=C['ac'])
        threading.Thread(target=self._do_log_analysis, daemon=True).start()

    def _do_log_analysis(self):
        # Grep for failed logins, sudo abuse
        failed, _, _ = run("grep -c 'Failed password' /var/log/auth.log")
        sudo_fail, _, _ = run("grep -c 'sudo:.*command not found' /var/log/auth.log")
        root_login, _, _ = run("grep -c 'session opened for user root' /var/log/auth.log")
        
        msg = (f"• Failed SSH/Login Attempts: {failed}\n"
               f"• Failed Sudo Commands: {sudo_fail}\n"
               f"• Root Sessions Opened: {root_login}")
        
        self.log_res.configure(text=msg, text_color=C['tx'])

    def _create_baseline(self):
        hashes = {}
        for b in CRITICAL_BINS:
            if os.path.exists(b):
                try:
                    with open(b, "rb") as f:
                        hashes[b] = hashlib.sha256(f.read()).hexdigest()
                except Exception:
                    pass
        try:
            with open(self._baseline_file, 'w') as f:
                json.dump(hashes, f)
            self.int_res.destroy()
            self.int_res = ResultBox(self._int_card, 'ok', 'BASELINE CREATED', f"Hashed {len(hashes)} binaries.")
            self.int_res.pack(fill='x', padx=8, pady=8)
        except Exception as e:
            pass

    def _verify_integrity(self):
        if not os.path.exists(self._baseline_file):
            return
        
        with open(self._baseline_file) as f:
            baseline = json.load(f)
        
        changed = []
        for b, old_hash in baseline.items():
            if os.path.exists(b):
                try:
                    with open(b, "rb") as f:
                        new_hash = hashlib.sha256(f.read()).hexdigest()
                    if new_hash != old_hash:
                        changed.append(b)
                except Exception:
                    pass
            else:
                changed.append(f"{b} (MISSING)")
        
        self.int_res.destroy()
        parent = self._int_card  # use stored ref instead of fragile winfo_children[-1]
        if changed:
             self.int_res = ResultBox(parent, 'warn', 'INTEGRITY VIOLATION', f"Modified/Missing: {', '.join(changed)}")
        else:
             self.int_res = ResultBox(parent, 'ok', 'INTEGRITY VERIFIED', "All monitored binaries match baseline.")
        self.int_res.pack(fill='x', padx=8, pady=8)
