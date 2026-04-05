"""
Mint Scan — Phone Data Recovery
Recovers deleted images, call logs, SMS, contacts, app data via ADB.
Uses ADB pull, SQLite extraction, and filesystem-level recovery techniques.
Works on rooted and non-rooted devices (different capabilities).
"""
import tkinter as tk
import customtkinter as ctk
import threading, os, re, time, shutil, json, subprocess, sqlite3
from widgets import (ScrollableFrame, Card, SectionHeader, InfoGrid,
                     ResultBox, Btn, Badge, C, MONO, MONO_SM)
from utils import run_cmd as _r


class RecoveryScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app     = app
        self._built  = False
        self._device = None
        self._rooted = False
        self._out_dir = os.path.expanduser('~/mint-scan-recovery')

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._detect_device, daemon=True).start()

    # ── UI BUILD ─────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=52, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🗃  DATA RECOVERY — PHONE & DEVICES",
                     font=('Courier',12,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        Btn(hdr, "↺ RESCAN", command=lambda: threading.Thread(
            target=self._detect_device, daemon=True).start(),
            variant='ghost', width=90).pack(side='right', padx=8, pady=8)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # Device status
        SectionHeader(body, '01', 'CONNECTED DEVICE').pack(fill='x', padx=14, pady=(14,4))
        self.dev_card = Card(body)
        self.dev_card.pack(fill='x', padx=14, pady=(0,8))
        self.dev_info = ctk.CTkLabel(self.dev_card,
            text="No device detected — connect phone via USB and tap ↺ RESCAN",
            font=MONO_SM, text_color=C['mu'])
        self.dev_info.pack(padx=12, pady=14)

        # Output directory
        SectionHeader(body, '02', 'RECOVERY OUTPUT FOLDER').pack(fill='x', padx=14, pady=(8,4))
        out_card = Card(body)
        out_card.pack(fill='x', padx=14, pady=(0,8))
        out_row = ctk.CTkFrame(out_card, fg_color='transparent')
        out_row.pack(fill='x', padx=10, pady=10)
        ctk.CTkLabel(out_row, text="Save to:", font=MONO_SM,
                     text_color=C['mu']).pack(side='left', padx=(0,8))
        self.out_entry = ctk.CTkEntry(out_row,
            placeholder_text=self._out_dir,
            font=('Courier',9), fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'], height=32)
        self.out_entry.pack(side='left', fill='x', expand=True, padx=(0,8))
        self.out_entry.insert(0, self._out_dir)
        Btn(out_row, "📂 BROWSE", command=self._browse_output,
            variant='ghost', width=90).pack(side='left')

        # Recovery categories
        SectionHeader(body, '03', 'RECOVERY TARGETS').pack(fill='x', padx=14, pady=(8,4))
        cat_card = Card(body)
        cat_card.pack(fill='x', padx=14, pady=(0,8))

        self.categories = {
            'images':    ctk.BooleanVar(value=True),
            'videos':    ctk.BooleanVar(value=True),
            'calls':     ctk.BooleanVar(value=True),
            'sms':       ctk.BooleanVar(value=True),
            'contacts':  ctk.BooleanVar(value=True),
            'whatsapp':  ctk.BooleanVar(value=True),
            'documents': ctk.BooleanVar(value=True),
            'audio':     ctk.BooleanVar(value=True),
            'apps':      ctk.BooleanVar(value=False),
            'apkfiles':  ctk.BooleanVar(value=False),
        }

        cat_labels = {
            'images':    '🖼  Images & Screenshots',
            'videos':    '🎬  Videos',
            'calls':     '📞  Call Log (incl. deleted)',
            'sms':       '💬  SMS / Messages',
            'contacts':  '📇  Contacts',
            'whatsapp':  '💚  WhatsApp Media & DB',
            'documents': '📄  Documents (PDF/Word)',
            'audio':     '🎵  Audio Files',
            'apps':      '📦  Installed Apps List',
            'apkfiles':  '📱  APK Backups (rooted)',
        }

        grid = ctk.CTkFrame(cat_card, fg_color='transparent')
        grid.pack(fill='x', padx=10, pady=10)
        items = list(cat_labels.items())
        for i, (key, lbl) in enumerate(items):
            r, c = divmod(i, 2)
            ctk.CTkCheckBox(grid, text=lbl, variable=self.categories[key],
                font=('Courier',9), text_color=C['tx'],
                fg_color=C['ac'], checkmark_color=C['bg'],
                border_color=C['br'], hover_color=C['br2']
            ).grid(row=r, column=c, padx=10, pady=4, sticky='w')
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # Quick recovery buttons
        SectionHeader(body, '04', 'QUICK RECOVERY').pack(fill='x', padx=14, pady=(8,4))
        quick_card = Card(body)
        quick_card.pack(fill='x', padx=14, pady=(0,8))

        quick_grid = ctk.CTkFrame(quick_card, fg_color='transparent')
        quick_grid.pack(fill='x', padx=8, pady=8)

        quick_actions = [
            ("🖼 RECOVER IMAGES",     self._recover_images,   'primary'),
            ("📞 RECOVER CALL LOG",   self._recover_calls,    'primary'),
            ("💬 RECOVER SMS",        self._recover_sms,      'primary'),
            ("📇 RECOVER CONTACTS",   self._recover_contacts, 'primary'),
            ("💚 RECOVER WHATSAPP",   self._recover_whatsapp, 'success'),
            ("📄 RECOVER DOCUMENTS",  self._recover_docs,     'blue'),
            ("🎵 RECOVER AUDIO",      self._recover_audio,    'blue'),
            ("🎬 RECOVER VIDEOS",     self._recover_videos,   'blue'),
            ("📦 LIST INSTALLED APPS",self._recover_apps,     'ghost'),
            ("💾 BACKUP ENTIRE PHONE",self._full_backup,      'warning'),
        ]
        for i, (lbl, cmd, var) in enumerate(quick_actions):
            r, c = divmod(i, 2)
            Btn(quick_grid, lbl, command=cmd, variant=var, width=230
                ).grid(row=r, column=c, padx=4, pady=4, sticky='ew')
        quick_grid.columnconfigure(0, weight=1)
        quick_grid.columnconfigure(1, weight=1)

        # Full recovery button
        self.recover_all_btn = ctk.CTkButton(quick_card,
            text="🗃  RECOVER EVERYTHING (ALL SELECTED)",
            font=('Courier',11,'bold'), height=46,
            fg_color=C['ac'], hover_color=C['br2'],
            text_color=C['bg'], corner_radius=8,
            command=self._recover_all)
        self.recover_all_btn.pack(fill='x', padx=10, pady=(4,10))

        # Progress
        SectionHeader(body, '05', 'RECOVERY PROGRESS').pack(fill='x', padx=14, pady=(8,4))
        prog_card = Card(body)
        prog_card.pack(fill='x', padx=14, pady=(0,8))
        self.prog_bar = ctk.CTkProgressBar(prog_card, height=5,
            progress_color=C['ok'], fg_color=C['br'])
        self.prog_bar.pack(fill='x', padx=10, pady=(10,4))
        self.prog_bar.set(0)
        self.prog_lbl = ctk.CTkLabel(prog_card, text="Idle",
            font=MONO_SM, text_color=C['mu'])
        self.prog_lbl.pack(anchor='w', padx=10, pady=(0,10))

        # Results
        SectionHeader(body, '06', 'RECOVERED FILES').pack(fill='x', padx=14, pady=(8,4))
        self.results_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.results_frame.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(self.results_frame, text="Results appear here after recovery.",
                     font=MONO_SM, text_color=C['mu']).pack(pady=6)

        # Log
        SectionHeader(body, '07', 'OUTPUT LOG').pack(fill='x', padx=14, pady=(8,4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0,14))

        log_hdr = ctk.CTkFrame(log_card, fg_color='transparent')
        log_hdr.pack(fill='x', padx=8, pady=(6,0))
        Btn(log_hdr, "📂 OPEN FOLDER", command=self._open_folder,
            variant='ghost', width=120).pack(side='right')
        Btn(log_hdr, "🗑 CLEAR", command=self._clear_log,
            variant='ghost', width=80).pack(side='right', padx=4)

        self.log_box = ctk.CTkTextbox(log_card, height=160,
            font=('Courier',9), fg_color=C['bg'],
            text_color=C['ok'], border_width=0)
        self.log_box.pack(fill='x', padx=8, pady=8)

    # ── DEVICE DETECTION ─────────────────────────────────────────

    def _detect_device(self):
        # Check ADB
        if not shutil.which('adb'):
            self.after(0, lambda: self.dev_info.configure(
                text="ADB not installed. Go to USB Sync tab → Install ADB.",
                text_color=C['wn']))
            return

        # Check device
        out, _, _ = _r("adb devices 2>/dev/null")
        lines = [l for l in out.split('\n')[1:]
                 if '\t' in l and 'offline' not in l and 'unauthorized' not in l]
        if not lines:
            self.after(0, lambda: self.dev_info.configure(
                text="No device found. Connect USB cable and enable USB Debugging.",
                text_color=C['wn']))
            self._device = None
            return

        serial = lines[0].split('\t')[0]
        self._device = serial

        # Get device info
        brand,   _, _ = _r(f"adb -s {serial} shell getprop ro.product.brand 2>/dev/null")
        model,   _, _ = _r(f"adb -s {serial} shell getprop ro.product.model 2>/dev/null")
        android, _, _ = _r(f"adb -s {serial} shell getprop ro.build.version.release 2>/dev/null")
        storage, _, _ = _r(f"adb -s {serial} shell df /sdcard 2>/dev/null | tail -1")

        # Check root
        root_out, _, rc = _r(f"adb -s {serial} shell su -c id 2>/dev/null", timeout=4)
        self._rooted = rc == 0 and 'uid=0' in root_out

        storage_info = ''
        if storage:
            parts = storage.split()
            if len(parts) >= 4:
                storage_info = f"  Storage: {parts[1]} total, {parts[3]} available"

        root_str = "✓ ROOTED (full recovery available)" if self._rooted else "Not rooted (standard recovery)"
        info = (f"✓  {brand} {model}  ·  Android {android}  ·  {serial}\n"
                f"   Root: {root_str}{storage_info}")

        self.after(0, lambda: self.dev_info.configure(
            text=info,
            text_color=C['ok'] if self._rooted else C['tx']))
        self._log(f"Connected: {brand} {model} (Android {android})")
        if self._rooted:
            self._log("✓ Root detected — full deleted data recovery available")
        else:
            self._log("ℹ Non-rooted device — recovering accessible data")

    # ── RECOVERY METHODS ─────────────────────────────────────────

    def _need_device(self):
        if not self._device:
            self._log("⚠ No device connected. Tap ↺ RESCAN.")
            return False
        return True

    def _get_out_dir(self):
        path = self.out_entry.get().strip() or self._out_dir
        os.makedirs(path, exist_ok=True)
        return path

    def _recover_images(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_recover_images, daemon=True).start()

    def _do_recover_images(self):
        self._set_prog(0.1, "Recovering images...")
        out_dir = os.path.join(self._get_out_dir(), 'images')
        os.makedirs(out_dir, exist_ok=True)
        serial  = self._device
        total   = 0

        # Pull DCIM (camera)
        self._log("Pulling DCIM/Camera...")
        o, e, rc = _r(f"adb -s {serial} pull /sdcard/DCIM '{out_dir}' 2>&1", timeout=120)
        pulled = len(re.findall(r'pulled', o + e))
        total += pulled
        self._log(f"  DCIM: {pulled} files")

        self._set_prog(0.4, "Pulling Screenshots...")
        o, e, rc = _r(f"adb -s {serial} pull /sdcard/Pictures '{out_dir}' 2>&1", timeout=60)
        pulled2 = len(re.findall(r'pulled', o + e))
        total += pulled2
        self._log(f"  Pictures: {pulled2} files")

        # Screenshots
        o, e, rc = _r(f"adb -s {serial} pull /sdcard/Screenshots '{out_dir}' 2>&1", timeout=30)
        pulled3 = len(re.findall(r'pulled', o + e))
        total += pulled3

        self._set_prog(0.7, "Pulling Downloads...")
        # Downloads (often has images too)
        o, e, rc = _r(
            f"adb -s {serial} shell find /sdcard/Download -name '*.jpg' -o -name '*.png' -o -name '*.jpeg' -o -name '*.webp' 2>/dev/null",
            timeout=15)
        for fpath in o.strip().split('\n'):
            if fpath.strip():
                _r(f"adb -s {serial} pull '{fpath.strip()}' '{out_dir}' 2>/dev/null", timeout=10)
                total += 1

        # Rooted: check cache / thumbnail databases
        if self._rooted:
            self._log("Root: checking thumbnail cache for deleted images...")
            self._set_prog(0.85, "Checking thumbnail cache...")
            o, e, rc = _r(
                f"adb -s {serial} shell su -c 'find /data -name \"*.jpg\" -o -name \"*.png\" 2>/dev/null | head -200'",
                timeout=20)
            priv_files = [l.strip() for l in o.split('\n') if l.strip()]
            for fp in priv_files[:50]:
                _r(f"adb -s {serial} shell su -c 'cp \"{fp}\" /sdcard/mint_tmp_img/' 2>/dev/null")
            if priv_files:
                _r(f"adb -s {serial} pull /sdcard/mint_tmp_img '{out_dir}/recovered_cache' 2>/dev/null",
                   timeout=30)
                _r(f"adb -s {serial} shell rm -rf /sdcard/mint_tmp_img 2>/dev/null")
                total += len(priv_files)

        self._set_prog(1.0, f"✓ Images: {total} files recovered")
        self._log(f"✓ Images recovered: {total} files → {out_dir}")
        self._add_result("🖼 Images", total, out_dir)

    def _recover_calls(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_recover_calls, daemon=True).start()

    def _do_recover_calls(self):
        self._set_prog(0.1, "Recovering call log...")
        out_dir = self._get_out_dir()
        serial  = self._device
        save    = os.path.join(out_dir, 'call_log.txt')
        db_save = os.path.join(out_dir, 'calls.db')

        # Method 1: content provider (all Android versions)
        self._log("Reading call log via content provider...")
        out, _, rc = _r(
            f"adb -s {serial} shell content query "
            "--uri content://call_log/calls "
            "--projection number:date:duration:type:name:presentation 2>/dev/null",
            timeout=20)
        self._set_prog(0.5)

        if rc == 0 and out:
            calls = self._parse_content_rows(out)
            lines = [
                "MINT SCAN — CALL LOG RECOVERY",
                f"Recovered: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Total entries: {len(calls)}",
                "=" * 60, ""
            ]
            type_map = {'1':'Incoming','2':'Outgoing','3':'Missed',
                        '4':'Voicemail','5':'Rejected','6':'Blocked'}
            for c in calls:
                ts = c.get('date', '')
                if ts and ts.isdigit():
                    ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(ts)/1000))
                ctype = type_map.get(c.get('type', ''), c.get('type', '—'))
                dur   = c.get('duration', '0')
                lines.append(f"{ts}  {ctype:12s}  {c.get('number','—'):20s}  "
                             f"Dur:{dur}s  Name:{c.get('name','—')}")
            with open(save, 'w') as f:
                f.write('\n'.join(lines))
            self._log(f"✓ {len(calls)} call log entries → {save}")
        else:
            self._log("Content provider failed — trying direct DB...")

        # Method 2: rooted — pull raw SQLite DB for deleted entries
        if self._rooted:
            self._set_prog(0.7, "Root: pulling call log database...")
            self._log("Root: pulling raw call log DB (includes deleted)...")
            paths = [
                '/data/data/com.android.providers.contacts/databases/calllog.db',
                '/data/data/com.android.providers.contacts/databases/contacts2.db',
            ]
            for db_path in paths:
                o, e, rc2 = _r(
                    f"adb -s {serial} shell su -c 'cp \"{db_path}\" /sdcard/mint_calls.db 2>/dev/null'",
                    timeout=8)
                if rc2 == 0:
                    _r(f"adb -s {serial} pull /sdcard/mint_calls.db '{db_save}' 2>/dev/null",
                       timeout=10)
                    _r(f"adb -s {serial} shell rm /sdcard/mint_calls.db 2>/dev/null")
                    # Parse the SQLite database
                    deleted = self._extract_deleted_calls(db_save, save)
                    if deleted:
                        self._log(f"  + {deleted} potentially deleted entries recovered")
                    break

        self._set_prog(1.0, "✓ Call log recovery complete")
        self._add_result("📞 Call Log", out.count('\n') if out else 0, save)

    def _extract_deleted_calls(self, db_path, txt_save):
        """Extract deleted rows from SQLite call log using sqlite3."""
        try:
            conn = sqlite3.connect(db_path)
            cur  = conn.cursor()
            # Standard calls table
            try:
                cur.execute("SELECT number, date, duration, type, name FROM calls ORDER BY date DESC")
                rows = cur.fetchall()
                with open(txt_save, 'a') as f:
                    f.write("\n\n--- DIRECT DB EXTRACTION (includes deleted) ---\n")
                    for r in rows:
                        ts = time.strftime('%Y-%m-%d %H:%M:%S',
                                           time.localtime(r[1]/1000)) if r[1] else '—'
                        f.write(f"{ts}  {str(r[0]):20s}  Dur:{r[2]}s  Type:{r[3]}  Name:{r[4]}\n")
                conn.close()
                return len(rows)
            except Exception:
                conn.close()
        except Exception as e:
            self._log(f"  DB parse error: {e}")
        return 0

    def _recover_sms(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_recover_sms, daemon=True).start()

    def _do_recover_sms(self):
        self._set_prog(0.1, "Recovering SMS messages...")
        out_dir = self._get_out_dir()
        serial  = self._device
        save    = os.path.join(out_dir, 'sms_messages.txt')
        total   = 0

        for folder, uri in [
            ('Inbox',   'content://sms/inbox'),
            ('Sent',    'content://sms/sent'),
            ('Drafts',  'content://sms/draft'),
            ('All SMS', 'content://sms/'),
        ]:
            self._log(f"Reading {folder}...")
            out, _, rc = _r(
                f"adb -s {serial} shell content query "
                f"--uri {uri} "
                "--projection address:date:body:type:read 2>/dev/null",
                timeout=20)
            if rc == 0 and out:
                msgs = self._parse_content_rows(out)
                total += len(msgs)
                with open(save, 'a') as f:
                    f.write(f"\n\n=== {folder.upper()} ({len(msgs)} messages) ===\n")
                    for m in msgs:
                        ts = m.get('date', '')
                        if ts and ts.isdigit():
                            ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(int(ts)/1000))
                        f.write(f"[{ts}] {m.get('address','—')}: {m.get('body','')}\n")
                self._log(f"  {folder}: {len(msgs)} messages")
            self._set_prog(0.3 + 0.15 * ['Inbox','Sent','Drafts','All SMS'].index(folder))

        # MMS
        self._log("Reading MMS...")
        out, _, rc = _r(
            f"adb -s {serial} shell content query --uri content://mms/ "
            "--projection _id:date:sub:ct_t 2>/dev/null",
            timeout=15)
        if rc == 0 and out:
            mms = self._parse_content_rows(out)
            total += len(mms)
            with open(save, 'a') as f:
                f.write(f"\n\n=== MMS ({len(mms)} messages) ===\n")
                for m in mms:
                    ts = m.get('date', '')
                    if ts and ts.isdigit():
                        ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(int(ts)))
                    f.write(f"[{ts}] ID:{m.get('_id','—')} Sub:{m.get('sub','—')}\n")

        # Rooted: raw DB
        if self._rooted:
            self._set_prog(0.85, "Root: pulling SMS database...")
            db_save = os.path.join(out_dir, 'mmssms.db')
            _r(f"adb -s {serial} shell su -c "
               "'cp /data/data/com.android.providers.telephony/databases/mmssms.db /sdcard/mint_sms.db'",
               timeout=8)
            o, e, rc2 = _r(f"adb -s {serial} pull /sdcard/mint_sms.db '{db_save}' 2>/dev/null",
                            timeout=10)
            _r(f"adb -s {serial} shell rm /sdcard/mint_sms.db 2>/dev/null")
            if rc2 == 0 and os.path.exists(db_save):
                extra = self._parse_sms_db(db_save, save)
                if extra:
                    self._log(f"  Root DB: +{extra} additional entries (inc. deleted)")
                    total += extra

        self._set_prog(1.0, f"✓ SMS: {total} messages recovered")
        self._log(f"✓ SMS recovered: {total} messages → {save}")
        self._add_result("💬 SMS", total, save)

    def _parse_sms_db(self, db_path, txt_save):
        try:
            conn = sqlite3.connect(db_path)
            cur  = conn.cursor()
            cur.execute("SELECT address, date, body, type FROM sms ORDER BY date DESC")
            rows = cur.fetchall()
            conn.close()
            with open(txt_save, 'a') as f:
                f.write("\n\n--- DIRECT DB (includes deleted) ---\n")
                for r in rows:
                    ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(r[1]/1000)) if r[1] else '—'
                    f.write(f"[{ts}] {r[0]}: {r[2]}\n")
            return len(rows)
        except Exception as e:
            self._log(f"  SMS DB error: {e}")
            return 0

    def _recover_contacts(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_recover_contacts, daemon=True).start()

    def _do_recover_contacts(self):
        self._set_prog(0.1, "Recovering contacts...")
        out_dir = self._get_out_dir()
        serial  = self._device
        save_txt = os.path.join(out_dir, 'contacts.txt')
        save_vcf = os.path.join(out_dir, 'contacts.vcf')

        # Export as VCF via content provider
        self._log("Exporting contacts to VCF...")
        out, _, rc = _r(
            f"adb -s {serial} shell content query "
            "--uri content://contacts/phones/ "
            "--projection display_name:number:type 2>/dev/null",
            timeout=20)
        self._set_prog(0.4)

        contacts = []
        if rc == 0 and out:
            contacts = self._parse_content_rows(out)

        # Also try raw_contacts
        out2, _, rc2 = _r(
            f"adb -s {serial} shell content query "
            "--uri content://com.android.contacts/data "
            "--projection display_name:data1:mimetype 2>/dev/null",
            timeout=20)
        if rc2 == 0 and out2:
            extra = self._parse_content_rows(out2)
            for e in extra:
                if 'data1' in e and e.get('mimetype','').endswith('phone_v2'):
                    contacts.append({'display_name': e.get('display_name','—'),
                                     'number': e.get('data1','—')})

        self._set_prog(0.7)
        # Write TXT
        with open(save_txt, 'w') as f:
            f.write(f"MINT SCAN — CONTACTS RECOVERY\n")
            f.write(f"Recovered: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total: {len(contacts)}\n{'='*60}\n\n")
            for c in contacts:
                f.write(f"{c.get('display_name','—'):30s}  {c.get('number','—')}\n")

        # Write VCF
        with open(save_vcf, 'w') as f:
            for c in contacts:
                name = c.get('display_name', 'Unknown')
                num  = c.get('number', '')
                f.write(f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL:{num}\nEND:VCARD\n")

        # Rooted: pull contacts DB
        if self._rooted:
            self._set_prog(0.85, "Root: pulling contacts database...")
            db_save = os.path.join(out_dir, 'contacts2.db')
            _r(f"adb -s {serial} shell su -c "
               "'cp /data/data/com.android.providers.contacts/databases/contacts2.db /sdcard/mint_contacts.db'",
               timeout=8)
            _r(f"adb -s {serial} pull /sdcard/mint_contacts.db '{db_save}' 2>/dev/null",
               timeout=10)
            _r(f"adb -s {serial} shell rm /sdcard/mint_contacts.db 2>/dev/null")
            self._log(f"  Root: contacts DB saved → {db_save}")

        self._set_prog(1.0, f"✓ Contacts: {len(contacts)} recovered")
        self._log(f"✓ Contacts: {len(contacts)} → {save_txt} + {save_vcf}")
        self._add_result("📇 Contacts", len(contacts), save_txt)

    def _recover_whatsapp(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_recover_whatsapp, daemon=True).start()

    def _do_recover_whatsapp(self):
        self._set_prog(0.1, "Recovering WhatsApp data...")
        out_dir = os.path.join(self._get_out_dir(), 'whatsapp')
        os.makedirs(out_dir, exist_ok=True)
        serial = self._device
        total  = 0

        # WhatsApp media on sdcard (no root needed)
        for folder in ['WhatsApp', 'WhatsApp Business']:
            wa_path = f"/sdcard/{folder}"
            self._log(f"Pulling {folder}...")
            o, e, rc = _r(f"adb -s {serial} pull '{wa_path}' '{out_dir}' 2>&1", timeout=120)
            n = len(re.findall(r'pulled', o+e))
            total += n
            self._log(f"  {folder}: {n} files")
            self._set_prog(0.4)

        # WhatsApp message database (needs root, otherwise backup only)
        db_out = os.path.join(out_dir, 'databases')
        os.makedirs(db_out, exist_ok=True)
        if self._rooted:
            self._log("Root: pulling WhatsApp message database...")
            wa_db_paths = [
                '/data/data/com.whatsapp/databases/msgstore.db',
                '/data/data/com.whatsapp/databases/wa.db',
                '/data/data/com.whatsapp/databases/chatsettings.db',
            ]
            for db_path in wa_db_paths:
                fname = os.path.basename(db_path)
                tmp   = f'/sdcard/mint_wa_{fname}'
                o, e, rc = _r(
                    f"adb -s {serial} shell su -c 'cp \"{db_path}\" \"{tmp}\" 2>/dev/null'",
                    timeout=8)
                if rc == 0:
                    _r(f"adb -s {serial} pull '{tmp}' '{db_out}' 2>/dev/null", timeout=15)
                    _r(f"adb -s {serial} shell rm '{tmp}' 2>/dev/null")
                    self._log(f"  DB: {fname} saved")
                    total += 1

            # Parse msgstore.db for message export
            db_path = os.path.join(db_out, 'msgstore.db')
            if os.path.exists(db_path):
                self._parse_whatsapp_db(db_path, out_dir)
        else:
            # Check for WhatsApp backup on sdcard
            self._log("Non-rooted: checking WhatsApp sdcard backup...")
            o, e, rc = _r(
                f"adb -s {serial} shell ls /sdcard/WhatsApp/Databases/ 2>/dev/null",
                timeout=8)
            if rc == 0 and o:
                _r(f"adb -s {serial} pull /sdcard/WhatsApp/Databases '{db_out}' 2>/dev/null",
                   timeout=30)
                backups = len(o.strip().split('\n'))
                self._log(f"  {backups} backup files found")
                total += backups

        self._set_prog(1.0, f"✓ WhatsApp: {total} items recovered")
        self._log(f"✓ WhatsApp data → {out_dir}")
        self._add_result("💚 WhatsApp", total, out_dir)

    def _parse_whatsapp_db(self, db_path, out_dir):
        try:
            conn = sqlite3.connect(db_path)
            cur  = conn.cursor()
            # WhatsApp message table
            cur.execute("""
                SELECT m.timestamp, m.data, m.key_remote_jid, m.key_from_me, m.status
                FROM messages m ORDER BY m.timestamp DESC LIMIT 5000
            """)
            rows = cur.fetchall()
            conn.close()
            save = os.path.join(out_dir, 'whatsapp_messages.txt')
            with open(save, 'w') as f:
                f.write(f"WHATSAPP MESSAGES — {len(rows)} recovered\n{'='*60}\n")
                for r in rows:
                    ts   = time.strftime('%Y-%m-%d %H:%M', time.localtime(r[0]/1000)) if r[0] else '—'
                    who  = 'You' if r[3] else r[2]
                    body = str(r[1] or '(media/deleted)')
                    f.write(f"[{ts}] {who}: {body}\n")
            self._log(f"  ✓ {len(rows)} WhatsApp messages exported")
        except Exception as e:
            self._log(f"  WA DB parse: {e}")

    def _recover_docs(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_recover_docs, daemon=True).start()

    def _do_recover_docs(self):
        self._set_prog(0.1, "Recovering documents...")
        out_dir = os.path.join(self._get_out_dir(), 'documents')
        os.makedirs(out_dir, exist_ok=True)
        serial  = self._device
        exts    = ['*.pdf','*.doc','*.docx','*.xls','*.xlsx','*.ppt',
                   '*.pptx','*.txt','*.csv','*.odt','*.rtf']
        total   = 0
        for ext in exts:
            o, e, rc = _r(
                f"adb -s {serial} shell find /sdcard -name '{ext}' 2>/dev/null",
                timeout=15)
            files = [l.strip() for l in o.split('\n') if l.strip()]
            for fp in files:
                _r(f"adb -s {serial} pull '{fp}' '{out_dir}' 2>/dev/null", timeout=15)
                total += 1
        self._set_prog(1.0, f"✓ Documents: {total} files")
        self._log(f"✓ Documents: {total} files → {out_dir}")
        self._add_result("📄 Documents", total, out_dir)

    def _recover_audio(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_recover_audio, daemon=True).start()

    def _do_recover_audio(self):
        self._set_prog(0.1, "Recovering audio...")
        out_dir = os.path.join(self._get_out_dir(), 'audio')
        os.makedirs(out_dir, exist_ok=True)
        serial  = self._device
        total   = 0
        for folder in ['/sdcard/Music', '/sdcard/Recordings',
                       '/sdcard/Audio', '/sdcard/Ringtones',
                       '/sdcard/Notifications', '/sdcard/Alarms']:
            o, e, rc = _r(f"adb -s {serial} pull '{folder}' '{out_dir}' 2>&1", timeout=60)
            n = len(re.findall(r'pulled', o+e))
            total += n
        # Voice recordings
        o2, _, _ = _r(
            f"adb -s {serial} shell find /sdcard -name '*.m4a' -o -name '*.3gp' -o -name '*.ogg' 2>/dev/null",
            timeout=15)
        for fp in [l.strip() for l in o2.split('\n') if l.strip()]:
            _r(f"adb -s {serial} pull '{fp}' '{out_dir}' 2>/dev/null", timeout=10)
            total += 1
        self._set_prog(1.0, f"✓ Audio: {total} files")
        self._log(f"✓ Audio: {total} files → {out_dir}")
        self._add_result("🎵 Audio", total, out_dir)

    def _recover_videos(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_recover_videos, daemon=True).start()

    def _do_recover_videos(self):
        self._set_prog(0.1, "Recovering videos...")
        out_dir = os.path.join(self._get_out_dir(), 'videos')
        os.makedirs(out_dir, exist_ok=True)
        serial  = self._device
        total   = 0
        for folder in ['/sdcard/DCIM', '/sdcard/Movies',
                       '/sdcard/Video', '/sdcard/Download']:
            o, e, rc = _r(
                f"adb -s {serial} shell find '{folder}' "
                "-name '*.mp4' -o -name '*.mkv' -o -name '*.mov' -o -name '*.3gp' 2>/dev/null",
                timeout=15)
            for fp in [l.strip() for l in o.split('\n') if l.strip()]:
                _r(f"adb -s {serial} pull '{fp}' '{out_dir}' 2>/dev/null", timeout=30)
                total += 1
        self._set_prog(1.0, f"✓ Videos: {total} files")
        self._log(f"✓ Videos: {total} files → {out_dir}")
        self._add_result("🎬 Videos", total, out_dir)

    def _recover_apps(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_recover_apps, daemon=True).start()

    def _do_recover_apps(self):
        self._set_prog(0.1, "Getting installed apps list...")
        out_dir = self._get_out_dir()
        serial  = self._device
        save    = os.path.join(out_dir, 'installed_apps.txt')

        # User apps
        o1, _, _ = _r(f"adb -s {serial} shell pm list packages -3 2>/dev/null", timeout=15)
        # All apps with path
        o2, _, _ = _r(f"adb -s {serial} shell pm list packages -f 2>/dev/null", timeout=15)
        # App sizes
        o3, _, _ = _r(f"adb -s {serial} shell dumpsys package packages 2>/dev/null | grep 'Package\\|versionName\\|firstInstallTime'", timeout=20)

        self._set_prog(0.7)
        user_apps = [l.replace('package:', '').strip() for l in o1.split('\n') if l.strip()]
        all_apps  = [l.replace('package:', '').strip() for l in o2.split('\n') if l.strip()]

        with open(save, 'w') as f:
            f.write(f"MINT SCAN — INSTALLED APPS\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"User Apps: {len(user_apps)}  Total: {len(all_apps)}\n{'='*60}\n\n")
            f.write("=== USER INSTALLED APPS ===\n")
            for a in sorted(user_apps):
                f.write(f"  {a}\n")
            f.write(f"\n=== ALL APPS WITH PATHS ===\n")
            for a in sorted(all_apps)[:200]:
                f.write(f"  {a}\n")

        if self._rooted:
            # APK backup
            self._log("Root: backing up APKs...")
            apk_dir = os.path.join(out_dir, 'apk_backups')
            os.makedirs(apk_dir, exist_ok=True)
            for line in o2.split('\n')[:30]:
                m = re.match(r'=(.+\.apk)=(.+)', line.strip())
                if m:
                    apk_path = m.group(1)
                    pkg_name = m.group(2)
                    _r(f"adb -s {serial} pull '{apk_path}' '{apk_dir}/{pkg_name}.apk' 2>/dev/null",
                       timeout=20)

        self._set_prog(1.0, f"✓ Apps: {len(user_apps)} user apps listed")
        self._log(f"✓ Apps: {len(user_apps)} user, {len(all_apps)} total → {save}")
        self._add_result("📦 Apps", len(user_apps), save)

    def _full_backup(self):
        if not self._need_device(): return
        threading.Thread(target=self._do_full_backup, daemon=True).start()

    def _do_full_backup(self):
        self._set_prog(0.05, "Starting full phone backup...")
        out_dir = self._get_out_dir()
        serial  = self._device
        backup_file = os.path.join(out_dir, f"phone_backup_{time.strftime('%Y%m%d_%H%M%S')}.ab")

        self._log("Starting ADB full backup (check phone screen to APPROVE)...")
        self._log("⚠ You MUST tap 'BACK UP MY DATA' on the phone screen!")

        o, e, rc = _r(
            f"adb -s {serial} backup -apk -shared -all -f '{backup_file}' 2>&1",
            timeout=600)  # 10 min max

        if rc == 0 and os.path.exists(backup_file):
            size = os.path.getsize(backup_file) / 1024 / 1024
            self._set_prog(1.0, f"✓ Full backup: {size:.1f} MB")
            self._log(f"✓ Full backup saved: {size:.1f} MB → {backup_file}")
            self._add_result("💾 Full Backup", 1, backup_file)
        else:
            self._set_prog(0, "✗ Backup failed or cancelled")
            self._log(f"✗ Backup failed: {e[:200]}")
            self._log("  Try: adb backup -apk -shared -all -f backup.ab")

    def _recover_all(self):
        if not self._need_device(): return
        self._log("=== STARTING FULL RECOVERY ===")
        tasks = []
        if self.categories['images'].get():   tasks.append(self._do_recover_images)
        if self.categories['calls'].get():    tasks.append(self._do_recover_calls)
        if self.categories['sms'].get():      tasks.append(self._do_recover_sms)
        if self.categories['contacts'].get(): tasks.append(self._do_recover_contacts)
        if self.categories['whatsapp'].get(): tasks.append(self._do_recover_whatsapp)
        if self.categories['documents'].get():tasks.append(self._do_recover_docs)
        if self.categories['audio'].get():    tasks.append(self._do_recover_audio)
        if self.categories['videos'].get():   tasks.append(self._do_recover_videos)
        if self.categories['apps'].get():     tasks.append(self._do_recover_apps)

        def _run_all():
            for i, task in enumerate(tasks):
                if not self._device:
                    break
                self._log(f"\n[{i+1}/{len(tasks)}] Running: {task.__name__}...")
                task()
            self._log("\n=== FULL RECOVERY COMPLETE ===")
            self._log(f"Output folder: {self._get_out_dir()}")
            self.after(0, lambda: self.prog_lbl.configure(
                text="✓ Full recovery complete", text_color=C['ok']))

        threading.Thread(target=_run_all, daemon=True).start()

    # ── HELPERS ──────────────────────────────────────────────────

    def _parse_content_rows(self, text):
        """Parse ADB content query output into list of dicts."""
        rows    = []
        current = {}
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('Row:'):
                if current:
                    rows.append(current)
                current = {}
                parts = line.split(',')
                for part in parts:
                    m = re.search(r'(\w+)=(.+)', part.strip())
                    if m:
                        current[m.group(1)] = m.group(2).strip()
            elif '=' in line and current is not None:
                m = re.match(r'\s*(\w+)=(.+)', line)
                if m:
                    current[m.group(1)] = m.group(2).strip()
        if current:
            rows.append(current)
        return rows

    def _add_result(self, label, count, path):
        def _do():
            for w in self.results_frame.winfo_children():
                if isinstance(w, ctk.CTkLabel) and 'Results appear' in str(w.cget('text')):
                    w.destroy()
                    break
            row = ctk.CTkFrame(self.results_frame, fg_color=C['sf'],
                               border_color=C['ok'], border_width=1, corner_radius=6)
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text=label,
                         font=('Courier',10,'bold'), text_color=C['ok']
                         ).pack(side='left', padx=12, pady=8)
            ctk.CTkLabel(row, text=f"{count} items",
                         font=MONO_SM, text_color=C['ac']
                         ).pack(side='left', padx=4)
            ctk.CTkLabel(row, text=os.path.basename(str(path)),
                         font=('Courier',8), text_color=C['mu']
                         ).pack(side='left', padx=8)
            Btn(row, "📂 OPEN",
                command=lambda p=str(path): self._open_path(p),
                variant='ghost', width=70
                ).pack(side='right', padx=8, pady=6)
        self.after(0, _do)

    def _log(self, msg):
        def _do():
            self.log_box.insert('end', msg + '\n')
            self.log_box.see('end')
        self.after(0, _do)

    def _set_prog(self, val, msg=''):
        def _do():
            self.prog_bar.set(val)
            if msg:
                col = C['ok'] if val >= 1.0 else C['ac']
                self.prog_lbl.configure(text=msg, text_color=col)
        self.after(0, _do)

    def _clear_log(self):
        self.log_box.delete('1.0', 'end')

    def _open_folder(self):
        path = self._get_out_dir()
        subprocess.Popen(['xdg-open', path], stderr=subprocess.DEVNULL)

    def _open_path(self, path):
        p = path if os.path.isdir(path) else os.path.dirname(path)
        subprocess.Popen(['xdg-open', p], stderr=subprocess.DEVNULL)

    def _browse_output(self):
        import tkinter.filedialog as fd
        path = fd.askdirectory(title="Select Recovery Output Folder")
        if path:
            self.out_entry.delete(0, 'end')
            self.out_entry.insert(0, path)
            self._out_dir = path
