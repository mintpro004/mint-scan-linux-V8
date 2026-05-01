"""
Mint Scan v8 — Stabilised Terminal
- Real PTY shell with full Ctrl+C / Ctrl+D / Ctrl+L
- External clipboard paste (Ctrl+V / Ctrl+Shift+V / right-click)
- Copy output to clipboard
- ANSI colour stripped cleanly
- Buffer capped at 3000 lines to prevent memory growth
- Safe shutdown / restart on tab switch
"""
import os, threading, subprocess, select, time, re, signal as _signal
try:
    import pty as _pty
    _HAS_PTY = True
except ImportError:
    _HAS_PTY = False

import tkinter as tk
import customtkinter as ctk
from widgets import C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader, Btn
from logger import get_logger

log = get_logger('terminal')

# Strip ANSI escape codes
_ANSI = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class TerminalScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app       = app
        self._built    = False
        self._history  = []
        self._hist_idx = -1
        self._proc     = None
        self._running  = False
        self._master   = None

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        if not self._running or self._proc is None:
            self._start_shell()
        try:
            self._input.focus_set()
        except Exception:
            pass

    def on_blur(self):
        pass  # keep shell alive when switching tabs

    # ── Build UI ────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='>_  TERMINAL',
                     font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        self._shell_lbl = ctk.CTkLabel(hdr, text='',
                                        font=('DejaVu Sans Mono', 9),
                                        text_color=C['mu'])
        self._shell_lbl.pack(side='left', padx=4)

        Btn(hdr, '🗑 CLEAR',  command=self._clear,
            variant='ghost',  width=80).pack(side='right', padx=4, pady=8)
        Btn(hdr, '📋 COPY',   command=self._copy_output,
            variant='ghost',  width=80).pack(side='right', padx=4, pady=8)
        Btn(hdr, '📄 PASTE',  command=self._paste_clipboard,
            variant='ghost',  width=80).pack(side='right', padx=4, pady=8)
        Btn(hdr, '⟳ NEW',    command=self._restart_shell,
            variant='ghost',  width=70).pack(side='right', padx=4, pady=8)
        Btn(hdr, '⏹ KILL',   command=self._kill_proc,
            variant='danger', width=70).pack(side='right', padx=4, pady=8)
        
        # Theme selector
        self._theme_var = tk.StringVar(value='Matrix')
        self._theme_menu = ctk.CTkOptionMenu(
            hdr, variable=self._theme_var, values=['Matrix', 'Classic', 'Solarized', 'White', 'Dracula'],
            command=self._apply_terminal_theme, width=110, height=28,
            fg_color=C['s2'], button_color=C['br2'], dropdown_fg_color=C['sf'])
        self._theme_menu.pack(side='right', padx=8)
        ctk.CTkLabel(hdr, text='Theme:', font=('DejaVu Sans Mono', 8), text_color=C['mu']).pack(side='right')

    def _apply_terminal_theme(self, choice):
        themes = {
            'Matrix':    {'bg': '#010d18', 'fg': '#33ff88', 'insert': '#00ffe0'},
            'Classic':   {'bg': '#000000', 'fg': '#ffffff', 'insert': '#ffffff'},
            'Solarized': {'bg': '#002b36', 'fg': '#839496', 'insert': '#268bd2'},
            'White':     {'bg': '#ffffff', 'fg': '#000000', 'insert': '#000000'},
            'Dracula':   {'bg': '#282a36', 'fg': '#f8f8f2', 'insert': '#bd93f9'},
        }
        t = themes.get(choice, themes['Matrix'])
        self._output.configure(fg_color=t['bg'], text_color=t['fg'])
        self._input.configure(fg_color=t['bg'], text_color=t['fg'])
        try:
            tw = self._output._textbox
            tw.configure(insertbackground=t['insert'])
        except Exception: pass

        # Output area
        out_wrap = ctk.CTkFrame(self, fg_color='#010d18', corner_radius=0)
        out_wrap.pack(fill='both', expand=True, padx=0, pady=0)

        self._output = ctk.CTkTextbox(
            out_wrap,
            font=('DejaVu Sans Mono', 12),
            fg_color='#010d18',
            text_color='#c8e6ff',
            border_width=0,
            corner_radius=0,
            wrap='none',
            state='normal')
        self._output.pack(fill='both', expand=True, padx=0, pady=0)

        self._font_size = 12
        # Bind zoom
        self._output.bind("<Control-MouseWheel>", self._on_zoom)
        self._output.bind("<Control-plus>",       lambda e: self._on_zoom(delta=1))
        self._output.bind("<Control-equal>",      lambda e: self._on_zoom(delta=1))
        self._output.bind("<Control-minus>",      lambda e: self._on_zoom(delta=-1))
        self._input.bind("<Control-plus>",        lambda e: self._on_zoom(delta=1))
        self._input.bind("<Control-minus>",       lambda e: self._on_zoom(delta=-1))

    def _on_zoom(self, event=None, delta=0):
        if event and hasattr(event, 'delta'):
            delta = 1 if event.delta > 0 else -1
        
        self._font_size = max(6, min(48, self._font_size + delta))
        new_font = ('DejaVu Sans Mono', self._font_size)
        self._output.configure(font=new_font)
        self._input.configure(font=new_font)
        self._prompt_lbl.configure(font=('DejaVu Sans Mono', self._font_size, 'bold'))
        return 'break'

        # Configure inner text widget for crisp rendering + right-click paste
        try:
            tw = self._output._textbox
            tw.configure(font=('DejaVu Sans Mono', 12),
                         relief='flat', padx=8, pady=6,
                         spacing1=1, spacing2=0, spacing3=1,
                         insertbackground=C['ac'],
                         selectbackground=C['br2'],
                         selectforeground=C['tx'])
            # Right-click context menu
            menu = tk.Menu(tw, tearoff=0, bg=C['sf'], fg=C['tx'],
                           activebackground=C['br2'], activeforeground=C['tx'])
            menu.add_command(label='Copy',  command=self._copy_output)
            menu.add_command(label='Paste', command=self._paste_clipboard)
            menu.add_separator()
            menu.add_command(label='Clear', command=self._clear)
            tw.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))
        except Exception:
            pass

        # Separator
        ctk.CTkFrame(self, height=1, fg_color=C['br']).pack(fill='x')

        # Input row
        inp_frame = ctk.CTkFrame(self, fg_color='#010d18', height=42)
        inp_frame.pack(fill='x')
        inp_frame.pack_propagate(False)

        self._prompt_lbl = ctk.CTkLabel(
            inp_frame, text='$ ',
            font=('DejaVu Sans Mono', 12, 'bold'), text_color=C['ok'])
        self._prompt_lbl.pack(side='left', padx=(10, 2), pady=8)

        self._input = ctk.CTkEntry(
            inp_frame,
            font=('DejaVu Sans Mono', 12),
            fg_color='#010d18',
            border_width=0,
            text_color='#c8e6ff',
            placeholder_text='Type command and press Enter…',
            placeholder_text_color='#3a5a7a')
        self._input.pack(side='left', fill='both', expand=True, pady=6)

        # Key bindings
        self._input.bind('<Return>',         self._on_enter)
        self._input.bind('<Up>',             self._hist_up)
        self._input.bind('<Down>',           self._hist_down)
        self._input.bind('<Control-c>',      self._send_interrupt)
        self._input.bind('<Control-l>',      lambda e: self._clear())
        self._input.bind('<Tab>',            self._tab_complete)
        self._input.bind('<Control-v>',      self._paste_to_input)
        self._input.bind('<Control-V>',      self._paste_to_input)
        # Also allow Ctrl+Shift+V
        self._input.bind('<Control-Shift-v>',self._paste_to_input)

        Btn(inp_frame, '↩ RUN', command=lambda: self._on_enter(None),
            width=70).pack(side='right', padx=6, pady=6)

        # Quick-commands bar
        quick = ctk.CTkFrame(self, fg_color=C['s2'])
        quick.pack(fill='x')
        ctk.CTkLabel(quick, text='Quick:',
                     font=('DejaVu Sans Mono', 9), text_color=C['mu']
                     ).pack(side='left', padx=8, pady=3)
        for cmd in ['ls -la', 'ps aux | head -20', 'ss -tlnp',
                    'df -h', 'free -h', 'ufw status verbose',
                    'ip addr', 'nmcli dev status', 'who', 'last | head -10']:
            Btn(quick, cmd, command=lambda c=cmd: self._run_quick(c),
                variant='ghost', width=max(60, len(cmd)*7+10),
                height=24).pack(side='left', padx=2, pady=3)

    # ── Shell lifecycle ──────────────────────────────────────────

    def _start_shell(self):
        self._running = True
        shell = os.environ.get('SHELL', '/bin/bash')
        try:
            self._shell_lbl.configure(text=f'({shell})')
        except Exception:
            pass
        self._print(
            f'Mint Scan v8 Terminal  —  {shell}\n'
            f'cwd: {os.path.expanduser("~")}\n'
            f'Ctrl+C = interrupt  ·  Ctrl+L = clear  ·  ↑↓ = history\n'
            f'Ctrl+V / PASTE button = paste from clipboard\n'
            + '─' * 56 + '\n')

        try:
            if not _HAS_PTY:
                raise ImportError('pty unavailable')
            self._master, slave = _pty.openpty()
            self._proc = subprocess.Popen(
                [shell, '--norc', '--noprofile'],
                stdin=slave, stdout=slave, stderr=slave,
                preexec_fn=os.setsid,
                env={**os.environ,
                     'TERM': 'xterm-256color',
                     'PS1': r'\u@\h:\w\$ '})
            os.close(slave)
            log.info(f'PTY shell started  pid={self._proc.pid}')
            threading.Thread(target=self._read_loop, daemon=True).start()
        except Exception as exc:
            log.warning(f'PTY failed: {exc} — simple mode')
            self._master = None
            self._proc   = None
            self._print('(Simple mode — PTY unavailable; each command runs in isolation)\n')

    def _restart_shell(self):
        self._kill_proc()
        time.sleep(0.2)
        self._clear()
        self._start_shell()

    def _kill_proc(self):
        self._running = False
        try:
            if self._proc:
                os.killpg(os.getpgid(self._proc.pid), _signal.SIGTERM)
        except Exception:
            pass
        self._master = None
        self._proc   = None
        self._print('\n[Shell terminated — click ⟳ NEW to start fresh]\n')

    def _read_loop(self):
        """Read PTY output — strip ANSI, write to textbox."""
        while self._running and self._master:
            try:
                r, _, _ = select.select([self._master], [], [], 0.05)
                if r:
                    data = os.read(self._master, 4096)
                    text = data.decode('utf-8', errors='replace')
                    text = _ANSI.sub('', text)
                    if text:
                        self.after(0, self._print, text)
            except OSError:
                break
            except Exception:
                break
        self.after(0, self._print, '\n[Shell exited]\n')

    # ── Input handling ───────────────────────────────────────────

    def _on_enter(self, event):
        cmd = self._input.get().strip()
        self._input.delete(0, 'end')
        if not cmd:
            return 'break'
        if not self._history or self._history[-1] != cmd:
            self._history.append(cmd)
        self._hist_idx = len(self._history)
        self._print(f'$ {cmd}\n')
        if self._master:
            try:
                os.write(self._master, (cmd + '\n').encode())
            except OSError:
                self._run_simple(cmd)
        else:
            self._run_simple(cmd)
        return 'break'

    def _run_simple(self, cmd):
        def _bg():
            try:
                r = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30,
                    env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})
                out = r.stdout + (r.stderr or '')
                self.after(0, self._print, out or '(no output)\n')
            except subprocess.TimeoutExpired:
                self.after(0, self._print, '[timeout after 30s]\n')
            except Exception as e:
                self.after(0, self._print, f'[error: {e}]\n')
        threading.Thread(target=_bg, daemon=True).start()

    def _run_quick(self, cmd):
        self._input.delete(0, 'end')
        self._input.insert(0, cmd)
        self._on_enter(None)

    # ── Output helpers ───────────────────────────────────────────

    def _print(self, text: str):
        try:
            if not self.winfo_exists() or not hasattr(self, '_output'):
                return
            self._output.configure(state='normal')
            self._output.insert('end', text)
            self._output.see('end')
            # Cap buffer
            line_count = int(self._output.index('end').split('.')[0])
            if line_count > 3000:
                self._output.delete('1.0', f'{line_count - 2000}.0')
        except Exception:
            pass

    def _clear(self):
        try:
            self._output.configure(state='normal')
            self._output.delete('1.0', 'end')
        except Exception:
            pass

    # ── Clipboard ────────────────────────────────────────────────

    def _copy_output(self):
        """Copy terminal output to system clipboard."""
        try:
            txt = self._output.get('1.0', 'end').strip()
            if txt:
                self.winfo_toplevel().clipboard_clear()
                self.winfo_toplevel().clipboard_append(txt)
                self.winfo_toplevel().update()
                self._print('\n[Output copied to clipboard]\n')
        except Exception as e:
            self._print(f'\n[Copy failed: {e}]\n')

    def _paste_clipboard(self):
        """Paste system clipboard text into the terminal / PTY."""
        try:
            text = self.winfo_toplevel().clipboard_get()
        except Exception:
            self._print('\n[Clipboard empty or unavailable]\n')
            return
        if not text:
            return
        if self._master:
            # Write directly to PTY so multiline pastes work
            try:
                os.write(self._master, text.encode('utf-8', errors='replace'))
                return
            except OSError:
                pass
        # Fallback: put in input box
        self._input.delete(0, 'end')
        # Only first line for single-command input
        first_line = text.split('\n')[0].strip()
        self._input.insert(0, first_line)
        self._input.focus_set()

    def _paste_to_input(self, event=None):
        """Ctrl+V in input field — paste from clipboard."""
        try:
            text = self.winfo_toplevel().clipboard_get()
            if text:
                pos = self._input.index(tk.INSERT)
                self._input.insert(pos, text.split('\n')[0])
        except Exception:
            pass
        return 'break'

    # ── Interrupt / signals ──────────────────────────────────────

    def _send_interrupt(self, event=None):
        if self._master:
            try:
                os.write(self._master, b'\x03')
            except Exception:
                pass
        return 'break'

    # ── History ──────────────────────────────────────────────────

    def _hist_up(self, event):
        if self._history and self._hist_idx > 0:
            self._hist_idx -= 1
            self._input.delete(0, 'end')
            self._input.insert(0, self._history[self._hist_idx])
        return 'break'

    def _hist_down(self, event):
        if self._hist_idx < len(self._history) - 1:
            self._hist_idx += 1
            self._input.delete(0, 'end')
            self._input.insert(0, self._history[self._hist_idx])
        elif self._hist_idx == len(self._history) - 1:
            self._hist_idx = len(self._history)
            self._input.delete(0, 'end')
        return 'break'

    # ── Tab completion ───────────────────────────────────────────

    def _tab_complete(self, event):
        partial = self._input.get().strip()
        if not partial:
            return 'break'
        try:
            r = subprocess.run(
                ['bash', '-c', f'compgen -f -- {partial} 2>/dev/null | head -8'],
                capture_output=True, text=True, timeout=2)
            matches = [m.strip() for m in r.stdout.splitlines() if m.strip()]
        except Exception:
            matches = []
        if len(matches) == 1:
            self._input.delete(0, 'end')
            self._input.insert(0, matches[0] + ' ')
        elif len(matches) > 1:
            self._print('  '.join(matches[:8]) + '\n')
        return 'break'
