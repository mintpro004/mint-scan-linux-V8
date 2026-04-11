"""
Mint Scan v8 — Guardian Auto-Defense
Real monitoring: watches ports, processes, failed logins.
Fires desktop notifications for critical events.
"""
import customtkinter as ctk
import threading, subprocess, time, os
from widgets import (ScrollableFrame, Card, SectionHeader,
                     InfoGrid, ResultBox, Btn, C, MONO, MONO_SM)
from utils import run_cmd, run_safe
from logger import get_logger
from notifier import critical, warning

log = get_logger('guardian')


class GuardianScreen(ctk.CTkFrame):
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
        self.app              = app
        self._built           = False
        self._guardian_active = False
        self._monitor_thread  = None
        self._usb_locked      = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._refresh_status()

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text='🛡  GUARDIAN AUTO-DEFENSE',
                     font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)
        self._body = body

        # ── 01 Guardian Mode ──────────────────────────────────────
        SectionHeader(body, '01', 'GUARDIAN MODE').pack(
            fill='x', padx=14, pady=(14, 4))
        mode_card = Card(body)
        mode_card.pack(fill='x', padx=14, pady=(0, 8))

        self.status_lbl = ctk.CTkLabel(
            mode_card, text='STATUS: INACTIVE',
            font=('DejaVu Sans Mono', 13, 'bold'), text_color=C['mu'])
        self.status_lbl.pack(pady=(12, 4))

        ctk.CTkLabel(mode_card,
            text='Monitors: dangerous open ports, failed SSH logins,\n'
                 'suspicious processes, firewall state, disk usage.\n'
                 'Sends desktop notifications on critical findings.',
            font=MONO_SM, text_color=C['mu']).pack(pady=(0, 8))

        self.toggle_btn = Btn(mode_card, 'ENABLE GUARDIAN',
                              command=self._toggle_guardian, width=180)
        self.toggle_btn.pack(pady=(0, 12))

        # Live stats
        self._stats_frame = ctk.CTkFrame(mode_card, fg_color='transparent')
        self._stats_frame.pack(fill='x', padx=8, pady=(0, 10))

        # ── 02 Rules ──────────────────────────────────────────────
        SectionHeader(body, '02', 'MONITOR RULES').pack(
            fill='x', padx=14, pady=(10, 4))
        rules_card = Card(body)
        rules_card.pack(fill='x', padx=14, pady=(0, 8))
        self._rules = {}
        for key, label, default in [
            ('ports',   'Dangerous open ports (4444, 5555, 23…)', True),
            ('ssh',     'SSH brute-force (5+ fails/5min)',         True),
            ('fw',      'Firewall disabled alert',                 True),
            ('disk',    'Disk >90% full alert',                    True),
            ('process', 'Known malware process names',             True),
        ]:
            row = ctk.CTkFrame(rules_card, fg_color='transparent')
            row.pack(fill='x', padx=12, pady=3)
            var = ctk.BooleanVar(value=default)
            self._rules[key] = var
            ctk.CTkSwitch(row, text='', variable=var,
                          onvalue=True, offvalue=False,
                          button_color=C['ac'],
                          progress_color=C['br2'],
                          width=46).pack(side='left')
            ctk.CTkLabel(row, text=label,
                         font=MONO_SM, text_color=C['tx']
                         ).pack(side='left', padx=8)

        # ── 03 Emergency Controls ─────────────────────────────────
        SectionHeader(body, '03', 'EMERGENCY CONTROLS').pack(
            fill='x', padx=14, pady=(10, 4))
        panic_card = Card(body, accent=C['wn'])
        panic_card.pack(fill='x', padx=14, pady=(0, 8))

        ctk.CTkLabel(panic_card, text='⚠  PANIC BUTTON',
                     font=('DejaVu Sans Mono', 14, 'bold'),
                     text_color=C['wn']).pack(pady=(12, 4))
        ctk.CTkLabel(panic_card,
            text='Instantly kills all network interfaces and locks screen.\n'
                 'Use if you suspect active intrusion.',
            font=MONO_SM, text_color=C['mu']).pack(pady=(0, 8))
        Btn(panic_card, '☢ EXECUTE PANIC',
            command=self._panic, variant='danger', width=200).pack(pady=(0, 12))

        # ── 04 USB Lockdown ───────────────────────────────────────
        SectionHeader(body, '04', 'USB LOCKDOWN').pack(
            fill='x', padx=14, pady=(10, 4))
        usb_card = Card(body)
        usb_card.pack(fill='x', padx=14, pady=(0, 8))
        ctk.CTkLabel(usb_card,
            text='Block new USB mass-storage devices from mounting.',
            font=MONO_SM, text_color=C['mu']).pack(pady=(10, 4))
        self.usb_btn = Btn(usb_card, '🔒 BLOCK NEW USB',
                           command=self._toggle_usb_lock,
                           variant='ghost', width=180)
        self.usb_btn.pack(pady=(0, 12))

        # ── 05 Guardian Log ───────────────────────────────────────
        SectionHeader(body, '05', 'GUARDIAN LOG').pack(
            fill='x', padx=14, pady=(10, 4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0, 14))
        self._glog = ctk.CTkTextbox(
            log_card, height=140, font=('DejaVu Sans Mono', 9),
            fg_color=C['bg'], text_color=C['ok'], border_width=0)
        self._glog.pack(fill='x', padx=8, pady=8)
        self._glog.configure(state='disabled')

    def _glog_line(self, msg):
        def _do():
            self._glog.configure(state='normal')
            ts = time.strftime('%H:%M:%S')
            self._glog.insert('end', f'[{ts}] {msg}\n')
            self._glog.see('end')
            self._glog.configure(state='disabled')
        self._safe_after(0, _do)

    def _refresh_status(self):
        pass

    def _toggle_guardian(self):
        self._guardian_active = not self._guardian_active
        if self._guardian_active:
            self.status_lbl.configure(text='STATUS: ● ACTIVE', text_color=C['ok'])
            self.toggle_btn.configure(text='DISABLE GUARDIAN', variant='danger')
            self._glog_line('Guardian started — monitoring system...')
            log.info('Guardian activated')
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
        else:
            self.status_lbl.configure(text='STATUS: ○ INACTIVE', text_color=C['mu'])
            self.toggle_btn.configure(text='ENABLE GUARDIAN', variant='primary')
            self._glog_line('Guardian stopped.')
            log.info('Guardian deactivated')

    def _monitor_loop(self):
        DANGER_PORTS = {4444, 5555, 7547, 31337, 23, 2375, 1337}
        BAD_PROCS    = {'cryptominer', 'xmrig', 'minerd', 'kthreadd2',
                        'ddostool', 'mirai', 'tsunami'}
        while self._guardian_active:
            try:
                # Check dangerous ports
                if self._rules.get('ports', ctk.BooleanVar()).get():
                    from utils import get_open_ports
                    ports = get_open_ports()
                    for p in ports:
                        try:
                            num = int(str(p.get('port', 0)))
                        except Exception:
                            continue
                        if num in DANGER_PORTS:
                            msg = f'Dangerous port {num} open!'
                            self._glog_line(f'⚠ {msg}')
                            critical('🚨 Guardian Alert', msg)

                # Check SSH failures
                if self._rules.get('ssh', ctk.BooleanVar()).get():
                    out, _, _ = run_cmd(
                        "journalctl -u ssh --since '5 minutes ago' 2>/dev/null"
                        " | grep -c 'Failed password' || echo 0")
                    try:
                        n = int(out.strip())
                        if n >= 5:
                            msg = f'{n} failed SSH attempts in 5 min!'
                            self._glog_line(f'🔐 {msg}')
                            critical('🔐 SSH Attack Detected', msg)
                    except Exception:
                        pass

                # Check firewall
                if self._rules.get('fw', ctk.BooleanVar()).get():
                    ufw, _, rc = run_cmd('ufw status 2>/dev/null | head -1')
                    if rc == 0 and 'inactive' in ufw.lower():
                        msg = 'Firewall is inactive!'
                        self._glog_line(f'🔥 {msg}')
                        warning('⚠ Firewall Disabled', msg)

                # Check disk
                if self._rules.get('disk', ctk.BooleanVar()).get():
                    df, _, _ = run_cmd("df / --output=pcent | tail -1")
                    try:
                        pct = int(df.strip().replace('%', ''))
                        if pct >= 90:
                            msg = f'Disk {pct}% full!'
                            self._glog_line(f'💾 {msg}')
                            warning('💾 Disk Nearly Full', msg)
                    except Exception:
                        pass

                # Check bad processes
                if self._rules.get('process', ctk.BooleanVar()).get():
                    procs_out, _, _ = run_cmd("ps aux --no-headers 2>/dev/null")
                    for line in procs_out.splitlines():
                        parts = line.split()
                        if len(parts) > 10:
                            cmd_name = parts[10].lower()
                            for bad in BAD_PROCS:
                                if bad in cmd_name:
                                    msg = f'Suspicious process: {parts[10]}'
                                    self._glog_line(f'⚠ {msg}')
                                    critical('🦠 Malware Process', msg)
                                    break

                self._glog_line('● Scan complete — all clear')

            except Exception as e:
                log.warning(f'Guardian monitor error: {e}')

            time.sleep(60)

    def _panic(self):
        log.warning('PANIC BUTTON ACTIVATED')
        # Kill network - try multiple methods
        run_cmd('nmcli networking off 2>/dev/null || true', timeout=5)
        # Bring down all UP interfaces
        ifaces_out, _, _ = run_cmd("ip link show | awk -F: '/state UP/{print $2}' | tr -d ' '")
        for iface in ifaces_out.splitlines():
            iface = iface.strip()
            if iface and iface != 'lo':
                run_safe(["sudo ip link set", (iface,), "down 2>/dev/null || true"], timeout=3)
        # Lock screen
        run_cmd('loginctl lock-session 2>/dev/null || xdg-screensaver lock 2>/dev/null || true', timeout=3)
        self._glog_line('☢ PANIC EXECUTED — network killed, screen locked')
        critical('☢ Panic Button', 'Network killed and screen locked.')

    def _toggle_usb_lock(self):
        self._usb_locked = not self._usb_locked
        if self._usb_locked:
            run_cmd("sudo modprobe -r usb_storage 2>/dev/null || true")
            self.usb_btn.configure(text='🔓 UNLOCK USB', variant='danger')
            self._glog_line('USB mass-storage blocked')
            log.info('USB locked')
        else:
            run_cmd("sudo modprobe usb_storage 2>/dev/null || true")
            self.usb_btn.configure(text='🔒 BLOCK NEW USB', variant='ghost')
            self._glog_line('USB mass-storage unlocked')
            log.info('USB unlocked')
