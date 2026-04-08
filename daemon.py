"""
Mint Scan v8 — Daemon / Service Mode
Run Mint Scan headlessly as a background service.
Installs a systemd unit, monitors threats, sends notifications.
"""
import os, sys, subprocess, threading, time, signal
from logger import get_logger

log = get_logger('daemon')

UNIT_NAME = 'mint-scan'
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
UNIT_FILE = f'/etc/systemd/system/{UNIT_NAME}.service'

UNIT_CONTENT = """\
[Unit]
Description=Mint Scan v8 Security Monitor
After=network.target
Wants=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={base}
ExecStart={python} {base}/daemon.py --run
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


def install_service() -> tuple[bool, str]:
    """Install and enable the systemd service."""
    user    = os.environ.get('USER', 'root')
    python  = os.path.join(BASE_DIR, 'venv', 'bin', 'python3')
    if not os.path.exists(python):
        python = sys.executable
    content = UNIT_CONTENT.format(user=user, base=BASE_DIR, python=python)
    try:
        tmp = '/tmp/mint-scan.service'
        with open(tmp, 'w') as f:
            f.write(content)
        r = subprocess.run(f'sudo cp {tmp} {UNIT_FILE}',
                           shell=True, capture_output=True)
        if r.returncode != 0:
            return False, r.stderr.decode()
        subprocess.run('sudo systemctl daemon-reload', shell=True)
        subprocess.run(f'sudo systemctl enable {UNIT_NAME}', shell=True)
        subprocess.run(f'sudo systemctl start {UNIT_NAME}', shell=True)
        log.info('Daemon service installed and started')
        return True, f'Service installed: {UNIT_FILE}'
    except Exception as e:
        return False, str(e)


def uninstall_service() -> tuple[bool, str]:
    try:
        subprocess.run(f'sudo systemctl stop {UNIT_NAME}', shell=True)
        subprocess.run(f'sudo systemctl disable {UNIT_NAME}', shell=True)
        subprocess.run(f'sudo rm -f {UNIT_FILE}', shell=True)
        subprocess.run('sudo systemctl daemon-reload', shell=True)
        log.info('Daemon service removed')
        return True, 'Service removed'
    except Exception as e:
        return False, str(e)


def service_status() -> dict:
    """Return dict with status info."""
    r = subprocess.run(
        f'systemctl is-active {UNIT_NAME} 2>/dev/null',
        shell=True, capture_output=True, text=True)
    active = r.stdout.strip() == 'active'
    r2 = subprocess.run(
        f'systemctl is-enabled {UNIT_NAME} 2>/dev/null',
        shell=True, capture_output=True, text=True)
    enabled = r2.stdout.strip() == 'enabled'
    return {'active': active, 'enabled': enabled,
            'unit_exists': os.path.exists(UNIT_FILE)}


def run_daemon():
    """
    Headless daemon loop — called when running as service.
    Monitors threats and sends notifications indefinitely.
    """
    log.info('Mint Scan v8 daemon starting...')
    from notifier import start_threat_monitor
    start_threat_monitor(interval=60)

    # Keep alive
    def _handle_signal(sig, frame):
        log.info(f'Daemon received signal {sig} — shutting down')
        sys.exit(0)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    while True:
        log.debug('Daemon heartbeat')
        time.sleep(300)


# ── Daemon Manager Screen ─────────────────────────────────────────
import tkinter as tk
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, ResultBox, InfoGrid)


class DaemonScreen(ctk.CTkFrame):
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
        self.app    = app
        self._built = False

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
        ctk.CTkLabel(hdr, text='⚙  DAEMON / SERVICE MODE',
                     font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, '↺ REFRESH', command=self._refresh_status,
            variant='ghost', width=90).pack(side='right', padx=8, pady=6)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        SectionHeader(body, '01', 'SERVICE STATUS').pack(
            fill='x', padx=14, pady=(14, 4))
        self._status_card = Card(body)
        self._status_card.pack(fill='x', padx=14, pady=(0, 8))
        self._status_lbl = ctk.CTkLabel(
            self._status_card, text='Checking...',
            font=('Courier', 12, 'bold'), text_color=C['mu'])
        self._status_lbl.pack(pady=(12, 4))
        self._status_grid = ctk.CTkFrame(self._status_card, fg_color='transparent')
        self._status_grid.pack(fill='x', padx=8, pady=(0, 10))

        SectionHeader(body, '02', 'CONTROLS').pack(
            fill='x', padx=14, pady=(8, 4))
        ctrl_card = Card(body)
        ctrl_card.pack(fill='x', padx=14, pady=(0, 8))
        br = ctk.CTkFrame(ctrl_card, fg_color='transparent')
        br.pack(fill='x', padx=12, pady=12)
        Btn(br, '▶ INSTALL & START',
            command=self._install, width=170).pack(side='left', padx=(0, 8))
        Btn(br, '⏹ STOP & REMOVE',
            command=self._uninstall, variant='danger', width=150).pack(side='left')

        SectionHeader(body, '03', 'SERVICE FILE').pack(
            fill='x', padx=14, pady=(8, 4))
        fc = Card(body)
        fc.pack(fill='x', padx=14, pady=(0, 8))
        user   = os.environ.get('USER', 'user')
        python = os.path.join(BASE_DIR, 'venv', 'bin', 'python3')
        ctk.CTkLabel(fc,
            text=UNIT_CONTENT.format(user=user, base=BASE_DIR, python=python),
            font=('Courier', 8), text_color=C['mu'], justify='left'
            ).pack(anchor='w', padx=12, pady=10)

        self._msg_lbl = ctk.CTkLabel(body, text='',
                                      font=MONO_SM, text_color=C['ok'])
        self._msg_lbl.pack(pady=8)

    def _refresh_status(self):
        st = service_status()
        active  = st['active']
        enabled = st['enabled']
        exists  = st['unit_exists']
        self._status_lbl.configure(
            text='● RUNNING' if active else '○ STOPPED',
            text_color=C['ok'] if active else C['mu'])
        for w in self._status_grid.winfo_children():
            w.destroy()
        InfoGrid(self._status_grid, [
            ('ACTIVE',   'Yes' if active  else 'No',  C['ok'] if active  else C['wn']),
            ('ENABLED',  'Yes' if enabled else 'No',  C['ok'] if enabled else C['mu']),
            ('UNIT FILE','Exists' if exists else 'Not installed', C['ac'] if exists else C['mu']),
            ('UNIT NAME', UNIT_NAME, C['tx']),
        ], columns=4).pack(fill='x')

    def _install(self):
        self._msg_lbl.configure(text='Installing service...', text_color=C['ac'])
        def _bg():
            ok, msg = install_service()
            self._safe_after(0, self._msg_lbl.configure,
                       {'text': ('✓ ' if ok else '✗ ') + msg,
                        'text_color': C['ok'] if ok else C['wn']})
            self.after(500, self._refresh_status)
        threading.Thread(target=_bg, daemon=True).start()

    def _uninstall(self):
        self._msg_lbl.configure(text='Removing service...', text_color=C['am'])
        def _bg():
            ok, msg = uninstall_service()
            self._safe_after(0, self._msg_lbl.configure,
                       {'text': ('✓ ' if ok else '✗ ') + msg,
                        'text_color': C['ok'] if ok else C['wn']})
            self.after(500, self._refresh_status)
        threading.Thread(target=_bg, daemon=True).start()


if __name__ == '__main__' and '--run' in sys.argv:
    run_daemon()
