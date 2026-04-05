"""Dashboard Screen — real system info"""
from widgets import C, MONO, MONO_SM, MONO_LG, MONO_XL, ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn
import tkinter as tk
import customtkinter as ctk
import threading
import platform
import socket
from utils import get_system_info, get_public_ip_info, get_local_ip, get_battery_info
from installer import install_all_tools


class DashScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._load()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="⬡  DASHBOARD", font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16, pady=12)
        self.refresh_btn = Btn(hdr, "↺  REFRESH", command=self._load,
                               variant='ghost', width=100)
        self.refresh_btn.pack(side='right', padx=12)

        # Scrollable body
        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=0)
        body = self.scroll

        # ── Score hero ──
        hero = Card(body)
        hero.pack(fill='x', padx=14, pady=(14, 6))
        hero_inner = ctk.CTkFrame(hero, fg_color='transparent')
        hero_inner.pack(fill='x', padx=4, pady=4)

        left = ctk.CTkFrame(hero_inner, fg_color='transparent')
        left.pack(side='left', fill='y', padx=8)
        self.score_num = ctk.CTkLabel(left, text="—", font=('Courier', 64, 'bold'),
                                       text_color=C['ok'])
        self.score_num.pack()
        self.score_lbl = ctk.CTkLabel(left, text="SECURITY SCORE",
                                       font=('Courier', 8), text_color=C['mu'])
        self.score_lbl.pack()

        right = ctk.CTkFrame(hero_inner, fg_color='transparent')
        right.pack(side='left', fill='both', expand=True, padx=16)
        self.status_lbl = ctk.CTkLabel(right, text="LOADING...",
                                        font=('Courier', 11), text_color=C['ok'])
        self.status_lbl.pack(anchor='w', pady=(8, 4))

        # Progress bars
        for name in ['SYSTEM', 'NETWORK', 'BATTERY']:
            row = ctk.CTkFrame(right, fg_color='transparent')
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text=name, font=('Courier', 8),
                         text_color=C['mu'], width=70).pack(side='left')
            bar = ctk.CTkProgressBar(row, height=6, corner_radius=3,
                                      progress_color=C['ok'],
                                      fg_color=C['br'])
            bar.pack(side='left', fill='x', expand=True, padx=6)
            bar.set(0)
            setattr(self, f'bar_{name.lower()}', bar)
            lbl = ctk.CTkLabel(row, text="—%", font=('Courier', 8),
                               text_color=C['mu'], width=36)
            lbl.pack(side='left')
            setattr(self, f'bar_{name.lower()}_lbl', lbl)

        # Settings button in hero
        Btn(right, "⚙ CONFIGURE UI & SETTINGS", 
            command=lambda: self.app._switch_tab('settings'),
            variant='ghost', width=200).pack(anchor='e', pady=(8,0))

        # ── System Info ──
        SectionHeader(body, '01', 'SYSTEM INFORMATION').pack(
            fill='x', padx=14, pady=(10, 4))
        self.sys_grid = InfoGrid(body, [], columns=3)
        self.sys_grid.pack(fill='x', padx=14)

        # ── Network Info ──
        SectionHeader(body, '02', 'NETWORK IDENTITY').pack(
            fill='x', padx=14, pady=(10, 4))
        self.net_grid = InfoGrid(body, [], columns=3)
        self.net_grid.pack(fill='x', padx=14)

        # ── Battery ──
        SectionHeader(body, '03', 'BATTERY').pack(
            fill='x', padx=14, pady=(10, 4))
        self.bat_grid = InfoGrid(body, [], columns=3)
        self.bat_grid.pack(fill='x', padx=14, pady=(0, 14))

    def _load(self):
        self.refresh_btn.configure(state='disabled', text='LOADING...')
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        sysinfo = get_system_info()
        bat     = get_battery_info()
        local_ip = get_local_ip()
        ipinfo  = get_public_ip_info()
        self.after(0, self._render, sysinfo, bat, local_ip, ipinfo)

    def _render(self, sysinfo, bat, local_ip, ipinfo):
        # Score
        score = 100
        if bat and bat.get('health', '').lower() not in ('good', 'unknown', '—'):
            score -= 10
        score = max(0, score)
        col = C['ok'] if score >= 75 else C['am'] if score >= 50 else C['wn']
        self.score_num.configure(text=str(score), text_color=col)
        status = 'SYSTEM SECURE' if score >= 75 else 'AT RISK' if score >= 50 else 'CRITICAL'
        self.score_lbl.configure(text='SECURITY SCORE')
        self.status_lbl.configure(text=status, text_color=col)
        self.app.update_score(score)

        # Bars
        self.bar_system.set(score / 100)
        self.bar_system.configure(progress_color=col)
        self.bar_system_lbl.configure(text=f'{score}%', text_color=col)
        bat_pct = bat['level'] if bat and bat.get('level') else 80
        bat_col = C['ok'] if bat_pct > 60 else C['am'] if bat_pct > 20 else C['wn']
        self.bar_battery.set(bat_pct / 100)
        self.bar_battery.configure(progress_color=bat_col)
        self.bar_battery_lbl.configure(text=f'{bat_pct}%', text_color=bat_col)
        self.bar_network.set(0.85)
        self.bar_network.configure(progress_color=C['ac'])
        self.bar_network_lbl.configure(text='85%', text_color=C['ac'])

        # Rebuild sys grid
        self.sys_grid.destroy()
        self.sys_grid = InfoGrid(self.scroll, [
            ('OS',          sysinfo.get('os', '—')),
            ('DISTRO',      sysinfo.get('distro', '—')[:30]),
            ('KERNEL',      sysinfo.get('kernel', '—')),
            ('HOSTNAME',    sysinfo.get('hostname', '—')),
            ('ARCH',        sysinfo.get('arch', '—')),
            ('MACHINE',     sysinfo.get('machine', '—')),
            ('CPU',         sysinfo.get('cpu_model', '—')[:28], C['ac']),
            ('CPU CORES',   sysinfo.get('cpu_cores', '—')),
            ('RAM TOTAL',   sysinfo.get('ram_total', '—'), C['ac']),
            ('RAM USED',    sysinfo.get('ram_used', '—')),
            ('RAM FREE',    sysinfo.get('ram_free', '—')),
            ('UPTIME',      sysinfo.get('uptime', '—')),
            ('DISK TOTAL',  sysinfo.get('disk_total', '—')),
            ('DISK USED',   sysinfo.get('disk_used', '—')),
            ('DISK FREE',   sysinfo.get('disk_free', '—')),
        ], columns=3)
        self.sys_grid.pack(fill='x', padx=14)

        # Net grid
        self.net_grid.destroy()
        self.net_grid = InfoGrid(self.scroll, [
            ('LOCAL IP',    local_ip,                    C['am']),
            ('PUBLIC IP',   ipinfo.get('ip', '—'),       C['wn']),
            ('ISP',         ipinfo.get('org', '—')),
            ('COUNTRY',     ipinfo.get('country_name', '—')),
            ('CITY',        ipinfo.get('city', '—')),
            ('REGION',      ipinfo.get('region', '—')),
            ('TIMEZONE',    ipinfo.get('timezone', '—')),
            ('ASN',         ipinfo.get('asn', '—')),
            ('CURRENCY',    ipinfo.get('currency_name', '—')),
        ], columns=3)
        self.net_grid.pack(fill='x', padx=14)

        # Battery grid
        self.bat_grid.destroy()
        bat_items = [
            ('LEVEL',   f"{bat['level']}%" if bat and bat.get('level') else '—',
             bat_col if bat else C['mu']),
            ('STATUS',  bat.get('status', '—') if bat else 'N/A (Desktop)'),
            ('HEALTH',  bat.get('health', '—') if bat else '—'),
            ('TECH',    bat.get('tech', '—') if bat else '—'),
            ('VOLTAGE', bat.get('voltage', '—') if bat else '—'),
            ('CURRENT', bat.get('current', '—') if bat else '—'),
            ('CYCLES',  bat.get('cycles', '—') if bat else '—'),
        ] if bat else [('STATUS', 'No battery detected (Desktop/AC)', C['mu'])]
        self.bat_grid = InfoGrid(self.scroll, bat_items, columns=3)
        self.bat_grid.pack(fill='x', padx=14, pady=(0, 14))

        self.refresh_btn.configure(state='normal', text='↺  REFRESH')
