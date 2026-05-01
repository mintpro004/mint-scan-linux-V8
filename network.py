"""
Mint Scan v8 — Advanced Network Screen
ANALOG SPEEDOMETER gauges for download/upload, animated ping graph,
full clipboard Traffic Log, live connection table, public IP panel.
"""
import tkinter as tk
import customtkinter as ctk
import threading, time, math, os, csv, io
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader,
                     InfoGrid, ResultBox, Btn, LiveBadge)
from utils import (get_network_interfaces, get_public_ip_info, get_local_ip,
                   get_active_connections, ping, run_cmd, copy_to_clipboard)


# ── Canvas helpers ────────────────────────────────────────────────
def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _lerp_color(c1, c2, t):
    r1,g1,b1 = _hex_to_rgb(c1)
    r2,g2,b2 = _hex_to_rgb(c2)
    return '#{:02x}{:02x}{:02x}'.format(
        int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))


# ═══════════════════════════════════════════════════════════════════
# ANALOG SPEEDOMETER GAUGE
# ═══════════════════════════════════════════════════════════════════
class SpeedometerGauge(tk.Canvas):
    """
    High-quality analog speedometer with:
    - Gradient arc track (green→amber→red)
    - Animated needle with smooth sweep
    - Tick marks with value labels
    - Digital readout in center
    - Unit label below
    """
    def __init__(self, parent, max_val=100, unit='Mbps',
                 label='DOWNLOAD', color=None, size=200, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=C['bg'], highlightthickness=0, **kw)
        self._max    = max_val
        self._unit   = unit
        self._label  = label
        self._color  = color or C['ac']
        self._size   = size
        self._val    = 0
        self._target = 0
        self._after  = None
        self._draw(0)

    def set_value(self, val, animate=True):
        self._target = max(0, min(val, self._max))
        if animate:
            self._animate()
        else:
            self._val = self._target
            self._draw(self._val)

    def _animate(self):
        if self._after:
            self.after_cancel(self._after)
        diff = self._target - self._val
        if abs(diff) > 0.2:
            self._val += diff * 0.10
            self._draw(self._val)
            self._after = self.after(16, self._animate)
        else:
            self._val = self._target
            self._draw(self._val)

    def _draw(self, val):
        self.delete('all')
        s   = self._size
        cx  = s // 2
        cy  = int(s * 0.54)
        r   = int(s * 0.40)
        track_w = max(10, int(s * 0.065))

        # ── Arc spans 220° from bottom-left to bottom-right ──
        START = 220   # degrees (tkinter: counter-clockwise from 3 o'clock)
        SWEEP = -220  # negative = clockwise

        # Background track
        pad = track_w // 2 + 2
        self.create_arc(cx-r-pad, cy-r-pad, cx+r+pad, cy+r+pad,
                        start=START, extent=SWEEP,
                        style='arc', outline=C['br2'], width=track_w+4)

        # Gradient coloured arc — draw in segments
        SEGS = 60
        for i in range(SEGS):
            t   = i / SEGS
            ang = START + SWEEP * t
            ext = SWEEP / SEGS * 1.5
            col = _lerp_color(
                _lerp_color(C['ok'], C['am'], min(t*2, 1)),
                _lerp_color(C['am'], C['wn'], max(0, t*2-1)), t)
            self.create_arc(cx-r-pad, cy-r-pad, cx+r+pad, cy+r+pad,
                            start=ang, extent=ext,
                            style='arc', outline=col, width=track_w)

        # Active value arc overlay (brighter, thicker)
        active_t = val / self._max if self._max else 0
        if active_t > 0.01:
            active_col = _lerp_color(
                _lerp_color(C['ok'], C['am'], min(active_t*2, 1)),
                _lerp_color(C['am'], C['wn'], max(0, active_t*2-1)), active_t)
            self.create_arc(cx-r-pad, cy-r-pad, cx+r+pad, cy+r+pad,
                            start=START, extent=SWEEP * active_t,
                            style='arc', outline=active_col, width=track_w+2)

        # ── Tick marks ──────────────────────────────────────
        TICKS = 11   # 0,10,20…100 (or scaled)
        for i in range(TICKS):
            t_frac = i / (TICKS - 1)
            ang_deg= START + SWEEP * t_frac
            ang_r  = math.radians(ang_deg)
            is_major = (i % 2 == 0)
            tick_len = int(r * (0.18 if is_major else 0.10))
            x1 = cx + (r - track_w//2 - 2) * math.cos(ang_r)
            y1 = cy - (r - track_w//2 - 2) * math.sin(ang_r)
            x2 = cx + (r - track_w//2 - 2 - tick_len) * math.cos(ang_r)
            y2 = cy - (r - track_w//2 - 2 - tick_len) * math.sin(ang_r)
            col = C['mu'] if not is_major else C['mu2']
            self.create_line(x1, y1, x2, y2, fill=col,
                             width=2 if is_major else 1)
            if is_major:
                tick_val = int(self._max * t_frac)
                lx = cx + (r - track_w - int(s*0.09)) * math.cos(ang_r)
                ly = cy - (r - track_w - int(s*0.09)) * math.sin(ang_r)
                self.create_text(lx, ly, text=str(tick_val),
                                 fill=C['mu'], font=('DejaVu Sans Mono', max(6, int(s*0.045))))

        # ── Needle ──────────────────────────────────────────
        needle_ang_r = math.radians(START + SWEEP * (val / self._max if self._max else 0))
        needle_len   = int(r * 0.72)
        hub_r        = int(s * 0.040)

        # Needle shadow
        sx = cx + needle_len * math.cos(needle_ang_r)
        sy = cy - needle_len * math.sin(needle_ang_r)
        self.create_line(cx+1, cy+1, sx+1, sy+1,
                         fill='#000000', width=3, capstyle='round')

        # Needle body — tapered using polygon
        side_ang = needle_ang_r + math.pi/2
        base_w   = max(2, int(s * 0.018))
        p1x = cx + base_w * math.cos(side_ang)
        p1y = cy - base_w * math.sin(side_ang)
        p2x = cx - base_w * math.cos(side_ang)
        p2y = cy + base_w * math.sin(side_ang)
        active_col = _lerp_color(
            _lerp_color(C['ok'], C['am'], min(active_t*2, 1)),
            _lerp_color(C['am'], C['wn'], max(0, active_t*2-1)), active_t)
        self.create_polygon(p1x,p1y, p2x,p2y, sx,sy,
                            fill=active_col if active_t>0.01 else C['mu2'],
                            outline='', smooth=True)

        # Hub circle
        self.create_oval(cx-hub_r, cy-hub_r, cx+hub_r, cy+hub_r,
                         fill=C['br2'], outline=C['ac'], width=2)

        # ── Digital readout ─────────────────────────────────
        disp = f'{val:.1f}'
        font_size = max(14, int(s * 0.11))
        self.create_text(cx, cy + int(s * 0.13),
                         text=disp,
                         fill=active_col if active_t > 0.01 else C['mu'],
                         font=('DejaVu Sans Mono', font_size, 'bold'))
        self.create_text(cx, cy + int(s * 0.22),
                         text=self._unit,
                         fill=C['mu'], font=('DejaVu Sans Mono', max(7, int(s*0.05))))

        # ── Label ────────────────────────────────────────────
        self.create_text(cx, int(s * 0.10),
                         text=self._label,
                         fill=self._color,
                         font=('DejaVu Sans Mono', max(7, int(s*0.055)), 'bold'))

        # Bottom label
        grade = '—'
        if self._unit == 'Mbps' and val > 0:
            grade = ('A+' if val>100 else 'A' if val>50 else 'B' if val>25
                     else 'C' if val>10 else 'D' if val>5 else 'F')
        if grade != '—':
            g_col = (C['ok'] if grade in ('A+','A') else
                     C['am'] if grade in ('B','C') else C['wn'])
            self.create_text(cx, int(s * 0.90),
                             text=f'GRADE  {grade}',
                             fill=g_col,
                             font=('DejaVu Sans Mono', max(7, int(s*0.05)), 'bold'))


# ═══════════════════════════════════════════════════════════════════
# PING GRAPH
# ═══════════════════════════════════════════════════════════════════
class PingGraph(tk.Canvas):
    """Animated ping sparkline with shaded fill, min/avg/max labels."""
    def __init__(self, parent, height=90, **kw):
        super().__init__(parent, height=height,
                         bg=C['bg'], highlightthickness=0, **kw)
        self._data = []
        self.bind('<Configure>', lambda e: self._redraw())

    def push(self, ms):
        self._data.append(ms)
        if len(self._data) > 80:
            self._data = self._data[-80:]
        self._redraw()

    def _redraw(self):
        self.delete('all')
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4 or not self._data:
            return
        pad   = 6
        n     = len(self._data)
        mx    = max(self._data) * 1.2 or 100
        mn_v  = min(self._data)
        avg_v = sum(self._data) / n

        # Grid lines
        for pct in (0.25, 0.5, 0.75):
            gy = pad + (1 - pct) * (h - 2*pad)
            self.create_line(0, gy, w, gy, fill=C['br'], width=1, dash=(3,6))
            ms_label = int(mx * pct)
            self.create_text(2, gy, text=f'{ms_label}ms',
                             fill=C['mu'], font=('DejaVu Sans Mono',7), anchor='nw')

        def to_pt(i, v):
            x = pad + i * (w - 2*pad) / max(n-1,1)
            y = pad + (1 - v/mx) * (h - 2*pad)
            return x, y

        pts = [to_pt(i, v) for i, v in enumerate(self._data)]

        # Fill
        poly = [pad, h-pad] + [c for p in pts for c in p] + [pts[-1][0], h-pad]
        r,g,b = _hex_to_rgb(C['ac'])
        self.create_polygon(poly, fill=f'#{r//5:02x}{g//5:02x}{b//5:02x}', outline='')

        # Line with color by latency
        for i in range(len(pts)-1):
            v  = self._data[i]
            col = (C['ok'] if v < 30 else C['am'] if v < 80 else C['wn'])
            self.create_line(pts[i][0], pts[i][1],
                             pts[i+1][0], pts[i+1][1],
                             fill=col, width=2, smooth=True)

        # Latest dot
        if pts:
            lx, ly = pts[-1]
            v   = self._data[-1]
            col = (C['ok'] if v < 30 else C['am'] if v < 80 else C['wn'])
            self.create_oval(lx-5, ly-5, lx+5, ly+5,
                             fill=col, outline=C['bg'], width=2)
            self.create_text(lx+8, ly, text=f'{v:.0f}ms',
                             fill=col, font=('DejaVu Sans Mono',8,'bold'), anchor='w')

        # Avg line
        avg_y = pad + (1 - avg_v/mx) * (h - 2*pad)
        self.create_line(0, avg_y, w, avg_y,
                         fill=C['mu'], width=1, dash=(2,4))


# ═══════════════════════════════════════════════════════════════════
# NETWORK SCREEN
# ═══════════════════════════════════════════════════════════════════
class NetworkScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app             = app
        self._built          = False
        self._ping_running = False
        self._traffic_running = False
        self._traffic_proc   = None
        self._find_positions = []
        self._find_idx       = 0

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._start_ping()
        threading.Thread(target=self._load, daemon=True).start()

    def on_blur(self):
        """Stop background threads when leaving this tab."""
        self._ping_running = False
        self._traffic_running = False
        if self._traffic_proc:
            try:
                self._traffic_proc.terminate()
            except Exception:
                pass
            self._traffic_proc = None

    # ── BUILD ─────────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=52, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='📡  NETWORK',
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        self._speed_btn = Btn(hdr, '▶ SPEED TEST',
                              command=self._run_speed, width=130)
        self._speed_btn.pack(side='right', padx=8, pady=8)
        Btn(hdr, '↺ REFRESH',
            command=lambda: threading.Thread(target=self._load, daemon=True).start(),
            variant='ghost', width=100).pack(side='right', padx=4, pady=8)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── 01 PING GRAPH ─────────────────────────────────────
        SectionHeader(body, '01', 'LIVE LATENCY — RTT GRAPH').pack(
            fill='x', padx=14, pady=(14,4))
        ping_card = Card(body)
        ping_card.pack(fill='x', padx=14, pady=(0,6))

        ph = ctk.CTkFrame(ping_card, fg_color='transparent')
        ph.pack(fill='x', padx=10, pady=(8,4))
        LiveBadge(ph).pack(side='left')
        self._ping_val = ctk.CTkLabel(ph, text='— ms',
                                       font=('DejaVu Sans Mono',13,'bold'),
                                       text_color=C['ok'])
        self._ping_val.pack(side='right')

        self._ping_graph = PingGraph(ping_card, height=90)
        self._ping_graph.pack(fill='x', padx=8, pady=4)

        stats = ctk.CTkFrame(ping_card, fg_color='transparent')
        stats.pack(fill='x', padx=10, pady=(0,10))
        self._ping_min = ctk.CTkLabel(stats, text='MIN: —',
                                       font=('DejaVu Sans Mono',8), text_color=C['ok'])
        self._ping_avg = ctk.CTkLabel(stats, text='AVG: —',
                                       font=('DejaVu Sans Mono',8), text_color=C['am'])
        self._ping_max = ctk.CTkLabel(stats, text='MAX: —',
                                       font=('DejaVu Sans Mono',8), text_color=C['wn'])
        self._ping_jitter = ctk.CTkLabel(stats, text='JITTER: —',
                                          font=('DejaVu Sans Mono',8), text_color=C['mu'])
        for l in [self._ping_min, self._ping_avg,
                  self._ping_max, self._ping_jitter]:
            l.pack(side='left', padx=10)

        # ── 02 ANALOG SPEEDOMETERS ────────────────────────────
        SectionHeader(body, '02', 'SPEED TEST — ANALOG GAUGES').pack(
            fill='x', padx=14, pady=(10,4))
        speed_card = Card(body, accent=C['ac'])
        speed_card.pack(fill='x', padx=14, pady=(0,6))

        gauge_row = ctk.CTkFrame(speed_card, fg_color='transparent')
        gauge_row.pack(fill='x', padx=10, pady=(10,6))

        # Download gauge
        dl_frame = ctk.CTkFrame(gauge_row, fg_color=C['s2'],
                                border_color=C['ac'], border_width=1,
                                corner_radius=8)
        dl_frame.pack(side='left', fill='both', expand=True, padx=(0,8))
        self._gauge_dl = SpeedometerGauge(dl_frame, max_val=200,
                                           unit='Mbps', label='▼ DOWNLOAD',
                                           color=C['ac'], size=210)
        self._gauge_dl.pack(pady=8)

        # Upload gauge
        ul_frame = ctk.CTkFrame(gauge_row, fg_color=C['s2'],
                                border_color=C['bl'], border_width=1,
                                corner_radius=8)
        ul_frame.pack(side='left', fill='both', expand=True, padx=(0,8))
        self._gauge_ul = SpeedometerGauge(ul_frame, max_val=100,
                                           unit='Mbps', label='▲ UPLOAD',
                                           color=C['bl'], size=210)
        self._gauge_ul.pack(pady=8)

        # Ping gauge
        ping_frame = ctk.CTkFrame(gauge_row, fg_color=C['s2'],
                                  border_color=C['ok'], border_width=1,
                                  corner_radius=8)
        ping_frame.pack(side='left', fill='both', expand=True)
        self._gauge_ping = SpeedometerGauge(ping_frame, max_val=300,
                                             unit='ms', label='◉ PING',
                                             color=C['ok'], size=210)
        self._gauge_ping.pack(pady=8)

        # Status row under gauges
        status_row = ctk.CTkFrame(speed_card, fg_color='transparent')
        status_row.pack(fill='x', padx=10, pady=(0,12))
        self._speed_status = ctk.CTkLabel(status_row,
                                           text='Tap ▶ SPEED TEST to start',
                                           font=('DejaVu Sans Mono',10), text_color=C['mu'])
        self._speed_status.pack(side='left')
        self._speed_grade = ctk.CTkLabel(status_row, text='',
                                          font=('DejaVu Sans Mono',14,'bold'),
                                          text_color=C['ok'])
        self._speed_grade.pack(side='right', padx=10)

        # Progress bar for speed test
        self._speed_prog = ctk.CTkProgressBar(speed_card, height=4,
                                               progress_color=C['ac'],
                                               fg_color=C['br'])
        self._speed_prog.pack(fill='x', padx=10, pady=(0,10))
        self._speed_prog.set(0)

        # ── 03 INTERFACES ─────────────────────────────────────
        SectionHeader(body, '03', 'NETWORK INTERFACES').pack(
            fill='x', padx=14, pady=(10,4))
        self._iface_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._iface_frame.pack(fill='x', padx=14, pady=(0,6))

        # ── 04 PUBLIC IDENTITY ────────────────────────────────
        SectionHeader(body, '04', 'PUBLIC IDENTITY').pack(
            fill='x', padx=14, pady=(10,4))
        self._pub_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._pub_frame.pack(fill='x', padx=14, pady=(0,6))

        # ── 05 ACTIVE CONNECTIONS ─────────────────────────────
        SectionHeader(body, '05', 'ACTIVE CONNECTIONS').pack(
            fill='x', padx=14, pady=(10,4))
        self._conn_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._conn_frame.pack(fill='x', padx=14, pady=(0,6))

        # ══════════════════════════════════════════════════════
        # 06 TRAFFIC LOG — full clipboard & file operations
        # ══════════════════════════════════════════════════════
        SectionHeader(body, '06', 'TRAFFIC LOG — LIVE CAPTURE').pack(
            fill='x', padx=14, pady=(10,4))
        tlog_card = Card(body)
        tlog_card.pack(fill='x', padx=14, pady=(0,14))

        # Capture controls
        ctrl_row = ctk.CTkFrame(tlog_card, fg_color='transparent')
        ctrl_row.pack(fill='x', padx=8, pady=(8,4))
        self._cap_status = ctk.CTkLabel(ctrl_row,
                                         text='● IDLE — tap CAPTURE to start',
                                         font=MONO_SM, text_color=C['mu'])
        self._cap_status.pack(side='left', padx=4)

        self._cap_btn = Btn(ctrl_row, '▶ CAPTURE', command=self._toggle_capture,
                            variant='primary', width=100)
        self._cap_btn.pack(side='right', padx=3)
        Btn(ctrl_row, '📊 ANALYZE', command=self._analyze,
            variant='blue', width=90).pack(side='right', padx=3)

        # Action buttons row
        act_row = ctk.CTkFrame(tlog_card, fg_color='transparent')
        act_row.pack(fill='x', padx=8, pady=(2,4))
        Btn(act_row, '📋 COPY ALL', command=self._copy_all,
            variant='ghost', width=100).pack(side='left', padx=2)
        Btn(act_row, '📌 PASTE',    command=self._paste,
            variant='ghost', width=80).pack(side='left', padx=2)
        Btn(act_row, '💾 SAVE TXT', command=lambda: self._save('txt'),
            variant='ghost', width=95).pack(side='left', padx=2)
        Btn(act_row, '📊 SAVE CSV', command=lambda: self._save('csv'),
            variant='ghost', width=95).pack(side='left', padx=2)
        Btn(act_row, '🗑 CLEAR',    command=self._clear_log,
            variant='ghost', width=70).pack(side='left', padx=2)

        # Find row
        find_row = ctk.CTkFrame(tlog_card, fg_color='transparent')
        find_row.pack(fill='x', padx=8, pady=(0,4))
        ctk.CTkLabel(find_row, text='Find:',
                     font=('DejaVu Sans Mono',9), text_color=C['mu']).pack(side='left')
        self._find_entry = ctk.CTkEntry(find_row, width=200,
                                         font=('DejaVu Sans Mono',9),
                                         fg_color=C['bg'], border_color=C['br'],
                                         text_color=C['tx'], height=26,
                                         placeholder_text='search...')
        self._find_entry.pack(side='left', padx=4)
        Btn(find_row, '↓ NEXT', command=self._find_next,
            variant='ghost', width=70).pack(side='left', padx=2)
        Btn(find_row, '↑ PREV', command=self._find_prev,
            variant='ghost', width=70).pack(side='left', padx=2)
        self._find_lbl = ctk.CTkLabel(find_row, text='',
                                       font=('DejaVu Sans Mono',8), text_color=C['mu'])
        self._find_lbl.pack(side='left', padx=6)

        # The log box — always normal state, fully interactive
        self._tlog = ctk.CTkTextbox(tlog_card, height=200,
                                     font=('DejaVu Sans Mono',10),
                                     fg_color=C['bg'],
                                     text_color=C['ok'],
                                     border_width=0,
                                     wrap='none')
        self._tlog.pack(fill='x', padx=8, pady=(0,8))
        self._tlog.configure(state='normal')
        # Keyboard shortcuts
        self._tlog.bind('<Control-a>', lambda e: self._select_all())
        self._tlog.bind('<Control-A>', lambda e: self._select_all())
        self._tlog.bind('<Control-c>', lambda e: self._copy_selection())
        self._tlog.bind('<Control-C>', lambda e: self._copy_selection())
        self._tlog.bind('<Control-v>', lambda e: self._paste())
        self._tlog.bind('<Control-V>', lambda e: self._paste())

    # ── PING LOOP ─────────────────────────────────────────────────

    def _start_ping(self):
        if self._ping_running:
            return
        self._ping_running = True
        self._ping_hist = []
        threading.Thread(target=self._ping_loop, daemon=True).start()

    def _ping_loop(self):
        while self._ping_running:
            ms = ping('1.1.1.1', 1)
            if ms is not None:
                self._ping_hist.append(ms)
                if len(self._ping_hist) > 80:
                    self._ping_hist = self._ping_hist[-80:]
                self.after(0, self._update_ping, ms)
            time.sleep(2)

    def _update_ping(self, ms):
        # Guard: widget may be destroyed if tab was switched
        try:
            if not self.winfo_exists():
                return
            if not hasattr(self, '_ping_val') or not self._ping_val.winfo_exists():
                return
        except Exception:
            return
        col = C['ok'] if ms < 30 else C['am'] if ms < 80 else C['wn']
        try:
            self._ping_val.configure(text=f'{ms:.0f} ms', text_color=col)
            self._ping_graph.push(ms)
            h = self._ping_hist
            if h:
                mn = min(h); av = sum(h)/len(h); mx = max(h)
                jit = max(h) - min(h)
                self._ping_min.configure(text=f'MIN: {mn:.0f}ms')
                self._ping_avg.configure(text=f'AVG: {av:.0f}ms')
                self._ping_max.configure(text=f'MAX: {mx:.0f}ms')
                self._ping_jitter.configure(text=f'JITTER: {jit:.0f}ms')
        except Exception:
            pass

    # ── SPEED TEST ────────────────────────────────────────────────

    def _run_speed(self):
        self._speed_btn.configure(state='disabled', text='TESTING...')
        self._speed_status.configure(text='Initialising speed test...',
                                      text_color=C['ac'])
        self._speed_grade.configure(text='')
        self._speed_prog.set(0)
        self._gauge_dl.set_value(0)
        self._gauge_ul.set_value(0)
        self._gauge_ping.set_value(0)
        threading.Thread(target=self._do_speed, daemon=True).start()

    def _do_speed(self):
        # Step 1: Ping
        self.after(0, lambda: (
            self._speed_status.configure(text='Testing latency...'),
            self._speed_prog.set(0.1)))
        ms = ping('1.1.1.1', 3)
        if ms:
            self.after(0, lambda: self._gauge_ping.set_value(ms))
        self.after(0, lambda: self._speed_prog.set(0.25))

        # Step 2: Download
        self.after(0, lambda: self._speed_status.configure(
            text='Testing download speed...'))
        dl = None
        try:
            import speedtest as _st
            st = _st.Speedtest()
            st.get_best_server()
            self.after(0, lambda: self._speed_prog.set(0.40))
            # Animate gauge while downloading
            def _anim_dl():
                if self._speed_prog.get() < 0.70:
                    self._gauge_dl.set_value(self._gauge_dl._val + 2, animate=False)
                    self.after(200, _anim_dl)
            self.after(0, _anim_dl)
            dl_raw = st.download()
            dl = dl_raw / 1e6
            self.after(0, lambda: self._gauge_dl.set_value(dl))
            self.after(0, lambda: self._speed_prog.set(0.65))

            # Step 3: Upload
            self.after(0, lambda: self._speed_status.configure(
                text='Testing upload speed...'))
            ul_raw = st.upload()
            ul = ul_raw / 1e6
            self.after(0, lambda: self._gauge_ul.set_value(ul))
            self.after(0, lambda: self._speed_prog.set(0.90))

        except Exception:
            # Fallback: HTTP download test
            try:
                import urllib.request, time as _t
                self.after(0, lambda: self._speed_status.configure(
                    text='Running HTTP speed test (fallback)...'))
                t0 = _t.time()
                urllib.request.urlretrieve(
                    'https://speed.cloudflare.com/__down?bytes=5000000',
                    '/dev/null')
                elapsed = _t.time() - t0
                dl = (5 * 8) / elapsed  # Mbps
                self.after(0, lambda: self._gauge_dl.set_value(dl))
                ul = dl * 0.3   # estimate
                self.after(0, lambda: self._gauge_ul.set_value(ul))
            except Exception:
                pass

        # Final
        grade = '—'
        if dl:
            grade = ('A+' if dl>100 else 'A' if dl>50 else 'B' if dl>25
                     else 'C' if dl>10 else 'D' if dl>5 else 'F')
        g_col = (C['ok']  if grade in ('A+','A') else
                 C['am']  if grade in ('B','C')  else C['wn'])

        def _done():
            self._speed_prog.set(1.0)
            self._speed_grade.configure(text=f'GRADE: {grade}', text_color=g_col)
            dl_s = f'{dl:.1f}' if dl else 'N/A'
            ms_s = f'{ms:.0f}ms' if ms else '—'
            self._speed_status.configure(
                text=f'↓{dl_s} Mbps  ◉{ms_s}  Grade:{grade}',
                text_color=C['ok'])
            self._speed_btn.configure(state='normal', text='↺ RETEST')
            self._tlog_line(f'[SPEED] ↓{dl_s}Mbps ◉{ms_s} Grade:{grade}')
        self.after(0, _done)

    # ── DATA LOAD ─────────────────────────────────────────────────

    def _load(self):
        ifaces  = get_network_interfaces()
        conns   = get_active_connections()
        local   = get_local_ip()
        ipinfo  = get_public_ip_info()
        self.after(0, self._render, ifaces, conns, local, ipinfo)

    def _render(self, ifaces, conns, local, ipinfo):
        # Interfaces
        for w in self._iface_frame.winfo_children(): w.destroy()
        for iface in ifaces[:6]:
            row = ctk.CTkFrame(self._iface_frame, fg_color=C['sf'],
                               border_color=C['br'], border_width=1,
                               corner_radius=6)
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text=iface['name'],
                         font=('DejaVu Sans Mono',10,'bold'),
                         text_color=C['ac']).pack(side='left', padx=10, pady=6)
            ctk.CTkLabel(row, text=iface['ip4'],
                         font=MONO_SM,
                         text_color=C['tx']).pack(side='left', padx=8)
            ctk.CTkLabel(row, text=iface.get('mac','—'),
                         font=('DejaVu Sans Mono',8),
                         text_color=C['mu']).pack(side='right', padx=10)

        # Public identity
        for w in self._pub_frame.winfo_children(): w.destroy()
        InfoGrid(self._pub_frame, [
            ('LOCAL IP',  local,                        C['am']),
            ('PUBLIC IP', ipinfo.get('ip','—'),          C['wn']),
            ('ISP',       ipinfo.get('org','—')),
            ('COUNTRY',   ipinfo.get('country_name','—')),
            ('CITY',      ipinfo.get('city','—')),
            ('TIMEZONE',  ipinfo.get('timezone','—')),
            ('ASN',       ipinfo.get('asn','—')),
            ('CURRENCY',  ipinfo.get('currency_name','—')),
            ('LATITUDE',  str(ipinfo.get('latitude','—'))),
        ], columns=3).pack(fill='x')

        # Connections
        for w in self._conn_frame.winfo_children(): w.destroy()
        if conns:
            hdr_row = ctk.CTkFrame(self._conn_frame, fg_color=C['s2'],
                                   corner_radius=4)
            hdr_row.pack(fill='x', pady=(0,2))
            for txt, w_ in [('LOCAL',120),('REMOTE',140),('PROCESS',160)]:
                ctk.CTkLabel(hdr_row, text=txt,
                             font=('DejaVu Sans Mono',8,'bold'),
                             text_color=C['mu'], width=w_).pack(side='left', padx=4)
            for c in conns[:10]:
                r = ctk.CTkFrame(self._conn_frame, fg_color=C['sf'],
                                 border_color=C['br'], border_width=1,
                                 corner_radius=4)
                r.pack(fill='x', pady=1)
                ctk.CTkLabel(r, text=c['local'],
                             font=('DejaVu Sans Mono',8), text_color=C['tx'], width=120
                             ).pack(side='left', padx=4, pady=4)
                ctk.CTkLabel(r, text=c['remote'],
                             font=('DejaVu Sans Mono',8), text_color=C['ac'], width=140
                             ).pack(side='left', padx=4)
                ctk.CTkLabel(r, text=c.get('process','—')[:24],
                             font=('DejaVu Sans Mono',8), text_color=C['mu'], width=160
                             ).pack(side='left', padx=4)
        else:
            ctk.CTkLabel(self._conn_frame,
                         text='No active connections found.',
                         font=MONO_SM, text_color=C['mu']).pack(pady=6)

    # ── TRAFFIC CAPTURE ───────────────────────────────────────────

    def _toggle_capture(self):
        if self._traffic_running:
            self._stop_capture()
        else:
            self._start_capture()

    def _start_capture(self):
        self._traffic_running = True
        self._cap_btn.configure(text='⏹ STOP', variant='danger')
        self._cap_status.configure(text='● CAPTURING TRAFFIC',
                                    text_color=C['ok'])
        threading.Thread(target=self._do_capture, daemon=True).start()

    def _stop_capture(self):
        self._traffic_running = False
        if self._traffic_proc:
            try:
                self._traffic_proc.terminate()
            except Exception:
                pass
            self._traffic_proc = None
        self._cap_btn.configure(text='▶ CAPTURE', variant='primary')
        self._cap_status.configure(text='● STOPPED', text_color=C['mu'])

    def _do_capture(self):
        import subprocess
        tcpdump = run_cmd(['which', 'tcpdump'])[0].strip()
        if tcpdump:
            self.after(0, lambda: self._tlog_line("ℹ Starting packet capture via tcpdump..."))
            cmd = f'sudo {tcpdump} -l -n -q -c 500 2>/dev/null'
        else:
            self.after(0, lambda: self._tlog_line("ℹ tcpdump not found. Monitoring active connections via 'ss' instead."))
            cmd = 'ss -tnp 2>/dev/null'

        try:
            self._traffic_proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True)
            
            count = 0
            for line in self._traffic_proc.stdout:
                if not self._traffic_running:
                    break
                self.after(0, self._tlog_line, line.rstrip())
                count += 1
            
            if count == 0:
                self.after(0, lambda: self._tlog_line("⚠ No traffic captured. Check your network permissions or interface."))
        except Exception as e:
            self.after(0, self._tlog_line, f'Capture error: {e}')
        finally:
            self._traffic_running = False
            self.after(0, lambda: (
                self._cap_btn.configure(text='▶ CAPTURE', variant='primary'),
                self._cap_status.configure(text='● CAPTURE ENDED',
                                            text_color=C['mu'])))

    def _tlog_line(self, msg):
        try:
            if not self.winfo_exists():
                return
            if not hasattr(self, '_tlog') or not self._tlog.winfo_exists():
                return
            ts = time.strftime('%H:%M:%S')
            self._tlog.insert('end', f'[{ts}] {msg}\n')
            self._tlog.see('end')
        except Exception:
            pass

    def _analyze(self):
        txt = self._tlog.get('1.0','end').strip()
        if not txt:
            return
        import re
        lines  = txt.splitlines()
        ips    = re.findall(r'(\d{1,3}(?:\.\d{1,3}){3})', txt)
        uniq   = set(ips)
        http   = sum(1 for l in lines if '.80 ' in l or '.443 ' in l)
        dns    = sum(1 for l in lines if '.53 ' in l)
        self._tlog_line('─── ANALYSIS ───')
        self._tlog_line(f'Lines: {len(lines)} | Unique IPs: {len(uniq)} | HTTP/S: {http} | DNS: {dns}')
        for ip in sorted(uniq)[:10]:
            self._tlog_line(f'  • {ip}')

    # ── CLIPBOARD OPS ─────────────────────────────────────────────

    def _select_all(self):
        self._tlog.tag_add('sel','1.0','end')
        return 'break'

    def _copy_selection(self):
        try:
            txt = self._tlog.get('sel.first','sel.last')
        except Exception:
            txt = self._tlog.get('1.0','end').strip()
        if txt:
            copy_to_clipboard(txt)
            n = len(txt.splitlines())
            self._cap_status.configure(text=f'● COPIED ({n} lines)',
                                        text_color=C['ok'])
        return 'break'

    def _copy_all(self):
        txt = self._tlog.get('1.0','end').strip()
        if not txt:
            self._cap_status.configure(text='● LOG IS EMPTY', text_color=C['mu'])
            return
        copy_to_clipboard(txt)
        self._cap_status.configure(
            text=f'● COPIED {len(txt.splitlines())} lines', text_color=C['ok'])

    def _paste(self):
        try:
            txt = self.winfo_toplevel().clipboard_get()
        except Exception:
            try:
                import subprocess as _sp
                txt = _sp.run('xclip -selection clipboard -o',
                              shell=True, capture_output=True, text=True,
                              timeout=2).stdout
            except Exception:
                txt = ''
        if txt:
            self._tlog.insert('end', txt)
            self._tlog.see('end')
            self._cap_status.configure(
                text=f'● PASTED ({len(txt)} chars)', text_color=C['ok'])
        return 'break'

    def _clear_log(self):
        self._tlog.delete('1.0','end')
        self._find_positions = []
        self._find_idx       = 0
        self._find_lbl.configure(text='')
        self._cap_status.configure(text='● LOG CLEARED', text_color=C['mu'])

    def _find_next(self): self._find(reverse=False)
    def _find_prev(self): self._find(reverse=True)

    def _find(self, reverse=False):
        query = self._find_entry.get().strip()
        if not query:
            return
        self._tlog.tag_remove('found','1.0','end')
        self._tlog.tag_configure('found',
                                  background=C['am'], foreground=C['bg'])
        # Highlight all
        total = 0
        idx = '1.0'
        while True:
            idx = self._tlog.search(query, idx, nocase=True, stopindex='end')
            if not idx:
                break
            end_ = f'{idx}+{len(query)}c'
            self._tlog.tag_add('found', idx, end_)
            total += 1
            idx = end_
        if total == 0:
            self._find_lbl.configure(text='Not found', text_color=C['wn'])
            return
        # Navigate
        search_from = getattr(self, '_find_from', '1.0')
        nxt = self._tlog.search(query, search_from, nocase=True,
                                 stopindex='1.0' if reverse else 'end',
                                 backwards=reverse)
        if not nxt:
            nxt = self._tlog.search(query,
                                     'end' if reverse else '1.0',
                                     nocase=True,
                                     stopindex='1.0' if reverse else 'end',
                                     backwards=reverse)
        if nxt:
            self._tlog.see(nxt)
            self._find_from = (f'{nxt}+{len(query)}c' if not reverse else nxt)
            self._find_lbl.configure(
                text=f'{total} match(es)', text_color=C['ok'])

    def _save(self, fmt):
        txt = self._tlog.get('1.0','end').strip()
        if not txt:
            self._cap_status.configure(text='● NOTHING TO SAVE', text_color=C['mu'])
            return
        import tkinter.filedialog as fd
        ts  = time.strftime('%Y%m%d_%H%M%S')
        ext = f'.{fmt}'
        path = fd.asksaveasfilename(
            defaultextension=ext,
            initialfile=f'traffic_{ts}{ext}',
            filetypes=[('Text log','*.txt'), ('CSV','*.csv'), ('All','*.*')])
        if not path:
            return
        if fmt == 'csv':
            buf = io.StringIO()
            w   = csv.writer(buf)
            w.writerow(['timestamp','raw_line'])
            import re as _re
            for ln in txt.splitlines():
                m = _re.match(r'\[(\d{2}:\d{2}:\d{2})\] (.*)', ln)
                w.writerow([m.group(1), m.group(2)] if m else ['', ln])
            with open(path,'w',newline='') as f:
                f.write(buf.getvalue())
        else:
            with open(path,'w') as f:
                f.write(f'# Mint Scan v8 — Traffic Log\n')
                f.write(f'# Saved: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
                f.write(f'# Lines: {len(txt.splitlines())}\n\n')
                f.write(txt)
        sz = os.path.getsize(path)
        self._cap_status.configure(
            text=f'● SAVED: {os.path.basename(path)} ({sz//1024+1}KB)',
            text_color=C['ok'])
