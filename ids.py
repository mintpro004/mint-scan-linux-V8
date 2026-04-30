"""
Mint Scan v8 — IDS/IPS Integration (Suricata / Snort)
Industry-standard implementation:
- Auto-detects network interface (never hardcoded)
- Dynamic controls: install button hides once tool is present
- Full EVE JSON + fast.log parsing
- Suricata community rules auto-update
- Snort debconf pre-seeding (no interactive prompts)
- Real-time alert polling with on_blur/on_focus lifecycle
"""
import os, threading, time, subprocess, shutil, json, re
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, InfoGrid)
from utils import run_cmd
from logger import get_logger

log = get_logger('ids')

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
    """Detect active network interface — never hardcoded."""
    # Method 1: default route interface
    out, _, rc = run_cmd(
        "ip route show default 2>/dev/null | awk 'NR==1{print $5}'", timeout=4)
    if rc == 0 and out.strip():
        return out.strip()
    # Method 2: first UP non-loopback interface
    out2, _, _ = run_cmd(
        "ip -o link show up 2>/dev/null | awk -F': ' '{print $2}' | grep -v '^lo$' | head -1",
        timeout=4)
    if out2.strip():
        return out2.strip()
    # Method 3: wireless interface
    out3, _, _ = run_cmd("iw dev 2>/dev/null | awk '/Interface/{print $2}' | head -1", timeout=3)
    if out3.strip():
        return out3.strip()
    return 'eth0'


def detect_ids() -> dict:
    procs, _, _ = run_cmd('ps aux 2>/dev/null', timeout=5)
    sur_log   = next((f for f in SURICATA_LOGS if os.path.exists(f)), None)
    snort_log = next((f for f in SNORT_LOGS if os.path.exists(f)), None)
    sur_bin   = shutil.which('suricata')
    snort_bin = shutil.which('snort')
    # Check if suricata is running via systemd too
    sur_svc, _, sur_svc_rc = run_cmd('systemctl is-active suricata 2>/dev/null', timeout=3)
    return {
        'suricata':         bool(sur_bin),
        'suricata_path':    sur_bin or '',
        'suricata_running': ('suricata' in procs.lower() or
                             (sur_svc_rc == 0 and sur_svc.strip() == 'active')),
        'suricata_log':     sur_log,
        'snort':            bool(snort_bin),
        'snort_path':       snort_bin or '',
        'snort_running':    'snort' in procs.lower(),
        'snort_log':        snort_log,
        'default_iface':    _get_default_iface(),
    }


def get_recent_alerts(n: int = 100) -> list:
    """Parse both fast.log and EVE JSON — return most recent alerts."""
    alerts = []

    # Suricata fast.log
    for path in SURICATA_LOGS:
        if path.endswith('fast.log') and os.path.exists(path):
            try:
                lines = open(path, errors='replace').readlines()[-n:]
                for ln in reversed(lines):
                    ln = ln.strip()
                    if ln:
                        alerts.append({'source': 'Suricata', 'line': ln,
                                       'level': _classify(ln)})
            except Exception:
                pass
            break

    # Suricata EVE JSON (richer data)
    for path in SURICATA_LOGS:
        if path.endswith('eve.json') and os.path.exists(path):
            try:
                lines = open(path, errors='replace').readlines()[-n:]
                for ln in reversed(lines):
                    try:
                        ev = json.loads(ln)
                        if ev.get('event_type') == 'alert':
                            al  = ev.get('alert', {})
                            sig = al.get('signature', 'Unknown')
                            sev = al.get('severity', '?')
                            src = ev.get('src_ip', '?')
                            dst = ev.get('dest_ip', '?')
                            ts  = ev.get('timestamp', '')[:19]
                            proto = ev.get('proto', '')
                            line = f"{ts} [{sev}] {sig} | {src}→{dst} {proto}"
                            alerts.append({'source': 'Suricata-EVE', 'line': line,
                                           'level': _classify_sev(sev)})
                    except Exception:
                        pass
            except Exception:
                pass
            break

    # Snort
    for path in SNORT_LOGS:
        if os.path.exists(path):
            try:
                lines = open(path, errors='replace').readlines()[-n:]
                for ln in reversed(lines):
                    ln = ln.strip()
                    if ln:
                        alerts.append({'source': 'Snort', 'line': ln,
                                       'level': _classify(ln)})
            except Exception:
                pass
            break

    return alerts[:n]


def _classify(line: str) -> str:
    l = line.lower()
    if any(x in l for x in ['critical', 'severity 1', '[1]', 'exploit',
                              'attack', 'trojan', 'malware', 'backdoor']):
        return 'CRITICAL'
    if any(x in l for x in ['warning', 'severity 2', '[2]', 'scan',
                              'brute', 'suspicious', 'probe']):
        return 'HIGH'
    return 'INFO'


def _classify_sev(sev) -> str:
    try:
        s = int(sev)
        if s == 1: return 'CRITICAL'
        if s == 2: return 'HIGH'
    except Exception:
        pass
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

    def _safe_after(self, delay, fn, *args):
        def _g():
            try:
                if self.winfo_exists():
                    fn(*args)
            except Exception:
                pass
        try:
            self.after(delay, _g)
        except Exception:
            pass

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='🚨  IDS/IPS — SURICATA & SNORT',
                     font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['wn']).pack(side='left', padx=16)
        Btn(hdr, '↺ REFRESH',
            command=lambda: threading.Thread(target=self._bg_refresh, daemon=True).start(),
            variant='ghost', width=90).pack(side='right', padx=8, pady=8)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # ── STATUS ────────────────────────────────────────────
        SectionHeader(body, '01', 'IDS STATUS').pack(fill='x', padx=14, pady=(14, 4))
        self._sc = Card(body)
        self._sc.pack(fill='x', padx=14, pady=(0, 8))
        self._sgrid = ctk.CTkFrame(self._sc, fg_color='transparent')
        self._sgrid.pack(fill='x', padx=8, pady=10)

        # ── INTERFACE ─────────────────────────────────────────
        SectionHeader(body, '02', 'MONITORING INTERFACE').pack(fill='x', padx=14, pady=(8, 4))
        ic = Card(body)
        ic.pack(fill='x', padx=14, pady=(0, 8))
        ir = ctk.CTkFrame(ic, fg_color='transparent')
        ir.pack(fill='x', padx=12, pady=10)
        ctk.CTkLabel(ir, text='Interface:', font=MONO_SM,
                     text_color=C['mu']).pack(side='left')
        self._iface_entry = ctk.CTkEntry(
            ir, width=120, font=MONO_SM,
            fg_color=C['bg'], border_color=C['br'], text_color=C['tx'])
        self._iface_entry.pack(side='left', padx=8)
        self._iface_lbl = ctk.CTkLabel(ir, text='auto-detecting...',
                                        font=('DejaVu Sans Mono', 8), text_color=C['mu'])
        self._iface_lbl.pack(side='left')

        # ── SURICATA ──────────────────────────────────────────
        SectionHeader(body, '03', 'SURICATA').pack(fill='x', padx=14, pady=(8, 4))
        self._sur_card = Card(body, accent=C['ac'])
        self._sur_card.pack(fill='x', padx=14, pady=(0, 8))
        self._sur_content = ctk.CTkFrame(self._sur_card, fg_color='transparent')
        self._sur_content.pack(fill='x', padx=12, pady=10)

        # ── SNORT ─────────────────────────────────────────────
        SectionHeader(body, '04', 'SNORT').pack(fill='x', padx=14, pady=(8, 4))
        self._snort_card = Card(body, accent=C['bl'])
        self._snort_card.pack(fill='x', padx=14, pady=(0, 8))
        self._snort_content = ctk.CTkFrame(self._snort_card, fg_color='transparent')
        self._snort_content.pack(fill='x', padx=12, pady=10)

        # ── LIVE ALERTS ───────────────────────────────────────
        SectionHeader(body, '05', 'LIVE ALERTS').pack(fill='x', padx=14, pady=(8, 4))
        ac = Card(body, accent=C['wn'])
        ac.pack(fill='x', padx=14, pady=(0, 8))
        ah = ctk.CTkFrame(ac, fg_color='transparent')
        ah.pack(fill='x', padx=8, pady=(6, 0))
        self._alert_count = ctk.CTkLabel(ah, text='No alerts',
                                          font=('DejaVu Sans Mono', 9, 'bold'),
                                          text_color=C['mu'])
        self._alert_count.pack(side='left')
        Btn(ah, '🗑 CLEAR', command=self._clear_alerts,
            variant='ghost', width=70).pack(side='right')
        self._alert_log = ctk.CTkTextbox(
            ac, height=220, font=('DejaVu Sans Mono', 9),
            fg_color=C['bg'], text_color=C['ok'], border_width=0, wrap='none')
        self._alert_log.pack(fill='x', padx=8, pady=8)
        self._alert_log.configure(state='normal')

        # ── RULE TESTER ───────────────────────────────────────
        SectionHeader(body, '06', 'SURICATA RULE TESTER').pack(
            fill='x', padx=14, pady=(8, 4))
        rc_card = Card(body)
        rc_card.pack(fill='x', padx=14, pady=(0, 14))
        ctk.CTkLabel(rc_card, text='Test Suricata rule syntax (does not activate rule):',
                     font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10, 2))
        self._rule_entry = ctk.CTkEntry(
            rc_card,
            placeholder_text='alert tcp any any -> any 4444 (msg:"Test"; sid:9001; rev:1;)',
            font=('DejaVu Sans Mono', 9), fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'])
        self._rule_entry.pack(fill='x', padx=12, pady=(0, 4))
        Btn(rc_card, '▶ TEST SYNTAX', command=self._test_rule, width=150).pack(pady=(0, 10))
        self._rule_status = ctk.CTkLabel(rc_card, text='',
                                          font=MONO_SM, text_color=C['mu'])
        self._rule_status.pack(pady=(0, 8))

    # ── BACKGROUND REFRESH ────────────────────────────────────

    def _bg_refresh(self):
        ids = detect_ids()
        self._iface = ids['default_iface']
        self._safe_after(0, self._apply_status, ids)

    def _apply_status(self, ids):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        # Status grid
        for w in self._sgrid.winfo_children():
            w.destroy()
        InfoGrid(self._sgrid, [
            ('SURICATA', f"✓ {ids['suricata_path']}" if ids['suricata'] else '✗ Not installed',
             C['ok'] if ids['suricata'] else C['wn']),
            ('SNORT', f"✓ {ids['snort_path']}" if ids['snort'] else '✗ Not installed',
             C['ok'] if ids['snort'] else C['wn']),
            ('SUR STATUS', '● Running' if ids['suricata_running'] else '○ Stopped',
             C['ok'] if ids['suricata_running'] else C['mu']),
            ('SNT STATUS', '● Running' if ids['snort_running'] else '○ Stopped',
             C['ok'] if ids['snort_running'] else C['mu']),
            ('SUR LOG', ids['suricata_log'] or 'No log yet', C['ok'] if ids['suricata_log'] else C['mu']),
            ('SNT LOG', ids['snort_log'] or 'No log yet', C['ok'] if ids['snort_log'] else C['mu']),
        ], columns=3).pack(fill='x')

        # Interface
        if not self._iface_entry.get():
            self._iface_entry.insert(0, self._iface)
        self._iface_lbl.configure(text=f'(detected: {self._iface})')

        # Suricata controls — dynamic
        for w in self._sur_content.winfo_children():
            w.destroy()
        if ids['suricata']:
            ctk.CTkLabel(self._sur_content,
                text=f"✓ Suricata installed: {ids['suricata_path']}",
                font=('DejaVu Sans Mono', 9, 'bold'), text_color=C['ok']
                ).pack(anchor='w', pady=(0, 6))
            br = ctk.CTkFrame(self._sur_content, fg_color='transparent')
            br.pack(fill='x')
            if ids['suricata_running']:
                Btn(br, '⏹ STOP', command=self._stop_suricata,
                    variant='danger', width=90).pack(side='left', padx=(0, 6))
                Btn(br, '📋 VIEW STATUS', command=self._sur_status,
                    variant='ghost', width=130).pack(side='left', padx=(0, 6))
            else:
                Btn(br, '▶ START', command=self._start_suricata,
                    width=90).pack(side='left', padx=(0, 6))
            Btn(br, '📦 UPDATE RULES', command=self._update_rules,
                variant='ghost', width=140).pack(side='left')
        else:
            ctk.CTkLabel(self._sur_content,
                text='Suricata not installed.',
                font=MONO_SM, text_color=C['mu']).pack(anchor='w', pady=(0, 6))
            ctk.CTkLabel(self._sur_content,
                text='Suricata is recommended — supports modern rules and EVE JSON output.',
                font=('DejaVu Sans Mono', 8), text_color=C['mu']).pack(anchor='w', pady=(0, 4))
            Btn(self._sur_content, '⬇ INSTALL SURICATA',
                command=lambda: self._install('suricata', 'suricata'),
                width=200).pack(anchor='w')

        # Snort controls — dynamic
        for w in self._snort_content.winfo_children():
            w.destroy()
        if ids['snort']:
            ctk.CTkLabel(self._snort_content,
                text=f"✓ Snort installed: {ids['snort_path']}",
                font=('DejaVu Sans Mono', 9, 'bold'), text_color=C['ok']
                ).pack(anchor='w', pady=(0, 6))
            br2 = ctk.CTkFrame(self._snort_content, fg_color='transparent')
            br2.pack(fill='x')
            if ids['snort_running']:
                Btn(br2, '⏹ STOP', command=self._stop_snort,
                    variant='danger', width=90).pack(side='left', padx=(0, 6))
            else:
                Btn(br2, '▶ START', command=self._start_snort,
                    width=90).pack(side='left', padx=(0, 6))
        else:
            ctk.CTkLabel(self._snort_content,
                text='Snort not installed.',
                font=MONO_SM, text_color=C['mu']).pack(anchor='w', pady=(0, 6))
            Btn(self._snort_content, '⬇ INSTALL SNORT',
                command=lambda: self._install('snort', 'snort'),
                variant='blue', width=170).pack(anchor='w')

        self._load_alerts()

    def _get_iface(self) -> str:
        return self._iface_entry.get().strip() or self._iface or _get_default_iface()

    # ── ALERT HANDLING ────────────────────────────────────────

    def _load_alerts(self):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        alerts = get_recent_alerts(100)
        self._alert_log.configure(state='normal')
        self._alert_log.delete('1.0', 'end')
        if alerts:
            n_crit = sum(1 for a in alerts if a['level'] == 'CRITICAL')
            n_high = sum(1 for a in alerts if a['level'] == 'HIGH')
            self._alert_count.configure(
                text=f'{len(alerts)} alert(s) — {n_crit} critical, {n_high} high',
                text_color=C['wn'] if n_crit else C['am'] if n_high else C['ok'])
            for a in alerts[:80]:
                icon = '🔴' if a['level'] == 'CRITICAL' else '🟡' if a['level'] == 'HIGH' else '⚪'
                self._alert_log.insert('end', f"{icon} [{a['source']}] {a['line']}\n")
        else:
            self._alert_count.configure(text='No alerts', text_color=C['mu'])
            ids = detect_ids()
            if not ids['suricata'] and not ids['snort']:
                msg = ('Neither Suricata nor Snort is installed.\n\n'
                       '→ Tap ⬇ INSTALL SURICATA in the Suricata section above.\n'
                       '→ After installing, tap ▶ START to begin monitoring.\n\n'
                       'Suricata is recommended — it supports EVE JSON output\n'
                       'and has a community ruleset (sudo suricata-update).')
            elif not ids['suricata_running'] and not ids['snort_running']:
                msg = (f'IDS installed but not running.\n\n'
                       f'→ Tap ▶ START in the Suricata section above.\n'
                       f'→ Listening interface: {self._get_iface()}\n\n'
                       f'Alerts will appear here in real-time once running.')
            else:
                msg = f'IDS running on {self._get_iface()} — no alerts yet.\nAlert output will appear here as threats are detected.'
            self._alert_log.insert('end', msg)
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

    # ── CONTROLS ─────────────────────────────────────────────

    def _start_suricata(self):
        iface = self._get_iface()
        # Basic validation: only alphanumeric + some chars, no shell metachars
        if not re.match(r'^[a-z0-9.\-_]+$', iface):
            self._rule_status.configure(text=f"✗ Invalid interface: {iface}", text_color=C['wn'])
            return

        log.info(f'Starting Suricata on {iface}')
        self._rule_status.configure(text=f'Starting Suricata on {iface}...', text_color=C['ac'])
        def _bg():
            run_cmd(['sudo', 'mkdir', '-p', '/var/log/suricata'], timeout=5)
            # Use --af-packet for best performance on Linux
            cmd = [
                'sudo', 'suricata', f'--af-packet={iface}', '-D',
                '--pidfile', '/var/run/suricata.pid',
                '-l', '/var/log/suricata/'
            ]
            out, err, rc = run_cmd(cmd, timeout=30)
            result = (out or err or f'exit={rc}')[:100]
            ok = rc == 0 or 'daemon' in result.lower() or 'pid' in result.lower()
            self._safe_after(0, self._rule_status.configure, {
                'text': ('✓ Suricata started' if ok else f'✗ {result}'),
                'text_color': C['ok'] if ok else C['wn']})
            log.info(f'Suricata start: {result}')
            self._safe_after(800, lambda: threading.Thread(
                target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _stop_suricata(self):
        def _bg():
            run_cmd(['sudo', 'killall', 'suricata'], timeout=8)
            run_cmd(['sudo', 'rm', '-f', '/var/run/suricata.pid'], timeout=5)
            log.info('Suricata stopped')
            self._safe_after(500, lambda: threading.Thread(
                target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _sur_status(self):
        def _bg():
            out, _, _ = run_cmd(['sudo', 'suricata', '--list-runmodes'], timeout=5)
            svc, _, _ = run_cmd(['systemctl', 'status', 'suricata'], timeout=5)
            text = (out or svc or 'Suricata status unavailable')[:200]
            self._safe_after(0, self._rule_status.configure,
                             {'text': text, 'text_color': C['ac']})
        threading.Thread(target=_bg, daemon=True).start()

    def _update_rules(self):
        self._rule_status.configure(text='Updating Suricata rules...', text_color=C['ac'])
        def _bg():
            out, err, rc = run_cmd(['sudo', 'suricata-update'], timeout=180)
            result = (out or err or f'exit={rc}')[-200:]
            self._safe_after(0, self._rule_status.configure, {
                'text': ('✓ Rules updated' if rc == 0 else f'✗ {result[:80]}'),
                'text_color': C['ok'] if rc == 0 else C['wn']})
        threading.Thread(target=_bg, daemon=True).start()

    def _start_snort(self):
        iface = self._get_iface()
        if not re.match(r'^[a-z0-9.\-_]+$', iface):
            self._rule_status.configure(text=f"✗ Invalid interface: {iface}", text_color=C['wn'])
            return

        log.info(f'Starting Snort on {iface}')
        def _bg():
            run_cmd(['sudo', 'mkdir', '-p', '/var/log/snort'], timeout=5)
            conf = '/etc/snort/snort.conf'
            cmd = ['sudo', 'snort', '-D', '-i', iface, '-A', 'fast', '-l', '/var/log/snort/']
            if os.path.exists(conf):
                cmd.extend(['-c', conf])
            
            out, err, rc = run_cmd(cmd, timeout=25)
            result = (out or err or f'exit={rc}')[:100]
            ok = rc == 0
            log.info(f'Snort start: {result}')
            self._safe_after(0, self._rule_status.configure, {
                'text': ('✓ Snort started' if ok else f'✗ {result}'),
                'text_color': C['ok'] if ok else C['wn']})
            self._safe_after(800, lambda: threading.Thread(
                target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _stop_snort(self):
        run_cmd(['sudo', 'killall', 'snort'], timeout=8)
        threading.Thread(target=self._bg_refresh, daemon=True).start()

    def _test_rule(self):
        rule = self._rule_entry.get().strip()
        if not rule:
            return
        if not shutil.which('suricata'):
            self._rule_status.configure(text='Suricata not installed', text_color=C['wn'])
            return
        self._rule_status.configure(text='Testing rule...', text_color=C['ac'])
        def _bg():
            tmp = '/tmp/mint_scan_test.rules'
            with open(tmp, 'w') as f:
                f.write(rule + '\n')
            out, err, rc = run_cmd(f'suricata -T -S {tmp} 2>&1', timeout=20)
            result = (out or err or 'No output')[:150]
            ok = rc == 0 or 'successfully loaded' in result.lower()
            self._safe_after(0, self._rule_status.configure, {
                'text': '✓ Rule syntax valid' if ok else f'✗ {result}',
                'text_color': C['ok'] if ok else C['wn']})
        threading.Thread(target=_bg, daemon=True).start()

    def _install(self, pkg: str, check_bin: str):
        from installer import InstallerPopup

        if pkg == 'snort':
            cmds = [
                'sudo apt-get update -qq',
                # Pre-seed debconf to avoid all interactive prompts
                'echo "snort snort/address_range string 0.0.0.0/0" | sudo debconf-set-selections',
                'echo "snort snort/interface string eth0" | sudo debconf-set-selections',
                'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y snort',
                'sudo mkdir -p /etc/snort/rules /var/log/snort',
                # Create minimal config if missing
                'test -f /etc/snort/snort.conf || (echo "include $RULE_PATH/local.rules" | sudo tee /etc/snort/snort.conf)',
                'sudo touch /etc/snort/rules/local.rules 2>/dev/null || true',
                'echo "✓ Snort installed"',
            ]
        elif pkg == 'suricata':
            cmds = [
                'sudo apt-get update -qq',
                'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y suricata',
                'sudo mkdir -p /var/log/suricata /etc/suricata',
                # Update rules — community ruleset
                'which suricata-update 2>/dev/null && sudo suricata-update || '
                'echo "suricata-update not available yet (install suricata-update separately)"',
                'echo "✓ Suricata installed"',
            ]
        else:
            cmds = ['sudo apt-get update -qq',
                    f'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}']

        def _after():
            threading.Thread(target=self._bg_refresh, daemon=True).start()

        InstallerPopup(self, f'Install {pkg}', cmds,
                       f'{pkg} installed successfully!', on_done=_after)
