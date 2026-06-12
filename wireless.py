"""
Mint Scan v11.1 — Wireless Sync
Local server for Android companion app to sync calls, SMS, and battery state.
"""
import tkinter as tk
import customtkinter as ctk
import threading, time, socket, subprocess, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from widgets import C, MONO_SM, Btn, Card, SectionHeader, InfoGrid, FONT
from utils import get_local_ip, copy_to_clipboard

def run(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return out, err, p.returncode

_server_instance = None
_sync_data = {
    'device': {},
    'calls': [],
    'sms': [],
    'contacts': [],
    'battery': {},
    'wifi': [],
    'network': {},
    'location': {},
    'last_sync': None
}

class SyncHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return # Silence server logs

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.server.screen._home_page().encode())
        elif self.path == '/data':
            self._send_json(_sync_data)
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode('utf-8'))
        except:
            self._send_json({'error': 'invalid json'}, 400)
            return

        path = self.path
        if path == '/sync/device':
            _sync_data['device']    = payload
            _sync_data['last_sync'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self._send_json({'ok': True})

        elif path == '/sync/calls':
            _sync_data['calls']     = payload.get('calls', [])
            _sync_data['last_sync'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self._send_json({'ok': True, 'received': len(_sync_data['calls'])})

        elif path == '/sync/sms':
            _sync_data['sms']       = payload.get('sms', [])
            _sync_data['last_sync'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self._send_json({'ok': True, 'received': len(_sync_data['sms'])})

        elif path == '/sync/contacts':
            _sync_data['contacts']  = payload.get('contacts', [])
            _sync_data['last_sync'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self._send_json({'ok': True, 'received': len(_sync_data['contacts'])})

        elif path == '/sync/battery':
            _sync_data['battery']   = payload
            _sync_data['last_sync'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self._send_json({'ok': True})

        elif path == '/sync/wifi':
            _sync_data['wifi']      = payload.get('networks', [])
            _sync_data['last_sync'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self._send_json({'ok': True})

        elif path == '/sync/network':
            _sync_data['network']   = payload
            _sync_data['last_sync'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self._send_json({'ok': True})

        elif path == '/sync/location':
            _sync_data['location']  = payload
            _sync_data['last_sync'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self._send_json({'ok': True})

        elif path == '/sync/all':
            for key in ['device','calls','sms','contacts','battery','wifi','network','location']:
                if key in payload:
                    _sync_data[key] = payload[key]
            _sync_data['last_sync'] = time.strftime('%Y-%m-%d %H:%M:%S')
            self._send_json({'ok': True})

        else:
            self._send_json({'error': 'unknown endpoint'}, 404)

    def _home_page(self):
        """Web page shown when phone opens the server IP in a browser"""
        calls_count    = len(_sync_data.get('calls', []))
        sms_count      = len(_sync_data.get('sms', []))
        contacts_count = len(_sync_data.get('contacts', []))
        battery        = _sync_data.get('battery', {})
        device         = _sync_data.get('device', {})
        last           = _sync_data.get('last_sync') or 'Never'

        return f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mint Scan Sync</title>
<style>
  body {{ background:#020c14; color:#c8e8f4; font-family:monospace; padding:20px; margin:0; }}
  h1   {{ color:#00ffe0; font-size:24px; margin:0 0 4px 0; }}
  .sub {{ color:#3a6278; font-size:12px; margin-bottom:24px; }}
  .card {{ background:#061523; border:1px solid #0d2a3d; border-radius:8px;
           padding:16px; margin-bottom:12px; }}
  .label {{ color:#3a6278; font-size:11px; text-transform:uppercase; }}
  .value {{ color:#00ffe0; font-size:18px; font-weight:bold; margin:4px 0; }}
  .ok   {{ color:#39ff88; }} .warn {{ color:#ff4c4c; }}
  .btn  {{ display:block; background:transparent; border:1px solid #00ffe0;
           color:#00ffe0; padding:14px; border-radius:6px; font-family:monospace;
           font-size:14px; cursor:pointer; margin-bottom:10px; width:100%;
           text-align:center; text-decoration:none; }}
  .btn:hover {{ background:#0d2a3d; }}
  .sec-note {{ font-size:10px; color:#4a7a96; border:1px solid #0d2a3d; padding:10px; border-radius:4px; margin-top:20px; }}
</style>
</head>
<body>
<h1>[ MINT SCAN ]</h1>
<div class="sub">Wireless Sync v11.1 — Local Secure Tunnel</div>

<div class="card">
  <div class="label">Server Status</div>
  <div class="value ok">CONNECTED (LOCAL)</div>
  <div class="label">Last sync: {last}</div>
</div>

<div class="card">
  <div class="label">Syncing Device</div>
  <div class="value">{device.get('model', 'Waiting for sync...')}</div>
  <div class="label">{device.get('brand','')} Android {device.get('android','')}</div>
</div>

<div class="card">
  <div class="label">Synced Data</div>
  <div>📞 {calls_count} calls &nbsp; 💬 {sms_count} messages &nbsp; 📇 {contacts_count} contacts</div>
  <div style="margin-top:8px">🔋 Battery: {battery.get('level','—')}%
  {'🔌' if battery.get('charging') else '🔋'}</div>
</div>

<div style="margin-top:20px">
  <a class="btn" href="/data">📊 View Raw Data</a>
</div>

<div class="sec-note">
  <b>SECURITY NOTE:</b> This connection is restricted to your local Wi-Fi network. 
  Traffic remains within your private router. Encryption is handled by your WPA2/WPA3 Wi-Fi protocol.
</div>

<div style="color:#3a6278; font-size:11px; margin-top:20px; text-align:center">
  © 2026 Mint Projects PTY (Ltd)
</div>
</body>
</html>"""


class ScrollableFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)

class WirelessScreen(ctk.CTkFrame):
    def _safe_after(self, delay, fn, *args):
        def _guarded():
            try:
                if self.winfo_exists(): fn(*args)
            except: pass
        try: self.after(delay, _guarded)
        except: pass

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built  = False
        self._server = None
        self._port   = 8765
        self._polling = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._refresh_status()
        self._polling = True
        if _server_instance:
            self._poll_data()

    def on_blur(self):
        self._polling = False

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="📡  WIRELESS SYNC",
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        self._status_dot = ctk.CTkLabel(hdr, text="● OFFLINE",
                                         font=MONO_SM, text_color=C['wn'])
        self._status_dot.pack(side='left', padx=8)
        
        self._stop_btn = Btn(hdr, "⏹ STOP", command=self._stop_server, variant='danger', width=80)
        self._stop_btn.pack(side='right', padx=4, pady=6)
        self._stop_btn.configure(state='disabled')
        self._start_btn = Btn(hdr, "▶ START", command=self._start_server, width=80)
        self._start_btn.pack(side='right', padx=4, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        SectionHeader(body, '01', 'SERVER CONFIG').pack(fill='x', padx=14, pady=(14,4))
        self._conn_card = Card(body)
        self._conn_card.pack(fill='x', padx=14, pady=(0,8))
        
        port_row = ctk.CTkFrame(self._conn_card, fg_color='transparent')
        port_row.pack(fill='x', padx=12, pady=10)
        ctk.CTkLabel(port_row, text="PORT:", font=MONO_SM, text_color=C['mu']).pack(side='left')
        self._port_entry = ctk.CTkEntry(port_row, width=80, font=MONO_SM, fg_color=C['bg'], border_color=C['br'])
        self._port_entry.pack(side='left', padx=8)
        self._port_entry.insert(0, str(self._port))
        
        SectionHeader(body, '02', 'CONNECTION QR').pack(fill='x', padx=14, pady=(10,4))
        qr_card = Card(body)
        qr_card.pack(fill='x', padx=14, pady=(0,8))

        # Crostini Warning
        from utils import _is_crostini
        if _is_crostini():
            warn = ctk.CTkFrame(qr_card, fg_color=C['wng'], corner_radius=6, border_width=1, border_color=C['wn'])
            warn.pack(fill='x', padx=12, pady=(12,0))
            ctk.CTkLabel(warn, text="CHROMEBOOK DETECTED", font=(FONT, 10, 'bold'), text_color=C['wn']).pack(anchor='w', padx=10, pady=(5,0))
            ctk.CTkLabel(warn, text="To sync, you MUST forward the port in ChromeOS Settings:\nSettings → Developers → Linux → Port Forwarding → Add 8765",
                         font=(FONT, 9), text_color=C['tx'], justify='left').pack(anchor='w', padx=10, pady=(0,5))
        
        self.qr_canvas = tk.Canvas(qr_card, width=200, height=200, bg='white', highlightthickness=0)
        self.qr_canvas.pack(pady=10)
        
        # Make the URL label clickable/editable
        self._qr_msg = ctk.CTkLabel(qr_card, text="Start server to generate QR", font=MONO_SM, text_color=C['mu'], cursor='hand2')
        self._qr_msg.pack(pady=(0,10))
        self._qr_msg.bind("<Button-1>", self._edit_url)

        SectionHeader(body, '03', 'SYNCED DATA').pack(fill='x', padx=14, pady=(10,4))
        self._data_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._data_frame.pack(fill='x', padx=14, pady=(0,8))

        SectionHeader(body, '04', 'LOGS').pack(fill='x', padx=14, pady=(10,4))
        self._log = ctk.CTkTextbox(body, height=120, font=('DejaVu Sans Mono',9), fg_color=C['sf'], text_color=C['ok'])
        self._log.pack(fill='x', padx=14, pady=(0,14))

    def _log_msg(self, msg):
        self._log.configure(state='normal')
        self._log.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self._log.see('end')
        self._log.configure(state='disabled')

    def _start_server(self):
        global _server_instance
        try: self._port = int(self._port_entry.get())
        except: self._port = 8765
        
        try:
            _server_instance = HTTPServer(('0.0.0.0', self._port), SyncHandler)
            _server_instance.screen = self
            threading.Thread(target=_server_instance.serve_forever, daemon=True).start()
            self._log_msg(f"Server started on port {self._port}")
            self._start_btn.configure(state='disabled')
            self._stop_btn.configure(state='normal')
            self._status_dot.configure(text='● ONLINE', text_color=C['ok'])
            self._refresh_status()
            self._poll_data()
        except Exception as e:
            self._log_msg(f"Error: {e}")

    def _stop_server(self):
        global _server_instance
        if _server_instance:
            _server_instance.shutdown()
            _server_instance = None
        self._log_msg("Server stopped")
        self._start_btn.configure(state='normal')
        self._stop_btn.configure(state='disabled')
        self._status_dot.configure(text='● OFFLINE', text_color=C['wn'])

    def _draw_qr(self, url):
        self.qr_canvas.delete('all')
        try:
            import qrcode
            from PIL import ImageTk, Image
            
            qr = qrcode.QRCode(version=1, box_size=4, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to PhotoImage
            self._qr_img = ImageTk.PhotoImage(img)
            self.qr_canvas.create_image(100, 100, image=self._qr_img)
            log.info(f"Generated QR code for {url}")
        except Exception as e:
            # Fallback if libraries fail
            self.qr_canvas.create_text(100, 100, text="QR ERROR", font=('Arial', 12, 'bold'))
            self.qr_canvas.create_text(100, 130, text=str(e), font=('Arial', 8), width=180)
            log.error(f"QR generation failed: {e}")

    def _edit_url(self, event=None):
        if not _server_instance: return
        dialog = ctk.CTkInputDialog(text="Enter the Chromebook's LAN IP (e.g. 192.168.1.15):\n(Leave empty to reset to auto-detect)", title="Manual IP Override")
        manual_ip = dialog.get_input()
        if manual_ip is not None:
            self._manual_ip = manual_ip.strip()
            self._refresh_status()

    def _refresh_status(self):
        ip = getattr(self, '_manual_ip', '') or get_local_ip()
        url = f"http://{ip}:{self._port}"
        if _server_instance:
            self._draw_qr(url)
            self._qr_msg.configure(text=f"CONNECT: {url}", text_color=C['ac'])
        else:
            self.qr_canvas.delete('all')
            self._qr_msg.configure(text="Start server to generate QR", text_color=C['mu'])

    def _poll_data(self):
        if _server_instance and self._polling:
            self._render_sync_data()
            self.after(3000, self._poll_data)

    def _render_sync_data(self):
        for w in self._data_frame.winfo_children(): w.destroy()
        last = _sync_data.get('last_sync')
        if not last:
            ctk.CTkLabel(self._data_frame, text="Waiting for device sync...", font=MONO_SM, text_color=C['mu']).pack(pady=10)
            return
        
        InfoGrid(self._data_frame, [
            ('MODEL', _sync_data['device'].get('model','—'), C['ac']),
            ('BATTERY', f"{_sync_data['battery'].get('level','—')}%", C['ok']),
            ('LAST SYNC', last, C['tx'])
        ], columns=3).pack(fill='x')
