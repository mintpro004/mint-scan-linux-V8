"""
Mint Scan v8 — IDS/IPS Integration (Suricata / Snort)
Dynamic install buttons: hidden when tool is already installed.
Auto-detects network interface. Real log parsing.
"""
import os, threading, time, subprocess, shutil, json
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, InfoGrid)
from utils import run_cmd
from logger import get_logger

log = get_logger('ids')

SURICATA_LOGS = ['/var/log/suricata/fast.log', '/var/log/suricata/eve.json',
                 '/tmp/suricata/fast.log']
SNORT_LOGS    = ['/var/log/snort/alert', '/var/log/snort/snort.alert.fast',
                 '/tmp/snort/alert']


def _get_default_iface() -> str:
    out, _, rc = run_cmd("ip route show default 2>/dev/null | awk '{print $5}' | head -1", timeout=4)
    if rc == 0 and out.strip():
        return out.strip()
    out2, _, _ = run_cmd("ip link show | awk -F: '/state UP/{print $2}' | head -1", timeout=4)
    if out2.strip():
        return out2.strip()
    # Last resort: try any UP interface
    out3, _, _ = run_cmd("ip -o link show | awk '{print $2}' | tr -d : | grep -v lo | head -1", timeout=3)
    return out3.strip() or 'eth0'


def detect_ids() -> dict:
    procs, _, _ = run_cmd('ps aux 2>/dev/null', timeout=5)
    sur_log   = next((f for f in SURICATA_LOGS if os.path.exists(f)), None)
    snort_log = next((f for f in SNORT_LOGS if os.path.exists(f)), None)
    suricata_bin = shutil.which('suricata')
    snort_bin    = shutil.which('snort')
    return {
        'snort':            bool(snort_bin),
        'snort_path':       snort_bin or '',
        'suricata':         bool(suricata_bin),
        'suricata_path':    suricata_bin or '',
        'suricata_running': 'suricata' in procs.lower(),
        'snort_running':    'snort' in procs.lower(),
        'suricata_log':     sur_log,
        'snort_log':        snort_log,
        'default_iface':    _get_default_iface(),
    }


def get_recent_alerts(n=80) -> list:
    alerts = []
    for path in SURICATA_LOGS:
        if path.endswith('fast.log') and os.path.exists(path):
            try:
                lines = open(path, errors='replace').readlines()[-n:]
                for ln in reversed(lines):
                    ln = ln.strip()
                    if ln:
                        alerts.append({'source':'Suricata','line':ln,
                                       'level':_classify(ln)})
            except Exception: pass
            break
    for path in SURICATA_LOGS:
        if path.endswith('eve.json') and os.path.exists(path):
            try:
                lines = open(path, errors='replace').readlines()[-n:]
                for ln in reversed(lines):
                    try:
                        ev = json.loads(ln)
                        if ev.get('event_type') == 'alert':
                            al = ev.get('alert',{})
                            line = (f"{ev.get('timestamp','')[:19]} "
                                    f"[{al.get('severity','?')}] {al.get('signature','')} "
                                    f"{ev.get('src_ip','?')}→{ev.get('dest_ip','?')}")
                            alerts.append({'source':'Suricata-EVE','line':line,
                                           'level':_classify(line)})
                    except Exception: pass
            except Exception: pass
            break
    for path in SNORT_LOGS:
        if os.path.exists(path):
            try:
                lines = open(path, errors='replace').readlines()[-n:]
                for ln in reversed(lines):
                    ln = ln.strip()
                    if ln:
                        alerts.append({'source':'Snort','line':ln,
                                       'level':_classify(ln)})
            except Exception: pass
            break
    return alerts[:n]


def _classify(line):
    l = line.lower()
    if any(x in l for x in ['critical','severity 1','exploit','attack','[1]']):
        return 'CRITICAL'
    if any(x in l for x in ['warning','severity 2','scan','brute','[2]']):
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

    def _safe_after(self, delay, fn, *args):
        def _g():
            try:
                if self.winfo_exists(): fn(*args)
            except Exception: pass
        try: self.after(delay, _g)
        except Exception: pass

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x'); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='🚨  IDS/IPS — SNORT & SURICATA',
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['wn']
                     ).pack(side='left', padx=16)
        Btn(hdr, '↺ REFRESH', command=lambda: threading.Thread(
            target=self._bg_refresh, daemon=True).start(),
            variant='ghost', width=90).pack(side='right', padx=8, pady=8)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # ── STATUS ──────────────────────────────────────────────
        SectionHeader(body, '01', 'IDS STATUS').pack(fill='x', padx=14, pady=(14,4))
        self._sc = Card(body)
        self._sc.pack(fill='x', padx=14, pady=(0,8))
        self._sgrid = ctk.CTkFrame(self._sc, fg_color='transparent')
        self._sgrid.pack(fill='x', padx=8, pady=10)

        # ── INTERFACE ───────────────────────────────────────────
        SectionHeader(body, '02', 'NETWORK INTERFACE').pack(fill='x', padx=14, pady=(8,4))
        ic = Card(body)
        ic.pack(fill='x', padx=14, pady=(0,8))
        ir = ctk.CTkFrame(ic, fg_color='transparent')
        ir.pack(fill='x', padx=12, pady=10)
        ctk.CTkLabel(ir, text='Interface:', font=MONO_SM,
                     text_color=C['mu']).pack(side='left')
        self._iface_entry = ctk.CTkEntry(ir, width=100, font=MONO_SM,
                                          fg_color=C['bg'], border_color=C['br'],
                                          text_color=C['tx'])
        self._iface_entry.pack(side='left', padx=8)
        self._iface_detected = ctk.CTkLabel(ir, text='', font=('DejaVu Sans Mono',8),
                                             text_color=C['mu'])
        self._iface_detected.pack(side='left')

        # ── SURICATA CONTROLS ───────────────────────────────────
        SectionHeader(body, '03', 'SURICATA').pack(fill='x', padx=14, pady=(8,4))
        self._sur_card = Card(body, accent=C['ac'])
        self._sur_card.pack(fill='x', padx=14, pady=(0,8))
        self._sur_content = ctk.CTkFrame(self._sur_card, fg_color='transparent')
        self._sur_content.pack(fill='x', padx=12, pady=10)

        # ── SNORT CONTROLS ──────────────────────────────────────
        SectionHeader(body, '04', 'SNORT').pack(fill='x', padx=14, pady=(8,4))
        self._snort_card = Card(body, accent=C['bl'])
        self._snort_card.pack(fill='x', padx=14, pady=(0,8))
        self._snort_content = ctk.CTkFrame(self._snort_card, fg_color='transparent')
        self._snort_content.pack(fill='x', padx=12, pady=10)

        # ── ALERTS ──────────────────────────────────────────────
        SectionHeader(body, '05', 'LIVE ALERTS').pack(fill='x', padx=14, pady=(8,4))
        ac = Card(body, accent=C['wn'])
        ac.pack(fill='x', padx=14, pady=(0,8))
        ah = ctk.CTkFrame(ac, fg_color='transparent')
        ah.pack(fill='x', padx=8, pady=(6,0))
        self._alert_count = ctk.CTkLabel(ah, text='No alerts',
                                          font=('DejaVu Sans Mono',9,'bold'), text_color=C['mu'])
        self._alert_count.pack(side='left')
        Btn(ah, '🗑 CLEAR', command=self._clear_alerts, variant='ghost', width=70).pack(side='right')
        self._alert_log = ctk.CTkTextbox(ac, height=200, font=('DejaVu Sans Mono',9),
                                          fg_color=C['bg'], text_color=C['ok'],
                                          border_width=0, wrap='none')
        self._alert_log.pack(fill='x', padx=8, pady=8)
        self._alert_log.configure(state='normal')

        # ── RULE TESTER ─────────────────────────────────────────
        SectionHeader(body, '06', 'RULE TESTER').pack(fill='x', padx=14, pady=(8,4))
        rc_card = Card(body)
        rc_card.pack(fill='x', padx=14, pady=(0,14))
        ctk.CTkLabel(rc_card, text='Suricata rule (test syntax):',
                     font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10,2))
        self._rule_entry = ctk.CTkEntry(rc_card,
            placeholder_text='alert tcp any any -> any 4444 (msg:"Metasploit"; sid:9001; rev:1;)',
            font=('DejaVu Sans Mono',9), fg_color=C['bg'], border_color=C['br'], text_color=C['tx'])
        self._rule_entry.pack(fill='x', padx=12, pady=(0,4))
        Btn(rc_card, '▶ TEST RULE SYNTAX', command=self._test_rule, width=180).pack(pady=(0,10))
        self._rule_status = ctk.CTkLabel(rc_card, text='', font=MONO_SM, text_color=C['mu'])
        self._rule_status.pack(pady=(0,8))

    def _bg_refresh(self):
        ids = detect_ids()
        self._iface = ids['default_iface']
        self._safe_after(0, self._apply_status, ids)

    def _apply_status(self, ids):
        try:
            if not self.winfo_exists(): return
        except Exception: return

        # Status grid
        for w in self._sgrid.winfo_children(): w.destroy()
        InfoGrid(self._sgrid, [
            ('SURICATA',     f"✓ {ids['suricata_path']}" if ids['suricata'] else '✗ Not installed',
             C['ok'] if ids['suricata'] else C['wn']),
            ('SNORT',        f"✓ {ids['snort_path']}" if ids['snort'] else '✗ Not installed',
             C['ok'] if ids['snort'] else C['wn']),
            ('SUR RUNNING',  '● Active' if ids['suricata_running'] else '○ Stopped',
             C['ok'] if ids['suricata_running'] else C['mu']),
            ('SNT RUNNING',  '● Active' if ids['snort_running'] else '○ Stopped',
             C['ok'] if ids['snort_running'] else C['mu']),
            ('SUR LOG',      ids['suricata_log'] or 'No log found', C['ok'] if ids['suricata_log'] else C['mu']),
            ('SNT LOG',      ids['snort_log'] or 'No log found',    C['ok'] if ids['snort_log'] else C['mu']),
        ], columns=3).pack(fill='x')

        # Interface
        if not self._iface_entry.get():
            self._iface_entry.insert(0, self._iface)
        self._iface_detected.configure(text=f'(detected: {self._iface})')

        # Suricata controls — dynamic based on install state
        for w in self._sur_content.winfo_children(): w.destroy()
        if ids['suricata']:
            ctk.CTkLabel(self._sur_content,
                text=f"✓ Installed: {ids['suricata_path']}",
                font=('DejaVu Sans Mono',9,'bold'), text_color=C['ok']
                ).pack(anchor='w', pady=(0,6))
            br = ctk.CTkFrame(self._sur_content, fg_color='transparent')
            br.pack(fill='x')
            Btn(br, '▶ START', command=self._start_suricata, width=100
                ).pack(side='left', padx=(0,6))
            Btn(br, '⏹ STOP', command=self._stop_suricata,
                variant='danger', width=90).pack(side='left', padx=(0,6))
            Btn(br, '📋 UPDATE RULES', command=self._update_suricata_rules,
                variant='ghost', width=150).pack(side='left')
        else:
            ctk.CTkLabel(self._sur_content,
                text='Suricata not installed',
                font=MONO_SM, text_color=C['mu']).pack(anchor='w', pady=(0,6))
            Btn(self._sur_content, '⬇ INSTALL SURICATA',
                command=lambda: self._install('suricata suricata-update',
                                              'suricata'), width=200).pack(anchor='w')

        # Snort controls — dynamic
        for w in self._snort_content.winfo_children(): w.destroy()
        if ids['snort']:
            ctk.CTkLabel(self._snort_content,
                text=f"✓ Installed: {ids['snort_path']}",
                font=('DejaVu Sans Mono',9,'bold'), text_color=C['ok']
                ).pack(anchor='w', pady=(0,6))
            br2 = ctk.CTkFrame(self._snort_content, fg_color='transparent')
            br2.pack(fill='x')
            Btn(br2, '▶ START', command=self._start_snort, width=100
                ).pack(side='left', padx=(0,6))
            Btn(br2, '⏹ STOP', command=self._stop_snort,
                variant='danger', width=90).pack(side='left')
        else:
            ctk.CTkLabel(self._snort_content,
                text='Snort not installed',
                font=MONO_SM, text_color=C['mu']).pack(anchor='w', pady=(0,6))
            Btn(self._snort_content, '⬇ INSTALL SNORT',
                command=lambda: self._install('snort', 'snort'),
                variant='blue', width=180).pack(anchor='w')

        self._load_alerts()

    def _get_iface(self):
        return self._iface_entry.get().strip() or self._iface or _get_default_iface()

    def _ctl_msg(self, msg, col=None):
        log.info(f'IDS: {msg}')

    def _load_alerts(self):
        try:
            if not self.winfo_exists(): return
        except Exception: return
        alerts = get_recent_alerts(80)
        self._alert_log.configure(state='normal')
        self._alert_log.delete('1.0','end')
        if alerts:
            n_crit = sum(1 for a in alerts if a['level']=='CRITICAL')
            self._alert_count.configure(
                text=f'{len(alerts)} alert(s) — {n_crit} critical',
                text_color=C['wn'] if n_crit else C['am'])
            for a in alerts[:60]:
                prefix = '🔴' if a['level']=='CRITICAL' else '🟡' if a['level']=='HIGH' else '⚪'
                self._alert_log.insert('end', f"{prefix} [{a['source']}] {a['line']}\n")
        else:
            ids = detect_ids()
            self._alert_count.configure(text='No alerts', text_color=C['mu'])
            if not ids['suricata'] and not ids['snort']:
                msg = ('Neither Suricata nor Snort is installed.\n\n'
                       'Recommendation: Install Suricata (better maintained).\n'
                       'Tap ⬇ INSTALL SURICATA in the Suricata section above.\n\n'
                       'After install, run: sudo suricata-update\n'
                       'Then tap ▶ START.')
            elif not ids['suricata_running'] and not ids['snort_running']:
                msg = (f'IDS installed but not running.\n\n'
                       f'Tap ▶ START in the Suricata or Snort section above.\n'
                       f'Interface: {self._get_iface()}\n\n'
                       f'Logs will appear here once running.')
            else:
                msg = 'IDS running — no alerts yet. Traffic will appear here as threats are detected.'
            self._alert_log.insert('end', msg)
        self._alert_log.configure(state='disabled')

    def _clear_alerts(self):
        self._alert_log.configure(state='normal')
        self._alert_log.delete('1.0','end')
        self._alert_log.configure(state='disabled')
        self._alert_count.configure(text='Cleared', text_color=C['mu'])

    def _poll_loop(self):
        if not self._poll: return
        try:
            if not self.winfo_exists(): return
        except Exception: return
        self._load_alerts()
        self.after(8000, self._poll_loop)

    def _start_suricata(self):
        iface = self._get_iface()
        log.info(f'Starting Suricata on {iface}')
        def _bg():
            run_cmd('sudo mkdir -p /var/log/suricata', timeout=5)
            out, err, rc = run_cmd(
                f'sudo suricata -D --af-packet={iface} '
                f'--pidfile /var/run/suricata.pid -l /var/log/suricata/', timeout=25)
            result = out or err or f'rc={rc}'
            log.info(f'Suricata: {result[:80]}')
            self._safe_after(600, lambda: threading.Thread(
                target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _stop_suricata(self):
        run_cmd('sudo killall suricata 2>/dev/null')
        run_cmd('sudo rm -f /var/run/suricata.pid')
        threading.Thread(target=self._bg_refresh, daemon=True).start()

    def _update_suricata_rules(self):
        def _bg():
            out, err, rc = run_cmd('sudo suricata-update 2>&1', timeout=120)
            log.info(f'suricata-update: rc={rc}')
            self._safe_after(0, self._load_alerts)
        threading.Thread(target=_bg, daemon=True).start()

    def _start_snort(self):
        iface = self._get_iface()
        def _bg():
            run_cmd('sudo mkdir -p /var/log/snort', timeout=5)
            conf = '/etc/snort/snort.conf'
            if not os.path.exists(conf):
                # Try without config (basic mode)
                out, err, rc = run_cmd(
                    f'sudo snort -D -i {iface} -A fast -l /var/log/snort/', timeout=20)
            else:
                out, err, rc = run_cmd(
                    f'sudo snort -D -i {iface} -A fast -l /var/log/snort/ -c {conf}', timeout=20)
            log.info(f'Snort: {out or err or f"rc={rc}"}')
            self._safe_after(600, lambda: threading.Thread(
                target=self._bg_refresh, daemon=True).start())
        threading.Thread(target=_bg, daemon=True).start()

    def _stop_snort(self):
        run_cmd('sudo killall snort 2>/dev/null')
        threading.Thread(target=self._bg_refresh, daemon=True).start()

    def _test_rule(self):
        rule = self._rule_entry.get().strip()
        if not rule:
            return
        if not shutil.which('suricata'):
            self._rule_status.configure(text='Suricata not installed', text_color=C['wn'])
            return
        self._rule_status.configure(text='Testing...', text_color=C['ac'])
        def _bg():
            tmp = '/tmp/mint_scan_test.rules'
            with open(tmp,'w') as f: f.write(rule+'\n')
            out, err, rc = run_cmd(f'suricata -T -S {tmp} 2>&1', timeout=20)
            result = (out or err or 'No output')[:120]
            ok = rc==0 or 'successfully loaded' in result
            self._safe_after(0, self._rule_status.configure, {
                'text': ('✓ Rule OK' if ok else f'✗ {result}'),
                'text_color': C['ok'] if ok else C['wn']})
        threading.Thread(target=_bg, daemon=True).start()

    def _install(self, pkg, check_bin):
        from installer import InstallerPopup
        # Pre-seed debconf to prevent interactive prompts during install
        # Snort in particular asks for network ranges — we answer 0/0 to skip
        cmds = [
            'sudo apt-get update -qq',
        ]
        if 'snort' in pkg:
            cmds += [
                # Pre-answer snort debconf prompts to avoid hanging
                'echo "snort snort/address_range string 0.0.0.0/0" | sudo debconf-set-selections',
                'echo "snort snort/interface string eth0" | sudo debconf-set-selections',
                f'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}',
                # Create basic snort config if missing
                'sudo mkdir -p /etc/snort/rules /var/log/snort',
                'test -f /etc/snort/snort.conf || echo "include $RULE_PATH/local.rules" | sudo tee /etc/snort/snort.conf',
                'sudo touch /etc/snort/rules/local.rules',
                'echo "✓ Snort installed and configured"',
            ]
        elif 'suricata' in pkg:
            cmds += [
                f'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}',
                'sudo mkdir -p /var/log/suricata /etc/suricata',
                # Update rules if suricata-update is available
                'which suricata-update && sudo suricata-update 2>/dev/null || echo "suricata-update not available, skipping rules download"',
                'echo "✓ Suricata installed"',
            ]
        else:
            cmds.append(f'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}')

        def _after_install():
            threading.Thread(target=self._bg_refresh, daemon=True).start()

        InstallerPopup(self, f'Install {pkg}', cmds,
                       f'{pkg} installed!', on_done=_after_install)
