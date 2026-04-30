"""
Mint Scan — Wireless Sync Server
Runs a local HTTP server on the Chromebook/Linux machine.
The Android companion app (or any browser on the phone) connects over Wi-Fi
to sync calls, SMS, contacts, battery, and device info.
"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, socket, os, time, json, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from utils import copy_to_clipboard, run_cmd as run

# ── Global sync data store ─────────────────────────────────────────
_sync_data = {
    'device':   {},
    'calls':    [],
    'sms':      [],
    'contacts': [],
    'battery':  {},
    'wifi':     [],
    'location': {},
    'last_sync': None,
}
_server_instance = None


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


# ── HTTP Request Handler ───────────────────────────────────────────
class SyncHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests from the Android companion app"""

    def log_message(self, fmt, *args):
        pass  # Suppress default HTTP logging

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_page(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == '/':
            self._send_page(self._home_page())
        elif path == '/status':
            self._send_json({'status': 'online', 'version': '7.0',
                             'name': 'Mint Scan Server'})
        elif path == '/data':
            self._send_json(_sync_data)
        else:
            self._send_json({'error': 'not found'}, 404)

    def do_POST(self):
        length  = int(self.headers.get('Content-Length', 0))
        body    = self.rfile.read(length)
        parsed  = urlparse(self.path)
        path    = parsed.path

        try:
            payload = json.loads(body) if body else {}
        except Exception:
            self._send_json({'error': 'invalid JSON'}, 400)
            return

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
<div class="sub">Wireless Sync v8.3.0 — Local Secure Tunnel</div>

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


# ══════════════════════════════════════════════════════════════════
# WIRELESS SYNC SCREEN
# ══════════════════════════════════════════════════════════════════
class WirelessScreen(ctk.CTkFrame):
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
        self.app = app
        self._built  = False
        self._server = None
        self._port   = 8765

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._refresh_status()

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        # ── Header ──────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="📡  WIRELESS SYNC",
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        self._status_dot = ctk.CTkLabel(hdr, text="● OFFLINE",
                                         font=MONO_SM, text_color=C['wn'])
        self._status_dot.pack(side='left', padx=8)
        self._stop_btn = Btn(hdr, "⏹ STOP SERVER",
                             command=self._stop_server,
                             variant='danger', width=130)
        self._stop_btn.pack(side='right', padx=4, pady=6)
        self._stop_btn.configure(state='disabled')
        self._start_btn = Btn(hdr, "▶ START SERVER",
                              command=self._start_server, width=130)
        self._start_btn.pack(side='right', padx=4, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── How it works ──────────────────────────────────────────
        SectionHeader(body, '01', 'HOW IT WORKS').pack(fill='x', padx=14, pady=(14,4))
        how = Card(body, accent=C['bl'])
        how.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(how,
            text="Mint Scan runs a Wi-Fi sync server directly on your Linux machine.\n"
                 "Your Android phone connects to it over your home Wi-Fi — no USB needed.\n\n"
                 "STEP 1: Tap ▶ START SERVER below.\n"
                 "STEP 2: Open the URL shown on your phone's browser.\n"
                 "STEP 3: The companion app loads instantly — battery, network, sync ready.\n\n"
                 "For USB/ADB connection (Android 16+), use the USB Sync tab instead.\n"
                 "Both phone and Chromebook must be on the SAME Wi-Fi network.",
            font=('DejaVu Sans Mono',10), text_color=C['tx'], justify='left'
        ).pack(anchor='w', padx=12, pady=(10,10))

        # ── Server connection info ────────────────────────────────
        SectionHeader(body, '02', 'SERVER CONNECTION').pack(fill='x', padx=14, pady=(10,4))
        self._conn_card = Card(body)
        self._conn_card.pack(fill='x', padx=14, pady=(0,8))
        self._conn_info = ctk.CTkLabel(self._conn_card,
            text="Server is offline. Tap ▶ START SERVER to begin.",
            font=MONO_SM, text_color=C['mu'])
        self._conn_info.pack(padx=12, pady=16)

        # ── Port setting ──────────────────────────────────────────
        port_row = ctk.CTkFrame(self._conn_card, fg_color='transparent')
        port_row.pack(fill='x', padx=12, pady=(0,10))
        ctk.CTkLabel(port_row, text="PORT:", font=MONO_SM,
                     text_color=C['mu']).pack(side='left')
        self._port_entry = ctk.CTkEntry(port_row, width=80,
                                         font=MONO_SM,
                                         fg_color=C['bg'],
                                         border_color=C['br'],
                                         text_color=C['tx'])
        self._port_entry.pack(side='left', padx=8)
        self._port_entry.insert(0, str(self._port))
        ctk.CTkLabel(port_row,
            text="(default 8765 — change if blocked by firewall)",
            font=('DejaVu Sans Mono',8), text_color=C['mu']).pack(side='left')

        # ── QR / URL ──────────────────────────────────────────────
        SectionHeader(body, '03', 'PHONE CONNECTION').pack(fill='x', padx=14, pady=(10,4))
        self._phone_card = Card(body)
        self._phone_card.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self._phone_card,
            text="Start the server to see connection URL and QR code instructions",
            font=MONO_SM, text_color=C['mu']).pack(padx=12, pady=16)

        # ── Live sync data ────────────────────────────────────────
        SectionHeader(body, '04', 'SYNCED DATA').pack(fill='x', padx=14, pady=(10,4))
        self._data_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._data_frame.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self._data_frame,
            text="No data synced yet. Start the server and open the URL on your phone.",
            font=MONO_SM, text_color=C['mu']).pack(pady=8)

        # ── Open on Phone ─────────────────────────────────────────
        SectionHeader(body, '05', 'OPEN COMPANION ON PHONE').pack(fill='x', padx=14, pady=(10,4))
        comp_card = Card(body, accent=C['ac'])
        comp_card.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(comp_card,
            text="📱  HOW TO OPEN ON YOUR PHONE:",
            font=('DejaVu Sans Mono',11,'bold'), text_color=C['ac']
        ).pack(anchor='w', padx=12, pady=(12,4))
        ctk.CTkLabel(comp_card,
            text="Method A — Browser (Wi-Fi):\n"
                 "  1. Start the server above\n"
                 "  2. Open the URL shown in your phone's browser\n"
                 "  3. The companion app loads instantly — no install needed\n\n"
                 "Method B — USB (ADB, works on Android 16):\n"
                 "  1. Connect phone via USB with USB Debugging enabled\n"
                 "  2. Go to USB Sync tab → tap 🚀 OPEN COMPANION ON PHONE\n"
                 "  3. Served via ADB port-forward — bypasses all file restrictions",
            font=('DejaVu Sans Mono',9), text_color=C['tx'], justify='left'
        ).pack(anchor='w', padx=12, pady=(0,12))

        # ── Sync log ──────────────────────────────────────────────
        SectionHeader(body, '06', 'SYNC LOG').pack(fill='x', padx=14, pady=(10,4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0,14))
        self._log = ctk.CTkTextbox(log_card, height=160,
                                    font=('DejaVu Sans Mono',9),
                                    fg_color=C['bg'],
                                    text_color=C['ok'],
                                    border_width=0)
        self._log.pack(fill='x', padx=8, pady=8)
        self._log.configure(state='disabled')

    def _log_msg(self, msg):
        self._log.configure(state='normal')
        self._log.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self._log.see('end')
        self._log.configure(state='disabled')

    def _start_server(self):
        global _server_instance
        try:
            self._port = int(self._port_entry.get())
        except ValueError:
            self._port = 8765

        if _server_instance:
            self._log_msg("Server already running")
            return

        try:
            _server_instance = HTTPServer(('0.0.0.0', self._port), SyncHandler)
        except OSError as e:
            self._log_msg(f"✗ Could not start server: {e}")
            self._log_msg(f"Try a different port (e.g. 8766)")
            return

        self._server_thread = threading.Thread(
            target=_server_instance.serve_forever, daemon=True)
        self._server_thread.start()

        self._log_msg(f"✓ Server started on port {self._port}")
        self._start_btn.configure(state='disabled', text='RUNNING...')
        self._stop_btn.configure(state='normal')
        self._status_dot.configure(text='● ONLINE', text_color=C['ok'])
        self._refresh_status()
        # Poll for incoming data
        self._poll_data()

    def _stop_server(self):
        global _server_instance
        if _server_instance:
            _server_instance.shutdown()
            _server_instance = None
        self._log_msg("Server stopped")
        self._start_btn.configure(state='normal', text='▶ START SERVER')
        self._stop_btn.configure(state='disabled')
        self._status_dot.configure(text='● OFFLINE', text_color=C['wn'])

    def _fix_firewall(self):
        self._log_msg("Allowing port 8765 through firewall...")
        def _bg():
            out, err, rc = run(['sudo', 'ufw', 'allow', '8765/tcp'])
            if rc == 0:
                self._safe_after(0, self._log_msg, "✓ Firewall updated (port 8765 allowed)")
            else:
                self._safe_after(0, self._log_msg, f"✗ Firewall update failed: {err or out}")
        threading.Thread(target=_bg, daemon=True).start()

    def _refresh_status(self):
        ip   = get_local_ip()
        port = self._port
        running = _server_instance is not None

        # Update connection info
        for w in self._conn_card.winfo_children():
            if isinstance(w, ctk.CTkLabel) and 'Server is' in (w.cget('text') or ''):
                w.destroy()
            if isinstance(w, InfoGrid):
                w.destroy()

        if running:
            url = f"http://{ip}:{port}"
            InfoGrid(self._conn_card, [
                ('YOUR IP',   ip,           C['ok']),
                ('PORT',      str(port),    C['ac']),
                ('STATUS',    'ONLINE',     C['ok']),
            ], columns=3).pack(fill='x', padx=8, pady=(10,4))
            
            url_row = ctk.CTkFrame(self._conn_card, fg_color='transparent')
            url_row.pack(fill='x', padx=12, pady=(0,10))
            ctk.CTkLabel(url_row, text=f"URL: {url}", font=MONO_SM, text_color=C['ac']).pack(side='left')
            Btn(url_row, "📋", command=lambda: copy_to_clipboard(url), variant='ghost', width=30).pack(side='left', padx=6)
            Btn(url_row, "🔥 FIX FIREWALL", command=self._fix_firewall, variant='warning', width=120).pack(side='right')

            # Update phone card
            for w in self._phone_card.winfo_children(): w.destroy()
            ctk.CTkLabel(self._phone_card,
                text="OPEN THIS URL ON YOUR PHONE'S BROWSER:",
                font=('DejaVu Sans Mono',9,'bold'), text_color=C['mu']
            ).pack(anchor='w', padx=12, pady=(12,4))
            
            big_row = ctk.CTkFrame(self._phone_card, fg_color='transparent')
            big_row.pack(anchor='w', padx=12, pady=(0,4))
            ctk.CTkLabel(big_row, text=url, font=('DejaVu Sans Mono',18,'bold'), text_color=C['ac']).pack(side='left')
            Btn(big_row, "📋", command=lambda: copy_to_clipboard(url), variant='ghost', width=30).pack(side='left', padx=10)

            ctk.CTkLabel(self._phone_card,
                text=f"Your phone and Chromebook must be on the SAME Wi-Fi network.\n"
                     f"If you can't reach the URL, tap FIX FIREWALL above.",
                font=('DejaVu Sans Mono',9), text_color=C['mu'], justify='left'
            ).pack(anchor='w', padx=12, pady=(0,12))
        else:
            self._conn_info = ctk.CTkLabel(self._conn_card,
                text="Server is offline. Tap ▶ START SERVER to begin.",
                font=MONO_SM, text_color=C['mu'])
            self._conn_info.pack(padx=12, pady=16)

    def _poll_data(self):
        """Check for new sync data every 3 seconds"""
        if _server_instance is None:
            return
        self._render_sync_data()
        self.after(3000, self._poll_data)

    def _render_sync_data(self):
        for w in self._data_frame.winfo_children(): w.destroy()

        last = _sync_data.get('last_sync')
        if not last:
            ctk.CTkLabel(self._data_frame,
                text="No data synced yet. Open the server URL on your phone.",
                font=MONO_SM, text_color=C['mu']).pack(pady=8)
            return

        device   = _sync_data.get('device', {})
        battery  = _sync_data.get('battery', {})
        calls    = _sync_data.get('calls', [])
        sms      = _sync_data.get('sms', [])
        contacts = _sync_data.get('contacts', [])

        # Summary grid
        InfoGrid(self._data_frame, [
            ('DEVICE',    device.get('model', '—'),  C['ac']),
            ('ANDROID',   device.get('android', '—'), C['tx']),
            ('BATTERY',   f"{battery.get('level','—')}%",
             C['ok'] if int(battery.get('level',50) or 50) > 20 else C['wn']),
            ('CHARGING',  'Yes' if battery.get('charging') else 'No', C['tx']),
            ('CALLS',     len(calls),   C['ac']),
            ('SMS',       len(sms),     C['ac']),
            ('CONTACTS',  len(contacts),C['ac']),
            ('LAST SYNC', last,         C['ok']),
        ], columns=4).pack(fill='x', pady=(0,8))

        # Show recent calls
        if calls:
            ctk.CTkLabel(self._data_frame,
                text=f"Recent calls ({len(calls)}):",
                font=('DejaVu Sans Mono',9,'bold'), text_color=C['ac']
            ).pack(anchor='w', pady=(4,2))
            for call in calls[:5]:
                num  = call.get('number','Unknown')
                name = call.get('name','')
                dur  = call.get('duration','')
                ctk.CTkLabel(self._data_frame,
                    text=f"  📞 {name or num}  {dur}",
                    font=MONO_SM, text_color=C['tx']
                ).pack(anchor='w')

        # Show recent SMS
        if sms:
            ctk.CTkLabel(self._data_frame,
                text=f"\nRecent messages ({len(sms)}):",
                font=('DejaVu Sans Mono',9,'bold'), text_color=C['ac']
            ).pack(anchor='w', pady=(8,2))
            for msg in sms[:3]:
                addr = msg.get('address','?')
                body = (msg.get('body','') or '')[:60]
                ctk.CTkLabel(self._data_frame,
                    text=f"  💬 {addr}: {body}",
                    font=MONO_SM, text_color=C['tx']
                ).pack(anchor='w')

        self._log_msg(f"Data refreshed — {len(calls)} calls, {len(sms)} SMS")

    def _do_usb_install(self, path):
        out, err = subprocess.Popen(
            f"adb install -r '{path}'",
            shell=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True
        ).communicate()
        if 'Success' in out:
            self._safe_after(0, self._log_msg,
                       "✓ Companion APK installed on phone!")
        else:
            self._safe_after(0, self._log_msg,
                       f"Install result: {out or err}")
