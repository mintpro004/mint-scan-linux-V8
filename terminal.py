"""
Mint Scan v8 — Built-in Terminal
Full interactive terminal using subprocess PTY.
Supports: command history, colour output (ANSI stripped), copy/paste, clear.
"""
import os, threading, subprocess, select, time
try:
    import pty
    _HAS_PTY = True
except ImportError:
    _HAS_PTY = False
import tkinter as tk
import customtkinter as ctk
from widgets import (C, MONO, MONO_SM, ScrollableFrame,
                     Card, SectionHeader, Btn)
from logger import get_logger

log = get_logger('terminal')


class TerminalScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app      = app
        self._built   = False
        self._history = []
        self._hist_idx = -1
        self._proc    = None
        self._running = False
        self._master  = None
        self._slave   = None

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        # Only start shell if it's not already running
        if not self._running or self._proc is None:
            self._start_shell()
        # Focus input
        try:
            self._input.focus_set()
        except Exception:
            pass

    def on_blur(self):
        pass  # keep shell alive when switching tabs

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='> TERMINAL',
                     font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        self._shell_lbl = ctk.CTkLabel(hdr, text='',
                                        font=('Courier', 9), text_color=C['mu'])
        self._shell_lbl.pack(side='left', padx=4)

        Btn(hdr, '🗑 CLEAR', command=self._clear,
            variant='ghost', width=80).pack(side='right', padx=4, pady=8)
        Btn(hdr, '📋 COPY',  command=self._copy_output,
            variant='ghost', width=80).pack(side='right', padx=4, pady=8)
        Btn(hdr, '⏹ KILL',  command=self._kill_proc,
            variant='danger', width=70).pack(side='right', padx=4, pady=8)

        # Output area — large monospace textbox
        out_frame = ctk.CTkFrame(self, fg_color=C['bg'])
        out_frame.pack(fill='both', expand=True, padx=6, pady=(6,0))

        self._output = ctk.CTkTextbox(
            out_frame,
            font=('Courier', 10),
            fg_color='#020a13',   # near-black terminal bg
            text_color='#e8f4ff',
            border_color=C['br'],
            border_width=1,
            corner_radius=4,
            wrap='none')
        self._output.pack(fill='both', expand=True)
        self._output.configure(state='normal')

        # Input row
        inp_frame = ctk.CTkFrame(self, fg_color=C['sf'], height=42)
        inp_frame.pack(fill='x', padx=6, pady=6)
        inp_frame.pack_propagate(False)

        self._prompt_lbl = ctk.CTkLabel(
            inp_frame, text='$ ',
            font=('Courier', 11, 'bold'), text_color=C['ok'])
        self._prompt_lbl.pack(side='left', padx=(10,2), pady=8)

        self._input = ctk.CTkEntry(
            inp_frame,
            font=('Courier', 11),
            fg_color='#020a13',
            border_width=0,
            text_color='#e8f4ff',
            placeholder_text='Type command and press Enter...',
            placeholder_text_color=C['mu'])
        self._input.pack(side='left', fill='both', expand=True, pady=6)
        self._input.bind('<Return>',   self._on_enter)
        self._input.bind('<Up>',       self._hist_up)
        self._input.bind('<Down>',     self._hist_down)
        self._input.bind('<Control-c>', self._send_interrupt)
        self._input.bind('<Control-l>', lambda e: self._clear())
        self._input.bind('<Tab>',      self._tab_complete)
        self._input.focus_set()

        Btn(inp_frame, '↩ RUN', command=lambda: self._on_enter(None),
            width=70).pack(side='right', padx=6, pady=6)

        # Quick commands bar
        quick = ctk.CTkFrame(self, fg_color=C['s2'])
        quick.pack(fill='x', padx=6, pady=(0,4))
        ctk.CTkLabel(quick, text='Quick:',
                     font=('Courier', 8), text_color=C['mu']
                     ).pack(side='left', padx=8, pady=3)
        for cmd in ['ls -la', 'ps aux | head -20', 'netstat -tlnp',
                    'df -h', 'free -h', 'ufw status verbose',
                    'ip addr', 'who', 'last | head -10']:
            Btn(quick, cmd, command=lambda c=cmd: self._run_quick(c),
                variant='ghost', width=max(60, len(cmd)*7+10),
                height=24).pack(side='left', padx=2, pady=3)

    def _start_shell(self):
        """Start a real interactive shell via PTY."""
        self._running = True
        shell = os.environ.get('SHELL', '/bin/bash')
        self._shell_lbl.configure(text=f'({shell})')
        self._print(f'Mint Scan v8 Terminal — {shell}\n'
                    f'Working dir: {os.path.expanduser("~")}\n'
                    f'Type commands below. Ctrl+C to interrupt.\n'
                    + '─' * 50 + '\n')

        # Use PTY for real interactive shell
        try:
            if not _HAS_PTY:
                raise ImportError("pty not available")
            self._master, self._slave = pty.openpty()
            self._proc = subprocess.Popen(
                [shell, '--norc', '--noprofile'],
                stdin=self._slave, stdout=self._slave, stderr=self._slave,
                preexec_fn=os.setsid,
                env={**os.environ, 'TERM': 'xterm-256color',
                     'PS1': '\\u@\\h:\\w\\$ '})
            log.info(f'Shell started: pid={self._proc.pid}')
            threading.Thread(target=self._read_loop, daemon=True).start()
        except Exception as e:
            log.warning(f'PTY shell failed: {e} — using simple mode')
            self._start_simple_mode()

    def _start_simple_mode(self):
        """Fallback: run each command directly without PTY."""
        self._master = None
        self._proc   = None
        self._print('(Simple mode — PTY not available)\n')

    def _read_loop(self):
        """Read PTY output and write to textbox."""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        while self._running and self._master:
            try:
                r, _, _ = select.select([self._master], [], [], 0.05)
                if r:
                    data = os.read(self._master, 4096)
                    text = data.decode('utf-8', errors='replace')
                    text = ansi_escape.sub('', text)  # strip ANSI colours
                    if text:
                        self.after(0, self._print, text)
            except (OSError, Exception):
                break
        self.after(0, self._print, '\n[Shell exited]\n')

    def _on_enter(self, event):
        cmd = self._input.get().strip()
        self._input.delete(0, 'end')
        if not cmd:
            return 'break'

        # History
        if not self._history or self._history[-1] != cmd:
            self._history.append(cmd)
        self._hist_idx = len(self._history)

        self._print(f'$ {cmd}\n')

        if self._master:
            # Write to PTY
            try:
                os.write(self._master, (cmd + '\n').encode())
            except OSError:
                self._run_simple(cmd)
        else:
            self._run_simple(cmd)
        return 'break'

    def _run_simple(self, cmd):
        """Run command without PTY, capture output."""
        def _bg():
            try:
                r = subprocess.run(
                    cmd, shell=True,
                    capture_output=True, text=True, timeout=30,
                    env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})
                out = r.stdout + (r.stderr if r.stderr else '')
                self.after(0, self._print, out or '(no output)\n')
            except subprocess.TimeoutExpired:
                self.after(0, self._print, '[timeout]\n')
            except Exception as e:
                self.after(0, self._print, f'[error: {e}]\n')
        threading.Thread(target=_bg, daemon=True).start()

    def _run_quick(self, cmd):
        self._input.delete(0, 'end')
        self._input.insert(0, cmd)
        self._on_enter(None)

    def _print(self, text: str):
        try:
            if not self.winfo_exists():
                return
            if not hasattr(self, '_output'):
                return
            self._output.configure(state='normal')
            self._output.insert('end', text)
            self._output.see('end')
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

    def _copy_output(self):
        try:
            txt = self._output.get('1.0', 'end').strip()
            if txt:
                self.winfo_toplevel().clipboard_clear()
                self.winfo_toplevel().clipboard_append(txt)
        except Exception:
            pass

    def _send_interrupt(self, event=None):
        if self._master:
            try:
                os.write(self._master, b'\x03')  # Ctrl+C
            except Exception:
                pass
        return 'break'

    def _kill_proc(self):
        if self._proc:
            try:
                import signal, os
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except Exception:
                pass
        self._running = False
        self._master  = None
        self._proc    = None
        self._print('\n[Killed — click focus to start new shell]\n')

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

    def _tab_complete(self, event):
        """Tab completion using bash compgen."""
        partial = self._input.get().strip()
        if not partial:
            return 'break'
        try:
            import subprocess as _sp
            r = _sp.run(
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

