"""
Mint Scan v8 — Secure Erase Tool
Wipes files/folders using shred (DoD 3-pass) or manual overwrite.
"""
import tkinter as tk
import customtkinter as ctk
import threading, subprocess, os, shutil, time
from tkinter import filedialog
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, ResultBox)
from logger import get_logger

log = get_logger('secureerase')


def shred_file(path: str, passes: int = 3, log_fn=None):
    """Securely erase a file using shred. Returns (success, msg)."""
    def _l(m):
        log.info(m)
        if log_fn:
            log_fn(m)

    if not os.path.exists(path):
        return False, 'File not found'

    size = os.path.getsize(path)
    _l(f'Shredding: {path} ({size:,} bytes, {passes} passes)')

    if shutil.which('shred'):
        r = subprocess.run(
            ['shred', f'-n{passes}', '-z', '-u', path],
            capture_output=True, text=True)
        if r.returncode == 0:
            _l(f'✓ Shredded and removed: {os.path.basename(path)}')
            return True, 'Shredded successfully'
        else:
            _l(f'shred error: {r.stderr}')

    # Manual fallback — overwrite with zeros then delete
    try:
        _l('shred not available — manual overwrite...')
        with open(path, 'r+b') as f:
            for p in range(passes):
                f.seek(0)
                f.write(os.urandom(size))
                f.flush()
                os.fsync(f.fileno())
                _l(f'  Pass {p+1}/{passes} complete')
            f.seek(0)
            f.write(b'\x00' * size)
            f.flush()
            os.fsync(f.fileno())
        os.remove(path)
        _l(f'✓ Manually wiped: {os.path.basename(path)}')
        return True, 'Wiped successfully'
    except Exception as e:
        return False, str(e)


def shred_folder(folder: str, passes: int = 3, log_fn=None):
    """Recursively shred all files in a folder, then remove it."""
    count = ok = 0
    for root, dirs, files in os.walk(folder):
        for fn in files:
            fp = os.path.join(root, fn)
            count += 1
            success, _ = shred_file(fp, passes, log_fn)
            if success:
                ok += 1
    try:
        shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        pass
    return ok, count


class SecureEraseScreen(ctk.CTkFrame):
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

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text='🗑  SECURE ERASE',
                     font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['wn']).pack(side='left', padx=16)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # Warning banner
        SectionHeader(body, '01', 'WARNING — IRREVERSIBLE').pack(
            fill='x', padx=14, pady=(14, 4))
        wc = Card(body, accent=C['wn'])
        wc.pack(fill='x', padx=14, pady=(0, 8))
        ctk.CTkLabel(wc,
            text='⚠  Securely erased files CANNOT be recovered.\n'
                 'Uses shred (DoD 3-pass overwrite) — bypasses Recycle Bin.\n'
                 'Always verify your selection before proceeding.',
            font=MONO_SM, text_color=C['am'], justify='left'
            ).pack(anchor='w', padx=12, pady=12)

        # File picker
        SectionHeader(body, '02', 'SELECT TARGET').pack(
            fill='x', padx=14, pady=(8, 4))
        sel_card = Card(body)
        sel_card.pack(fill='x', padx=14, pady=(0, 8))
        self._path_lbl = ctk.CTkLabel(sel_card,
            text='No file or folder selected.',
            font=('DejaVu Sans Mono', 9), text_color=C['mu'])
        self._path_lbl.pack(anchor='w', padx=12, pady=(12, 4))
        btn_row = ctk.CTkFrame(sel_card, fg_color='transparent')
        btn_row.pack(fill='x', padx=12, pady=(0, 10))
        Btn(btn_row, '📄 SELECT FILE',
            command=self._pick_file, width=140).pack(side='left', padx=(0, 8))
        Btn(btn_row, '📁 SELECT FOLDER',
            command=self._pick_folder, variant='blue', width=150).pack(side='left')
        self._selected = None

        # Passes
        SectionHeader(body, '03', 'OVERWRITE PASSES').pack(
            fill='x', padx=14, pady=(8, 4))
        pc = Card(body)
        pc.pack(fill='x', padx=14, pady=(0, 8))
        pr = ctk.CTkFrame(pc, fg_color='transparent')
        pr.pack(fill='x', padx=12, pady=10)
        self._pass_var = ctk.IntVar(value=3)
        for n, label in [(1, '1 pass (fast)'), (3, '3 pass DoD'),
                         (7, '7 pass (slow)')]:
            ctk.CTkRadioButton(
                pr, text=label, variable=self._pass_var, value=n,
                font=MONO_SM, text_color=C['tx'],
                fg_color=C['ac'], border_color=C['br']
                ).pack(side='left', padx=12)

        # Execute
        SectionHeader(body, '04', 'EXECUTE').pack(
            fill='x', padx=14, pady=(8, 4))
        ec = Card(body, accent=C['wn'])
        ec.pack(fill='x', padx=14, pady=(0, 8))
        self._erase_btn = Btn(ec, '☢ SECURE ERASE NOW',
                              command=self._confirm_erase,
                              variant='danger', width=200)
        self._erase_btn.pack(pady=12)

        # Log
        SectionHeader(body, '05', 'ERASE LOG').pack(
            fill='x', padx=14, pady=(8, 4))
        lc = Card(body)
        lc.pack(fill='x', padx=14, pady=(0, 14))
        self._log = ctk.CTkTextbox(
            lc, height=140, font=('DejaVu Sans Mono', 9),
            fg_color=C['bg'], text_color=C['ok'], border_width=0)
        self._log.pack(fill='x', padx=8, pady=8)
        self._log.configure(state='disabled')

    def _pick_file(self):
        p = filedialog.askopenfilename(title='Select file to securely erase')
        if p:
            self._selected = p
            sz = os.path.getsize(p)
            self._path_lbl.configure(
                text=f'FILE: {p}\nSize: {sz:,} bytes',
                text_color=C['wn'])

    def _pick_folder(self):
        p = filedialog.askdirectory(title='Select folder to securely erase')
        if p:
            self._selected = p
            self._path_lbl.configure(
                text=f'FOLDER: {p}', text_color=C['wn'])

    def _confirm_erase(self):
        if not self._selected:
            self._ulog('No target selected.')
            return
        # Confirmation popup
        popup = ctk.CTkToplevel(self)
        popup.title('Confirm Secure Erase')
        popup.geometry('440x200')
        popup.configure(fg_color=C['bg'])
        popup.lift(); popup.focus_force()
        ctk.CTkLabel(popup, text='☢  CONFIRM IRREVERSIBLE ERASE',
                     font=('DejaVu Sans Mono', 12, 'bold'),
                     text_color=C['wn']).pack(pady=(20, 8))
        ctk.CTkLabel(popup,
            text=f'Target:\n{self._selected}\n\nThis CANNOT be undone.',
            font=MONO_SM, text_color=C['tx'], justify='center'
            ).pack(pady=4)
        br = ctk.CTkFrame(popup, fg_color='transparent')
        br.pack(pady=16)
        Btn(br, '✗ CANCEL', command=popup.destroy,
            variant='ghost', width=100).pack(side='left', padx=8)
        Btn(br, '☢ ERASE', variant='danger', width=100,
            command=lambda: (popup.destroy(), self._do_erase())
            ).pack(side='left', padx=8)

    def _do_erase(self):
        self._erase_btn.configure(state='disabled', text='ERASING...')
        passes = self._pass_var.get()
        target = self._selected
        def _bg():
            if os.path.isdir(target):
                ok, total = shred_folder(target, passes, self._ulog)
                self._safe_after(0, self._ulog,
                    f'Done: {ok}/{total} files erased.')
            else:
                success, msg = shred_file(target, passes, self._ulog)
                self._safe_after(0, self._ulog, msg)
            self._safe_after(0, self._erase_btn.configure,
                       {'state': 'normal', 'text': '☢ SECURE ERASE NOW'})
            self._safe_after(0, self._path_lbl.configure,
                       {'text': 'Done — select another target.',
                        'text_color': C['ok']})
            self._selected = None
        threading.Thread(target=_bg, daemon=True).start()

    def _ulog(self, msg):
        def _do():
            self._log.configure(state='normal')
            ts = time.strftime('%H:%M:%S')
            self._log.insert('end', f'[{ts}] {msg}\n')
            self._log.see('end')
            self._log.configure(state='disabled')
        self._safe_after(0, _do)

