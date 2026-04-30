"""
APK Installer — install any APK to Android phone via USB.
Also installs Mint Scan Companion APK if provided.
"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, os, re, time, shutil
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from installer import install_adb, InstallerPopup
from utils import run_cmd as _r


class ApkScreen(ctk.CTkFrame):
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
        self._device = None

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._detect, daemon=True).start()

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=52, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📦  APK INSTALLER",
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        self.dev_lbl = ctk.CTkLabel(hdr, text="● Scanning...",
                                     font=MONO_SM, text_color=C['mu'])
        self.dev_lbl.pack(side='left', padx=8)
        Btn(hdr, "↺ RESCAN",
            command=lambda: threading.Thread(target=self._detect, daemon=True).start(),
            variant='ghost', width=90).pack(side='right', padx=8, pady=8)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── ADB status ───────────────────────────────────────
        SectionHeader(body,'01','SETUP').pack(fill='x', padx=14, pady=(14,4))
        setup = Card(body, accent=C['bl'])
        setup.pack(fill='x', padx=14, pady=(0,8))

        # Check ADB installed
        adb_ok = shutil.which('adb') is not None
        if adb_ok:
            ResultBox(setup,'ok','✓ ADB Installed',
                      'Android Debug Bridge is ready.').pack(fill='x', padx=8, pady=(8,4))
        else:
            ResultBox(setup,'warn','⚠ ADB Not Installed',
                      'Required to communicate with your Android phone via USB.'
                      ).pack(fill='x', padx=8, pady=(8,4))
            Btn(setup, "⬇ INSTALL ADB",
                command=lambda: install_adb(self, on_done=lambda: threading.Thread(
                    target=self._detect, daemon=True).start()),
                variant='primary', width=180).pack(anchor='w', padx=12, pady=(0,10))

        ctk.CTkLabel(setup,
            text="Phone setup:\n"
                 "  1. Settings → About Phone → tap Build Number 7 times\n"
                 "  2. Settings → Developer Options → USB Debugging → ON\n"
                 "  3. Connect USB cable → tap Allow on phone",
            font=('DejaVu Sans Mono',8), text_color=C['mu'], justify='left'
        ).pack(anchor='w', padx=12, pady=(4,10))

        # ── Device status ────────────────────────────────────
        SectionHeader(body,'02','CONNECTED DEVICE').pack(fill='x', padx=14, pady=(10,4))
        self.dev_card = Card(body)
        self.dev_card.pack(fill='x', padx=14, pady=(0,8))
        self.dev_info = ctk.CTkLabel(self.dev_card,
            text="No device detected. Connect phone and tap ↺ RESCAN",
            font=MONO_SM, text_color=C['mu'])
        self.dev_info.pack(padx=12, pady=12)

        # ── APK file selection ───────────────────────────────
        SectionHeader(body,'03','SELECT APK FILE').pack(fill='x', padx=14, pady=(10,4))
        apk_card = Card(body)
        apk_card.pack(fill='x', padx=14, pady=(0,8))

        ctk.CTkLabel(apk_card,
                     text="Enter full path to APK, or use Browse:",
                     font=MONO_SM, text_color=C['mu']
                     ).pack(anchor='w', padx=12, pady=(10,4))
        inp = ctk.CTkFrame(apk_card, fg_color='transparent')
        inp.pack(fill='x', padx=12, pady=(0,8))
        self.apk_entry = ctk.CTkEntry(inp,
            placeholder_text="/home/mint/Downloads/app.apk",
            font=MONO_SM, fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'], height=36)
        self.apk_entry.pack(side='left', fill='x', expand=True, padx=(0,8))
        Btn(inp,'BROWSE', command=self._browse, variant='ghost', width=80).pack(side='left')
        self.apk_info_lbl = ctk.CTkLabel(apk_card, text="",
                                          font=('DejaVu Sans Mono',8), text_color=C['mu'])
        self.apk_info_lbl.pack(anchor='w', padx=12, pady=(0,6))

        # ── Install options ──────────────────────────────────
        SectionHeader(body,'04','OPTIONS').pack(fill='x', padx=14, pady=(10,4))
        opts = Card(body)
        opts.pack(fill='x', padx=14, pady=(0,8))
        og = ctk.CTkFrame(opts, fg_color='transparent')
        og.pack(fill='x', padx=12, pady=10)
        self.opt_replace   = ctk.BooleanVar(value=True)
        self.opt_grant     = ctk.BooleanVar(value=True)
        self.opt_downgrade = ctk.BooleanVar(value=False)
        for var, label in [
            (self.opt_replace,   "Replace existing app (-r)"),
            (self.opt_grant,     "Grant all permissions (-g)"),
            (self.opt_downgrade, "Allow downgrade (-d)"),
        ]:
            ctk.CTkCheckBox(og, text=label, variable=var,
                            font=MONO_SM, text_color=C['tx'],
                            checkmark_color=C['bg'], fg_color=C['ac'],
                            border_color=C['br'], hover_color=C['br2']
                            ).pack(anchor='w', pady=3)

        # ── Install button ───────────────────────────────────
        SectionHeader(body,'05','INSTALL').pack(fill='x', padx=14, pady=(10,4))
        inst_card = Card(body)
        inst_card.pack(fill='x', padx=14, pady=(0,8))
        btn_row = ctk.CTkFrame(inst_card, fg_color='transparent')
        btn_row.pack(fill='x', padx=12, pady=10)
        self.install_btn = Btn(btn_row, "📦 INSTALL APK TO PHONE",
                                command=self._install, width=240)
        self.install_btn.pack(side='left', padx=(0,8))
        Btn(btn_row, "📋 LIST APPS",
            command=self._list_apps, variant='ghost', width=120).pack(side='left')

        self.prog = ctk.CTkProgressBar(inst_card, height=5,
                                        progress_color=C['ac'], fg_color=C['br'])
        self.prog.pack(fill='x', padx=12, pady=(0,6))
        self.prog.set(0)

        self.output = ctk.CTkTextbox(inst_card, height=150, font=('DejaVu Sans Mono',8),
                                      fg_color=C['bg'], text_color=C['ok'],
                                      border_width=0)
        self.output.pack(fill='x', padx=8, pady=(0,8))
        self.output.configure(state='disabled')
        ctk.CTkLabel(body, text="", height=16).pack()

    # ── Helpers ───────────────────────────────────────────────

    def _log(self, msg):
        def _do():
            self.output.configure(state='normal')
            self.output.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.output.see('end')
            self.output.configure(state='disabled')
        self._safe_after(0, _do)

    def _detect(self):
        if not shutil.which('adb'):
            self._safe_after(0, lambda: (
                self.dev_lbl.configure(text='● ADB not installed', text_color=C['wn']),
                self.dev_info.configure(text='Install ADB first — see setup section above.')
            ))
            return
        out, _, rc = _r("adb devices 2>/dev/null")
        lines = [l for l in out.split('\n')[1:] if '\t' in l and 'offline' not in l]
        if not lines:
            self._device = None
            self._safe_after(0, lambda: (
                self.dev_lbl.configure(text='● No device', text_color=C['wn']),
                self.dev_info.configure(
                    text='No Android device found.\n'
                         '1. Connect USB cable\n'
                         '2. Enable USB Debugging\n'
                         '3. Tap Allow on phone\n'
                         '4. Tap ↺ RESCAN', text_color=C['wn'])
            ))
            return
        serial = lines[0].split('\t')[0]
        self._device = serial
        model,  _, _ = _r(f"adb -s {serial} shell getprop ro.product.model")
        brand,  _, _ = _r(f"adb -s {serial} shell getprop ro.product.brand")
        android,_, _ = _r(f"adb -s {serial} shell getprop ro.build.version.release")
        bat,    _, _ = _r(f"adb -s {serial} shell dumpsys battery 2>/dev/null | grep level")
        bat_pct = re.search(r'level: (\d+)', bat)
        info = (f"✓ {brand} {model}  •  Android {android}  "
                f"•  Battery {bat_pct.group(1)+'%' if bat_pct else '—'}")
        self._safe_after(0, lambda: (
            self.dev_lbl.configure(text=f"● {brand} {model}", text_color=C['ok']),
            self.dev_info.configure(text=info, text_color=C['ok'])
        ))

    def _browse(self):
        try:
            import tkinter.filedialog as fd
            path = fd.askopenfilename(
                title="Select APK",
                filetypes=[("Android Package","*.apk"),("All","*.*")],
                initialdir=os.path.expanduser("~/Downloads"))
            if path:
                self.apk_entry.delete(0,'end')
                self.apk_entry.insert(0, path)
                size = os.path.getsize(path)/1024/1024
                self.apk_info_lbl.configure(
                    text=f"File: {os.path.basename(path)}  ({size:.1f} MB)")
        except Exception as e:
            self._log(f"Browse: {e}")

    def _install(self):
        if not self._device:
            self._log("No device. Connect phone and tap RESCAN."); return
        path = self.apk_entry.get().strip()
        if not path:
            self._log("No APK selected."); return
        if not os.path.exists(path):
            self._log(f"File not found: {path}"); return
        self.install_btn.configure(state='disabled', text='INSTALLING...')
        self.prog.set(0.1)
        threading.Thread(target=self._do_install, args=(path,), daemon=True).start()

    def _do_install(self, path):
        flags = []
        if self.opt_replace.get():   flags.append('-r')
        if self.opt_grant.get():     flags.append('-g')
        if self.opt_downgrade.get(): flags.append('-d')

        # Properly shell-quote the path to handle spaces and special chars
        import shlex
        quoted_path = shlex.quote(path)
        flag_str    = ' '.join(flags)
        cmd = f"adb -s {self._device} install {flag_str} {quoted_path}"

        self._safe_after(0, lambda: self.prog.set(0.3))
        self._log(f"Running: adb install {flag_str} <apk>")
        self._log(f"Device: {self._device}")

        out, err, rc = _r(cmd, timeout=180)   # large APKs can take time
        combined = (out + ' ' + err).strip()

        self._safe_after(0, lambda: self.prog.set(1.0))

        if 'Success' in combined or rc == 0:
            self._log('✓ INSTALLATION SUCCESSFUL')
            self._log(f'  App installed on device: {self._device}')
        else:
            self._log(f'✗ INSTALLATION FAILED')
            if combined:
                self._log(f'  Output: {combined[:300]}')

            # Helpful hints for common errors
            hints = {
                'UNKNOWN_SOURCES': 'Fix: Settings → Security → Install Unknown Apps → Allow',
                'VERSION_DOWNGRADE': "Fix: Enable 'Allow downgrade' option above",
                'ALREADY_EXISTS':    'Fix: Enable Replace existing app (-r) option',
                'INSTALL_FAILED_INSUFFICIENT_STORAGE': 'Fix: Free storage on the device',
                'INSTALL_FAILED_OLDER_SDK': 'App requires newer Android version',
                'INSTALL_FAILED_TEST_ONLY': 'Fix: add -t flag  (test APK)',
                'no devices': 'Fix: device disconnected — tap ↺ RESCAN',
                'unauthorized': 'Fix: tap Allow on phone when USB dialog appears',
                'closed': 'Fix: reconnect USB cable and tap ↺ RESCAN',
            }
            for key, hint in hints.items():
                if key.lower() in combined.lower():
                    self._log(f'  → {hint}')
                    break

        self._safe_after(0, lambda: self.install_btn.configure(
            state='normal', text='📦 INSTALL APK TO PHONE'))

    def _list_apps(self):
        if not self._device:
            self._log("No device connected."); return
        def _do():
            out, _, _ = _r(f"adb -s {self._device} shell pm list packages -3 2>/dev/null")
            pkgs = [l.replace('package:','') for l in out.split('\n') if l.strip()]
            self._log(f"Installed apps ({len(pkgs)}):")
            for p in pkgs[:25]: self._log(f"  {p}")
        threading.Thread(target=_do, daemon=True).start()
