"""Shared utilities and real data collectors for Mint Scan Linux"""
import subprocess
import socket
import os
import re
import json
import threading
import time
import shutil
import shlex
from logger import get_logger as _get_logger
_log = _get_logger("utils")

# Import colours and fonts from widgets (single source of truth)
from widgets import C, MONO, MONO_SM, MONO_LG, MONO_XL


def run_cmd(cmd, timeout=8):
    """
    Run a shell command safely.
    Uses sudo -n (passwordless) so commands work on Chromebook/Crostini.
    Sets DEBIAN_FRONTEND=noninteractive for apt commands.
    """
    if isinstance(cmd, list):
        # Convert list to a safe shell string
        cmd = " ".join(shlex.quote(arg) for arg in cmd)

    original_cmd = cmd

    # For sudo commands: use sudo -n (non-interactive) first,
    # fall back to plain sudo (user may have passwordless sudo configured)
    # sudo -n = non-interactive; works with Chromebook passwordless sudo
    if cmd.strip().startswith('sudo ') and os.geteuid() != 0:
        inner = cmd.strip()[5:].strip()
        # Use shlex.quote for more robust escaping if it was just a string
        # but wait, if it's already a complex command string with its own quotes
        # we might break it if we shlex.quote(inner) as a whole.
        # The original implementation's inner.replace("'", "'\\''") is actually
        # the correct way to escape for a bash -c '...' string.
        inner_q = inner.replace("'", "'\\''")
        cmd = f"sudo -n bash -c '{inner_q}' 2>/dev/null || sudo bash -c '{inner_q}'"

    run_env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}

    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout, env=run_env)
        if r.returncode != 0 and r.stderr.strip():
            _log.debug(f'cmd [{r.returncode}]: {r.stderr.strip()[:120]}')
        return r.stdout.strip(), r.stderr.strip(), r.returncode

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


def run_safe(parts, timeout=8):
    """
    Execute a command formed from parts. Parts can be strings (literal)
    or tuples (value_to_quote,).
    Example: run_safe(["ls -la", (path,)]) -> ls -la '/path with spaces'
    """
    cmd_str = ""
    for part in parts:
        if isinstance(part, tuple):
            cmd_str += shlex.quote(str(part[0]))
        else:
            cmd_str += str(part)
        cmd_str += " "
    return run_cmd(cmd_str.strip(), timeout=timeout)


def get_public_ip_info():
    """Fetch real public IP, ISP, city, country from ipapi.co."""
    try:
        import urllib.request
        req = urllib.request.Request(
            'https://ipapi.co/json/',
            headers={'User-Agent': 'MintScan/8'})
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


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
    out, _, rc = run_safe(['ping -c', (count,), '-W 2', (host,)])
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


def get_wifi_networks():
    """
    Real Wi-Fi scan using nmcli (NetworkManager).
    Returns list of dicts with ssid, signal, security, channel, freq, bssid.
    """
    networks = []

    # Rescan first
    run_cmd("nmcli device wifi rescan 2>/dev/null", timeout=5)

    out, err, rc = run_cmd(
        "nmcli -t -f SSID,BSSID,SIGNAL,SECURITY,CHAN,FREQ device wifi list 2>/dev/null")

    if (rc != 0 or not out) and os.geteuid() != 0:
        out, err, rc = run_cmd(
            "sudo nmcli -t -f SSID,BSSID,SIGNAL,SECURITY,CHAN,FREQ device wifi list 2>/dev/null")

    if rc == 0 and out:
        for line in out.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split(':')
            if len(parts) >= 5:
                ssid     = parts[0] if parts[0] else '(hidden)'
                bssid    = ':'.join(parts[1:7]) if len(parts) >= 7 else parts[1]
                try:
                    signal = int(parts[-4]) if len(parts) >= 5 else 0
                except ValueError:
                    signal = 0
                security = parts[-3] if len(parts) >= 4 else 'OPEN'
                channel  = parts[-2] if len(parts) >= 3 else '—'
                freq     = parts[-1] if len(parts) >= 2 else '—'
                networks.append({
                    'ssid':     ssid,
                    'bssid':    bssid,
                    'signal':   signal,
                    'security': 'OPEN' if not security or security == '--' else security,
                    'channel':  channel,
                    'freq':     freq,
                })
        if networks:
            return sorted(networks, key=lambda x: -x['signal'])

    # Fallback: iwlist scan
    iface = get_wifi_interface()
    if iface:
        out, _, rc = run_safe(['sudo iwlist', (iface,), 'scan 2>/dev/null'])
        if rc == 0 and 'ESSID' in out:
            cells = out.split('Cell ')
            for cell in cells[1:]:
                ssid_m   = re.search(r'ESSID:"([^"]*)"', cell)
                signal_m = re.search(r'Signal level=(-?\d+)', cell)
                enc_m    = re.search(r'Encryption key:(on|off)', cell)
                freq_m   = re.search(r'Frequency:([\d.]+)', cell)
                bssid_m  = re.search(r'Address: ([0-9A-F:]+)', cell)
                chan_m   = re.search(r'Channel:(\d+)', cell)
                networks.append({
                    'ssid':     ssid_m.group(1)   if ssid_m   else '(hidden)',
                    'bssid':    bssid_m.group(1)  if bssid_m  else '—',
                    'signal':   int(signal_m.group(1)) if signal_m else -100,
                    'security': 'WPA/WPA2' if enc_m and enc_m.group(1) == 'on' else 'OPEN',
                    'channel':  chan_m.group(1)   if chan_m   else '—',
                    'freq':     freq_m.group(1)+'GHz' if freq_m else '—',
                })

    return sorted(networks, key=lambda x: -x['signal'])


def get_wifi_interface():
    """Detect the wireless interface name."""
    out, _, _ = run_cmd('iw dev 2>/dev/null | grep Interface')
    if out:
        parts = out.strip().split()
        if len(parts) >= 2:
            return parts[-1]
    try:
        for iface in os.listdir('/sys/class/net'):
            if os.path.exists(f'/sys/class/net/{iface}/wireless'):
                return iface
    except Exception:
        pass
    return None


def get_current_wifi():
    """Get currently connected SSID."""
    out, _, rc = run_cmd('nmcli -t -f NAME,TYPE,DEVICE,STATE connection show --active 2>/dev/null')
    for line in out.split('\n'):
        if 'wifi' in line.lower() or '802-11' in line.lower():
            parts = line.split(':')
            if parts:
                return parts[0]
    out, _, rc = run_cmd('iwgetid -r 2>/dev/null')
    if rc == 0 and out:
        return out.strip()
    return None


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
    out, _, _ = run_safe(["ps aux --sort=-%cpu | head -n", (top_n+1,), "2>/dev/null"])
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
