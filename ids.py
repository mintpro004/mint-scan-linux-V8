"""
Mint Scan v8 — IDS/IPS Integration (Snort / Suricata)
Install, configure, start/stop, and view live alerts.
"""
import os, threading, time, subprocess, shutil
import tkinter as tk
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, ResultBox, InfoGrid)
from utils import run_cmd
from logger import get_logger

log = get_logger('ids')

SURICATA_LOG = '/var/log/suricata/fast.log'
SNORT_LOG    = '/var/log/snort/alert'


def detect_ids() -> dict:
    return {
        'snort':     bool(shutil.which('snort')),
        'suricata':  bool(shutil.which('suricata')),
        'suricata_log': os.path.exists(SURICATA_LOG),
        'snort_log':    os.path.exists(SNORT_LOG),
    }


def get_recent_alerts(n: int = 50) -> list:
    """Read most recent IDS alerts from Suricata or Snort log."""
    alerts = []
    # Suricata fast.log
    if os.path.exists(SURICATA_LOG):
        try:
            with open(SURICATA_LOG, 'r', errors='replace') as f:
                lines = f.readlines()[-n:]
            for l in reversed(lines):
                l = l.strip()
                if l:
                    alerts.append({'source': 'Suricata', 'line': l})
        except Exception:
            pass
    # Snort alert
    if os.path.exists(SNORT_LOG):
        try:
            with open(SNORT_LOG, 'r', errors='replace') as f:
                lines = f.readlines()[-n:]
            for l in reversed(lines):
                l = l.strip()
                if l:
                    alerts.append({'source': 'Snort', 'line': l})
        except Exception:
            pass
    return alerts[:n]


class IDSScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app     = app
        self._built  = False
        self._poll   = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._refresh()
        self._poll = True
        self._poll_loop()

    def on_blur(self):
        self._poll = False

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text='🚨  IDS/IPS — SNORT & SURICATA',
                     font=('Courier', 13, 'bold'),
                     text_color=C['wn']).pack(side='left', padx=16)
        Btn(hdr, '↺ REFRESH', command=self._refresh,
            variant='ghost', width=90).pack(side='right', padx=8, pady=6)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # Status
        SectionHeader(body, '01', 'IDS STATUS').pack(
            fill='x', padx=14, pady=(14, 4))
        self._sc = Card(body)
        self._sc.pack(fill='x', padx=14, pady=(0, 8))
        self._sgrid = ctk.CTkFrame(self._sc, fg_color='transparent')
        self._sgrid.pack(fill='x', padx=8, pady=10)

        # Controls
        SectionHeader(body, '02', 'CONTROLS').pack(
            fill='x', padx=14, pady=(8, 4))
        cc = Card(body)
        cc.pack(fill='x', padx=14, pady=(0, 8))
        br = ctk.CTkFrame(cc, fg_color='transparent')
        br.pack(fill='x', padx=12, pady=10)
        Btn(br, '▶ START SURICATA', command=self._start_suricata,
            width=170).pack(side='left', padx=(0, 6))
        Btn(br, '⏹ STOP SURICATA',  command=self._stop_suricata,
            variant='danger', width=160).pack(side='left', padx=(0, 6))
        Btn(br, '📊 TEST RULE', command=self._test_rule,
            variant='ghost', width=120).pack(side='left')

        # Install
        SectionHeader(body, '03', 'INSTALL').pack(
            fill='x', padx=14, pady=(8, 4))
        ic = Card(body)
        ic.pack(fill='x', padx=14, pady=(0, 8))
        ibr = ctk.CTkFrame(ic, fg_color='transparent')
        ibr.pack(fill='x', padx=12, pady=10)
        Btn(ibr, '⬇ INSTALL SURICATA',
            command=lambda: self._install('suricata'),
            width=180).pack(side='left', padx=(0, 8))
        Btn(ibr, '⬇ INSTALL SNORT',
            command=lambda: self._install('snort'),
            variant='blue', width=160).pack(side='left')

        # Live alerts
        SectionHeader(body, '04', 'LIVE ALERTS').pack(
            fill='x', padx=14, pady=(8, 4))
        ac = Card(body, accent=C['wn'])
        ac.pack(fill='x', padx=14, pady=(0, 8))
        self._alert_log = ctk.CTkTextbox(
            ac, height=220, font=('Courier', 9),
            fg_color=C['bg'], text_color=C['wn'], border_width=0)
        self._alert_log.pack(fill='x', padx=8, pady=8)
        self._alert_log.configure(state='normal')

        # Custom rule tester
        SectionHeader(body, '05', 'CUSTOM RULE TEST').pack(
            fill='x', padx=14, pady=(8, 4))
        rc_card = Card(body)
        rc_card.pack(fill='x', padx=14, pady=(0, 14))
        ctk.CTkLabel(rc_card,
            text='Suricata rule syntax:',
            font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,2))
        self._rule_entry = ctk.CTkEntry(
            rc_card,
            placeholder_text='alert tcp any any -> any 4444 (msg:"Metasploit"; sid:9001; rev:1;)',
            font=('Courier', 9), fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'])
        self._rule_entry.pack(fill='x', padx=12, pady=(0, 4))
        Btn(rc_card, '▶ TEST RULE', command=self._test_rule,
            width=120).pack(pady=(0, 10))

    def _refresh(self):
        ids = detect_ids()
        for w in self._sgrid.winfo_children(): w.destroy()
        InfoGrid(self._sgrid, [
            ('SNORT',        '✓ Found' if ids['snort'] else '✗ Not installed',
             C['ok'] if ids['snort'] else C['wn']),
            ('SURICATA',     '✓ Found' if ids['suricata'] else '✗ Not installed',
             C['ok'] if ids['suricata'] else C['wn']),
            ('SURICATA LOG', '✓ Active' if ids['suricata_log'] else '—',
             C['ok'] if ids['suricata_log'] else C['mu']),
            ('SNORT LOG',    '✓ Active' if ids['snort_log'] else '—',
             C['ok'] if ids['snort_log'] else C['mu']),
        ], columns=4).pack(fill='x')
        self._load_alerts()

    def _load_alerts(self):
        alerts = get_recent_alerts(60)
        self._alert_log.configure(state='normal')
        self._alert_log.delete('1.0', 'end')
        if alerts:
            for a in alerts[:30]:
                self._alert_log.insert('end',
                    f"[{a['source']}] {a['line']}\n")
        else:
            self._alert_log.insert('end',
                'No alerts found.\n'
                'Start Suricata or Snort, or check log paths:\n'
                f'  Suricata: {SURICATA_LOG}\n'
                f'  Snort:    {SNORT_LOG}\n')
        self._alert_log.configure(state='disabled')

    def _poll_loop(self):
        if not self._poll:
            return
        self._load_alerts()
        self.after(8000, self._poll_loop)

    def _start_suricata(self):
        def _bg():
            out, err, rc = run_cmd(
                'sudo suricata -D -i eth0 --pidfile /var/run/suricata.pid '
                '-l /var/log/suricata/ 2>&1 | head -5', timeout=15)
            log.info(f'Suricata start: {out or err}')
        threading.Thread(target=_bg, daemon=True).start()

    def _stop_suricata(self):
        run_cmd('sudo killall suricata 2>/dev/null')

    def _test_rule(self):
        rule = self._rule_entry.get().strip()
        if not rule:
            return
        # Write temp rule file and validate syntax
        tmp = '/tmp/mint_scan_test.rules'
        with open(tmp, 'w') as f:
            f.write(rule + '\n')
        out, err, rc = run_cmd(
            f'suricata -T -S {tmp} 2>&1 | tail -5', timeout=15)
        result = out or err or 'No output'
        self._alert_log.configure(state='normal')
        self._alert_log.insert('end', f'\n[RULE TEST] {result}\n')
        self._alert_log.configure(state='disabled')

    def _install(self, pkg):
        from installer import InstallerPopup
        InstallerPopup(self, f'Install {pkg}',
                       [f'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}'],
                       f'{pkg} installed!')

