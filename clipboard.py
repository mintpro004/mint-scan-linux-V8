"""
Clipboard Manager — History and Management
Tracks clipboard changes and allows quick copying of previous entries.
"""
import tkinter as tk
import customtkinter as ctk
import threading, time, os
from widgets import ScrollableFrame, Card, SectionHeader, Btn, C, MONO, MONO_SM
from utils import copy_to_clipboard

class ClipboardScreen(ctk.CTkFrame):
    def _safe_after(self, delay, fn, *args):
        def _g():
            try:
                if self.winfo_exists(): fn(*args)
            except Exception: pass
        try: self.after(delay, _g)
        except Exception: pass

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._history = []
        self._built = False
        self._running = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._running = True
        threading.Thread(target=self._monitor_clipboard, daemon=True).start()

    def on_blur(self):
        self._running = False

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="📋  CLIPBOARD MANAGER",
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        Btn(hdr, "🗑 CLEAR HISTORY", command=self._clear_history,
            variant='danger', width=130).pack(side='right', padx=8, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        self._render_history()

    def _monitor_clipboard(self):
        last_val = ""
        while self._running:
            try:
                # Try to get clipboard content
                root = tk.Tk()
                root.withdraw()
                current_val = root.clipboard_get()
                root.destroy()
                
                if current_val and current_val != last_val:
                    last_val = current_val
                    if current_val not in self._history:
                        self._history.insert(0, current_val)
                        if len(self._history) > 50:
                            self._history.pop()
                        self._safe_after(0, self._render_history)
            except Exception:
                pass
            time.sleep(2)

    def _render_history(self):
        if not self._built: return
        for w in self.scroll.winfo_children(): w.destroy()
        
        SectionHeader(self.scroll, '01', 'CLIPBOARD HISTORY').pack(fill='x', padx=14, pady=(14,4))
        
        if not self._history:
            ctk.CTkLabel(self.scroll, text="No clipboard history yet...",
                         font=MONO_SM, text_color=C['mu']).pack(pady=20)
            return

        for text in self._history:
            card = Card(self.scroll)
            card.pack(fill='x', padx=14, pady=4)
            
            # Preview text
            preview = text[:100] + ('...' if len(text) > 100 else '')
            lbl = ctk.CTkLabel(card, text=preview, font=MONO_SM, 
                               text_color=C['tx'], wraplength=500, justify='left')
            lbl.pack(side='left', padx=12, pady=8, fill='x', expand=True)
            
            btns = ctk.CTkFrame(card, fg_color='transparent')
            btns.pack(side='right', padx=8)
            
            Btn(btns, "📋 COPY", command=lambda t=text: copy_to_clipboard(t),
                variant='success', width=70).pack(side='left', padx=2)
            Btn(btns, "🗑", command=lambda t=text: self._remove_item(t),
                variant='danger', width=30).pack(side='left', padx=2)

    def _remove_item(self, text):
        if text in self._history:
            self._history.remove(text)
            self._render_history()

    def _clear_history(self):
        self._history = []
        self._render_history()
