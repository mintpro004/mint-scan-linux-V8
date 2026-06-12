"""
Mint Scan v11.1 — Live Events
Real-time system event monitor with visual Map Radar and Security Alerts.
High-Performance restructuring with decoupled UI processing.
"""
import customtkinter as ctk
import threading, subprocess, time, os, math, random, re, queue, signal
from widgets import C, MONO_SM, Btn
from logger import get_logger
from utils import IS_WINDOWS, IS_LINUX

try:
    import select
except ImportError:
    select = None

log = get_logger('live_events')

# ── Security Alert Rules ────────────────────────────────────────
SECURITY_RULES = [
    (r'invalid user', '🚨 AUTH: INVALID USER ATTEMPT'),
    (r'failed password', '🚨 AUTH: BRUTE-FORCE DETECTED'),
    (r'authentication failure', '🚨 AUTH: FAILURE'),
    (r'denied', '🚫 ACCESS: PERMISSION DENIED'),
    (r'usb.*new high-speed', '📱 HW: NEW USB CONNECTED'),
    (r'segfault', '💥 KERNEL: SEGFAULT DETECTED'),
    (r'out of memory', '⚠️  SYS: OOM CRITICAL'),
]

class RadarCanvas(ctk.CTkCanvas):
    def __init__(self, parent, **kwargs):
        bg = kwargs.pop('bg', '#010d18')
        super().__init__(parent, bg=bg, highlightthickness=0, **kwargs)
        self._dots = []
        self._angle = 0
        self._active = False
        self._loop_running = False

    def set_active(self, state):
        self._active = state
        if state and not self._loop_running:
            self._draw_radar()

    def add_dot(self, color=None, size=3):
        if not self._active: return
        self._dots.append({
            'a': random.uniform(0, 2 * math.pi),
            'd': random.uniform(20, 95),
            'life': 1.0,
            'c': color or C['ac'],
            's': size
        })

    def _draw_radar(self):
        try:
            if not self.winfo_exists() or not self._active:
                self._loop_running = False
                return

            self._loop_running = True
            self.delete('all')
            w, h = self.winfo_width(), self.winfo_height()
            if w < 10: w, h = 240, 240
            cx, cy = w // 2, h // 2
            r_max = min(cx, cy) - 15

            # Grid Rings
            for r_factor in [1.0, 0.7, 0.4]:
                r = r_max * r_factor
                self.create_oval(cx-r, cy-r, cx+r, cy+r, outline='#0a3a4a', width=1)

            # Crosshair
            self.create_line(cx-r_max, cy, cx+r_max, cy, fill='#0a3a4a', width=1)
            self.create_line(cx, cy-r_max, cx, cy+r_max, fill='#0a3a4a', width=1)

            # Sweep with Trail
            self._angle = (self._angle + 0.1) % (2 * math.pi)
            for i in range(12):
                a = self._angle - (i * 0.05)
                intensity = int(100 * (1 - i/12))
                col = f'#00{intensity:02x}{intensity:02x}' if i > 0 else '#00ffe0'
                sx = cx + r_max * math.cos(a)
                sy = cy + r_max * math.sin(a)
                self.create_line(cx, cy, sx, sy, fill=col, width=2 if i==0 else 1)

            # Fading Dots
            new_dots = []
            for d in self._dots:
                dx = cx + (d['d'] * r_max / 100) * math.cos(d['a'])
                dy = cy + (d['d'] * r_max / 100) * math.sin(d['a'])
                if d['life'] > 0:
                    rad = max(1, d['s'] * d['life'])
                    self.create_oval(dx-rad, dy-rad, dx+rad, dy+rad, fill=d['c'], outline='')
                    d['life'] -= 0.02
                    new_dots.append(d)
            self._dots = new_dots

            self.after(50, self._draw_radar)
        except:
            self._loop_running = False

class LiveEventsScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False
        self._monitoring = False
        self._proc = None
        self._queue = queue.Queue()
        self._queue_job = None
        self.radar = None # Initialized during _build()

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        if self.radar:
            self.radar.set_active(True)
        self._start_monitor()
        self._start_queue_processing()

    def on_blur(self):
        if self.radar:
            self.radar.set_active(False)
        self._stop_monitor()
        if self._queue_job:
            self.after_cancel(self._queue_job)
            self._queue_job = None

    def _start_queue_processing(self):
        if self._queue_job:
            self.after_cancel(self._queue_job)
        self._process_queue()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text='📊  LIVE EVENT VISUALIZER',
                     font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)

        self.status_lbl = ctk.CTkLabel(hdr, text='SCANNING', font=MONO_SM, text_color=C['ok'])
        self.status_lbl.pack(side='right', padx=16)
        Btn(hdr, "⟳ RESTART", command=self._start_monitor, variant='ghost', width=80).pack(side='right', padx=4)
        Btn(hdr, "🎭 MOCK", command=self._start_mock_only, variant='ghost', width=80).pack(side='right', padx=4)
        Btn(hdr, "📋 COPY", command=self._copy_logs, variant='ghost', width=80).pack(side='right', padx=4)
        Btn(hdr, "🗑 CLEAR", command=self._clear, variant='ghost', width=80).pack(side='right', padx=4)

        main = ctk.CTkFrame(self, fg_color='transparent')
        main.pack(fill='both', expand=True)

        left = ctk.CTkFrame(main, fg_color='transparent')
        left.pack(side='left', fill='both', expand=True, padx=(10, 5), pady=10)

        self.log_box = ctk.CTkTextbox(left, font=('DejaVu Sans Mono', 10),
                                      fg_color='#010d18', text_color='#00ffe0',
                                      border_color=C['br'], border_width=1, corner_radius=6)
        self.log_box.pack(fill='both', expand=True)
        self.log_box.configure(state='disabled')
        self._setup_tags()

        right = ctk.CTkFrame(main, fg_color='transparent', width=300)
        right.pack(side='right', fill='y', padx=(5, 10), pady=10)
        right.pack_propagate(False)

        # Radar
        ctk.CTkLabel(right, text="SYSTEM RADAR", font=('DejaVu Sans Mono', 9, 'bold'), text_color=C['mu']).pack()
        self.radar = RadarCanvas(right, height=240)
        self.radar.pack(fill='x', pady=5)

        # Traffic density
        ctk.CTkLabel(right, text="EVENT DENSITY", font=('DejaVu Sans Mono', 9, 'bold'), text_color=C['mu']).pack(pady=(15, 0))
        self.density_bar = ctk.CTkProgressBar(right, height=12, progress_color=C['ac'], fg_color=C['br'])
        self.density_bar.pack(fill='x', pady=5)
        self.density_bar.set(0.1)

        self.traffic_box = ctk.CTkTextbox(right, font=('DejaVu Sans Mono', 9),
                                          fg_color=C['sf'], text_color=C['tx'], height=200)
        self.traffic_box.pack(fill='both', expand=True, pady=(15, 0))
        self.traffic_box.configure(state='disabled')

    def _setup_tags(self):
        self.log_box.tag_config('info', foreground=C['tx'])
        self.log_box.tag_config('ok', foreground=C['ok'])
        self.log_box.tag_config('am', foreground=C['am'])
        self.log_box.tag_config('crit', foreground='#ff4444')
        self.log_box.tag_config('net', foreground=C['ac'])

    def _start_monitor(self):
        self._stop_monitor()
        self._monitoring = True
        try:
            self._clear()
            self.log_box.configure(state='normal')
            self.log_box.insert('end', "🔍 CONNECTING TO REAL-TIME SYSTEM LOGS...\n", 'info')
            self.log_box.configure(state='disabled')
            self.status_lbl.configure(text='● SCANNING', text_color=C['ac'])
        except: pass
        
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        threading.Thread(target=self._traffic_loop, daemon=True).start()
        self._start_queue_processing()

    def _stop_monitor(self):
        self._monitoring = False
        self._stop_proc()
        try: self.status_lbl.configure(text='○ STOPPED', text_color=C['mu'])
        except: pass

    def _stop_proc(self):
        if self._proc:
            try:
                if not IS_WINDOWS and hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                else:
                    self._proc.terminate()
            except:
                try: self._proc.terminate()
                except: pass
            self._proc = None

    def _monitor_loop(self):
        if not self._monitoring: return
        log.info("Starting monitor loop...")
        
        # 1. Try system-level real-time logs (Linux only)
        found_cmd = None
        if IS_LINUX:
            system_candidates = [
                ["journalctl", "-f", "-n", "20"],
                ["tail", "-f", "/var/log/syslog"],
                ["tail", "-f", "/var/log/auth.log"],
            ]
            
            for cmd in system_candidates:
                if not self._monitoring: return
                try:
                    # Preexec_fn is used to set process group so we can kill children easily
                    self._proc = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, 
                                                stderr=subprocess.STDOUT, text=True, 
                                                preexec_fn=os.setsid if hasattr(os, 'setsid') else None, 
                                                bufsize=1)
                    if select:
                        r, _, _ = select.select([self._proc.stdout], [], [], 0.5)
                        if r or self._proc.poll() is None:
                            found_cmd = cmd
                            self._queue.put((f"✓ SYSTEM LOG ACTIVE: {cmd[0].upper()}\n\n", 'net'))
                            break
                    else:
                        time.sleep(0.5)
                        if self._proc.poll() is None:
                            found_cmd = cmd
                            self._queue.put((f"✓ SYSTEM LOG ACTIVE: {cmd[0].upper()}\n\n", 'net'))
                            break
                    self._stop_proc()
                except: self._stop_proc()

        # 2. Fallback to application's own log file (guaranteed readable)
        if not found_cmd:
            from logger import LOG_FILE
            if os.path.exists(LOG_FILE):
                log.info(f"Falling back to app log: {LOG_FILE}")
                if IS_WINDOWS:
                    self._queue.put(("✓ APPLICATION LOG ACTIVE: Security & App events streaming.\n\n", 'ok'))
                    try:
                        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
                            f.seek(0, 2) # Go to end
                            while self._monitoring:
                                line = f.readline()
                                if line:
                                    self._queue.put((line, None))
                                else:
                                    time.sleep(0.5)
                    except Exception as e:
                        log.error(f"App log read error: {e}")
                    return
                else:
                    found_cmd = ["tail", "-f", LOG_FILE]
                    self._proc = subprocess.Popen(found_cmd, shell=False, stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT, text=True,
                                                preexec_fn=os.setsid if hasattr(os, 'setsid') else None, 
                                                bufsize=1)
                    self._queue.put(("✓ APPLICATION LOG ACTIVE: Security & App events streaming.\n\n", 'ok'))

        # 3. Final fallback to mock if everything else fails
        if not found_cmd:
            log.warning("No real logs accessible. Mock stream active.")
            self._queue.put(("⚠️  LOG ACCESS RESTRICTED: Using internal event stream.\n", 'crit'))
            while self._monitoring:
                time.sleep(random.uniform(1.0, 3.0))
                if not self._monitoring: break
                mock_msg = random.choice([
                    "AUDIT: System heartbeat OK",
                    "NET: Incoming packet from 127.0.0.1",
                    "SYS: Background scan active",
                    "KERN: Resource allocation peak",
                    "FIREWALL: Blocked incoming connection",
                ])
                self._queue.put((f"[{time.strftime('%H:%M:%S')}] {mock_msg}\n", 'info'))
            return

        try:
            while self._monitoring and self._proc and self._proc.stdout:
                if select:
                    r, _, _ = select.select([self._proc.stdout], [], [], 0.5)
                    if r:
                        line = self._proc.stdout.readline()
                        if not line:
                            if self._proc.poll() is not None: break
                            continue
                        self._queue.put((line, None))
                    else:
                        if self._proc.poll() is not None: break
                else:
                    line = self._proc.stdout.readline()
                    if line:
                        self._queue.put((line, None))
                    elif self._proc.poll() is not None:
                        break
                    else:
                        time.sleep(0.1)
        except Exception as e:
            log.error(f"Monitor loop error: {e}")
        finally: 
            self._stop_monitor()

    def _process_queue(self):
        if not self.winfo_exists(): return
        try:
            while True:
                msg, tag = self._queue.get_nowait()
                self._append_log(msg, tag)
                # Parse for radar hits
                if self.radar:
                    if any(r in msg.lower() for r in ['auth','fail','denied','alert','warn']):
                        self.radar.add_dot('#ff4444', size=4)
                    else:
                        self.radar.add_dot(C['ac'], size=2)
        except queue.Empty:
            pass
        if self._monitoring:
            self._queue_job = self.after(100, self._process_queue)

    def _append_log(self, text, tag=None):
        try:
            self.log_box.configure(state='normal')
            if not tag:
                # Basic rule engine
                for pattern, alert in SECURITY_RULES:
                    if re.search(pattern, text, re.I):
                        self.log_box.insert('end', f"[{time.strftime('%H:%M:%S')}] {alert}\n", 'crit')
                        break
            self.log_box.insert('end', text, tag or 'info')
            self.log_box.see('end')
            self.log_box.configure(state='disabled')
        except: pass

    def _traffic_loop(self):
        import psutil
        while self._monitoring:
            try:
                # Real traffic density from net_connections
                conns = psutil.net_connections(kind='inet')
                count = len(conns)
                val = (count / 100)
                self.after(0, lambda v=val: self.density_bar.set(min(1.0, v)))
                
                # Sample connections for the traffic box
                c_out = ""
                for c in conns[:15]:
                    laddr = f"{c.laddr.ip}:{c.laddr.port}"
                    raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "-"
                    c_out += f"{c.status:<12} {laddr:<25} {raddr}\n"
                
                self.after(0, self._update_traffic, c_out)
            except Exception as e:
                log.error(f"Traffic loop error: {e}")
            time.sleep(3)

    def _update_traffic(self, text):
        try:
            self.traffic_box.configure(state='normal')
            self.traffic_box.delete('1.0', 'end')
            self.traffic_box.insert('end', text)
            self.traffic_box.configure(state='disabled')
        except: pass

    def _start_mock_only(self):
        self._stop_monitor()
        self._monitoring = True
        self._clear()
        self._queue.put(("🧪 DEBUG: Starting forced mock stream...\n", 'info'))
        threading.Thread(target=self._mock_loop, daemon=True).start()
        self._start_queue_processing()

    def _mock_loop(self):
        while self._monitoring:
            time.sleep(random.uniform(0.5, 2.0))
            if not self._monitoring: break
            msg = random.choice([
                "DEBUG: Event loop heart-beat OK",
                "DEBUG: Queue processing active",
                "DEBUG: Radar sweep nominal",
                "DEBUG: Simulated security event",
            ])
            self._queue.put((f"[{time.strftime('%H:%M:%S')}] {msg}\n", 'info'))

    def _clear(self):
        try:
            self.log_box.configure(state='normal')
            self.log_box.delete('1.0', 'end')
            self.log_box.configure(state='disabled')
        except: pass

    def _copy_logs(self):
        try:
            txt = self.log_box.get('1.0', 'end')
            self.winfo_toplevel().clipboard_clear()
            self.winfo_toplevel().clipboard_append(txt)
        except: pass
