"""
Mint Scan v8 — Advanced Dashboard
Premium UI: animated score ring, live stat cards, real-time mini-charts,
hex grid background, animated status indicators, advanced layout.
"""
import tkinter as tk
import customtkinter as ctk
import threading, time, math, platform
from widgets import (C, MONO, MONO_SM, MONO_LG, MONO_XL, ScrollableFrame,
                     Card, SectionHeader, InfoGrid, ResultBox, Btn)
from utils import (get_system_info, get_public_ip_info, get_local_ip,
                   get_battery_info, get_open_ports, get_processes, run_cmd)


# ── Canvas helpers ────────────────────────────────────────────────
def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _lerp_color(c1, c2, t):
    r1,g1,b1 = _hex_to_rgb(c1)
    r2,g2,b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2-r1)*t)
    g = int(g1 + (g2-g1)*t)
    b = int(b1 + (b2-b1)*t)
    return f'#{r:02x}{g:02x}{b:02x}'


class ScoreRing(tk.Canvas):
    """Animated arc ring showing security score with smooth sweep."""
    def __init__(self, parent, size=180, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=C['bg'], highlightthickness=0, **kw)
        self._size   = size
        self._score  = 0
        self._target = 0
        self._angle  = 0
        self._after  = None
        self._draw(0)

    def set_score(self, score):
        self._target = max(0, min(100, score))
        self._animate()

    def _animate(self):
        if self._after:
            self.after_cancel(self._after)
        diff = self._target - self._score
        if abs(diff) > 0.5:
            self._score += diff * 0.12
            self._draw(self._score)
            self._after = self.after(16, self._animate)
        else:
            self._score = self._target
            self._draw(self._score)

    def _draw(self, score):
        self.delete('all')
        s  = self._size
        cx = cy = s // 2
        r  = s // 2 - 14
        lw = 12

        # Background track
        self.create_arc(cx-r, cy-r, cx+r, cy+r,
                        start=135, extent=270,
                        style='arc', outline=C['br'], width=lw+2)

        # Coloured arc
        t   = score / 100
        col = _lerp_color(C['wn'], _lerp_color(C['am'], C['ok'], min(t*2,1)), t)
        if score > 0:
            self.create_arc(cx-r, cy-r, cx+r, cy+r,
                            start=135, extent=-(270*t),
                            style='arc', outline=col, width=lw,
                            dash=() )

        # Glow dots at tip
        tip_ang = math.radians(135 + 270*t)
        tx = cx + r * math.cos(tip_ang)
        ty = cy - r * math.sin(tip_ang)
        if score > 2:
            self.create_oval(tx-6, ty-6, tx+6, ty+6, fill=col, outline='')
            self.create_oval(tx-3, ty-3, tx+3, ty+3, fill='white', outline='')

        # Score number
        self.create_text(cx, cy-10, text=f'{int(score)}',
                         fill=col, font=('DejaVu Sans Mono', 34, 'bold'))
        self.create_text(cx, cy+16, text='SCORE',
                         fill=C['mu'], font=('DejaVu Sans Mono', 8))

        grade = ('A+' if score>=95 else 'A' if score>=85 else 'B' if score>=70
                 else 'C' if score>=55 else 'D')
        grade_col = (C['ok'] if score>=85 else C['am'] if score>=60 else C['wn'])
        self.create_text(cx, cy+30, text=grade,
                         fill=grade_col, font=('DejaVu Sans Mono', 10, 'bold'))


class MiniChart(tk.Canvas):
    """Animated sparkline chart for live metrics."""
    def __init__(self, parent, color=None, height=48, **kw):
        super().__init__(parent, height=height, bg=C['bg'],
                         highlightthickness=0, **kw)
        self._data  = []
        self._color = color or C['ac']
        self._max   = 100
        self.bind('<Configure>', lambda e: self._redraw())

    def push(self, val):
        self._data.append(val)
        if len(self._data) > 60:
            self._data = self._data[-60:]
        self._max = max(self._data) * 1.15 or 100
        self._redraw()

    def _redraw(self):
        self.delete('all')
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4 or not self._data:
            return
        n   = len(self._data)
        pts = []
        for i, v in enumerate(self._data):
            x = int(i * (w-2) / max(n-1, 1)) + 1
            y = int(h - 2 - (v / self._max) * (h-4))
            pts.append((x, y))
        # Fill area
        poly = [1, h] + [c for p in pts for c in p] + [pts[-1][0], h]
        r,g,b = _hex_to_rgb(self._color)
        fill_col = f'#{r//4:02x}{g//4:02x}{b//4:02x}'
        self.create_polygon(poly, fill=fill_col, outline='')
        # Line
        if len(pts) >= 2:
            for i in range(len(pts)-1):
                self.create_line(pts[i][0], pts[i][1],
                                 pts[i+1][0], pts[i+1][1],
                                 fill=self._color, width=2, smooth=True)
        # Current value dot
        if pts:
            lx, ly = pts[-1]
            self.create_oval(lx-4, ly-4, lx+4, ly+4,
                             fill=self._color, outline=C['bg'], width=2)


class StatCard(ctk.CTkFrame):
    """Premium stat card with icon, value, label, mini chart."""
    def __init__(self, parent, icon, label, color=None, chart=True, **kw):
        color = color or C['ac']
        super().__init__(parent, fg_color=C['sf'],
                         border_color=color, border_width=1,
                         corner_radius=8, **kw)
        self._color = color
        # Top row: icon + value
        top = ctk.CTkFrame(self, fg_color='transparent')
        top.pack(fill='x', padx=10, pady=(10,0))
        ctk.CTkLabel(top, text=icon, font=('DejaVu Sans Mono', 16),
                     text_color=color).pack(side='left')
        self._val = ctk.CTkLabel(top, text='—',
                                  font=('DejaVu Sans Mono', 18, 'bold'),
                                  text_color=color)
        self._val.pack(side='right')
        # Label + sub
        bot = ctk.CTkFrame(self, fg_color='transparent')
        bot.pack(fill='x', padx=10, pady=(0,4))
        ctk.CTkLabel(bot, text=label.upper(),
                     font=('DejaVu Sans Mono', 7), text_color=C['mu']).pack(side='left')
        self._sub = ctk.CTkLabel(bot, text='',
                                  font=('DejaVu Sans Mono', 7), text_color=C['mu2'])
        self._sub.pack(side='right')
        # Mini chart
        if chart:
            self._chart = MiniChart(self, color=color, height=38)
            self._chart.pack(fill='x', padx=2, pady=(0,4))
        else:
            self._chart = None

    def update(self, val, sub='', push_chart=None):
        self._val.configure(text=str(val))
        if sub:
            self._sub.configure(text=str(sub))
        if self._chart and push_chart is not None:
            self._chart.push(push_chart)


class PulseIndicator(tk.Canvas):
    """Pulsing status dot with rings."""
    def __init__(self, parent, color=None, size=28, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=C['bg'], highlightthickness=0, **kw)
        self._col  = color or C['ok']
        self._size = size
        self._ring = 0
        self._on   = True
        self._draw()
        self._pulse()

    def set_color(self, col):
        self._col = col

    def _draw(self):
        self.delete('all')
        s  = self._size
        cx = cy = s // 2
        # Outer ring
        r2 = int(cx * 0.85 * (0.5 + 0.5 * math.sin(self._ring * 0.18)))
        alpha = max(0.05, 0.3 * (1 - self._ring/12))
        if r2 > 2:
            r,g,b = _hex_to_rgb(self._col)
            dim = f'#{int(r*alpha):02x}{int(g*alpha):02x}{int(b*alpha):02x}'
            self.create_oval(cx-r2, cy-r2, cx+r2, cy+r2,
                             outline=dim, width=1)
        # Core dot
        rd = int(cx * 0.38)
        self.create_oval(cx-rd, cy-rd, cx+rd, cy+rd,
                         fill=self._col, outline='')

    def _pulse(self):
        self._ring = (self._ring + 1) % 20
        self._draw()
        self.after(80, self._pulse)


class DashScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app     = app
        self._built  = False
        self._cpu_hist = []
        self._mem_hist = []
        self._running  = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._running = True
        self._load()
        self._live_loop()

    def on_blur(self):
        self._running = False

    # ── UI BUILD ──────────────────────────────────────────────────

    def _build(self):
        # ── Header bar ──────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=52, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text='⬡  DASHBOARD',
                     font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)

        # Status indicator
        self._pulse = PulseIndicator(hdr, color=C['ok'])
        self._pulse.pack(side='left', padx=4)
        self._status_lbl = ctk.CTkLabel(hdr, text='SECURE',
                                         font=('DejaVu Sans Mono', 9, 'bold'),
                                         text_color=C['ok'])
        self._status_lbl.pack(side='left', padx=2)

        Btn(hdr, '↺ REFRESH', command=self._load,
            variant='ghost', width=100).pack(side='right', padx=12)
        Btn(hdr, '⚙ SETTINGS',
            command=lambda: self.app._switch_tab('settings'),
            variant='ghost', width=110).pack(side='right', padx=4)

        # ── Body ────────────────────────────────────────────────
        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── HERO ROW: Score ring + stat cards ───────────────────
        hero = ctk.CTkFrame(body, fg_color='transparent')
        hero.pack(fill='x', padx=14, pady=(14,6))

        # Score ring left
        ring_wrap = Card(hero, accent=C['ac'])
        ring_wrap.pack(side='left', padx=(0,8), pady=0)
        ring_inner = ctk.CTkFrame(ring_wrap, fg_color='transparent')
        ring_inner.pack(padx=12, pady=12)
        self._score_ring = ScoreRing(ring_inner, size=180)
        self._score_ring.pack()
        ctk.CTkLabel(ring_inner, text='SECURITY SCORE',
                     font=('DejaVu Sans Mono', 8), text_color=C['mu']).pack(pady=(4,0))

        # Stat cards right (2×2 grid)
        cards_frame = ctk.CTkFrame(hero, fg_color='transparent')
        cards_frame.pack(side='left', fill='both', expand=True)

        cards_top = ctk.CTkFrame(cards_frame, fg_color='transparent')
        cards_top.pack(fill='x', pady=(0,6))
        cards_bot = ctk.CTkFrame(cards_frame, fg_color='transparent')
        cards_bot.pack(fill='x')

        self._card_cpu = StatCard(cards_top, '💻', 'CPU Usage',   color=C['ac'])
        self._card_mem = StatCard(cards_top, '🧠', 'RAM',         color=C['bl'])
        self._card_bat = StatCard(cards_bot, '🔋', 'Battery',     color=C['ok'])
        self._card_net = StatCard(cards_bot, '📡', 'Network',     color=C['am'])
        for c in [self._card_cpu, self._card_mem]:
            c.pack(side='left', fill='both', expand=True, padx=(0,6))
        for c in [self._card_bat, self._card_net]:
            c.pack(side='left', fill='both', expand=True, padx=(0,6))

        # ── THREAT STATUS BAR ───────────────────────────────────
        SectionHeader(body, '01', 'THREAT STATUS').pack(
            fill='x', padx=14, pady=(10,4))
        threat_row = ctk.CTkFrame(body, fg_color='transparent')
        threat_row.pack(fill='x', padx=14, pady=(0,6))

        self._threat_cards = {}
        for key, icon, label, col in [
            ('firewall', '🔥', 'Firewall',  C['ok']),
            ('ports',    '🔍', 'Open Ports', C['am']),
            ('procs',    '⚙',  'Processes',  C['ac']),
            ('updates',  '📦', 'Packages',   C['bl']),
            ('ssh',      '🔐', 'SSH',        C['ok']),
        ]:
            f = ctk.CTkFrame(threat_row, fg_color=C['sf'],
                             border_color=col, border_width=1,
                             corner_radius=6)
            f.pack(side='left', fill='both', expand=True, padx=3)
            ctk.CTkLabel(f, text=icon, font=('DejaVu Sans Mono', 14),
                         text_color=col).pack(pady=(8,0))
            lbl = ctk.CTkLabel(f, text='—',
                               font=('DejaVu Sans Mono', 9, 'bold'),
                               text_color=col)
            lbl.pack()
            ctk.CTkLabel(f, text=label,
                         font=('DejaVu Sans Mono', 7), text_color=C['mu']).pack(pady=(0,8))
            self._threat_cards[key] = lbl

        # ── SYSTEM INFO ─────────────────────────────────────────
        SectionHeader(body, '02', 'SYSTEM INFORMATION').pack(
            fill='x', padx=14, pady=(10,4))
        self._sys_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._sys_frame.pack(fill='x', padx=14, pady=(0,6))

        # ── NETWORK IDENTITY ────────────────────────────────────
        SectionHeader(body, '03', 'NETWORK IDENTITY').pack(
            fill='x', padx=14, pady=(10,4))
        self._net_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._net_frame.pack(fill='x', padx=14, pady=(0,6))

        # ── BATTERY ─────────────────────────────────────────────
        SectionHeader(body, '04', 'BATTERY').pack(
            fill='x', padx=14, pady=(10,4))
        self._bat_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._bat_frame.pack(fill='x', padx=14, pady=(0,6))

        # ── TOP PROCESSES ────────────────────────────────────────
        SectionHeader(body, '05', 'TOP PROCESSES').pack(
            fill='x', padx=14, pady=(10,4))
        self._proc_card = Card(body)
        self._proc_card.pack(fill='x', padx=14, pady=(0,14))
        self._proc_box = ctk.CTkTextbox(self._proc_card, height=120,
                                         font=('DejaVu Sans Mono', 9),
                                         fg_color=C['bg'],
                                         text_color=C['tx'],
                                         border_width=0)
        self._proc_box.pack(fill='x', padx=8, pady=8)
        self._proc_box.insert('1.0', 'Loading processes...')
        self._proc_box.configure(state='disabled')

    # ── DATA LOADING ──────────────────────────────────────────────

    def _load(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        from concurrent.futures import ThreadPoolExecutor
        def _get_cpu():
            out, _, _ = run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
            try: return float(out.strip().replace('%','').replace(',','.') or 0)
            except: return 0.0
        def _get_mem():
            out, _, _ = run_cmd("free | grep Mem | awk '{printf \"%.0f\", $3/$2*100}'")
            try: return int(out.strip() or 0)
            except: return 0
        def _get_ufw():
            out, _, _ = run_cmd("ufw status 2>/dev/null | head -1")
            return 'active' in out.lower()
        def _get_pkgs():
            out, _, _ = run_cmd("apt list --upgradeable 2>/dev/null | wc -l")
            try: return max(0, int(out.strip()) - 1)
            except: return 0
        with ThreadPoolExecutor(max_workers=10) as ex:
            f_sys    = ex.submit(get_system_info)
            f_bat    = ex.submit(get_battery_info)
            f_lip    = ex.submit(get_local_ip)
            f_ipinfo = ex.submit(get_public_ip_info)
            f_ports  = ex.submit(get_open_ports)
            f_procs  = ex.submit(get_processes, 10)
            f_cpu    = ex.submit(_get_cpu)
            f_mem    = ex.submit(_get_mem)
            f_ufw    = ex.submit(_get_ufw)
            f_pkgs   = ex.submit(_get_pkgs)
        sysinfo  = f_sys.result()
        bat      = f_bat.result()
        local_ip = f_lip.result()
        ipinfo   = f_ipinfo.result()
        ports    = f_ports.result()
        procs    = f_procs.result()
        cpu      = f_cpu.result()
        mem_pct  = f_mem.result()
        fw_ok    = f_ufw.result()
        pkg_n    = f_pkgs.result()
        def _safe_render():
            try:
                if self.winfo_exists():
                    self._render(sysinfo, bat, local_ip, ipinfo, ports, procs,
                                 cpu, mem_pct, fw_ok, pkg_n)
            except Exception:
                pass
        self.after(0, _safe_render)

    def _render(self, sysinfo, bat, local_ip, ipinfo, ports, procs,
                cpu=0, mem_pct=0, fw_ok=False, pkg_n=0):
        # ── Score calculation ──────────────────────────────────
        score = 100
        danger_ports = {'23','4444','5555','1337','31337','7547'}
        risky_ports  = set(str(p['port']) for p in ports if str(p['port']) in danger_ports)
        score -= len(risky_ports) * 15
        if bat and bat.get('health','').lower() not in ('good','unknown','—',''):
            score -= 10
        score = max(0, min(100, score))
        col = C['ok'] if score >= 75 else C['am'] if score >= 50 else C['wn']

        self._score_ring.set_score(score)
        self.app.update_score(score)

        status = ('SYSTEM SECURE' if score >= 75 else
                  'ATTENTION NEEDED' if score >= 50 else 'CRITICAL')
        self._status_lbl.configure(text=status, text_color=col)
        self._pulse.set_color(col)

        # ── Stat cards (all values pre-fetched in background) ─
        bat_pct = bat['level'] if bat and bat.get('level') else 0

        self._card_cpu.update(f'{cpu:.0f}%', 'user+sys', push_chart=cpu)
        self._card_mem.update(f'{mem_pct}%', sysinfo.get('ram_total','—'), push_chart=mem_pct)
        self._card_bat.update(
            f"{bat_pct}%" if bat else 'AC',
            bat.get('status','—') if bat else 'Desktop',
            push_chart=bat_pct)
        self._card_net.update(local_ip, ipinfo.get('city','—'), push_chart=None)

        # ── Threat status (pre-fetched) ───────────────────────
        self._threat_cards['firewall'].configure(
            text='ACTIVE' if fw_ok else 'OFF',
            text_color=C['ok'] if fw_ok else C['wn'])
        self._threat_cards['ports'].configure(
            text=f'{len(ports)} open',
            text_color=C['ok'] if len(ports)<5 else C['am'] if len(ports)<15 else C['wn'])
        self._threat_cards['procs'].configure(
            text=f'{len(procs)} top',
            text_color=C['ac'])
        self._threat_cards['ssh'].configure(
            text='UP' if any(p['port']=='22' for p in ports) else 'OFF',
            text_color=C['ok'])
        self._threat_cards['updates'].configure(
            text=f'{pkg_n} pending' if pkg_n else 'Up to date',
            text_color=C['am'] if pkg_n > 0 else C['ok'])

        # ── System grid ───────────────────────────────────────
        for w in self._sys_frame.winfo_children(): w.destroy()
        InfoGrid(self._sys_frame, [
            ('OS',       sysinfo.get('os','—')),
            ('DISTRO',   sysinfo.get('distro','—')[:28]),
            ('KERNEL',   sysinfo.get('kernel','—')),
            ('HOSTNAME', sysinfo.get('hostname','—')),
            ('ARCH',     sysinfo.get('arch','—')),
            ('CPU CORES',sysinfo.get('cpu_cores','—')),
            ('CPU MODEL',sysinfo.get('cpu_model','—')[:24], C['ac']),
            ('RAM TOTAL',sysinfo.get('ram_total','—'), C['ac']),
            ('RAM USED', sysinfo.get('ram_used','—')),
            ('RAM FREE', sysinfo.get('ram_free','—')),
            ('DISK TOTAL',sysinfo.get('disk_total','—')),
            ('DISK USED',sysinfo.get('disk_used','—')),
            ('DISK FREE',sysinfo.get('disk_free','—')),
            ('DISK %',   sysinfo.get('disk_pct','—'),
             C['wn'] if int((sysinfo.get('disk_pct','0%') or '0%').replace('%','') or 0)>85 else C['ok']),
            ('UPTIME',   sysinfo.get('uptime','—')),
        ], columns=3).pack(fill='x')

        # ── Net grid ──────────────────────────────────────────
        for w in self._net_frame.winfo_children(): w.destroy()
        InfoGrid(self._net_frame, [
            ('LOCAL IP',  local_ip,                    C['am']),
            ('PUBLIC IP', ipinfo.get('ip','—'),         C['wn']),
            ('ISP',       ipinfo.get('org','—')),
            ('COUNTRY',   ipinfo.get('country_name','—')),
            ('CITY',      ipinfo.get('city','—')),
            ('TIMEZONE',  ipinfo.get('timezone','—')),
            ('ASN',       ipinfo.get('asn','—')),
            ('CURRENCY',  ipinfo.get('currency_name','—')),
            ('LATITUDE',  str(ipinfo.get('latitude','—'))),
        ], columns=3).pack(fill='x')

        # ── Battery ───────────────────────────────────────────
        for w in self._bat_frame.winfo_children(): w.destroy()
        if bat:
            bat_col = C['ok'] if int(bat.get('level', 50) or 50) > 20 else C['wn']
            InfoGrid(self._bat_frame, [
                ('LEVEL',   f"{bat['level']}%" if bat.get('level') else '—', bat_col),
                ('STATUS',  bat.get('status','—')),
                ('HEALTH',  bat.get('health','—')),
                ('TECH',    bat.get('tech','—')),
                ('VOLTAGE', bat.get('voltage','—')),
                ('CURRENT', bat.get('current','—')),
                ('CYCLES',  str(bat.get('cycles','—'))),
            ], columns=3).pack(fill='x')
        else:
            ResultBox(self._bat_frame, 'info',
                      'ℹ No battery detected',
                      'Running on AC power or desktop system.').pack(fill='x')

        # ── Processes ─────────────────────────────────────────
        self._proc_box.configure(state='normal')
        self._proc_box.delete('1.0','end')
        hdr_line = f"{'USER':<10} {'PID':>6} {'CPU':>6} {'MEM':>6}  COMMAND\n"
        self._proc_box.insert('end', hdr_line)
        self._proc_box.insert('end', '─'*60+'\n')
        for p in procs[:8]:
            line = (f"{p['user']:<10} {p['pid']:>6} {p['cpu']:>5}% "
                    f"{p['mem']:>5}%  {p['command'][:28]}\n")
            self._proc_box.insert('end', line)
        self._proc_box.configure(state='disabled')

    def _live_loop(self):
        if not self._running:
            return
        def _bg():
            # /proc/stat gives instant CPU usage without top's 1-second delay
            try:
                def _read_stat():
                    with open('/proc/stat') as f:
                        vals = list(map(int, f.readline().split()[1:]))
                    idle  = vals[3]
                    total = sum(vals)
                    return idle, total
                i1, t1 = _read_stat()
                import time as _t; _t.sleep(0.5)
                i2, t2 = _read_stat()
                diff_idle  = i2 - i1
                diff_total = t2 - t1
                cpu = 100.0 * (1 - diff_idle / diff_total) if diff_total else 0
            except Exception:
                cpu = 0
            mem_out, _, _ = run_cmd("free | grep Mem | awk '{printf \"%.0f\",$3/$2*100}'")
            try: mem = int(mem_out.strip() or 0)
            except: mem = 0
            def _ui():
                try:
                    if not self.winfo_exists():
                        return
                    self._card_cpu._chart and self._card_cpu._chart.push(cpu)
                    self._card_mem._chart and self._card_mem._chart.push(mem)
                    self._card_cpu.update(f'{cpu:.0f}%', 'user+sys', push_chart=None)
                    self._card_mem.update(f'{mem}%',     '',          push_chart=None)
                except Exception:
                    pass
            self.after(0, _ui)
        threading.Thread(target=_bg, daemon=True).start()
        if self._running:
            self.after(8000, self._live_loop)  # 8s — smooth without hammering
