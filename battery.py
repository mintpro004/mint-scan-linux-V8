"""Battery Screen — real /sys/class/power_supply data"""
from widgets import C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn
import tkinter as tk
import customtkinter as ctk
import threading, time
from utils import get_battery_info


class BatteryScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False
        self._history = []

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._load, daemon=True).start()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="🔋  BATTERY", font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, "↺  REFRESH", command=lambda: threading.Thread(
            target=self._load, daemon=True).start(),
            variant='ghost', width=100).pack(side='right', padx=12, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        SectionHeader(body, '01', 'BATTERY STATUS').pack(fill='x', padx=14, pady=(14,4))
        self.bat_card = Card(body)
        self.bat_card.pack(fill='x', padx=14, pady=(0,8))

        hero = ctk.CTkFrame(self.bat_card, fg_color='transparent')
        hero.pack(fill='x', padx=8, pady=8)

        # Battery icon
        bat_icon = ctk.CTkFrame(hero, fg_color='transparent')
        bat_icon.pack(side='left', padx=8)
        self.bat_body = ctk.CTkFrame(bat_icon, width=80, height=40,
                                      fg_color=C['bg'],
                                      border_color=C['ac'], border_width=2,
                                      corner_radius=5)
        self.bat_body.pack()
        self.bat_fill = ctk.CTkFrame(self.bat_body, height=32,
                                      fg_color=C['ok'], corner_radius=2)
        self.bat_fill.place(x=3, y=4, relwidth=0.8)

        info_side = ctk.CTkFrame(hero, fg_color='transparent')
        info_side.pack(side='left', fill='both', expand=True, padx=16)
        self.pct_lbl = ctk.CTkLabel(info_side, text="—%",
                                     font=('Courier', 48, 'bold'), text_color=C['ok'])
        self.pct_lbl.pack(anchor='w')
        self.status_lbl = ctk.CTkLabel(info_side, text="Reading...",
                                        font=MONO_SM, text_color=C['mu'])
        self.status_lbl.pack(anchor='w')

        # Progress bar
        self.bat_bar = ctk.CTkProgressBar(self.bat_card, height=8, corner_radius=4,
                                           progress_color=C['ok'], fg_color=C['br'])
        self.bat_bar.pack(fill='x', padx=12, pady=(0,4))
        self.bat_bar.set(0)

        self.bat_details = ctk.CTkFrame(self.bat_card, fg_color='transparent')
        self.bat_details.pack(fill='x', padx=8, pady=(0,8))

        SectionHeader(body, '02', 'BATTERY HISTORY').pack(fill='x', padx=14, pady=(10,4))
        self.history_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.history_frame.pack(fill='x', padx=14, pady=(0,14))

    def _load(self):
        bat = get_battery_info()
        self.after(0, self._render, bat)

    def _render(self, bat):
        if not bat:
            self.pct_lbl.configure(text='N/A')
            self.status_lbl.configure(text='No battery detected (Desktop / AC only)')
            return

        pct    = bat.get('level') or 0
        status = bat.get('status', 'Unknown')
        col    = C['ok'] if pct > 60 else C['am'] if pct > 20 else C['wn']

        self.pct_lbl.configure(text=f"{pct}%", text_color=col)
        self.status_lbl.configure(
            text=f"{status}  ·  Health: {bat.get('health','—')}  ·  {bat.get('tech','—')}",
            text_color=col)
        self.bat_bar.set(pct / 100)
        self.bat_bar.configure(progress_color=col)
        self.bat_fill.configure(
            fg_color=col,
            width=max(4, int(74 * pct / 100)))

        for w in self.bat_details.winfo_children(): w.destroy()
        InfoGrid(self.bat_details, [
            ('LEVEL',   f"{pct}%",                col),
            ('STATUS',  status,                    col),
            ('HEALTH',  bat.get('health','—')),
            ('TECH',    bat.get('tech','—')),
            ('VOLTAGE', bat.get('voltage','—'),    C['ac']),
            ('CURRENT', bat.get('current','—'),    C['ac']),
            ('CYCLES',  bat.get('cycles','—')),
        ], columns=4).pack(fill='x')

        # History
        self._history.append((time.strftime('%H:%M:%S'), pct))
        for w in self.history_frame.winfo_children(): w.destroy()
        for ts, p in self._history[-15:]:
            row = ctk.CTkFrame(self.history_frame, fg_color='transparent')
            row.pack(fill='x', pady=1)
            ctk.CTkLabel(row, text=ts, font=('Courier',8),
                         text_color=C['mu'], width=70).pack(side='left')
            c = C['ok'] if p>60 else C['am'] if p>20 else C['wn']
            bar = ctk.CTkProgressBar(row, height=6, progress_color=c, fg_color=C['br'])
            bar.pack(side='left', fill='x', expand=True, padx=6)
            bar.set(p/100)
            ctk.CTkLabel(row, text=f"{p}%", font=('Courier',8),
                         text_color=c, width=36).pack(side='left')
