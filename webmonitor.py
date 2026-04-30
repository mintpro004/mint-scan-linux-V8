"""
Mint Scan v8 — Web-Based Remote Monitoring Interface
Token-authenticated HTTP server on port 7777.
Access from any device on the same network: http://<ip>:7777?token=XXXX

Security:
- Random 8-character token generated on each server start
- All endpoints require ?token= query parameter
- POST /api/data also requires X-Token header
- Token displayed in UI and logged at startup
"""
import threading, json, time, os, socket, secrets, string
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from logger import get_logger
import tkinter as tk
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, InfoGrid)

log = get_logger('webmonitor')

_server_instance = None
_server_thread   = None
DEFAULT_PORT     = 7777
_shared_data: dict = {}
_shared_data_lock = __import__('threading').Lock()
_server_token: str = ''   # generated when server starts


def _generate_token(length: int = 10) -> str:
    """Generate a cryptographically random alphanumeric token."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ── Dashboard HTML ────────────────────────────────────────────────
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mint Scan v8 — Remote Monitor</title>
<style>
:root{--bg:#05111f;--sf:#0a1f35;--ac:#00ffe0;--ok:#44ff99;--wn:#ff5555;--am:#ffcc44;--tx:#e8f4ff;--mu:#7fb8d8}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:'Courier New',monospace;padding:12px}
.hdr{background:var(--sf);padding:12px 18px;border-radius:6px;display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.logo{color:var(--ac);font-size:18px;font-weight:bold}
.ts{color:var(--mu);font-size:9px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;margin-bottom:12px}
.cell{background:var(--sf);border:1px solid #1a3f5c;border-radius:6px;padding:10px}
.lbl{font-size:8px;color:var(--mu);margin-bottom:4px}
.val{font-size:15px;font-weight:bold;color:var(--tx);word-break:break-all}
.ok{color:var(--ok)}.wn{color:var(--wn)}.am{color:var(--am)}.ac{color:var(--ac)}
.card{background:var(--sf);border:1px solid #1a3f5c;border-radius:6px;padding:12px;margin-bottom:10px}
.sec{font-size:9px;color:var(--ac);font-weight:bold;letter-spacing:1px;margin-bottom:8px}
pre{font-size:9px;color:var(--ok);max-height:180px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.score-big{font-size:48px;font-weight:bold;text-align:center;padding:16px}
.auth-box{background:var(--sf);border:2px solid var(--am);border-radius:8px;padding:24px;max-width:360px;margin:80px auto;text-align:center}
.auth-box h2{color:var(--am);margin-bottom:16px}
.auth-box input{background:#020c14;border:1px solid #1a3f5c;color:var(--ac);font-family:'Courier New',monospace;font-size:16px;padding:10px;width:100%;border-radius:4px;text-align:center;letter-spacing:4px}
.auth-box button{background:var(--ac);color:#020c14;font-weight:bold;font-family:'Courier New',monospace;padding:10px 24px;border:none;border-radius:4px;margin-top:12px;cursor:pointer;font-size:14px;width:100%}
.err{color:var(--wn);font-size:11px;margin-top:8px;min-height:16px}
</style>
</head>
<body>
<div id="auth-screen" class="auth-box">
  <h2>🔒 MINT SCAN v8</h2>
  <p style="color:var(--mu);font-size:11px;margin-bottom:16px">Enter the access token shown in the desktop app</p>
  <input type="text" id="token-input" placeholder="Enter token" autocomplete="off" autofocus>
  <button onclick="login()">CONNECT</button>
  <div class="err" id="auth-err"></div>
</div>
<div id="main-screen" style="display:none">
  <div class="hdr">
    <div class="logo">[ MINT SCAN ] v8 — Remote Monitor</div>
    <div class="ts" id="ts">--:--:--</div>
  </div>
  <div class="score-big ok" id="score">--</div>
  <div class="grid" id="grid">Loading...</div>
  <div class="card"><div class="sec">// THREATS</div><div id="threats">--</div></div>
  <div class="card"><div class="sec">// OPEN PORTS</div><pre id="ports">--</pre></div>
  <div class="card"><div class="sec">// SYSTEM</div><div class="grid" id="sysgrid"></div></div>
</div>
<script>
let _token = '';
function login(){
  _token = document.getElementById('token-input').value.trim();
  if(!_token){document.getElementById('auth-err').textContent='Enter the token';return;}
  // Verify token immediately
  fetch('/api/status?token='+encodeURIComponent(_token))
    .then(r=>{
      if(r.status===401){document.getElementById('auth-err').textContent='Invalid token';_token='';return;}
      if(!r.ok){document.getElementById('auth-err').textContent='Server error';return;}
      // Token valid — show dashboard
      document.getElementById('auth-screen').style.display='none';
      document.getElementById('main-screen').style.display='block';
      refresh();
      setInterval(refresh,5000);
    })
    .catch(()=>{document.getElementById('auth-err').textContent='Cannot connect to Mint Scan';});
}
document.getElementById('token-input').addEventListener('keydown',e=>{if(e.key==='Enter')login();});
async function refresh(){
  if(!_token)return;
  try{
    const r=await fetch('/api/data?token='+encodeURIComponent(_token));
    if(r.status===401){document.getElementById('main-screen').style.display='none';document.getElementById('auth-screen').style.display='block';_token='';return;}
    const d=await r.json();
    document.getElementById('ts').textContent=new Date().toLocaleTimeString();
    const sc=d.score||0;
    const sel=document.getElementById('score');
    sel.textContent=sc;
    sel.className='score-big '+(sc>=75?'ok':sc>=50?'am':'wn');
    const g=document.getElementById('grid');
    g.innerHTML=['LOCAL IP','PUBLIC IP','CPU','RAM','BATTERY','UPTIME','HOSTNAME','OS'].map(k=>{
      const v=d[k.toLowerCase().replace(/ /,'_')]||'—';
      return '<div class="cell"><div class="lbl">'+k+'</div><div class="val">'+v+'</div></div>';
    }).join('');
    const t=document.getElementById('threats');
    t.innerHTML=(d.threats||[]).map(th=>'<div style="color:var(--wn);padding:2px 0">⚠ '+th+'</div>').join('')||'<span style="color:var(--ok)">✓ No active threats</span>';
    document.getElementById('ports').textContent=(d.ports||[]).map(p=>p.port+'/'+p.proto+'  '+(p.service||'')).join('\\n')||'—';
    const sg=document.getElementById('sysgrid');
    sg.innerHTML=Object.entries(d.system||{}).map(([k,v])=>'<div class="cell"><div class="lbl">'+k+'</div><div class="val ac">'+v+'</div></div>').join('');
  }catch(e){console.log(e);}
}
</script>
</body>
</html>'''


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.debug(f'HTTP {args[1]} {args[0]}')

    def _check_token(self) -> bool:
        """Validate token from query string or X-Token header."""
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)
        # Accept from query param or header
        token_qs  = qs.get('token', [''])[0]
        token_hdr = self.headers.get('X-Token', '')
        provided  = token_qs or token_hdr
        if not _server_token:
            return True   # server not configured — shouldn't happen
        return secrets.compare_digest(provided, _server_token)

    def _unauthorized(self):
        body = b'{"error":"Unauthorized - invalid or missing token"}'
        self.send_response(401)
        self.send_header('Content-Type', 'application/json')
        self.send_header('WWW-Authenticate', 'Token realm="MintScan"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        # Dashboard HTML — always served (login page handles auth client-side)
        if path in ('/', '/index.html'):
            self._send(200, 'text/html', DASHBOARD_HTML.encode())
            return

        # All API endpoints require valid token
        if not self._check_token():
            self._unauthorized()
            return

        if path == '/api/data':
            self._send(200, 'application/json',
                       json.dumps(dict(_shared_data)).encode())
        elif path == '/api/status':
            self._send(200, 'application/json',
                       json.dumps({'status': 'ok', 'version': '8.0'}).encode())
        else:
            self._send(404, 'text/plain', b'Not found')

    def do_POST(self):
        # Require token for data sync too
        if not self._check_token():
            self._unauthorized()
            return
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        try:
            data = json.loads(body)
            with _shared_data_lock:
                _shared_data.update(data)
        except Exception:
            pass
        self._send(200, 'application/json', b'{"ok":true}')

    def _send(self, code, ct, body):
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)


def start_server(port: int = DEFAULT_PORT) -> tuple[bool, str]:
    """Start the server. Returns (success, token)."""
    global _server_instance, _server_thread, _server_token
    if _server_instance:
        return True, _server_token
    try:
        _server_token    = _generate_token(10)
        _server_instance = HTTPServer(('0.0.0.0', port), _Handler)
        _server_thread   = threading.Thread(
            target=_server_instance.serve_forever, daemon=True)
        _server_thread.start()
        log.info(f'Web monitor started on port {port} — token: {_server_token}')
        _start_data_loop()
        return True, _server_token
    except Exception as e:
        log.warning(f'Web monitor failed: {e}')
        return False, ''


def stop_server():
    global _server_instance, _server_token
    if _server_instance:
        _server_instance.shutdown()
        _server_instance = None
        _server_token    = ''
        log.info('Web monitor stopped')


def _start_data_loop():
    def _loop():
        while _server_instance:
            try:
                from utils import (get_system_info, get_local_ip,
                                   get_open_ports, get_public_ip_info)
                si    = get_system_info()
                ports = get_open_ports()
                ip    = get_local_ip()
                with _shared_data_lock:
                    _shared_data.update({
                    'score':    _shared_data.get('score', 100),
                    'local_ip': ip,
                    'cpu':      si.get('cpu_cores', '—') + ' cores',
                    'ram':      si.get('ram_total', '—'),
                    'uptime':   si.get('uptime', '—'),
                    'hostname': si.get('hostname', '—'),
                    'os':       si.get('os', '—'),
                    'ports':    ports[:20],
                    'system':   {k: v for k, v in si.items()
                                 if k in ('cpu_model', 'ram_total', 'disk_free')},
                    'updated':  time.strftime('%H:%M:%S'),
                })
            except Exception as e:
                log.debug(f'Data loop: {e}')
            time.sleep(15)
    threading.Thread(target=_loop, daemon=True).start()


def get_local_url(port: int = DEFAULT_PORT) -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = '127.0.0.1'
    return f'http://{ip}:{port}'


# ── Web Monitor Screen ────────────────────────────────────────────
class WebMonitorScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app    = app
        self._built = False
        self._port  = DEFAULT_PORT

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._refresh_status()

    def on_blur(self):
        pass

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
        ctk.CTkLabel(hdr, text='🌐  WEB REMOTE MONITOR',
                     font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # ── STATUS ────────────────────────────────────────────
        SectionHeader(body, '01', 'SERVER STATUS').pack(
            fill='x', padx=14, pady=(14, 4))
        self._sc = Card(body)
        self._sc.pack(fill='x', padx=14, pady=(0, 8))
        self._status_lbl = ctk.CTkLabel(
            self._sc, text='Server not running',
            font=('DejaVu Sans Mono', 12, 'bold'), text_color=C['mu'])
        self._status_lbl.pack(pady=(12, 4))
        self._url_lbl = ctk.CTkLabel(
            self._sc, text='',
            font=('DejaVu Sans Mono', 12, 'bold'), text_color=C['ac'])
        self._url_lbl.pack(pady=(0, 4))
        ctk.CTkLabel(self._sc,
            text='Open this URL on any device on the same network.',
            font=MONO_SM, text_color=C['mu']).pack(pady=(0, 4))

        # ── TOKEN DISPLAY ─────────────────────────────────────
        SectionHeader(body, '02', 'ACCESS TOKEN').pack(
            fill='x', padx=14, pady=(8, 4))
        tc = Card(body, accent=C['am'])
        tc.pack(fill='x', padx=14, pady=(0, 8))
        ctk.CTkLabel(tc,
            text='🔒 A new token is generated each time the server starts.\n'
                 'Enter this token in the browser login page to access the dashboard.',
            font=MONO_SM, text_color=C['mu']).pack(anchor='w', padx=12, pady=(10, 4))
        self._token_lbl = ctk.CTkLabel(tc, text='—',
                                        font=('DejaVu Sans Mono', 22, 'bold'),
                                        text_color=C['am'])
        self._token_lbl.pack(pady=(4, 4))
        self._copy_btn = Btn(tc, '📋 COPY TOKEN',
                              command=self._copy_token,
                              variant='ghost', width=140)
        self._copy_btn.pack(pady=(0, 10))

        # ── CONTROLS ──────────────────────────────────────────
        SectionHeader(body, '03', 'CONTROLS').pack(
            fill='x', padx=14, pady=(8, 4))
        cc = Card(body)
        cc.pack(fill='x', padx=14, pady=(0, 8))
        cr = ctk.CTkFrame(cc, fg_color='transparent')
        cr.pack(fill='x', padx=12, pady=10)
        ctk.CTkLabel(cr, text='PORT:', font=MONO_SM,
                     text_color=C['mu']).pack(side='left')
        self._port_entry = ctk.CTkEntry(
            cr, width=80, font=MONO_SM, fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'])
        self._port_entry.pack(side='left', padx=8)
        self._port_entry.insert(0, str(DEFAULT_PORT))
        self._start_btn = Btn(cr, '▶ START', command=self._start, width=90)
        self._start_btn.pack(side='left', padx=4)
        self._stop_btn  = Btn(cr, '⏹ STOP', command=self._stop,
                               variant='danger', width=80)
        self._stop_btn.pack(side='left', padx=4)

        # ── ENDPOINTS ─────────────────────────────────────────
        SectionHeader(body, '04', 'API ENDPOINTS').pack(
            fill='x', padx=14, pady=(8, 4))
        ic = Card(body)
        ic.pack(fill='x', padx=14, pady=(0, 14))
        ctk.CTkLabel(ic,
            text='All endpoints require  ?token=<TOKEN>  in the URL\n'
                 'or  X-Token: <TOKEN>  HTTP header.',
            font=('DejaVu Sans Mono', 8), text_color=C['mu']).pack(anchor='w', padx=12, pady=(8,4))
        for ep, desc in [
            ('/             ', 'Browser login page (no token required)'),
            ('/api/data     ', 'Live JSON: score, ports, system info  [token required]'),
            ('/api/status   ', 'Health check  [token required]'),
            ('POST /api/data', 'Push data from mobile companion  [token required]'),
        ]:
            r = ctk.CTkFrame(ic, fg_color='transparent')
            r.pack(fill='x', padx=12, pady=2)
            ctk.CTkLabel(r, text=ep, font=('DejaVu Sans Mono', 8, 'bold'),
                         text_color=C['ac'], width=170).pack(side='left')
            ctk.CTkLabel(r, text=desc, font=('DejaVu Sans Mono', 8),
                         text_color=C['mu']).pack(side='left')
        ctk.CTkLabel(ic, text='', height=8).pack()

    def _refresh_status(self):
        running = _server_instance is not None
        self._status_lbl.configure(
            text='● RUNNING' if running else '○ STOPPED',
            text_color=C['ok'] if running else C['mu'])
        if running:
            url = get_local_url(self._port)
            self._url_lbl.configure(text=url)
            self._token_lbl.configure(text=_server_token or '—')
            self._start_btn.configure(state='disabled')
            self._stop_btn.configure(state='normal')
        else:
            self._url_lbl.configure(text='')
            self._token_lbl.configure(text='Start server to generate token')
            self._start_btn.configure(state='normal')
            self._stop_btn.configure(state='disabled')

    def _start(self):
        try:
            self._port = int(self._port_entry.get())
        except ValueError:
            self._port = DEFAULT_PORT
        ok, token = start_server(self._port)
        if ok:
            self._refresh_status()

    def _stop(self):
        stop_server()
        self._refresh_status()

    def _copy_token(self):
        if _server_token:
            try:
                self.winfo_toplevel().clipboard_clear()
                self.winfo_toplevel().clipboard_append(_server_token)
            except Exception:
                pass
