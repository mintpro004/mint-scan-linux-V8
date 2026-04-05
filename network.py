"""
Network Screen v8 — Speed test, ping graph, connections, Traffic Log with full clipboard ops
v8 NEW: Copy All, Copy Selection (Ctrl+C), Paste (Ctrl+V/PASTE button), Select All (Ctrl+A),
        Clear, Find/Search (next/prev, highlights all), Save TXT, Save CSV, live editable log
"""
from widgets import C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, LiveBadge
import tkinter as tk
import customtkinter as ctk
import threading, time, csv, os, subprocess, datetime
from utils import get_network_interfaces, get_public_ip_info, get_local_ip, get_active_connections, ping, run_cmd


class NetworkScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False
        self._ping_history = []
        self._ping_running = False
        self._traffic_lines = []
        self._find_positions = []
        self._find_idx = 0
        self._traffic_running = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._start_ping_loop()
        threading.Thread(target=self._load, daemon=True).start()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="📡  NETWORK", font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        self.speed_btn = Btn(hdr, "▶  SPEED TEST", command=self._run_speed, width=130)
        self.speed_btn.pack(side='right', padx=12, pady=6)
        self.refresh_btn = Btn(hdr, "↺  REFRESH",
                               command=lambda: threading.Thread(target=self._load, daemon=True).start(),
                               variant='ghost', width=100)
        self.refresh_btn.pack(side='right', padx=4, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # 01 ping graph
        SectionHeader(body, '01', 'LIVE RTT LATENCY').pack(fill='x', padx=14, pady=(14,4))
        ping_card = Card(body)
        ping_card.pack(fill='x', padx=14, pady=(0,6))
        top_row = ctk.CTkFrame(ping_card, fg_color='transparent')
        top_row.pack(fill='x', padx=8, pady=(8,0))
        LiveBadge(top_row).pack(side='left')
        self.ping_val = ctk.CTkLabel(top_row, text="—ms", font=('Courier',13,'bold'), text_color=C['ok'])
        self.ping_val.pack(side='right')
        self.ping_canvas = tk.Canvas(ping_card, height=80, bg=C['bg'], highlightthickness=0)
        self.ping_canvas.pack(fill='x', padx=8, pady=4)
        stats_row = ctk.CTkFrame(ping_card, fg_color='transparent')
        stats_row.pack(fill='x', padx=8, pady=(0,8))
        self.ping_min = ctk.CTkLabel(stats_row, text="MIN: —", font=('Courier',8), text_color=C['mu'])
        self.ping_min.pack(side='left', padx=8)
        self.ping_avg = ctk.CTkLabel(stats_row, text="AVG: —", font=('Courier',8), text_color=C['mu'])
        self.ping_avg.pack(side='left', padx=8)
        self.ping_max = ctk.CTkLabel(stats_row, text="MAX: —", font=('Courier',8), text_color=C['mu'])
        self.ping_max.pack(side='left', padx=8)

        # 02 speed test
        SectionHeader(body, '02', 'SPEED TEST').pack(fill='x', padx=14, pady=(10,4))
        speed_card = Card(body)
        speed_card.pack(fill='x', padx=14, pady=(0,6))
        spd_row = ctk.CTkFrame(speed_card, fg_color='transparent')
        spd_row.pack(fill='x', padx=8, pady=8)
        for attr, label in [('spd_dl','▼ DOWNLOAD'),('spd_ul','▲ UPLOAD'),
                             ('spd_ping','◉ PING'),('spd_grade','★ GRADE')]:
            box = ctk.CTkFrame(spd_row, fg_color=C['s2'], border_color=C['br'], border_width=1, corner_radius=6)
            box.pack(side='left', expand=True, fill='x', padx=4)
            val = ctk.CTkLabel(box, text='—', font=('Courier',22,'bold'), text_color=C['ac'])
            val.pack(pady=(8,0))
            ctk.CTkLabel(box, text=label, font=('Courier',7), text_color=C['mu']).pack(pady=(0,8))
            setattr(self, attr, val)

        # 03 interfaces
        SectionHeader(body, '03', 'NETWORK INTERFACES').pack(fill='x', padx=14, pady=(10,4))
        self.iface_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.iface_frame.pack(fill='x', padx=14, pady=(0,6))

        # 04 public IP
        SectionHeader(body, '04', 'PUBLIC IDENTITY').pack(fill='x', padx=14, pady=(10,4))
        self.pub_grid_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.pub_grid_frame.pack(fill='x', padx=14, pady=(0,6))

        # 05 connections
        SectionHeader(body, '05', 'ACTIVE CONNECTIONS').pack(fill='x', padx=14, pady=(10,4))
        self.conn_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.conn_frame.pack(fill='x', padx=14, pady=(0,6))

        # ════════════════════════════════════════════════════
        # 06 TRAFFIC LOG — v8 full clipboard & file ops
        # ════════════════════════════════════════════════════
        SectionHeader(body, '06', 'TRAFFIC LOG  [v8 — CLIPBOARD & FILE OPS]').pack(
            fill='x', padx=14, pady=(10,4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0,14))

        # toolbar row 1: action buttons
        tb1 = ctk.CTkFrame(log_card, fg_color='transparent')
        tb1.pack(fill='x', padx=6, pady=(6,2))

        def _tbtn(txt, cmd, v='ghost'):
            b = ctk.CTkButton(tb1, text=txt, command=cmd, height=26,
                              fg_color=C['s2'] if v=='ghost' else C['ac'],
                              text_color=C['tx'] if v=='ghost' else '#040e1a',
                              hover_color=C['s3'] if v=='ghost' else '#fff',
                              font=('Courier',9), corner_radius=5, width=0)
            b.pack(side='left', padx=2)
            return b

        _tbtn("📋 COPY ALL",   self._log_copy_all)
        _tbtn("📌 PASTE",      self._log_paste)
        _tbtn("☑ SELECT ALL", self._log_select_all)
        _tbtn("🗑 CLEAR",      self._log_clear)
        _tbtn("💾 SAVE TXT",   self._log_save_txt)
        _tbtn("📊 SAVE CSV",   self._log_save_csv)
        self.capture_btn = ctk.CTkButton(
            tb1, text="▶ CAPTURE", command=self._toggle_capture,
            height=26, fg_color=C.get('ok','#06d6a0'), text_color='#040e1a',
            hover_color='#fff', font=('Courier',9,'bold'), corner_radius=5, width=0)
        self.capture_btn.pack(side='right', padx=2)

        # toolbar row 2: search
        tb2 = ctk.CTkFrame(log_card, fg_color='transparent')
        tb2.pack(fill='x', padx=6, pady=(0,4))
        ctk.CTkLabel(tb2, text="🔍", font=('Courier',11), text_color=C['mu']).pack(side='left', padx=4)
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(tb2, textvariable=self.search_var,
                                         placeholder_text="Search log...",
                                         width=220, height=26,
                                         fg_color=C['s2'], border_color=C['br'],
                                         text_color=C['tx'])
        self.search_entry.pack(side='left', padx=2)
        self.search_var.trace_add('write', lambda *a: self._find_highlight())

        ctk.CTkButton(tb2, text="↓ NEXT", command=self._find_next, height=24,
                      fg_color=C['s2'], text_color=C['tx'], hover_color=C['s3'],
                      font=('Courier',8), corner_radius=4, width=60).pack(side='left', padx=2)
        ctk.CTkButton(tb2, text="↑ PREV", command=self._find_prev, height=24,
                      fg_color=C['s2'], text_color=C['tx'], hover_color=C['s3'],
                      font=('Courier',8), corner_radius=4, width=60).pack(side='left', padx=2)
        self.find_count_lbl = ctk.CTkLabel(tb2, text="", font=('Courier',8), text_color=C['mu'])
        self.find_count_lbl.pack(side='left', padx=6)

        # The log textbox — state='normal' always (v8 fix)
        self.log_box = tk.Text(
            log_card, height=16,
            bg=C['bg'], fg=C['tx'],
            font=('Courier',9),
            insertbackground=C['ac'],
            selectbackground=C['ac'],
            selectforeground='#040e1a',
            relief='flat', padx=8, pady=6,
            wrap='none',
            state='normal',   # always editable
            undo=True,
        )
        self.log_box.pack(fill='both', expand=True, padx=6, pady=(0,4))

        # scrollbars
        sb_y = ctk.CTkScrollbar(log_card, command=self.log_box.yview)
        sb_y.pack(side='right', fill='y')
        sb_x = ctk.CTkScrollbar(log_card, orientation='horizontal', command=self.log_box.xview)
        sb_x.pack(side='bottom', fill='x')
        self.log_box.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        # search highlight tags
        self.log_box.tag_config('highlight', background='#ffb830', foreground='#040e1a')
        self.log_box.tag_config('current',   background=C['ac'],   foreground='#040e1a')

        # keyboard shortcuts
        self.log_box.bind('<Control-c>', lambda e: (self._log_copy_selection(), 'break'))
        self.log_box.bind('<Control-v>', lambda e: (self._log_paste(),           'break'))
        self.log_box.bind('<Control-a>', lambda e: (self._log_select_all(),      'break'))

        # seed log
        self._tlog(f"[MINT SCAN v8] Traffic Log  —  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._tlog("[v8] COPY ALL · Ctrl+C selection · Ctrl+V paste · Ctrl+A select all · CLEAR")
        self._tlog("[v8] SAVE TXT (timestamped)  ·  SAVE CSV (Excel/LibreOffice compatible)")
        self._tlog("[v8] Search: type above → ↓ next / ↑ prev — all matches highlighted")
        self._tlog("─" * 72)

    # ─── Traffic Log operations ────────────────────────────────

    def _tlog(self, msg):
        ts   = datetime.datetime.now().strftime('%H:%M:%S')
        line = f"[{ts}] {msg}\n"
        self._traffic_lines.append({'ts': ts, 'msg': msg})
        if hasattr(self, 'log_box'):
            self.log_box.insert('end', line)
            self.log_box.see('end')

    def _log_copy_all(self):
        content = self.log_box.get('1.0', 'end')
        self._to_clipboard(content)
        self._tlog("[v8] ✓ Entire log copied to clipboard")

    def _log_copy_selection(self):
        try:
            sel = self.log_box.get('sel.first', 'sel.last')
            self._to_clipboard(sel)
        except tk.TclError:
            pass

    def _log_paste(self):
        try:
            text = self.log_box.clipboard_get()
            if text:
                self.log_box.insert('insert', text)
        except tk.TclError:
            self._tlog("[v8] ✗ Clipboard empty or unavailable")

    def _log_select_all(self):
        self.log_box.tag_add('sel', '1.0', 'end')
        self.log_box.mark_set('insert', 'end')

    def _log_clear(self):
        self.log_box.delete('1.0', 'end')
        self._traffic_lines.clear()
        self._find_positions.clear()
        self.find_count_lbl.configure(text="")
        self._tlog("[v8] Log cleared")

    def _log_save_txt(self):
        ts   = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.expanduser(f'~/mint_scan_traffic_{ts}.txt')
        hdr  = (f"# Mint Scan v8 — Traffic Log Export\n"
                f"# {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  {len(self._traffic_lines)} lines\n"
                f"# {'─'*60}\n\n")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(hdr + self.log_box.get('1.0', 'end'))
            self._tlog(f"[v8] ✓ Saved TXT → {path}")
        except Exception as e:
            self._tlog(f"[v8] ✗ Save failed: {e}")

    def _log_save_csv(self):
        ts   = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.expanduser(f'~/mint_scan_traffic_{ts}.csv')
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['Timestamp', 'Message', 'Export_Time'])
                exp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for e in self._traffic_lines:
                    w.writerow([e.get('ts',''), e.get('msg',''), exp])
            self._tlog(f"[v8] ✓ Saved CSV → {path}  ({len(self._traffic_lines)} rows)")
        except Exception as e:
            self._tlog(f"[v8] ✗ CSV save failed: {e}")

    def _find_highlight(self):
        self.log_box.tag_remove('highlight', '1.0', 'end')
        self.log_box.tag_remove('current',   '1.0', 'end')
        self._find_positions = []
        self._find_idx = 0
        term = self.search_var.get()
        if not term:
            self.find_count_lbl.configure(text="")
            return
        start = '1.0'
        while True:
            pos = self.log_box.search(term, start, stopindex='end', nocase=True)
            if not pos: break
            end = f"{pos}+{len(term)}c"
            self.log_box.tag_add('highlight', pos, end)
            self._find_positions.append((pos, end))
            start = end
        n = len(self._find_positions)
        self.find_count_lbl.configure(text=f"{n} match{'es' if n!=1 else ''}")
        if self._find_positions:
            self._jump_to_find(0)

    def _find_next(self):
        if not self._find_positions: return
        self._find_idx = (self._find_idx + 1) % len(self._find_positions)
        self._jump_to_find(self._find_idx)

    def _find_prev(self):
        if not self._find_positions: return
        self._find_idx = (self._find_idx - 1) % len(self._find_positions)
        self._jump_to_find(self._find_idx)

    def _jump_to_find(self, idx):
        self.log_box.tag_remove('current', '1.0', 'end')
        pos, end = self._find_positions[idx]
        self.log_box.tag_add('current', pos, end)
        self.log_box.see(pos)
        self.find_count_lbl.configure(text=f"{idx+1}/{len(self._find_positions)}")

    def _to_clipboard(self, text):
        try:
            self.log_box.clipboard_clear()
            self.log_box.clipboard_append(text)
            self.log_box.update()
            return
        except Exception:
            pass
        try:
            p = subprocess.Popen(['xclip','-selection','clipboard'], stdin=subprocess.PIPE)
            p.communicate(text.encode('utf-8'))
        except Exception:
            pass

    def _toggle_capture(self):
        if self._traffic_running:
            self._traffic_running = False
            self.capture_btn.configure(text="▶ CAPTURE")
            self._tlog("[v8] ◼ Live capture stopped")
        else:
            self._traffic_running = True
            self.capture_btn.configure(text="◼ STOP")
            self._tlog("[v8] ▶ Live capture started")
            threading.Thread(target=self._capture_worker, daemon=True).start()

    def _capture_worker(self):
        seen = set()
        while self._traffic_running:
            try:
                for c in get_active_connections():
                    key = f"{c.get('local','')}|{c.get('remote','')}"
                    r   = c.get('remote','')
                    if key not in seen and r and r not in ('0.0.0.0:*','*:*',''):
                        seen.add(key)
                        self.after(0, self._tlog,
                            f"[CONN] {c.get('local','?'):22s} → {r:22s}  {c.get('process','')}")
            except Exception:
                pass
            time.sleep(3)

    # ─── Data load & render ────────────────────────────────────

    def _load(self):
        ifaces = get_network_interfaces()
        ipinfo = get_public_ip_info()
        conns  = get_active_connections()
        self.after(0, self._render, ifaces, ipinfo, conns)

    def _render(self, ifaces, ipinfo, conns):
        if not hasattr(self, 'iface_frame'): return
        for w in self.iface_frame.winfo_children(): w.destroy()
        items = []
        for iface in ifaces[:8]:
            items.extend([(f"{iface['name']} IPv4", iface['ip4'], C['am']),
                          (f"{iface['name']} MAC",  iface['mac'])])
        InfoGrid(self.iface_frame, items, columns=4).pack(fill='x')

        if not hasattr(self, 'pub_grid_frame'): return
        for w in self.pub_grid_frame.winfo_children(): w.destroy()
        InfoGrid(self.pub_grid_frame, [
            ('PUBLIC IP', ipinfo.get('ip','—'),           C['wn']),
            ('ISP',       ipinfo.get('org','—')),
            ('COUNTRY',   ipinfo.get('country_name','—')),
            ('CITY',      ipinfo.get('city','—')),
            ('REGION',    ipinfo.get('region','—')),
            ('TIMEZONE',  ipinfo.get('timezone','—')),
            ('ASN',       ipinfo.get('asn','—')),
            ('LATITUDE',  str(ipinfo.get('latitude','—'))),
            ('LONGITUDE', str(ipinfo.get('longitude','—'))),
        ], columns=3).pack(fill='x')

        for w in self.conn_frame.winfo_children(): w.destroy()
        if conns:
            for conn in conns[:15]:
                row = ctk.CTkFrame(self.conn_frame, fg_color=C['sf'],
                                   border_color=C['br'], border_width=1, corner_radius=6)
                row.pack(fill='x', pady=2)
                ctk.CTkLabel(row, text=conn['local'],   font=MONO_SM, text_color=C['ac']).pack(side='left',  padx=8, pady=6)
                ctk.CTkLabel(row, text='→',             font=MONO_SM, text_color=C['mu']).pack(side='left')
                ctk.CTkLabel(row, text=conn['remote'],  font=MONO_SM, text_color=C['am']).pack(side='left',  padx=8)
                ctk.CTkLabel(row, text=conn['process'], font=('Courier',8), text_color=C['mu']).pack(side='right', padx=8)
        else:
            ctk.CTkLabel(self.conn_frame, text="No active connections found",
                         font=MONO_SM, text_color=C['mu']).pack(pady=8)

        if hasattr(self, 'log_box'):
            self._tlog(f"[REFRESH] Ifaces:{len(ifaces)}  Conns:{len(conns)}  IP:{ipinfo.get('ip','—')}")

    # ─── Ping graph ────────────────────────────────────────────

    def _start_ping_loop(self):
        if self._ping_running: return
        self._ping_running = True
        threading.Thread(target=self._ping_worker, daemon=True).start()

    def _ping_worker(self):
        while self._ping_running:
            ms = ping('1.1.1.1', 1)
            if ms is not None:
                self._ping_history = self._ping_history[-49:] + [ms]
                self.after(0, self._update_ping_graph)
            time.sleep(2)

    def _update_ping_graph(self):
        data = self._ping_history
        if not data: return
        last = data[-1]
        col  = C['ok'] if last < 80 else C['am'] if last < 200 else C['wn']
        self.ping_val.configure(text=f"{last:.0f}ms", text_color=col)
        mn, mx, avg = min(data), max(data), sum(data)/len(data)
        self.ping_min.configure(text=f"MIN: {mn:.0f}ms")
        self.ping_avg.configure(text=f"AVG: {avg:.0f}ms")
        self.ping_max.configure(text=f"MAX: {mx:.0f}ms")
        c = self.ping_canvas
        c.delete('all')
        w = c.winfo_width() or 600
        h, seg, peak = 80, w/max(len(data)-1,1), max(data) or 1
        for frac in [0.25,0.5,0.75]:
            y = h - frac*h
            c.create_line(0,y,w,y,fill=C['br'],dash=(2,4))
        pts = []
        for i,v in enumerate(data): pts.extend([i*seg, h-(v/peak)*h*0.9])
        if len(pts)>=4: c.create_line(*pts,fill=col,width=2,smooth=True)
        lx = (len(data)-1)*seg
        ly = h-(data[-1]/peak)*h*0.9
        c.create_oval(lx-4,ly-4,lx+4,ly+4,fill=col,outline='')

    # ─── Speed test ────────────────────────────────────────────

    def _run_speed(self):
        self.speed_btn.configure(state='disabled', text='TESTING...')
        for a in ['spd_dl','spd_ul','spd_ping','spd_grade']:
            getattr(self,a).configure(text='—', text_color=C['mu'])
        self._tlog("[SPEED] Starting speed test...")
        threading.Thread(target=self._do_speed, daemon=True).start()

    def _do_speed(self):
        ms = ping('1.1.1.1', 3)
        self.after(0, lambda: self.spd_ping.configure(
            text=f"{ms:.0f}" if ms else 'ERR', text_color=C['am'] if ms else C['wn']))
        dl = ul = None
        try:
            import speedtest
            st = speedtest.Speedtest(); st.get_best_server()
            dl = st.download()/1e6; ul = st.upload()/1e6
        except Exception:
            try:
                import urllib.request, time as _t
                t0 = _t.time()
                urllib.request.urlretrieve('http://speedtest.ftp.otenet.gr/files/test1Mb.db','/dev/null')
                dl = 8/(_t.time()-t0)
            except Exception: pass
        grade = '—'
        if dl: grade = 'A+' if dl>50 else 'A' if dl>25 else 'B' if dl>10 else 'C' if dl>5 else 'D'
        self.after(0, lambda: (
            self.spd_dl.configure(   text=f"{dl:.1f}" if dl else 'N/A', text_color=C['ac'] if dl else C['wn']),
            self.spd_ul.configure(   text=f"{ul:.1f}" if ul else 'N/A', text_color=C['bl'] if ul else C['wn']),
            self.spd_grade.configure(text=grade, text_color=C['ok'] if grade in ('A+','A') else C['am']),
            self.speed_btn.configure(state='normal', text='↺  RETEST'),
        ))
        self._tlog(f"[SPEED] ↓{dl:.1f}Mbps ↑{ul:.1f}Mbps Grade:{grade}" if dl else "[SPEED] Failed — no internet?")
