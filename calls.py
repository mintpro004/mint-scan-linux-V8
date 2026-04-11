"""Calls Screen — Linux call log via GNOME/KDE or manual entry"""
from widgets import C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn
import tkinter as tk
import customtkinter as ctk
import threading
import os, re
from utils import run_cmd, analyse_phone_number, SA_OPERATORS
from installer import install_kdeconnect


def get_gnome_calls():
    """Try to read call history from GNOME Calls / KDE Plasma."""
    calls = []

    # GNOME Calls stores history in ~/.local/share/gnome-calls/
    paths = [
        os.path.expanduser('~/.local/share/gnome-calls/history.db'),
        os.path.expanduser('~/.local/share/calls/history.db'),
        os.path.expanduser('~/.local/share/kdeconnect/'),
    ]

    for path in paths:
        if os.path.exists(path):
            if path.endswith(".db"):
                from utils import run_safe

                out, _, rc = run_safe(["sqlite3", (path,), " 'SELECT * FROM calls LIMIT 100' 2>/dev/null"])
                if rc == 0 and out:
                    for line in out.strip().split('\n'):
                        parts = line.split('|')
                        if len(parts) >= 3:
                            calls.append({
                                'number':    parts[0] if parts else '—',
                                'direction': 'INCOMING' if '1' in str(parts[1]) else 'OUTGOING',
                                'duration':  parts[2] if len(parts) > 2 else '—',
                                'date':      parts[3] if len(parts) > 3 else '—',
                            })

    # KDE Connect call notifications log
    kde_log = os.path.expanduser('~/.local/share/kdeconnect')
    if os.path.isdir(kde_log):
        for dev_dir in os.listdir(kde_log):
            log_file = os.path.join(kde_log, dev_dir, 'telephony.log')
            if os.path.exists(log_file):
                try:
                    with open(log_file) as f:
                        for line in f.readlines()[-50:]:
                            calls.append({'raw': line.strip(), 'source': 'KDE Connect'})
                except Exception:
                    pass

    return calls


class CallsScreen(ctk.CTkFrame):
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
        ctk.CTkLabel(hdr, text="📞  CALL LOG", font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, "↺  RELOAD", command=lambda: threading.Thread(
            target=self._load, daemon=True).start(),
            variant='ghost', width=100).pack(side='right', padx=12, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # Linux limitation notice
        SectionHeader(body, '01', 'CALL LOG ACCESS').pack(fill='x', padx=14, pady=(14,4))
        info_card = Card(body, accent=C['bl'])
        info_card.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(info_card,
                     text="Linux Call Log Sources",
                     font=('DejaVu Sans Mono', 10, 'bold'), text_color=C['bl']
                     ).pack(anchor='w', padx=12, pady=(10,2))
        ctk.CTkLabel(info_card,
                     text="On Linux, call logs are available from:\n"
                          "• GNOME Calls app  (~/.local/share/gnome-calls/)\n"
                          "• KDE Connect  (links to your Android phone)\n"
                          "• Manual entry below (for number analysis)\n\n"
                          "KDE Connect is the most powerful option — it mirrors your\n"
                          "Android phone's calls, SMS and notifications to your Linux desktop.",
                     font=MONO_SM, text_color=C['mu'], justify='left'
                     ).pack(anchor='w', padx=12, pady=(0,10))
        ctk.CTkFrame(info_card, fg_color='transparent').pack()
        btn_row = ctk.CTkFrame(info_card, fg_color='transparent')
        btn_row.pack(fill='x', padx=12, pady=(0,10))
        Btn(btn_row, "↺ LOAD FROM GNOME CALLS",
            command=lambda: threading.Thread(target=self._load, daemon=True).start()
            ).pack(side='left', padx=(0,8))
        Btn(btn_row, "⚙ INSTALL KDE CONNECT",
            command=self._install_kde_connect, variant='blue'
            ).pack(side='left')

        # Found calls
        SectionHeader(body, '02', 'CALL HISTORY').pack(fill='x', padx=14, pady=(10,4))
        self.calls_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.calls_frame.pack(fill='x', padx=14)

        # Phone number analyser
        SectionHeader(body, '03', 'NUMBER ANALYSER').pack(fill='x', padx=14, pady=(10,4))
        analyser = Card(body)
        analyser.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(analyser, text="Enter any phone number to analyse risk, SA operator, and scam patterns:",
                     font=MONO_SM, text_color=C['mu']
                     ).pack(anchor='w', padx=12, pady=(10,4))
        inp_row = ctk.CTkFrame(analyser, fg_color='transparent')
        inp_row.pack(fill='x', padx=12, pady=(0,8))
        self.num_entry = ctk.CTkEntry(inp_row, placeholder_text="+27821234567",
                                       font=MONO_SM, fg_color=C['bg'],
                                       border_color=C['br'], text_color=C['tx'],
                                       height=36)
        self.num_entry.pack(side='left', fill='x', expand=True, padx=(0,8))
        Btn(inp_row, "CHECK", command=self._check_number, width=80).pack(side='left')
        self.num_result = ctk.CTkFrame(analyser, fg_color='transparent')
        self.num_result.pack(fill='x', padx=12, pady=(0,8))

        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        calls = get_gnome_calls()
        self._safe_after(0, self._render_calls, calls)

    def _render_calls(self, calls):
        if not hasattr(self, "calls_frame"): return
        for w in self.calls_frame.winfo_children():
            w.destroy()

        if not calls:
            ctk.CTkLabel(self.calls_frame,
                         text="No call history found from GNOME Calls.\n\n"
                              "To get your Android call log on Linux, install KDE Connect:\n"
                              "  sudo apt install kdeconnect\n"
                              "Then pair your Android phone — calls, SMS and notifications\n"
                              "from your phone will appear here automatically.",
                         font=MONO_SM, text_color=C['mu'], justify='left'
                         ).pack(pady=12, anchor='w')
            return

        for call in calls[:50]:
            self._make_call_row(call)

    def _make_call_row(self, call):
        num = call.get('number') or call.get('raw', '—')
        analysis = analyse_phone_number(num) if '+' in num or num.startswith('0') else {}
        risk  = analysis.get('risk', 'LOW')
        rcolor = C['wn'] if risk == 'HIGH' else C['am'] if risk == 'MEDIUM' else C['ok']
        direction = call.get('direction', '?')
        icon = '📲' if direction == 'INCOMING' else '📤' if direction == 'OUTGOING' else '❌'

        row = ctk.CTkFrame(self.calls_frame, fg_color=C['sf'],
                            border_color=C['wn'] if risk == 'HIGH' else C['br'],
                            border_width=1, corner_radius=8)
        row.pack(fill='x', pady=3)
        ctk.CTkLabel(row, text=icon, font=('DejaVu Sans Mono', 18)).pack(side='left', padx=12, pady=8)

        mid = ctk.CTkFrame(row, fg_color='transparent')
        mid.pack(side='left', fill='both', expand=True, pady=8)
        ctk.CTkLabel(mid, text=num, font=('DejaVu Sans Mono', 11, 'bold'),
                     text_color=rcolor if risk == 'HIGH' else C['tx']).pack(anchor='w')
        meta = f"{direction}  ·  Duration: {call.get('duration','—')}  ·  {call.get('date','')}"
        ctk.CTkLabel(mid, text=meta, font=('DejaVu Sans Mono', 8),
                     text_color=C['mu']).pack(anchor='w')
        if analysis.get('operator'):
            ctk.CTkLabel(mid, text=f"Operator: {analysis['operator']}",
                         font=('DejaVu Sans Mono', 8), text_color=C['ac']).pack(anchor='w')
        for reason in analysis.get('reasons', []):
            ctk.CTkLabel(mid, text=f"⚠ {reason}", font=('DejaVu Sans Mono', 8),
                         text_color=C['wn']).pack(anchor='w')

        if risk != 'LOW':
            badge = ctk.CTkFrame(row, fg_color=rcolor,
                                  border_color=rcolor, border_width=1, corner_radius=3)
            badge.pack(side='right', padx=12)
            ctk.CTkLabel(badge, text=risk, font=('DejaVu Sans Mono', 7, 'bold'),
                         text_color=rcolor).pack(padx=6, pady=2)

    def _check_number(self):
        for w in self.num_result.winfo_children():
            w.destroy()
        num = self.num_entry.get().strip()
        if not num:
            return
        a = analyse_phone_number(num)
        rtype = 'warn' if a['risk'] == 'HIGH' else 'med' if a['risk'] == 'MEDIUM' else 'ok'
        details = f"Clean: {a['clean']}\n"
        if a.get('operator'): details += f"Operator: {a['operator']}\n"
        if a['reasons']: details += '\n'.join(f"⚠ {r}" for r in a['reasons'])
        else: details += "✓ No risk patterns detected"
        ResultBox(self.num_result, rtype, f"RISK: {a['risk']}", details).pack(fill='x')

    def _install_kde_connect(self):
        import subprocess
        subprocess.Popen(['x-terminal-emulator', '-e',
                          'bash -c "sudo apt install kdeconnect -y; read -p \'Done. Press Enter\'"'])
