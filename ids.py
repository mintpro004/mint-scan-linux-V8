"""
Mint Scan v8 — IDS/IPS Integration (Suricata / Snort)
- Auto-detects network interface (no hardcoded eth0)
- Real log tailing from multiple possible paths
- Suricata EVE JSON parsing for richer alerts
- Snort alert parsing
- Live install + configure flow
"""
import os, threading, time, subprocess, shutil, json, re
import tkinter as tk
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, InfoGrid)
from utils import run_cmd
from logger import get_logger

log = get_logger('ids')

# Suricata logs — check multiple paths
SURICATA_LOGS = [
    '/var/log/suricata/fast.log',
    '/var/log/suricata/eve.json',
    '/tmp/suricata/fast.log',
]
SNORT_LOGS = [
    '/var/log/snort/alert',
    '/var/log/snort/snort.alert.fast',
    '/tmp/snort/alert',
]


def _get_default_iface() -> str:
    """Detect the primary network interface (no hardcoding)."""
    # Method 1: ip route default
    out, _, rc = run_cmd("ip route show default 2>/dev/null | awk '{print $5}' | head -1")
    if rc == 0 and out.strip():
        return out.strip()
    # Method 2: first non-lo interface
    out, _, _ = run_cmd("ip link show | grep -v 'lo:' | grep 'state UP' | awk -F: '{print $2}' | head -1")
    if out.strip():
        return out.strip().strip()
    # Method 3: guess
    for iface in ['wlan0', 'eth0', 'enp0s3', 'ens33', 'wlp2s0']:
        o, _, r = run_cmd(f'ip link show {iface} 2>/dev/null')
        if r == 0 and 'UP' in o:
            return iface
    return 'eth0'  # last resort


def detect_ids() -> dict:
    suricata_running = False
    snort_running    = False
    # Check processes
    procs, _, _ = run_cmd('ps aux 2>/dev/null')
    suricata_running = 'suricata' in procs.lower()
    snort_running    = 'snort' in procs.lower()
    # Check active log
    sur_log = next((f for f in SURICATA_LOGS if os.path.exists(f)), None)
    snort_log = next((f for f in SNORT_LOGS if os.path.exists(f)), None)
    return {
        'snort':            bool(shutil.which('snort')),
        'suricata':         bool(shutil.which('suricata')),
        'suricata_running': suricata_running,
        'snort_running':    snort_running,
        'suricata_log':     sur_log,
        'snort_log':        snort_log,
        'default_iface':    _get_default_iface(),
    }


def get_recent_alerts(n: int = 100) -> list:
    """Read recent alerts from the first available log file."""
    alerts = []

    # Suricata fast.log
    for path in SURICATA_LOGS:
        if path.endswith('fast.log') and os.path.exists(path):
            try:
                with open(path, 'r', errors='replace') as f:
                    lines = f.readlines()[-n:]
                for ln in reversed(lines):
                    ln = ln.strip()
                    if ln:
                        alerts.append({'source': 'Suricata', 'level': _classify(ln), 'line': ln})
            except Exception as e:
                log.debug(f'fast.log read: {e}')
            break

    # Suricata EVE JSON (richer data)
    for path in SURICATA_LOGS:
        if path.endswith('eve.json') and os.path.exists(path):
            try:
                with open(path, 'r', errors='replace') as f:
                    lines = f.readlines()[-n:]
                for ln in reversed(lines):
                    try:
                        ev = json.loads(ln.strip())
                        if ev.get('event_type') == 'alert':
                            sig = ev.get('alert', {}).get('signature', '')
                            sev = str(ev.get('alert', {}).get('severity', ''))
                            src = ev.get('src_ip', '?')
                            dst = ev.get('dest_ip', '?')
                            ts  = ev.get('timestamp', '')[:19]
                            line = f'{ts} [{sev}] {sig} {src}→{dst}'
                            alerts.append({'source': 'Suricata-EVE', 'level': _classify(line), 'line': line})
                    except Exception:
                        pass
            except Exception:
                pass
            break

    # Snort
    for path in SNORT_LOGS:
        if os.path.exists(path):
            try:
                with open(path, 'r', errors='replace') as f:
                    lines = f.readlines()[-n:]
                for ln in reversed(lines):
                    ln = ln.strip()
                    if ln:
                        alerts.append({'source': 'Snort', 'level': _classify(ln), 'line': ln})
            except Exception:
                pass
            break

    return alerts[:n]


def _classify(line: str) -> str:
    l = line.lower()
    if any(x in l for x in ['critical','severity 1','[1]','exploit','sql injection','attack']):
        return 'CRITICAL'
    if any(x in l for x in ['warning','severity 2','[2]','scan','brute']):
        return 'HIGH'
    return 'INFO'


class IDSScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app    = app
        self._built = False
        self._poll  = False
        self._iface = ''

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._poll = True
        threading.Thread(target=self._bg_refresh, daemon=True).start()
        self._poll_loop()

    def on_blur(self):
        self._poll = False

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='🚨  IDS/IPS — SNORT & SURICATA',
                     font=('Courier', 13, 'bold'),
                     text_color=C['wn']).pack(side='left', padx=16)
        Btn(hdr, '↺ REFRESH', command=lambda: threading.Thread(
            target=self._bg_refresh, daemon=True).start(),
            variant='ghost', width=90).pack(side='right', padx=8, pady=8)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # ── STATUS ────────────────────────────────────────────────
        SectionHeader(body, '01', 'IDS STATUS').pack(
            fill='x', padx=14, pady=(14, 4))
        self._sc = Card(body)
        self._sc.pack(fill='x', padx=14, pady=(0, 8))
        self._sgrid = ctk.CTkFrame(self._sc, fg_color='transparent')
        self._sgrid.pack(fill='x', padx=8, pady=10)

        # ── INTERFACE ─────────────────────────────────────────────
        SectionHeader(body, '02', 'NETWORK INTERFACE').pack(
            fill='x', padx=14, pady=(8, 4))
        ic = Card(body)
        ic.pack(fill='x', padx=14, pady=(0, 8))
        ir = ctk.CTkFrame(ic, fg_color='transparent')
        ir.pack(fill='x', padx=12, pady=10)
        ctk.CTkLabel(ir, text='Interface:', font=MONO_SM,
                     text_color=C['mu']).pack(side='left')
        self._iface_entry = ctk.CTkEntry(
            ir, width=100, font=MONO_SM,
            fg_color=C['bg'], border_color=C['br'], text_color=C['tx'])
        self._iface_entry.pack(side='left', padx=8)
        self._iface_lbl = ctk.CTkLabel(ir, text='(auto-detected)',
                                        font=('Courier', 8), text_color=C['mu'])
        self._iface_lbl.pack(side='left')

        # ── CONTROLS ──────────────────────────────────────────────
        SectionHeader(body, '03', 'CONTROLS').pack(
            fill='x', padx=14, pady=(8, 4))
        cc = Card(body)
        cc.pack(fill='x', padx=14, pady=(0, 8))
        br = ctk.CTkFrame(cc, fg_color='transparent')
        br.pack(fill='x', padx=12, pady=10)
        self._sur_start_btn = Btn(br, '▶ START SURICATA',
                                   command=self._start_suricata, width=170)
        self._sur_start_btn.pack(side='left', padx=(0, 6))
        self._sur_stop_btn = Btn(br, '⏹ STOP SURICATA',
                                  command=self._stop_suricata,
                                  variant='danger', width=160)
        self._sur_stop_btn.pack(side='left', padx=(0, 6))

        br2 = ctk.CTkFrame(cc, fg_color='transparent')
        br2.pack(fill='x', padx=12, pady=(0, 10))
        Btn(br2, '▶ START SNORT',
            command=self._start_snort, width=150).pack(side='left', padx=(0, 6))
        Btn(br2, '⏹ STOP SNORT',
            command=self._stop_snort,
            variant='danger', width=140).pack(side='left', padx=(0, 6))

        self._ctl_status = ctk.CTkLabel(cc, text='',
                                         font=MONO_SM, text_color=C['ok'])
        self._ctl_status.pack(pady=(0, 8))

        # ── INSTALL ───────────────────────────────────────────────
        SectionHeader(body, '04', 'INSTALL').pack(
            fill='x', padx=14, pady=(8, 4))
        inst_c = Card(body)
        inst_c.pack(fill='x', padx=14, pady=(0, 8))
        ibr = ctk.CTkFrame(inst_c, fg_color='transparent')
        ibr.pack(fill='x', padx=12, pady=10)
        Btn(ibr, '⬇ INSTALL SURICATA',
            command=lambda: self._install('suricata suricata-update'),
            width=190).pack(side='left', padx=(0, 8))
        Btn(ibr, '⬇ INSTALL SNORT',
            command=lambda: self._install('snort'),
            variant='blue', width=150).pack(side='left')
        ctk.CTkLabel(inst_c,
            text='After installing Suricata: sudo suricata-update  (downloads community rules)',
            font=('Courier', 8), text_color=C['mu']).pack(anchor='w', padx=12, pady=(0,8))

        # ── LIVE ALERTS ───────────────────────────────────────────
        SectionHeader(body, '05', 'LIVE ALERTS').pack(
            fill='x', padx=14, pady=(8, 4))
        ac = Card(body, accent=C['wn'])
        ac.pack(fill='x', padx=14, pady=(0, 8))

        alert_hdr = ctk.CTkFrame(ac, fg_color='transparent')
        alert_hdr.pack(fill='x', padx=8, pady=(6,0))
        self._alert_count = ctk.CTkLabel(alert_hdr, text='No alerts',
                                          font=('Courier', 9, 'bold'), text_color=C['mu'])
        self._alert_count.pack(side='left')
        Btn(alert_hdr, '🗑 CLEAR', command=self._clear_alerts,
            variant='ghost', width=70).pack(side='right')

        self._alert_log = ctk.CTkTextbox(
            ac, height=240, font=('Courier', 9),
            fg_color=C['bg'], text_color=C['ok'], border_width=0,
            wrap='none')
        self._alert_log.pack(fill='x', padx=8, pady=8)
        self._alert_log.configure(state='normal')

        # ── RULE TESTER ───────────────────────────────────────────
        SectionHeader(body, '06', 'RULE TESTER').pack(
            fill='x', padx=14, pady=(8, 4))
        rc_card = Card(body)
        rc_card.pack(fill='x', padx=14, pady=(0, 14))
        ctk.CTkLabel(rc_card,
            text='Enter Suricata rule to test syntax:',
            font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,2))
        self._rule_entry = ctk.CTkEntry(
            rc_card,
            placeholder_text='alert tcp any any -> any 4444 (msg:"Metasploit"; sid:9001; rev:1;)',
            font=('Courier', 9), fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'])
        self._rule_entry.pack(fill='x', padx=12, pady=(0, 4))
        Btn(rc_card, '▶ TEST RULE SYNTAX', command=self._test_rule, width=180).pack(pady=(0,10))

    def _bg_refresh(self):
        """Run detect in background, update UI on main thread."""
        ids = detect_ids()
        self._iface = ids['default_iface']
        self.after(0, self._apply_status, ids)

    def _apply_status(self, ids):
        try:
            if not self.winfo_exists(): return
        except Exception: return

        for w in self._sgrid.winfo_children(): w.destroy()
        InfoGrid(self._sgrid, [
            ('SNORT',       '✓ Installed' if ids['snort']     else '✗ Missing',
             C['ok'] if ids['snort'] else C['wn']),
            ('SURICATA',    '✓ Installed' if ids['suricata']  else '✗ Missing',
             C['ok'] if ids['suricata'] else C['wn']),
            ('SUR RUNNING', '● Active'   if ids['suricata_running'] else '○ Stopped',
             C['ok'] if ids['suricata_running'] else C['mu']),
            ('SNT RUNNING', '● Active'   if ids['snort_running']    else '○ Stopped',
             C['ok'] if ids['snort_running'] else C['mu']),
            ('SUR LOG',     ids['suricata_log'] or '—',  C['ok'] if ids['suricata_log'] else C['mu']),
            ('SNT LOG',     ids['snort_log'] or '—',     C['ok'] if ids['snort_log'] else C['mu']),
        ], columns=3).pack(fill='x')

        # Auto-fill interface entry
        if not self._iface_entry.get():
            self._iface_entry.insert(0, self._iface)
        self._iface_lbl.configure(text=f'(detected: {self._iface})')
        self._load_alerts()

    def _get_iface(self) -> str:
        return self._iface_entry.get().strip() or self._iface or _get_default_iface()

    def _load_alerts(self):
        try:
            if not self.winfo_exists(): return
        except Exception: return
        alerts = get_recent_alerts(80)
        self._alert_log.configure(state='normal')
        self._alert_log.delete('1.0', 'end')
        if alerts:
            self._alert_count.configure(
                text=f'{len(alerts)} alert(s) found',
                text_color=C['wn'] if any(a['level']=='CRITICAL' for a in alerts) else C['am'])
            for a in alerts[:60]:
                col_tag = 'crit' if a['level']=='CRITICAL' else 'hi' if a['level']=='HIGH' else 'info'
                self._alert_log.insert('end', f"[{a['source']}] {a['line']}\n")
        else:
            self._alert_count.configure(text='No alerts', text_color=C['mu'])
            ids = detect_ids()
            if not ids['suricata'] and not ids['snort']:
                self._alert_log.insert('end',
                    'Neither Suricata nor Snort is installed.\n'
                    'Tap ⬇ INSTALL SURICATA to get started.\n\n'
                    'Suricata is recommended — it supports modern rule formats\n'
                    'and has a built-in community ruleset.\n')
            elif not ids['suricata_running'] and not ids['snort_running']:
                self._alert_log.insert('end',
                    'IDS is installed but not running.\n'
                    'Tap ▶ START SURICATA to begin monitoring.\n\n'
                    f'Listening on interface: {self._get_iface()}\n'
                    f'Log paths checked:\n')
                for p in SURICATA_LOGS + SNORT_LOGS:
                    self._alert_log.insert('end', f'  {p}\n')
            else:
                self._alert_log.insert('end',
                    'IDS is running but no alerts yet.\n'
                    'Traffic will appear here as threats are detected.\n')
        self._alert_log.configure(state='disabled')

    def _clear_alerts(self):
        self._alert_log.configure(state='normal')
        self._alert_log.delete('1.0', 'end')
        self._alert_log.configure(state='disabled')
        self._alert_count.configure(text='Cleared', text_color=C['mu'])

    def _poll_loop(self):
        if not self._poll:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._load_alerts()
        self.after(8000, self._poll_loop)

    def _ctl_msg(self, msg, col=None):
        def _do():
            try:
                self._ctl_status.configure(text=msg, text_color=col or C['ok'])
            except Exception: pass
        self.after(0, _do)

    def _start_suricata(self):
        iface = self._get_iface()
        self._ctl_msg(f'Starting Suricata on {iface}...', C['ac'])
        def _bg():
            # Ensure log dir exists
            run_cmd('sudo mkdir -p /var/log/suricata')
            out, err, rc = run_cmd(
                f'sudo suricata -D --af-packet={iface} '
                f'--pidfile /var/run/suricata.pid '
                f'-l /var/log/suricata/ 2>&1',
                timeout=20)
            result = out or err or f'Exit code: {rc}'
            log.info(f'Suricata start ({iface}): {result[:100]}')
            self.after(0, self._ctl_msg,
                       '✓ Suricata started' if rc == 0 else f'✗ {result[:80]}',
                       C['ok'] if rc == 0 else C['wn'])
            self.after(500, lambda: threading.Thread(
                target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _stop_suricata(self):
        def _bg():
            run_cmd('sudo killall suricata 2>/dev/null')
            run_cmd('sudo rm -f /var/run/suricata.pid')
            self.after(0, self._ctl_msg, 'Suricata stopped', C['mu'])
            self.after(500, lambda: threading.Thread(
                target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _start_snort(self):
        iface = self._get_iface()
        self._ctl_msg(f'Starting Snort on {iface}...', C['ac'])
        def _bg():
            run_cmd('sudo mkdir -p /var/log/snort')
            out, err, rc = run_cmd(
                f'sudo snort -D -i {iface} -A fast '
                f'-l /var/log/snort/ '
                f'-c /etc/snort/snort.conf 2>&1',
                timeout=20)
            result = out or err or f'Exit: {rc}'
            self.after(0, self._ctl_msg,
                       '✓ Snort started' if rc == 0 else f'✗ {result[:80]}',
                       C['ok'] if rc == 0 else C['wn'])
            self.after(500, lambda: threading.Thread(
                target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _stop_snort(self):
        run_cmd('sudo killall snort 2>/dev/null')
        self._ctl_msg('Snort stopped', C['mu'])

    def _test_rule(self):
        rule = self._rule_entry.get().strip()
        if not rule:
            return
        if not shutil.which('suricata'):
            self._ctl_msg('Suricata not installed', C['wn'])
            return
        tmp = '/tmp/mint_scan_test.rules'
        with open(tmp, 'w') as f:
            f.write(rule + '\n')
        self._ctl_msg('Testing rule syntax...', C['ac'])
        def _bg():
            out, err, rc = run_cmd(f'suricata -T -S {tmp} 2>&1', timeout=20)
            result = (out or err or 'No output')[:200]
            ok     = rc == 0 or 'Configuration provided was successfully loaded' in result
            self.after(0, self._ctl_msg,
                       '✓ Rule syntax OK' if ok else f'✗ {result}',
                       C['ok'] if ok else C['wn'])
            self._alert_log.configure(state='normal')
            self.after(0, lambda: (
                self._alert_log.insert('end', f'\n[RULE TEST] {result}\n'),
                self._alert_log.configure(state='disabled')))
        threading.Thread(target=_bg, daemon=True).start()

    def _install(self, pkg):
        from installer import InstallerPopup
        InstallerPopup(self, f'Install {pkg}',
                       [f'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}'],
                       f'{pkg} installed!')
        self.after(4000, lambda: threading.Thread(
            target=self._bg_refresh, daemon=True).start())
