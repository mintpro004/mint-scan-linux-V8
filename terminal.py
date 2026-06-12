"""
Mint Scan v11.1 — Ultra Professional Terminal
World-class features for high-stakes tasks:
- Dynamic Zoom (A+ / A-)
- Advanced Copy/Paste & Search in output
- Working Directory & User context
- Intelligent Tab-Completion
- Integrated Command History
"""
import os, sys, threading, subprocess, select, time, re, signal, glob
import tkinter as tk
import customtkinter as ctk
from widgets import C, MONO, MONO_SM, Btn, ScrollableFrame, Card, FONT
from logger import get_logger
from database import db
from utils import IS_WINDOWS, IS_LINUX

log = get_logger('terminal')

TERMINAL_THEMES = {
    'Matrix':    {'bg': '#000000', 'fg': '#00ff41', 'ac': '#003300', 'p': '#00ff41'},
    'Cyber':     {'bg': '#050505', 'fg': '#00ffe0', 'ac': '#1a0033', 'p': '#ff00ff'},
    'Retro':     {'bg': '#1a0505', 'fg': '#ffb830', 'ac': '#330a0a', 'p': '#ff4444'},
    'Monokai':   {'bg': '#272822', 'fg': '#f8f8f2', 'ac': '#3e3d32', 'p': '#a6e22e'},
}

class TerminalScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False
        self._proc = None
        self._running = False
        self._history = []
        self._hist_idx = -1
        self._font_size = 11
        self._theme = 'Matrix'
        self._lock = threading.Lock()
        
        # System Context
        import socket
        try:
            if IS_WINDOWS:
                self._user = os.environ.get('USERNAME', 'user')
            else:
                self._user = os.getlogin() if hasattr(os, 'getlogin') else "user"
            self._host = socket.gethostname()
        except:
            self._user = "user"
            self._host = "mint-scan"
        self._cwd = os.getcwd()

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._input.focus_set()
        self._load_snippets()

    def _load_snippets(self):
        for w in self._snip_scroll.winfo_children(): w.destroy()

        cursor = db.conn.cursor()
        cursor.execute("SELECT id, name, command FROM terminal_snippets")
        rows = cursor.fetchall()

        if not rows:
            ctk.CTkLabel(self._snip_scroll, text="No snippets yet.", font=MONO_SM, text_color=C['mu']).pack(pady=20)
            return

        for row in rows:
            sc = Card(self._snip_scroll, fg_color=C['bg'])
            sc.pack(fill='x', pady=2, padx=4)
            Btn(sc, row['name'], command=lambda c=row['command']: self._run_snippet(c), 
                variant='ghost', width=150, height=28, font=(FONT, 8)).pack(padx=2, pady=2)

    def _save_snippet(self):
        cmd = self._input.get().strip()
        if not cmd:
            self._write_to_ui("Type a command first to save it as a snippet.\n")
            return

        dialog = ctk.CTkInputDialog(text="Enter name for this snippet:", title="Save Snippet")
        name = dialog.get_input()
        if name:
            cursor = db.conn.cursor()
            cursor.execute("INSERT INTO terminal_snippets (name, command) VALUES (?, ?)", (name, cmd))
            db.conn.commit()
            self._load_snippets()

    def _run_snippet(self, cmd):
        self._input.delete(0, 'end')
        self._input.insert(0, cmd)
        self._execute()

    def _build(self):
        # ── Header ─────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=45, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        
        ctk.CTkLabel(hdr, text='>_ TERMINAL v11.1 PRO',
                     font=('DejaVu Sans Mono', 11, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        
        self._status_lbl = ctk.CTkLabel(hdr, text='READY', font=MONO_SM, text_color=C['ok'])
        self._status_lbl.pack(side='left', padx=4)

        # Actions
        Btn(hdr, '⏹ KILL',   command=self._kill_proc, variant='danger', width=60, height=26).pack(side='right', padx=4)
        Btn(hdr, '📋 COPY ALL', command=self._copy_all, variant='ghost', width=80, height=26).pack(side='right', padx=4)
        Btn(hdr, '🗑 CLEAR',   command=self._clear_output, variant='ghost', width=70, height=26).pack(side='right', padx=4)

        # Theme Selector
        self._theme_var = tk.StringVar(value=self._theme)
        ctk.CTkOptionMenu(hdr, values=list(TERMINAL_THEMES.keys()),
                          variable=self._theme_var, command=self._apply_theme,
                          width=100, height=26, font=MONO_SM,
                          fg_color=C['br'], button_color=C['br2'],
                          dropdown_fg_color=C['sf']).pack(side='right', padx=8)

        # Zoom
        zoom_frame = ctk.CTkFrame(hdr, fg_color='transparent')
        zoom_frame.pack(side='right', padx=5)
        Btn(zoom_frame, "A-", command=self._zoom_out, variant='ghost', width=26, height=26).pack(side='left', padx=1)
        self._zoom_lbl = ctk.CTkLabel(zoom_frame, text="100%", font=MONO_SM, width=35)
        self._zoom_lbl.pack(side='left')
        Btn(zoom_frame, "A+", command=self._zoom_in, variant='ghost', width=26, height=26).pack(side='left', padx=1)

        # ── Find Bar (Search) ──────────────────────────────────
        self._find_frame = ctk.CTkFrame(self, fg_color=C['s2'], height=35, corner_radius=0)
        self._find_frame.pack(fill='x')
        ctk.CTkLabel(self._find_frame, text=" FIND:", font=MONO_SM, text_color=C['mu']).pack(side='left', padx=(10,5))
        self._find_entry = ctk.CTkEntry(self._find_frame, height=25, width=200, font=MONO_SM, border_width=0, fg_color=C['bg'])
        self._find_entry.pack(side='left', pady=5)
        self._find_entry.bind('<Return>', lambda e: self._find_text())
        Btn(self._find_frame, "NEXT", command=self._find_text, variant='ghost', width=50, height=25).pack(side='left', padx=5)
        self._find_res_lbl = ctk.CTkLabel(self._find_frame, text="", font=MONO_SM, text_color=C['ac'])
        self._find_res_lbl.pack(side='left', padx=10)

        # ── Main Content Area ──────────────────────────────────
        main_row = ctk.CTkFrame(self, fg_color='transparent')
        main_row.pack(fill='both', expand=True)

        # ── Output Area ────────────────────────────────────────
        self._output = ctk.CTkTextbox(main_row, font=('DejaVu Sans Mono', self._font_size),
                                      fg_color=TERMINAL_THEMES[self._theme]['bg'],
                                      text_color=TERMINAL_THEMES[self._theme]['fg'],
                                      border_width=0, corner_radius=0, undo=True)
        self._output.pack(side='left', fill='both', expand=True, padx=0, pady=0)
        self._output.configure(state='disabled')
        
        # ── Snippets Sidebar ───────────────────────────────────
        self._side = ctk.CTkFrame(main_row, width=180, fg_color=C['sf'], corner_radius=0)
        self._side.pack(side='right', fill='y')
        ctk.CTkLabel(self._side, text="SAVED SNIPPETS", font=(FONT, 9, 'bold'), text_color=C['ac']).pack(pady=10)
        
        self._snip_scroll = ScrollableFrame(self._side, fg_color='transparent')
        self._snip_scroll.pack(fill='both', expand=True)
        
        Btn(self._side, "💾 SAVE CURRENT", command=self._save_snippet, variant='ghost', width=160).pack(pady=10)
        
        # Selection copy binding
        self._output.bind('<Control-c>', self._copy_selection)

        # ── Input Area ─────────────────────────────────────────
        self._input_frame = ctk.CTkFrame(self, fg_color=TERMINAL_THEMES[self._theme]['bg'], height=50, corner_radius=0,
                                         border_width=1, border_color=C['br'])
        self._input_frame.pack(fill='x', side='bottom')
        
        self._prompt_var = tk.StringVar(value=self._get_prompt_text())
        self._prompt = ctk.CTkLabel(self._input_frame, textvariable=self._prompt_var, 
                                    font=('DejaVu Sans Mono', 10, 'bold'), 
                                    text_color=TERMINAL_THEMES[self._theme]['p'],
                                    justify='left')
        self._prompt.pack(side='left', padx=(10, 0))

        self._input = ctk.CTkEntry(self._input_frame, font=('DejaVu Sans Mono', self._font_size),
                                   fg_color='transparent', border_width=0,
                                   text_color=TERMINAL_THEMES[self._theme]['fg'],
                                   height=35, placeholder_text="Enter command...")
        self._input.pack(side='left', fill='x', expand=True, padx=5)
        
        # Bindings
        self._input.bind('<Return>', self._execute)
        self._input.bind('<Up>', self._history_up)
        self._input.bind('<Down>', self._history_down)
        self._input.bind('<Tab>', self._tab_complete)
        self._input.bind('<Control-v>', self._paste)
        self._input.bind('<Control-f>', lambda e: self._find_entry.focus_set())
        
        self.bind('<Button-1>', lambda e: self._input.focus_set())

        self._write_to_ui(f"--- MINT SCAN v11.1 ULTRA PROFESSIONAL ---\n")
        self._write_to_ui(f"USER: {self._user}@{self._host} | DIR: {self._cwd}\n")
        self._write_to_ui("Zoom: Ctrl+/- | Search: Ctrl+F | Completion: Tab\n\n")

    def _get_prompt_text(self):
        cwd = self._cwd
        home = os.path.expanduser("~")
        if cwd.startswith(home): cwd = cwd.replace(home, "~", 1)
        return f"┌──({self._user}@{self._host})-[{cwd}]\n└─$ "

    def _apply_theme(self, theme_name):
        self._theme = theme_name
        theme = TERMINAL_THEMES[theme_name]
        self._output.configure(fg_color=theme['bg'], text_color=theme['fg'])
        self._input_frame.configure(fg_color=theme['bg'])
        self._input.configure(text_color=theme['fg'])
        self._prompt.configure(text_color=theme['p'])
        self._prompt_var.set(self._get_prompt_text())

    def _zoom_in(self):
        self._font_size = min(28, self._font_size + 1)
        self._update_zoom()

    def _zoom_out(self):
        self._font_size = max(6, self._font_size - 1)
        self._update_zoom()

    def _update_zoom(self):
        self._output.configure(font=('DejaVu Sans Mono', self._font_size))
        self._input.configure(font=('DejaVu Sans Mono', self._font_size))
        self._zoom_lbl.configure(text=f"{int(self._font_size/11*100)}%")

    def _copy_selection(self, event=None):
        try:
            txt = self._output.get("sel.first", "sel.last")
            if txt:
                self.winfo_toplevel().clipboard_clear()
                self.winfo_toplevel().clipboard_append(txt)
                self._status_lbl.configure(text='COPIED', text_color=C['ac'])
                self.after(1500, lambda: self._status_lbl.configure(text='READY', text_color=C['ok']))
        except: pass
        return 'break'

    def _copy_all(self):
        txt = self._output.get("1.0", "end")
        self.winfo_toplevel().clipboard_clear()
        self.winfo_toplevel().clipboard_append(txt)
        self._status_lbl.configure(text='ALL COPIED', text_color=C['ac'])
        self.after(1500, lambda: self._status_lbl.configure(text='READY', text_color=C['ok']))

    def _paste(self, event=None):
        try:
            txt = self.winfo_toplevel().clipboard_get()
            self._input.insert('insert', txt)
        except: pass
        return 'break'

    def _find_text(self):
        query = self._find_entry.get()
        if not query: return
        self._output.tag_remove('found', '1.0', 'end')
        idx = '1.0'
        count = 0
        while True:
            idx = self._output.search(query, idx, nocase=True, stopindex='end')
            if not idx: break
            last_idx = f"{idx}+{len(query)}c"
            self._output.tag_add('found', idx, last_idx)
            idx = last_idx
            count += 1
        self._output.tag_config('found', background='#444400', foreground='white')
        self._find_res_lbl.configure(text=f"Matches: {count}")
        if count > 0:
            self._output.see('found.last')

    def _tab_complete(self, event):
        txt = self._input.get()
        parts = txt.split()
        if not parts: return 'break'
        last = parts[-1]
        
        matches = glob.glob(last + '*')
        if not matches:
            # Try current directory if relative
            matches = glob.glob(os.path.join(self._cwd, last + '*'))
            matches = [os.path.basename(m) for m in matches]
            
        if len(matches) == 1:
            # Complete it
            to_add = matches[0][len(last):]
            self._input.insert('end', to_add)
        elif len(matches) > 1:
            # Show options
            self._write_to_ui("\n" + "  ".join(matches) + "\n")
        return 'break'

    def _write_to_ui(self, text):
        try:
            self._output.configure(state='normal')
            self._output.insert('end', text)
            self._output.see('end')
            self._output.configure(state='disabled')
        except: pass

    def _execute(self, event=None):
        cmd = self._input.get().strip()
        if not cmd: return
        self._history.append(cmd)
        self._hist_idx = -1
        self._input.delete(0, 'end')
        
        self._write_to_ui(f"\n{self._get_prompt_text()}{cmd}\n")
        
        if cmd == 'clear':
            self._clear_output()
            return
        if cmd.startswith('cd '):
            self._handle_cd(cmd[3:])
            return

        threading.Thread(target=self._run_command, args=(cmd,), daemon=True).start()

    def _handle_cd(self, path):
        path = os.path.expanduser(path.strip())
        try:
            os.chdir(path)
            self._cwd = os.getcwd()
            self._prompt_var.set(self._get_prompt_text())
        except Exception as e:
            self._write_to_ui(f"cd: {e}\n")

    def _run_command(self, cmd):
        with self._lock:
            if self._running: return
            self._running = True

        try:
            self._status_lbl.configure(text='RUNNING', text_color=C['am'])
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            self._proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True,
                                          cwd=self._cwd, env=env, 
                                          preexec_fn=os.setsid if hasattr(os, 'setsid') else None)
            buffer = []
            last_update = time.time()
            
            while self._running:
                line = self._proc.stdout.readline()
                if not line: break
                buffer.append(line)
                
                # Update UI every 100ms or if buffer gets large
                if time.time() - last_update > 0.1 or len(buffer) > 50:
                    text_to_write = "".join(buffer)
                    self.after(0, self._write_to_ui, text_to_write)
                    buffer = []
                    last_update = time.time()
            
            if buffer:
                self.after(0, self._write_to_ui, "".join(buffer))
                
            self._proc.wait()
            self.after(0, lambda: self._status_lbl.configure(text='READY', text_color=C['ok']))
        except Exception as e:
            self.after(0, self._write_to_ui, f"❌ ERROR: {e}\n")
        finally:
            with self._lock:
                self._running = False
                self._proc = None

    def _kill_proc(self):
        if self._proc:
            try:
                if not IS_WINDOWS and hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                else:
                    self._proc.terminate()
                self._write_to_ui("\n[ TERMINATED ]\n")
            except: pass
            self._running = False
            self._status_lbl.configure(text='READY', text_color=C['ok'])

    def _history_up(self, event):
        if not self._history: return
        if self._hist_idx == -1: self._hist_idx = len(self._history) - 1
        elif self._hist_idx > 0: self._hist_idx -= 1
        self._input.delete(0, 'end')
        self._input.insert(0, self._history[self._hist_idx])

    def _history_down(self, event):
        if self._hist_idx == -1: return
        if self._hist_idx < len(self._history) - 1:
            self._hist_idx += 1
            self._input.delete(0, 'end')
            self._input.insert(0, self._history[self._hist_idx])
        else:
            self._hist_idx = -1
            self._input.delete(0, 'end')

    def _clear_output(self):
        self._output.configure(state='normal')
        self._output.delete('1.0', 'end')
        self._output.configure(state='disabled')
