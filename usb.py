"""
USB Phone Sync + Companion App + APK Installer — unified phone tab.
Companion served over HTTP via ADB port-forward — works on ALL Android versions.
Chrome file:// access denied issue completely bypassed.
"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, os, re, time, shutil, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from installer import install_adb
from utils import run_cmd as _r

BASE = os.path.dirname(os.path.abspath(__file__))
COMPANION_HTML = os.path.join(BASE, 'companion_app.html')

# Port the mini HTTP server runs on locally — ADB forwards this to the phone
COMPANION_PORT = 8765


class _CompanionHandler(BaseHTTPRequestHandler):
    """Tiny HTTP server that serves companion_app.html over localhost.
    Headers set for Android 16 Chrome compatibility."""

    def log_message(self, fmt, *args):
        pass  # Silent

    def do_GET(self):
        try:
            html = open(COMPANION_HTML, 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(html))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            # Android 16 Chrome CORS — allow everything on loopback
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            # Allow battery, location, notifications APIs in Chrome
            self.send_header('Permissions-Policy', 'geolocation=*, battery=*')
            self.end_headers()
            self.wfile.write(html)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def do_POST(self):
        """Accept sync data posted back from the companion app."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = self.rfile.read(length)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception:
            self.send_response(500)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


class UsbScreen(ctk.CTkFrame):
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
        self._built   = False
        self._device  = None
        self._comp_server   = None   # HTTPServer instance
        self._comp_thread   = None   # server thread
        self._comp_port     = COMPANION_PORT

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._detect, daemon=True).start()

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=52, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📱  PHONE MANAGER",
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        self.dev_lbl = ctk.CTkLabel(hdr, text="● Detecting...",
                                     font=MONO_SM, text_color=C['mu'])
        self.dev_lbl.pack(side='left', padx=8)
        Btn(hdr, "↺ RESCAN",
            command=lambda: threading.Thread(
                target=self._detect, daemon=True).start(),
            variant='ghost', width=90).pack(side='right', padx=8, pady=8)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── 01 ADB Setup ──────────────────────────────────────
        SectionHeader(body,'01','USB SETUP').pack(fill='x', padx=14, pady=(14,4))
        setup = Card(body, accent=C['bl'])
        setup.pack(fill='x', padx=14, pady=(0,8))

        self.adb_status = ResultBox(setup,'ok','✓ Checking ADB...','')
        self.adb_status.pack(fill='x', padx=8, pady=(8,4))
        self.install_adb_btn = Btn(setup, "⬇ INSTALL ADB",
            command=lambda: install_adb(self, on_done=lambda: threading.Thread(
                target=self._detect, daemon=True).start()),
            variant='primary', width=160)
        self.install_adb_btn.pack(anchor='w', padx=12, pady=(0,4))
        self.install_adb_btn.pack_forget()   # hidden until needed

        ctk.CTkLabel(setup,
            text="One-time phone setup:\n"
                 "  1.  Settings → About Phone → tap Build Number 7 times\n"
                 "  2.  Settings → Developer Options → USB Debugging → ON\n"
                 "  3.  Connect USB cable to Chromebook\n"
                 "  4.  Phone shows Allow USB Debugging? → tap ALLOW",
            font=('DejaVu Sans Mono',8), text_color=C['mu'], justify='left'
        ).pack(anchor='w', padx=12, pady=(4,10))

        # ── 02 Device status ──────────────────────────────────
        SectionHeader(body,'02','CONNECTED DEVICE').pack(fill='x', padx=14, pady=(10,4))
        self.dev_card = Card(body)
        self.dev_card.pack(fill='x', padx=14, pady=(0,8))
        self.dev_info = ctk.CTkLabel(self.dev_card,
            text="No device detected.\nConnect phone and tap ↺ RESCAN",
            font=MONO_SM, text_color=C['mu'])
        self.dev_info.pack(padx=12, pady=12)

        # ── 03 Companion App ──────────────────────────────────
        SectionHeader(body,'03','MINT SCAN COMPANION APP').pack(
            fill='x', padx=14, pady=(10,4))

        comp = Card(body, accent=C['ac'])
        comp.pack(fill='x', padx=14, pady=(0,8))

        ctk.CTkLabel(comp,
            text="📱  COMPANION — HTTP SERVER (USB)",
            font=('DejaVu Sans Mono',11,'bold'), text_color=C['ac']
        ).pack(anchor='w', padx=12, pady=(12,4))

        ctk.CTkLabel(comp,
            text="Starts a local HTTP server and opens the companion\n"
                 "on your phone via ADB port-forward over the USB cable.\n"
                 "Works on ALL Android versions — no file:// error.",
            font=('DejaVu Sans Mono',8), text_color=C['mu'], justify='left'
        ).pack(anchor='w', padx=12, pady=(0,8))

        # THE button — starts HTTP server + ADB forward + opens on phone
        self.comp_btn = ctk.CTkButton(comp,
            text="🚀  OPEN COMPANION ON PHONE (USB)",
            font=('DejaVu Sans Mono',11,'bold'),
            height=48,
            fg_color=C['ac'],
            hover_color=C['br2'],
            text_color=C['bg'],
            corner_radius=8,
            command=self._install_companion)
        self.comp_btn.pack(fill='x', padx=12, pady=(0,6))

        Btn(comp, "⏹ STOP SERVER",
            command=self._stop_companion_server,
            variant='danger', width=160
        ).pack(anchor='w', padx=12, pady=(0,4))

        Btn(comp, "▶ REOPEN ON PHONE (server running)",
            command=self._open_companion,
            variant='ghost', width=260
        ).pack(anchor='w', padx=12, pady=(0,10))

        self.comp_prog = ctk.CTkProgressBar(comp, height=4,
                                             progress_color=C['ac'],
                                             fg_color=C['br'])
        self.comp_prog.pack(fill='x', padx=12, pady=(0,8))
        self.comp_prog.set(0)

        # ── 04 Install any APK ────────────────────────────────
        SectionHeader(body,'04','INSTALL ANY APK').pack(
            fill='x', padx=14, pady=(10,4))
        apk_card = Card(body)
        apk_card.pack(fill='x', padx=14, pady=(0,8))

        ctk.CTkLabel(apk_card,
            text="Install any APK file from your Linux filesystem to the phone:",
            font=MONO_SM, text_color=C['mu']
        ).pack(anchor='w', padx=12, pady=(10,4))

        path_row = ctk.CTkFrame(apk_card, fg_color='transparent')
        path_row.pack(fill='x', padx=12, pady=(0,6))
        self.apk_entry = ctk.CTkEntry(path_row,
            placeholder_text="/home/mint/Downloads/app.apk",
            font=MONO_SM, fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'], height=36)
        self.apk_entry.pack(side='left', fill='x', expand=True, padx=(0,8))
        Btn(path_row, "BROWSE", command=self._browse_apk,
            variant='ghost', width=80).pack(side='left')

        opts_row = ctk.CTkFrame(apk_card, fg_color='transparent')
        opts_row.pack(fill='x', padx=12, pady=(0,4))
        self.opt_replace   = ctk.BooleanVar(value=True)
        self.opt_grant     = ctk.BooleanVar(value=True)
        for var, lbl in [(self.opt_replace,'Replace existing (-r)'),
                         (self.opt_grant,  'Grant all permissions (-g)')]:
            ctk.CTkCheckBox(opts_row, text=lbl, variable=var,
                            font=('DejaVu Sans Mono',8), text_color=C['tx'],
                            fg_color=C['ac'], checkmark_color=C['bg'],
                            border_color=C['br'], hover_color=C['br2']
                            ).pack(side='left', padx=(0,16))

        Btn(apk_card, "📦 INSTALL APK TO PHONE",
            command=self._install_apk,
            variant='primary', width=220
        ).pack(anchor='w', padx=12, pady=(4,10))

        # ── 05 Data sync ──────────────────────────────────────
        SectionHeader(body,'05','SYNC DATA FROM PHONE').pack(
            fill='x', padx=14, pady=(10,4))
        sync = Card(body)
        sync.pack(fill='x', padx=14, pady=(0,8))
        sg = ctk.CTkFrame(sync, fg_color='transparent')
        sg.pack(fill='x', padx=8, pady=8)
        sync_actions = [
            ("📋 Call Log",   self._pull_calls,    'primary'),
            ("💬 SMS",        self._pull_sms,      'primary'),
            ("📇 Contacts",   self._pull_contacts, 'blue'),
            ("📶 Wi-Fi Nets", self._pull_wifi,     'warning'),
            ("📸 Screenshot", self._screenshot,    'ghost'),
            ("🔋 Battery",    self._phone_battery, 'ghost'),
            ("📱 Device Info",self._phone_info,    'ghost'),
            ("🔁 Full Sync",  self._full_sync,     'success'),
        ]
        for i,(lbl,cmd,var) in enumerate(sync_actions):
            r2,c2 = divmod(i,2)
            Btn(sg, lbl, command=cmd, variant=var, width=210
                ).grid(row=r2, column=c2, padx=4, pady=4, sticky='ew')
        sg.columnconfigure(0,weight=1)
        sg.columnconfigure(1,weight=1)

        # ── 06 ADB Forensics ──────────────────────────────────
        SectionHeader(body,'06','ADB FORENSICS').pack(fill='x', padx=14, pady=(10,4))
        for_card = Card(body, accent=C['wn'])
        for_card.pack(fill='x', padx=14, pady=(0,8))
        
        ctk.CTkLabel(for_card, text="Check integrity of critical Android system binaries.", font=MONO_SM, text_color=C['mu']).pack(pady=(12,4))
        Btn(for_card, "🛡 CHECK SYSTEM INTEGRITY", command=self._adb_integrity, variant='warning', width=220).pack(pady=(0,12))

        # ── 07 Output log ─────────────────────────────────────
        SectionHeader(body,'07','OUTPUT').pack(fill='x', padx=14, pady=(10,4))
        self.output = ctk.CTkTextbox(body, height=160, font=('DejaVu Sans Mono',10),
                                      fg_color=C['s2'], text_color=C['ok'],
                                      border_color=C['br'], border_width=1,
                                      corner_radius=6)
        self.output.pack(fill='x', padx=14, pady=(0,14))
        self.output.configure(state='normal')

        # Update ADB status on build
        threading.Thread(target=self._check_adb_status, daemon=True).start()

    def _adb_integrity(self):
        self._log("Checking Android system integrity...")
        threading.Thread(target=self._do_integrity, daemon=True).start()

    def _do_integrity(self):
        # Check /system/bin/sh permissions/size
        out, _, rc = _r("adb shell ls -l /system/bin/sh")
        if rc == 0:
            self._safe_after(0, self._log, f"Shell binary:\n{out}")
        
        # Check hash of app_process (zygote)
        # Try sha256sum, md5sum, or just ls -l
        out, _, rc = _r("adb shell sha256sum /system/bin/app_process32 2>/dev/null")
        if not out:
             out, _, rc = _r("adb shell md5sum /system/bin/app_process32 2>/dev/null")
        
        if out:
            self._safe_after(0, self._log, f"Zygote Hash:\n{out}")
        else:
            self._safe_after(0, self._log, "Could not compute hash (missing tools on phone).")

    # ── Logging ───────────────────────────────────────────────

    def _log(self, msg):
        def _do():
            self.output.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.output.see('end')
        self._safe_after(0, _do)

    # ── ADB check ─────────────────────────────────────────────

    def _check_adb_status(self):
        adb_ok = shutil.which('adb') is not None
        if adb_ok:
            ver, _, _ = _r("adb version 2>/dev/null | head -1")
            def _do():
                for w in self.adb_status.winfo_children(): w.destroy()
                ResultBox(self.adb_status.__class__.__bases__[0].__new__(
                    ctk.CTkFrame), 'ok',
                    f'✓ ADB Ready — {ver}', '').pack()
                # Recreate properly
                self.adb_status.destroy()
                self.adb_status = ResultBox(
                    self.adb_status.master if hasattr(self.adb_status,'master')
                    else self.scroll._body,
                    'ok', f'✓ ADB Ready  —  {ver[:50]}', '')
                self.install_adb_btn.pack_forget()
            # Simpler approach
            self._safe_after(0, lambda: self.install_adb_btn.pack_forget())
        else:
            self._safe_after(0, lambda: self.install_adb_btn.pack(
                anchor='w', padx=12, pady=(0,4)))
            self._log("ADB not installed — tap INSTALL ADB in the setup section")

    # ── Device detection ──────────────────────────────────────

    def _detect(self):
        if not shutil.which('adb'):
            self._safe_after(0, lambda: (
                self.dev_lbl.configure(text='● ADB needed', text_color=C['wn']),
                self.dev_info.configure(
                    text='Install ADB first — see section 01 above',
                    text_color=C['wn'])
            ))
            return

        out, _, _ = _r("adb devices 2>/dev/null")
        lines  = [l for l in out.split('\n')[1:]
                  if '\t' in l and 'offline' not in l and 'unauthorized' not in l]
        unauth = [l for l in out.split('\n')[1:] if 'unauthorized' in l]

        if not lines:
            msg = ("Phone connected but not authorized.\n"
                   "Check your phone screen → tap ALLOW USB Debugging"
                   if unauth else
                   "No device found.\n"
                   "1. Connect USB cable\n"
                   "2. Enable USB Debugging on phone\n"
                   "3. Tap Allow on phone screen\n"
                   "4. Tap ↺ RESCAN above")
            col = C['am'] if unauth else C['wn']
            self._device = None
            self._safe_after(0, lambda: (
                self.dev_lbl.configure(text='● No device', text_color=col),
                self.dev_info.configure(text=msg, text_color=col)
            ))
            return

        serial = lines[0].split('\t')[0]
        self._device = serial

        # Get device details
        brand,   _, _ = _r(f"adb -s {serial} shell getprop ro.product.brand 2>/dev/null")
        model,   _, _ = _r(f"adb -s {serial} shell getprop ro.product.model 2>/dev/null")
        android, _, _ = _r(f"adb -s {serial} shell getprop ro.build.version.release 2>/dev/null")
        bat,     _, _ = _r(f"adb -s {serial} shell dumpsys battery 2>/dev/null | grep level")
        bat_m = re.search(r'level: (\d+)', bat)
        bat_pct = (bat_m.group(1) + '%') if bat_m else '—'

        info = (f"✓  {brand} {model}\n"
                f"Android {android}  •  Battery {bat_pct}  •  {serial}")
        self._safe_after(0, lambda: (
            self.dev_lbl.configure(
                text=f"● {brand} {model}", text_color=C['ok']),
            self.dev_info.configure(text=info, text_color=C['ok'])
        ))
        self._log(f"Connected: {brand} {model} (Android {android}, {bat_pct})")

    # ── Companion — HTTP server over ADB port-forward ────────

    def _start_companion_server(self):
        """Start local HTTP server on COMPANION_PORT if not already running."""
        if self._comp_server is not None:
            return True  # Already running
        if not os.path.exists(COMPANION_HTML):
            self._log(f"✗ companion_app.html not found at: {COMPANION_HTML}")
            return False
        try:
            self._comp_server = HTTPServer(('127.0.0.1', self._comp_port), _CompanionHandler)
            self._comp_thread = threading.Thread(
                target=self._comp_server.serve_forever, daemon=True)
            self._comp_thread.start()
            self._log(f"✓ Companion HTTP server started on port {self._comp_port}")
            return True
        except OSError as e:
            # Port in use — try next port
            self._comp_port += 1
            if self._comp_port < COMPANION_PORT + 5:
                return self._start_companion_server()
            self._log(f"✗ Could not start HTTP server: {e}")
            return False

    def _stop_companion_server(self):
        """Shut down the HTTP server and remove ADB forward."""
        if self._comp_server:
            try:
                self._comp_server.shutdown()
                self._comp_server = None
                self._comp_thread = None
                self._comp_port   = COMPANION_PORT
                self._log("⏹ Companion server stopped.")
            except Exception as e:
                self._log(f"Stop error: {e}")
        # Remove ADB port forward
        if self._device:
            _r(f"adb -s {self._device} forward --remove tcp:{self._comp_port}", timeout=5)

    def _install_companion(self):
        """Start server + ADB forward + open URL on phone browser."""
        if not self._device:
            self._log("⚠ No phone connected.")
            self._log("  Connect USB cable → Enable USB Debugging → Tap Allow → Tap ↺ RESCAN")
            return
        self._safe_after(0, lambda: self.comp_btn.configure(
            state='disabled', text='⟳  Starting...'))
        self._safe_after(0, lambda: self.comp_prog.set(0.1))
        threading.Thread(target=self._do_install_companion, daemon=True).start()

    def _do_install_companion(self):
        # Step 1: Start local HTTP server on desktop
        if not self._start_companion_server():
            self._safe_after(0, lambda: self.comp_btn.configure(
                state='normal', text='🚀  OPEN COMPANION ON PHONE (USB)'))
            self._safe_after(0, lambda: self.comp_prog.set(0))
            return

        self._safe_after(0, lambda: self.comp_prog.set(0.35))

        # Step 2: adb reverse — tunnels phone's localhost:PORT → desktop:PORT
        # This is an ADB transport feature, works on all Android versions including 16
        fwd_out, fwd_err, fwd_rc = _r(
            f"adb -s {self._device} reverse tcp:{self._comp_port} tcp:{self._comp_port}",
            timeout=10)

        if fwd_rc != 0:
            self._log(f"⚠ adb reverse failed ({fwd_err.strip()}) — trying adb forward...")
            _, fwd_err2, fwd_rc2 = _r(
                f"adb -s {self._device} forward tcp:{self._comp_port} tcp:{self._comp_port}",
                timeout=10)
            if fwd_rc2 != 0:
                self._log(f"✗ Port-forward failed: {fwd_err2.strip()}")
                self._log("  Try: re-plug USB cable and tap ↺ RESCAN")
                self._safe_after(0, lambda: self.comp_btn.configure(
                    state='normal', text='🚀  OPEN COMPANION ON PHONE (USB)'))
                self._safe_after(0, lambda: self.comp_prog.set(0))
                return

        self._log(f"✓ Port-forward active on port {self._comp_port}")
        self._safe_after(0, lambda: self.comp_prog.set(0.65))

        # Step 3: Open http://localhost:PORT on phone browser
        # Android 16 am start syntax — must use -p for package (positional arg removed)
        url = f"http://localhost:{self._comp_port}"

        # Try explicit component first (most reliable on Android 16),
        # then -p package flag, then generic VIEW intent
        intents = [
            # Chrome — explicit component (Android 16 preferred)
            f"adb -s {self._device} shell am start"
            f" -n com.android.chrome/com.google.android.apps.chrome.Main"
            f" -a android.intent.action.VIEW -d '{url}'",

            # Samsung Internet — explicit component
            f"adb -s {self._device} shell am start"
            f" -n com.sec.android.app.sbrowser/.SBrowserMainActivity"
            f" -a android.intent.action.VIEW -d '{url}'",

            # Chrome with -p package flag (Android 13+ syntax)
            f"adb -s {self._device} shell am start"
            f" -a android.intent.action.VIEW -d '{url}'"
            f" -p com.android.chrome",

            # Firefox
            f"adb -s {self._device} shell am start"
            f" -a android.intent.action.VIEW -d '{url}'"
            f" -p org.mozilla.firefox",

            # Brave
            f"adb -s {self._device} shell am start"
            f" -a android.intent.action.VIEW -d '{url}'"
            f" -p com.brave.browser",

            # Android 16 generic — system picks default browser
            f"adb -s {self._device} shell am start"
            f" -a android.intent.action.VIEW -d '{url}'"
            f" --activity-single-top",
        ]

        opened = False
        for cmd in intents:
            out, err, rc = _r(cmd.replace('\n', ' '), timeout=8)
            combined = (out + err).lower()
            if rc == 0 and 'error' not in combined and 'exception' not in combined:
                opened = True
                self._log(f"✓ Browser intent sent successfully")
                break
            else:
                # Log which one failed for debugging
                pkg = re.search(r'(?:-n |\.)(com\.\S+)', cmd)
                if pkg:
                    self._log(f"  ↳ {pkg.group(1)}: not found, trying next...")

        self._safe_after(0, lambda: self.comp_prog.set(1.0))
        self._safe_after(0, lambda: self.comp_btn.configure(
            state='normal', text='🚀  OPEN COMPANION ON PHONE (USB)'))

        if opened:
            self._log(f"✓ Companion opened on phone!")
            self._log(f"  Server stays running. Tap ⏹ STOP SERVER when done.")
        else:
            # All intents failed — give manual URL prominently
            self._log(f"")
            self._log(f"✓ SERVER IS RUNNING — open this on your phone:")
            self._log(f"  ► http://localhost:{self._comp_port}")
            self._log(f"  Type this in your phone's browser address bar.")
            self._log(f"  (Works because ADB tunnel is active over USB)")

    def _open_companion(self):
        """Re-open companion — server must already be running."""
        if not self._device:
            self._log("No device. Tap ↺ RESCAN first.")
            return
        if self._comp_server is None:
            self._log("Server not running — tap 🚀 OPEN COMPANION first.")
            return
        url = f"http://localhost:{self._comp_port}"
        def _do():
            # Android 16: try component first, then generic
            cmds = [
                f"adb -s {self._device} shell am start"
                f" -n com.android.chrome/com.google.android.apps.chrome.Main"
                f" -a android.intent.action.VIEW -d '{url}'",
                f"adb -s {self._device} shell am start"
                f" -a android.intent.action.VIEW -d '{url}' --activity-single-top",
            ]
            for cmd in cmds:
                out, err, rc = _r(cmd.replace('\n', ' '), timeout=8)
                if rc == 0 and 'error' not in (out+err).lower():
                    self._log(f"✓ Reopened: {url}")
                    return
            self._log(f"Manual: open  http://localhost:{self._comp_port}  in phone browser")
        threading.Thread(target=_do, daemon=True).start()

    # ── APK install ───────────────────────────────────────────

    def _browse_apk(self):
        try:
            import tkinter.filedialog as fd
            path = fd.askopenfilename(
                title="Select APK file",
                filetypes=[("Android Package","*.apk"),("All","*.*")],
                initialdir=os.path.expanduser("~/Downloads"))
            if path:
                self.apk_entry.delete(0,'end')
                self.apk_entry.insert(0, path)
                sz = os.path.getsize(path)/1024/1024
                self._log(f"Selected: {os.path.basename(path)} ({sz:.1f} MB)")
        except Exception as e:
            self._log(f"Browse error: {e}")

    def _install_apk(self):
        if not self._device:
            self._log("No device connected. Tap ↺ RESCAN first.")
            return
        path = self.apk_entry.get().strip()
        if not path:
            self._log("Enter APK path or tap BROWSE to select a file.")
            return
        if not os.path.exists(path):
            self._log(f"File not found: {path}")
            return
        def _do():
            flags = []
            if self.opt_replace.get(): flags.append('-r')
            if self.opt_grant.get():   flags.append('-g')
            self._log(f"Installing {os.path.basename(path)}...")
            out, err, rc = _r(
                f"adb -s {self._device} install {' '.join(flags)} '{path}'",
                timeout=120)
            if 'Success' in out or rc == 0:
                self._log("✓ APK installed successfully")
            else:
                self._log(f"✗ Install failed: {out or err}")
                if 'UNKNOWN_SOURCES' in (out+err):
                    self._log("→ Fix: Settings → Security → Install Unknown Apps → Allow")
                elif 'DOWNGRADE' in (out+err):
                    self._log("→ The installed version is newer. Uninstall first.")
        threading.Thread(target=_do, daemon=True).start()

    # ── Data sync ─────────────────────────────────────────────

    def _need_device(self):
        if not self._device:
            self._log("No device. Connect phone and tap ↺ RESCAN.")
            return False
        return True

    def _pull_calls(self):
        if not self._need_device(): return
        def _do():
            self._log("Pulling call log...")
            out, err, rc = _r(
                f"adb -s {self._device} shell content query "
                "--uri content://call_log/calls "
                "--projection number:date:duration:type:name 2>/dev/null | head -60",
                timeout=15)
            if rc == 0 and out:
                save = os.path.expanduser('~/mint-scan-calls.txt')
                open(save,'w').write(out)
                self._log(f"✓ {len(out.splitlines())} call records → {save}")
            else:
                self._log(f"Could not read call log: {err[:80]}")
        threading.Thread(target=_do, daemon=True).start()

    def _pull_sms(self):
        if not self._need_device(): return
        def _do():
            self._log("Pulling SMS...")
            out, err, rc = _r(
                f"adb -s {self._device} shell content query "
                "--uri content://sms/inbox "
                "--projection address:date:body 2>/dev/null | head -40",
                timeout=15)
            if rc == 0 and out:
                save = os.path.expanduser('~/mint-scan-sms.txt')
                open(save,'w').write(out)
                self._log(f"✓ Pulled SMS → {save}")
            else:
                self._log(f"Could not read SMS: {err[:80]}")
        threading.Thread(target=_do, daemon=True).start()

    def _pull_contacts(self):
        if not self._need_device(): return
        def _do():
            self._log("Pulling contacts...")
            out, err, rc = _r(
                f"adb -s {self._device} shell content query "
                "--uri content://contacts/phones/ "
                "--projection display_name:number 2>/dev/null | head -60",
                timeout=15)
            if rc == 0 and out:
                save = os.path.expanduser('~/mint-scan-contacts.txt')
                open(save,'w').write(out)
                self._log(f"✓ Pulled contacts → {save}")
            else:
                self._log(f"Could not read contacts: {err[:80]}")
        threading.Thread(target=_do, daemon=True).start()

    def _pull_wifi(self):
        if not self._need_device(): return
        def _do():
            self._log("Reading Wi-Fi networks...")
            out, _, _ = _r(
                f"adb -s {self._device} shell cmd wifi list-networks 2>/dev/null")
            if out:
                self._log(f"Wi-Fi networks:\n{out}")
            else:
                self._log("Could not list Wi-Fi (some phones restrict this)")
        threading.Thread(target=_do, daemon=True).start()

    def _screenshot(self):
        if not self._need_device(): return
        def _do():
            self._log("Taking screenshot...")
            _r(f"adb -s {self._device} shell screencap -p /sdcard/mint_screen.png")
            save = os.path.expanduser('~/mint-scan-screenshot.png')
            out, err, rc = _r(
                f"adb -s {self._device} pull /sdcard/mint_screen.png '{save}'")
            self._log(f"✓ Screenshot → {save}" if rc==0 else f"✗ {err[:60]}")
        threading.Thread(target=_do, daemon=True).start()

    def _phone_battery(self):
        if not self._need_device(): return
        def _do():
            out, _, _ = _r(
                f"adb -s {self._device} shell dumpsys battery 2>/dev/null")
            self._log(f"Battery info:\n{out[:400]}")
        threading.Thread(target=_do, daemon=True).start()

    def _phone_info(self):
        if not self._need_device(): return
        def _do():
            self._log("Device info:")
            for prop, lbl in [
                ('ro.product.brand','Brand'),
                ('ro.product.model','Model'),
                ('ro.build.version.release','Android'),
                ('ro.build.version.sdk','API Level'),
                ('ro.product.cpu.abi','CPU'),
                ('gsm.sim.operator.alpha','Carrier'),
            ]:
                val, _, _ = _r(
                    f"adb -s {self._device} shell getprop {prop} 2>/dev/null")
                self._log(f"  {lbl}: {val or '—'}")
        threading.Thread(target=_do, daemon=True).start()

    def _full_sync(self):
        if not self._need_device(): return
        self._log("Starting full sync...")
        self._install_companion()
        for fn in [self._pull_calls, self._pull_sms,
                   self._pull_contacts, self._screenshot]:
            time.sleep(0.8)
            fn()
        self._log("✓ Full sync complete")


# Keep ApkScreen as an alias so app.py doesn't break if it references it
ApkScreen = UsbScreen
