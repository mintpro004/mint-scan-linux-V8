"""Notifications Screen — system notifications via dbus/libnotify"""
from widgets import C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader, ResultBox, Btn
import tkinter as tk
import customtkinter as ctk
import threading, time, subprocess
from utils import run_cmd
from installer import install_kdeconnect


class NotifsScreen(ctk.CTkFrame):
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
        self._notifs = []
        self._monitoring = False

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
        ctk.CTkLabel(hdr, text="🔔  NOTIFICATIONS", font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        self.mon_btn = Btn(hdr, "▶  START MONITOR",
                           command=self._toggle_monitor, width=160)
        self.mon_btn.pack(side='right', padx=12, pady=6)
        Btn(hdr, "🗑  CLEAR", command=self._clear,
            variant='ghost', width=80).pack(side='right', padx=4, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        SectionHeader(body, '01', 'MONITOR STATUS').pack(fill='x', padx=14, pady=(14,4))
        status_card = Card(body, accent=C['bl'])
        status_card.pack(fill='x', padx=14, pady=(0,8))
        ctk.CTkLabel(status_card,
                     text="Notification Monitor — Linux D-Bus",
                     font=('Courier', 10, 'bold'), text_color=C['bl']
                     ).pack(anchor='w', padx=12, pady=(10,2))
        ctk.CTkLabel(status_card,
                     text="Mint Scan monitors system notifications via D-Bus on Linux.\n"
                          "This captures desktop notifications from all apps:\n"
                          "• WhatsApp Web, Telegram, Signal (browser/desktop)\n"
                          "• Email clients (Thunderbird, Evolution)\n"
                          "• KDE Connect (mirrors Android SMS, calls, WhatsApp)\n"
                          "• System alerts, package manager updates\n\n"
                          "All real notifications — no fake demo data.",
                     font=MONO_SM, text_color=C['mu'], justify='left'
                     ).pack(anchor='w', padx=12, pady=(0,10))

        self.mon_status = ctk.CTkLabel(status_card, text="● IDLE",
                                        font=('Courier', 10, 'bold'), text_color=C['mu'])
        self.mon_status.pack(anchor='w', padx=12, pady=(0,10))

        SectionHeader(body, '02', 'CAPTURED NOTIFICATIONS').pack(fill='x', padx=14, pady=(10,4))
        self.notif_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.notif_frame.pack(fill='x', padx=14, pady=(0,8))

        self._show_empty()

        SectionHeader(body, '03', 'KDE CONNECT SETUP').pack(fill='x', padx=14, pady=(10,4))
        kde_card = Card(body, accent=C['bl'])
        kde_card.pack(fill='x', padx=14, pady=(0,14))
        ctk.CTkLabel(kde_card,
                     text="For full Android integration (SMS, WhatsApp, calls, notifications)\n"
                          "install KDE Connect. It mirrors everything from your phone to Linux.",
                     font=MONO_SM, text_color=C['mu'], justify='left'
                     ).pack(anchor='w', padx=12, pady=(10,6))
        btn_row = ctk.CTkFrame(kde_card, fg_color='transparent')
        btn_row.pack(fill='x', padx=12, pady=(0,10))
        Btn(btn_row, "INSTALL: sudo apt install kdeconnect",
            command=lambda: install_kdeconnect(self),
            variant='blue', width=360).pack(side='left')

    def _toggle_monitor(self):
        if self._monitoring:
            self._monitoring = False
            self.mon_btn.configure(text='▶  START MONITOR')
            self.mon_status.configure(text='● STOPPED', text_color=C['mu'])
        else:
            self._monitoring = True
            self.mon_btn.configure(text='⏹  STOP MONITOR')
            self.mon_status.configure(text='● MONITORING', text_color=C['ok'])
            threading.Thread(target=self._monitor_worker, daemon=True).start()

    def _monitor_worker(self):
        """Monitor D-Bus for desktop notifications."""
        try:
            proc = subprocess.Popen(
                ['dbus-monitor', '--session',
                 "interface='org.freedesktop.Notifications'"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            app_name = ''
            summary  = ''
            body_txt = ''
            for line in proc.stdout:
                if not self._monitoring:
                    proc.terminate()
                    break
                line = line.strip()
                if 'string' in line:
                    val = line.split('"')[1] if '"' in line else ''
                    if not app_name:
                        app_name = val
                    elif not summary:
                        summary = val
                    elif not body_txt:
                        body_txt = val
                        if app_name or summary:
                            notif = {
                                'app':  app_name or 'System',
                                'title': summary,
                                'body': body_txt,
                                'time': time.strftime('%H:%M:%S'),
                                'risk': self._assess_risk(summary, body_txt),
                            }
                            self._notifs.insert(0, notif)
                            self._safe_after(0, self._render_notifs)
                        app_name = summary = body_txt = ''
        except FileNotFoundError:
            self._safe_after(0, lambda: self.mon_status.configure(
                text='● dbus-monitor not found — install: sudo apt install dbus',
                text_color=C['wn']))
        except Exception as e:
            self._safe_after(0, lambda: self.mon_status.configure(
                text=f'● Error: {str(e)[:60]}', text_color=C['wn']))

    def _assess_risk(self, title, body):
        txt = f"{title} {body}".lower()
        score = sum(1 for p in [r'won|winner|prize', r'urgent.*account',
                                  r'verify.*bank', r'free.*cash', r'click.*link']
                    if __import__('re').search(p, txt))
        return 'HIGH' if score >= 2 else 'MEDIUM' if score == 1 else 'LOW'

    def _show_empty(self):
        for w in self.notif_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.notif_frame,
                     text="Tap START MONITOR to begin capturing desktop notifications.\n"
                          "New alerts will appear here in real time.",
                     font=MONO_SM, text_color=C['mu']).pack(pady=16)

    def _render_notifs(self):
        for w in self.notif_frame.winfo_children(): w.destroy()
        if not self._notifs:
            self._show_empty()
            return
        for n in self._notifs[:30]:
            rcolor = C['wn'] if n['risk']=='HIGH' else C['am'] if n['risk']=='MEDIUM' else C['ok']
            row = ctk.CTkFrame(self.notif_frame, fg_color=C['sf'],
                                border_color=rcolor if n['risk']!='LOW' else C['br'],
                                border_width=1, corner_radius=8)
            row.pack(fill='x', pady=3)
            top = ctk.CTkFrame(row, fg_color='transparent')
            top.pack(fill='x', padx=12, pady=(8,2))
            ctk.CTkLabel(top, text=n['app'], font=('Courier',10,'bold'),
                         text_color=C['tx']).pack(side='left')
            ctk.CTkLabel(top, text=n['time'], font=('Courier',8),
                         text_color=C['mu']).pack(side='right')
            ctk.CTkLabel(row, text=n['title'], font=MONO_SM,
                         text_color=C['tx']).pack(anchor='w', padx=12)
            if n['body']:
                ctk.CTkLabel(row, text=n['body'], font=('Courier',9),
                             text_color=C['mu'], wraplength=650
                             ).pack(anchor='w', padx=12, pady=(0,8))

    def _clear(self):
        self._notifs.clear()
        self._show_empty()
