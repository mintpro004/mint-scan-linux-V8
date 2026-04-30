"""Shared utilities and real data collectors for Mint Scan Linux"""
import subprocess
import socket
import os
import re
import json
import threading
import time
import shutil
from logger import get_logger as _get_logger
_log = _get_logger("utils")

# Import colours and fonts from widgets (single source of truth)
from widgets import C, MONO, MONO_SM, MONO_LG, MONO_XL


def run_cmd(cmd, timeout=8):
    """
    Run a command safely.
    - If 'cmd' is a list: runs with shell=False (SECURE).
    - If 'cmd' is a string: runs with shell=True (LEGACY/INSECURE).
    Uses sudo -n (non-interactive) to prevent hanging on password prompts.
    """
    original_cmd = cmd if isinstance(cmd, str) else " ".join(cmd)
    is_shell = isinstance(cmd, str)

    # Elevation handling
    if os.getuid() != 0:
        if is_shell and cmd.strip().startswith('sudo '):
            inner = cmd.strip()[5:].strip()
            inner_q = inner.replace("'", "'\\''")
            # Try non-interactive sudo first, then fall back
            cmd = f"sudo -n bash -c '{inner_q}' 2>/dev/null || sudo bash -c '{inner_q}'"
        elif not is_shell and cmd[0] == 'sudo':
            # For lists, we ensure -n is present if not already
            if '-n' not in cmd:
                cmd.insert(1, '-n')

    run_env = {**os.environ,
               'DEBIAN_FRONTEND': 'noninteractive',
               'SUDO_ASKPASS': '/bin/false'}

    try:
        r = subprocess.run(
            cmd, shell=is_shell, capture_output=True,
            text=True, timeout=timeout, env=run_env)
        
        stdout = r.stdout.strip() if r.stdout else ""
        stderr = r.stderr.strip() if r.stderr else ""
        
        if r.returncode != 0 and stderr:
            _log.debug(f'cmd [{r.returncode}]: {stderr[:120]}')
        return stdout, stderr, r.returncode

    except subprocess.TimeoutExpired:
        _log.warning(f'Timeout ({timeout}s): {original_cmd[:80]}')
        return '', f'timeout after {timeout}s', 1

    except FileNotFoundError as e:
        _log.error(f'Not found: {e}')
        return '', str(e), 127

    except PermissionError as e:
        _log.error(f'Permission denied: {e}')
        return '', str(e), 126

    except Exception as e:
        _log.error(f'run_cmd error: {e}')
        return '', str(e), 1


_ip_cache = {'data': {}, 'ts': 0.0}

def get_public_ip_info():
    """Fetch public IP info from ipapi.co — cached for 5 minutes."""
    now = time.time()
    if _ip_cache['data'] and (now - _ip_cache['ts']) < 300:
        return _ip_cache['data']
    try:
        import urllib.request
        req = urllib.request.Request(
            'https://ipapi.co/json/',
            headers={'User-Agent': 'MintScan/8.3.0'})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
        _ip_cache['data'] = data
        _ip_cache['ts']   = now
        return data
    except Exception:
        return _ip_cache['data'] or {}


def get_local_ip():
    """Get local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '—'


def get_hostname():
    try:
        return socket.gethostname()
    except Exception:
        return '—'


def ping(host='1.1.1.1', count=1):
    """Real ICMP ping — returns avg ms or None."""
    out, _, rc = run_cmd(f'ping -c {count} -W 2 {host}')
    if rc == 0:
        m = re.search(r'avg.*?([\d.]+)', out)
        if m:
            return float(m.group(1))
    return None


def copy_to_clipboard(text):
    """Copy text to clipboard using xclip, xsel, or tkinter."""
    # Try xclip first (most reliable on Linux)
    if shutil.which('xclip'):
        try:
            p = subprocess.Popen(['xclip', '-selection', 'clipboard'],
                                  stdin=subprocess.PIPE)
            p.communicate(input=text.encode())
            return True
        except Exception:
            pass
    # Try xsel
    if shutil.which('xsel'):
        try:
            p = subprocess.Popen(['xsel', '--clipboard', '--input'],
                                  stdin=subprocess.PIPE)
            p.communicate(input=text.encode())
            return True
        except Exception:
            pass
    # Tkinter fallback
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.after(2000, root.destroy)
        root.mainloop()
        return True
    except Exception:
        return False


# ── Chromebook / Crostini detection ──────────────────────────────────────────
def _is_crostini() -> bool:
    try:
        with open('/proc/version') as f:
            v = f.read().lower()
        if 'cros' in v or 'chromeos' in v:
            return True
    except Exception:
        pass
    return os.path.exists('/dev/.cros_milestone') or os.path.exists('/run/chrome')


def _crostini_wifi_info() -> dict:
    """Read what we can from /proc/net/wireless and iw on Crostini."""
    result = {'ssid': None, 'signal': None, 'interface': None}
    try:
        with open('/proc/net/wireless') as f:
            lines = f.readlines()
        for line in lines[2:]:
            parts = line.split()
            if len(parts) >= 4:
                iface = parts[0].rstrip(':')
                try:
                    raw = float(parts[3].rstrip('.'))
                    signal_dbm = raw if raw < 0 else raw - 256
                    pct = max(0, min(100, 2 * (signal_dbm + 100)))
                except Exception:
                    pct = 50
                result['interface'] = iface
                result['signal'] = int(pct)
    except Exception:
        pass
    iface = result.get('interface')
    if iface:
        try:
            out, _, _ = run_cmd(f'iw {iface} info 2>/dev/null', timeout=4)
            m = re.search(r'ssid (.+)', out or '')
            if m:
                result['ssid'] = m.group(1).strip()
        except Exception:
            pass
    if not result['ssid']:
        try:
            out, _, rc = run_cmd(
                "gdbus call --system --dest org.chromium.flimflam "
                "--object-path / --method org.chromium.flimflam.Manager.GetProperties 2>/dev/null",
                timeout=4)
            if rc == 0 and out:
                m = re.search(r"'Name'.*?'([^']+)'", out)
                if m:
                    result['ssid'] = m.group(1)
        except Exception:
            pass
    if not result['ssid'] and result['signal'] is not None:
        result['ssid'] = '(Chrome OS managed — SSID not accessible in container)'
    return result


def get_wifi_networks():
    """
    Robust Wi-Fi scan. Uses nmcli column output (tab/fixed-width) to avoid
    the colon-collision bug where BSSID aa:bb:cc:dd:ee:ff splits fields wrong.
    Falls back to iwlist if nmcli unavailable.
    On Chromebook/Crostini: returns current connection info from /proc/net/wireless.
    """
    networks = []

    # ── Chromebook/Crostini fast path ────────────────────────────
    if _is_crostini():
        info = _crostini_wifi_info()
        if info.get('signal') is not None or info.get('ssid'):
            networks.append({
                'ssid':     info.get('ssid') or '(Chrome OS Wi-Fi)',
                'bssid':    'CHROMEOS:MANAGED',
                'signal':   info.get('signal') or 50,
                'security': 'Chrome OS',
                'channel':  '—',
                'freq':     '—',
                '_crostini': True,
                '_note':    'Chrome OS manages Wi-Fi. Full scan unavailable in Linux container.',
            })
        else:
            networks.append({
                'ssid':     'Chrome OS manages Wi-Fi',
                'bssid':    'N/A',
                'signal':   0,
                'security': 'N/A',
                'channel':  '—',
                'freq':     '—',
                '_crostini': True,
                '_note':    'Linux container cannot directly scan Wi-Fi. '
                            'Use Chrome OS Settings → Wi-Fi to manage networks.',
            })
        return networks

    # Trigger a rescan — ignore errors (requires admin on some systems)
    run_cmd("nmcli device wifi rescan 2>/dev/null", timeout=6)
    time.sleep(1)  # give driver a moment to populate results

    # Use --escape no so BSSIDs (aa:bb:…) are not backslash-escaped,
    # and separate fields with a unique delimiter that never appears in SSIDs.
    DELIM = '\x00'
    cmd = (f"nmcli --escape no -g SSID,BSSID,SIGNAL,SECURITY,CHAN,FREQ "
           f"device wifi list 2>/dev/null")
    out, _, rc = run_cmd(cmd, timeout=10)

    # If failed, retry with explicit device
    if rc != 0 or not out.strip():
        iface = get_wifi_interface()
        if iface:
            out, _, rc = run_cmd(
                f"nmcli --escape no -g SSID,BSSID,SIGNAL,SECURITY,CHAN,FREQ "
                f"device wifi list ifname {iface} 2>/dev/null", timeout=10)

    if rc == 0 and out.strip():
        for line in out.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            # nmcli -g separates fields with ':' but BSSIDs also contain ':'
            # The BSSID is always exactly 17 chars (xx:xx:xx:xx:xx:xx).
            # Safe parse: find BSSID pattern, then split around it.
            bssid_m = re.search(r'([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})', line)
            if not bssid_m:
                continue
            bssid = bssid_m.group(1)
            before = line[:bssid_m.start()].rstrip(':')
            after  = line[bssid_m.end():].lstrip(':')
            ssid   = before if before else '(hidden)'

            tail = after.split(':')
            # tail is [signal, security, channel, freq_with_unit]
            try:    signal = int(tail[0]) if tail else 0
            except: signal = 0
            security = tail[1].strip() if len(tail) > 1 else ''
            channel  = tail[2].strip() if len(tail) > 2 else '—'
            freq     = ':'.join(tail[3:]).strip() if len(tail) > 3 else '—'

            networks.append({
                'ssid':     ssid.strip(),
                'bssid':    bssid.upper(),
                'signal':   signal,
                'security': 'OPEN' if not security or security in ('--','') else security,
                'channel':  channel or '—',
                'freq':     freq or '—',
            })

        if networks:
            # De-duplicate by BSSID, keep highest signal
            seen = {}
            for n in networks:
                k = n['bssid']
                if k not in seen or n['signal'] > seen[k]['signal']:
                    seen[k] = n
            return sorted(seen.values(), key=lambda x: -x['signal'])

    # ── Fallback: iwlist scan ─────────────────────────────────────
    iface = get_wifi_interface()
    if iface:
        out, _, rc = run_cmd(f'iwlist {iface} scan 2>/dev/null', timeout=10)
        if rc != 0:
            out, _, rc = run_cmd(f'sudo iwlist {iface} scan 2>/dev/null', timeout=10)
        if rc == 0 and 'ESSID' in out:
            for cell in out.split('Cell ')[1:]:
                ssid_m   = re.search(r'ESSID:"([^"]*)"', cell)
                signal_m = re.search(r'Signal level=(-?\d+)', cell)
                enc_m    = re.search(r'Encryption key:(on|off)', cell)
                freq_m   = re.search(r'Frequency:([\d.]+)', cell)
                bssid_m  = re.search(r'Address: ([0-9A-Fa-f:]{17})', cell)
                chan_m   = re.search(r'Channel:(\d+)', cell)
                networks.append({
                    'ssid':     (ssid_m.group(1) if ssid_m else '(hidden)').strip(),
                    'bssid':    bssid_m.group(1).upper() if bssid_m else '—',
                    'signal':   int(signal_m.group(1)) + 100 if signal_m else 0,
                    'security': 'WPA/WPA2' if enc_m and enc_m.group(1) == 'on' else 'OPEN',
                    'channel':  chan_m.group(1) if chan_m else '—',
                    'freq':     freq_m.group(1) + ' GHz' if freq_m else '—',
                })

    # ── Last resort: iw scan ──────────────────────────────────────
    if not networks and iface:
        out, _, rc = run_cmd(f'sudo iw {iface} scan 2>/dev/null', timeout=12)
        if rc == 0 and out:
            cur: dict = {}
            for line in out.split('\n'):
                line = line.strip()
                bss = re.match(r'BSS ([0-9a-f:]{17})', line)
                if bss:
                    if cur: networks.append(cur)
                    cur = {'ssid':'(hidden)','bssid':bss.group(1).upper(),
                           'signal':0,'security':'OPEN','channel':'—','freq':'—'}
                elif 'SSID:' in line and cur:
                    cur['ssid'] = line.split('SSID:',1)[1].strip() or '(hidden)'
                elif 'signal:' in line and cur:
                    try: cur['signal'] = int(float(line.split(':',1)[1].split()[0]) + 100)
                    except: pass
                elif 'RSN' in line or 'WPA' in line:
                    if cur: cur['security'] = 'WPA2'
                elif '* primary channel:' in line and cur:
                    try: cur['channel'] = line.split(':',1)[1].strip()
                    except: pass
            if cur: networks.append(cur)

    return sorted(networks, key=lambda x: -x['signal'])


def get_wifi_interface():
    """Detect the wireless interface name."""
    out, _, _ = run_cmd(['iw', 'dev'])
    if out:
        for line in out.splitlines():
            if 'Interface' in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    return parts[-1]
    try:
        for iface in os.listdir('/sys/class/net'):
            if os.path.exists(f'/sys/class/net/{iface}/wireless'):
                return iface
    except Exception:
        pass
    # Crostini: check /proc/net/wireless for interface names
    try:
        with open('/proc/net/wireless') as f:
            lines = f.readlines()
        for line in lines[2:]:
            parts = line.split()
            if parts:
                return parts[0].rstrip(':')
    except Exception:
        pass
    return None


def get_current_wifi():
    """Get currently connected SSID and details robustly."""
    # Chromebook/Crostini: use our dedicated helper
    if _is_crostini():
        info = _crostini_wifi_info()
        return info.get('ssid') or '(Chrome OS Wi-Fi — managed by Chrome OS)'
    # Method 1: nmcli active connection
    out, _, rc = run_cmd(
        "nmcli -t -f NAME,TYPE,DEVICE,STATE connection show --active 2>/dev/null")
    for line in out.split('\n'):
        lo = line.lower()
        if 'wifi' in lo or '802-11' in lo or 'wireless' in lo:
            name = line.split(':')[0].strip()
            if name:
                return name
    # Method 2: nmcli device active SSID
    out, _, rc = run_cmd(
        "nmcli -t -f ACTIVE,SSID device wifi list 2>/dev/null")
    for line in out.split('\n'):
        if line.startswith('yes:') or line.startswith('*:'):
            ssid = line.split(':', 1)[1].strip()
            if ssid:
                return ssid
    # Method 3: iwgetid
    out, _, rc = run_cmd('iwgetid -r 2>/dev/null')
    if rc == 0 and out.strip():
        return out.strip()
    # Method 4: iw dev
    iface = get_wifi_interface()
    if iface:
        out, _, _ = run_cmd(f'iw {iface} info 2>/dev/null')
        m = re.search(r'ssid (.+)', out)
        if m:
            return m.group(1).strip()
    return None


def get_saved_wifi_networks():
    """
    Return list of previously connected Wi-Fi networks with last-used time.
    Reads from NetworkManager connection profiles.
    """
    saved = []

    # Method 1: nmcli connection show (lists all profiles)
    out, _, rc = run_cmd(
        "nmcli -t -f NAME,TYPE,TIMESTAMP-REAL connection show 2>/dev/null",
        timeout=8)
    if rc == 0 and out:
        for line in out.split('\n'):
            line = line.strip()
            if not line:
                continue
            # Format: NAME:TYPE:TIMESTAMP
            # NAME may contain colons — split from right
            parts = line.rsplit(':', 2)
            if len(parts) < 2:
                continue
            if len(parts) == 3:
                name, ctype, ts = parts
            elif len(parts) == 2:
                name, ctype = parts
                ts = 'never'
            
            if '802-11' in ctype.lower() or 'wifi' in ctype.lower():
                saved.append({
                    'name': name,
                    'last': ts or 'never'
                })
    return saved


def connect_to_wifi(ssid, password=None):
    """Attempt to connect to a Wi-Fi network using nmcli."""
    if password:
        # Use --ask if we wanted interactive, but here we want automated
        cmd = ["nmcli", "device", "wifi", "connect", ssid, "password", password]
    else:
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
    
    out, err, rc = run_cmd(cmd, timeout=30)
    return rc == 0, out or err


def get_network_interfaces():
    """Get all network interfaces with IP, MAC, status."""
    ifaces = []
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            ip4   = addrs.get(netifaces.AF_INET,  [{}])[0].get('addr', '—')
            ip6   = addrs.get(netifaces.AF_INET6, [{}])[0].get('addr', '—')
            mac   = addrs.get(netifaces.AF_LINK,  [{}])[0].get('addr', '—')
            ifaces.append({'name': iface, 'ip4': ip4, 'ip6': ip6, 'mac': mac})
    except ImportError:
        out, _, _ = run_cmd('ip addr show 2>/dev/null')
        current = None
        for line in out.split('\n'):
            m = re.match(r'\d+: (\S+):', line)
            if m:
                current = {'name': m.group(1), 'ip4': '—', 'ip6': '—', 'mac': '—'}
                ifaces.append(current)
            if current:
                ip4_m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                mac_m = re.search(r'link/\S+ ([0-9a-f:]{17})', line)
                if ip4_m: current['ip4'] = ip4_m.group(1)
                if mac_m: current['mac'] = mac_m.group(1)
    return ifaces


def get_battery_info():
    """Read real battery info from /sys/class/power_supply."""
    base = '/sys/class/power_supply'
    if not os.path.exists(base):
        return None
    for name in os.listdir(base):
        path = os.path.join(base, name)
        try:
            ptype = open(os.path.join(path, 'type')).read().strip()
            if ptype == 'Battery':
                def r(f):
                    fp = os.path.join(path, f)
                    return open(fp).read().strip() if os.path.exists(fp) else None
                cap     = r('capacity')
                status  = r('status')
                health  = r('health')
                tech    = r('technology')
                voltage = r('voltage_now')
                current = r('current_now')
                cycles  = r('cycle_count')
                return {
                    'level':   int(cap) if cap else None,
                    'status':  status or 'Unknown',
                    'health':  health or 'Unknown',
                    'tech':    tech or 'Unknown',
                    'voltage': f"{int(voltage)/1e6:.2f}V" if voltage else '—',
                    'current': f"{abs(int(current))/1e6:.2f}A" if current else '—',
                    'cycles':  cycles or '—',
                }
        except Exception:
            continue
    return None


def get_system_info():
    """Collect real system information."""
    import platform
    info = {}
    info['os']       = platform.system()
    info['os_ver']   = platform.version()
    info['distro']   = platform.platform()
    info['machine']  = platform.machine()
    info['arch']     = platform.architecture()[0]
    info['hostname'] = get_hostname()
    info['kernel']   = run_cmd('uname -r')[0]
    info['cpu_model']= run_cmd("grep 'model name' /proc/cpuinfo | head -1 | cut -d: -f2")[0].strip()
    info['cpu_cores']= run_cmd("nproc")[0]
    mem_out = run_cmd("free -h | grep Mem")[0]
    if mem_out:
        parts = mem_out.split()
        if len(parts) >= 3:
            info['ram_total'] = parts[1]
            info['ram_used']  = parts[2]
            info['ram_free']  = parts[3] if len(parts) > 3 else '—'
    info['uptime'] = run_cmd("uptime -p")[0]
    disk_out = run_cmd("df -h / | tail -1")[0]
    if disk_out:
        parts = disk_out.split()
        if len(parts) >= 5:
            info['disk_total'] = parts[1]
            info['disk_used']  = parts[2]
            info['disk_free']  = parts[3]
            info['disk_pct']   = parts[4]
    info['gpu'] = run_cmd("lspci 2>/dev/null | grep -i 'vga\\|3d\\|2d' | head -1 | cut -d: -f3")[0].strip() or '—'
    return info


def get_processes(top_n=20):
    """Get top processes by CPU usage."""
    out, _, _ = run_cmd(f"ps aux --sort=-%cpu | head -{top_n+1} 2>/dev/null")
    procs = []
    for line in out.strip().split('\n')[1:]:
        parts = line.split(None, 10)
        if len(parts) >= 11:
            procs.append({
                'user':    parts[0],
                'pid':     parts[1],
                'cpu':     parts[2],
                'mem':     parts[3],
                'command': parts[10][:50],
            })
    return procs


def get_open_ports():
    """List open TCP/UDP ports using ss."""
    ports = []
    out, _, _ = run_cmd("ss -tlnp 2>/dev/null")
    for line in out.split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 4:
            local = parts[3]
            port_m = re.search(r':(\d+)$', local)
            if port_m:
                ports.append({
                    'proto':   'TCP',
                    'state':   parts[0],
                    'local':   local,
                    'port':    port_m.group(1),
                    'process': parts[5] if len(parts) > 5 else '—',
                })
    out2, _, _ = run_cmd("ss -ulnp 2>/dev/null")
    for line in out2.split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 4:
            local = parts[4] if len(parts) > 4 else parts[3]
            port_m = re.search(r':(\d+)$', local)
            if port_m:
                ports.append({
                    'proto':   'UDP',
                    'state':   'LISTENING',
                    'local':   local,
                    'port':    port_m.group(1),
                    'process': parts[5] if len(parts) > 5 else '—',
                })
    return ports


def check_root():
    return os.geteuid() == 0


def get_active_connections():
    """Get active network connections."""
    out, _, _ = run_cmd("ss -tnp state established 2>/dev/null")
    conns = []
    for line in out.split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 5:
            conns.append({
                'local':   parts[3],
                'remote':  parts[4],
                'process': parts[5] if len(parts) > 5 else '—',
            })
    return conns


SA_OPERATORS = {
    '60': 'Telkom', '61': 'Telkom', '62': 'Cell C', '63': 'Cell C',
    '64': 'Vodacom', '65': 'MTN', '66': 'MTN', '67': 'Cell C',
    '68': 'Telkom', '71': 'Vodacom', '72': 'Vodacom', '73': 'MTN',
    '74': 'Telkom', '76': 'Vodacom', '78': 'Vodacom', '79': 'Vodacom',
    '81': 'Vodacom', '82': 'Vodacom', '83': 'MTN',    '84': 'Cell C',
}


def analyse_phone_number(num):
    """Analyse a phone number for risk."""
    clean = re.sub(r'[\s\-()]()', '', num)
    risks = []
    if re.match(r'^0900', clean): risks.append('Premium rate (0900)')
    if re.match(r'^\+?1900', clean): risks.append('Premium rate (+1900)')
    if len(clean) < 7 and len(clean) > 2: risks.append('Short code')
    if re.search(r'(.)\1{4,}', clean): risks.append('Repeating digits')
    level = 'HIGH' if risks else 'LOW'
    sa_clean = re.sub(r'^\+27|^0027|^0', '', clean)
    op = SA_OPERATORS.get(sa_clean[:2])
    return {'risk': level, 'reasons': risks, 'operator': op, 'clean': clean}

