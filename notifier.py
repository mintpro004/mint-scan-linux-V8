"""
Mint Scan v11.1 — Real-Time Desktop Notifications
Sends desktop notifications for critical threats via:
  1. libnotify (notify-send) — all Linux
  2. plyer      (pip install plyer) — cross-platform fallback
  3. In-app toast if neither available
"""
import subprocess, threading, time, os, queue
from logger import get_logger

log = get_logger('notifier')

# ── Notification queue (avoids flooding) ─────────────────────────
_queue: queue.Queue = queue.Queue()
_COOLDOWN: dict     = {}   # title → last_sent epoch
COOLDOWN_SECS       = 120  # don't repeat same alert within 2 min

# In-app toast callbacks registered by the main window
_toast_callbacks = []


def register_toast(fn):
    """Register fn(title, msg, level) to receive in-app toast notifications."""
    _toast_callbacks.append(fn)


def _send_desktop(title: str, msg: str, urgency: str = 'critical'):
    """Send OS-level desktop notification."""
    import shutil
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')
    
    # Method 1: notify-send (most reliable on Linux)
    if shutil.which('notify-send'):
        cmd = ['notify-send', '--app-name=Mint Scan v11.1', f'--urgency={urgency}', title, msg]
        if os.path.exists(icon):
            cmd.insert(1, f'--icon={icon}')
            
        subprocess.Popen(cmd, shell=False, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return

    # Method 2: plyer
    try:
        from plyer import notification
        notification.notify(title=title, message=msg,
                            app_name='Mint Scan v11.1', timeout=8)
        return
    except Exception:
        pass

    log.warning(f'No desktop notifier — toast only: {title}: {msg}')


def _worker():
    """Background thread: drains the notification queue."""
    while True:
        try:
            title, msg, level = _queue.get(timeout=1)
        except queue.Empty:
            continue
        # Cooldown check
        now = time.time()
        key = title[:40]
        
        # Specific longer cooldown for disk warnings
        cooldown = 3600 if 'Disk Almost Full' in title else COOLDOWN_SECS
        
        if now - _COOLDOWN.get(key, 0) < cooldown:
            continue
        _COOLDOWN[key] = now

        log.info(f'[{level}] {title}: {msg}')
        urgency = 'critical' if level == 'CRITICAL' else 'normal'
        _send_desktop(title, msg, urgency)
        for cb in list(_toast_callbacks):
            try:
                cb(title, msg, level)
            except Exception:
                pass


threading.Thread(target=_worker, daemon=True, name='notifier').start()


def notify(title: str, msg: str, level: str = 'WARNING'):
    """
    Queue a notification. level: 'CRITICAL' | 'WARNING' | 'INFO'
    Non-blocking — returns immediately.
    """
    _queue.put((title, msg, level))


# ── Convenience wrappers ─────────────────────────────────────────

def critical(title: str, msg: str):
    notify(title, msg, 'CRITICAL')

def warning(title: str, msg: str):
    notify(title, msg, 'WARNING')

def info(title: str, msg: str):
    notify(title, msg, 'INFO')


# ── Threat monitor ───────────────────────────────────────────────

_monitor_running = False

def start_threat_monitor(interval: int = 60):
    """
    Background loop that checks for critical threats and fires notifications.
    Runs every `interval` seconds.
    """
    global _monitor_running
    if _monitor_running:
        return
    _monitor_running = True

    def _loop():
        from utils import run_cmd, get_open_ports
        while _monitor_running:
            try:
                _check_threats(run_cmd, get_open_ports)
            except Exception as e:
                log.warning(f'Threat monitor error: {e}')
            time.sleep(interval)

    threading.Thread(target=_loop, daemon=True, name='threat-monitor').start()
    log.info(f'Threat monitor started (interval={interval}s)')


def stop_threat_monitor():
    global _monitor_running
    _monitor_running = False


def _check_threats(run_cmd, get_open_ports):
    """Run quick checks and notify on findings."""
    # 1. Dangerous open ports
    DANGER = {4444: 'Metasploit', 5555: 'ADB exposed',
              7547: 'Mirai botnet', 31337: 'Back Orifice',
              23: 'Telnet exposed', 2375: 'Docker RCE'}
    ports = get_open_ports()
    for p in ports:
        try:
            num = int(str(p.get('port', 0)))
        except Exception:
            continue
        if num in DANGER:
            critical('🚨 Dangerous Port Open',
                     f'Port {num} ({DANGER[num]}) is open on this machine!')

    # 2. UFW disabled
    ufw_raw, _, rc = run_cmd(['sudo', 'ufw', 'status'])
    if rc == 0 and ufw_raw:
        if 'inactive' in ufw_raw.lower():
            warning('⚠ Firewall Inactive',
                    'UFW firewall is disabled. Your system is exposed.')

    # 3. Failed SSH logins
    # Use journalctl -u ssh and count in Python
    ssh_out, _, _ = run_cmd(['journalctl', '-u', 'ssh', '--since', '5 minutes ago'])
    if ssh_out:
        import re
        n = len(re.findall(r'Failed password', ssh_out))
        if n >= 5:
            critical('🔐 SSH Brute Force',
                     f'{n} failed SSH login attempts in last 5 minutes!')

    # 4. Disk nearly full
    df_out, _, _ = run_cmd(['df', '/'])
    if df_out:
        try:
            import re
            # Parse second line
            line = df_out.splitlines()[1]
            pct_m = re.search(r'(\d+)%', line)
            if pct_m:
                pct = int(pct_m.group(1))
                if pct >= 90:
                    warning('💾 Disk Almost Full', f'Root partition is {pct}% full.')
        except Exception:
            pass

