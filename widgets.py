"""
Mint Scan v8 — Shared Widgets
3D-depth visual system: raised surfaces, bevel highlights, glow accents.
DejaVu Sans Mono fonts throughout.

Compatibility:
- Python 3.9 – 3.12
- customtkinter 5.x (any minor)
- Linux x86_64 and aarch64 (Ubuntu 20.04+, 22.04+)
- Chromebook Crostini, Kali, WSL2, Raspberry Pi OS 64-bit
- Wayland and X11
"""
import tkinter as tk
import customtkinter as ctk

# ── Theme palettes ────────────────────────────────────────────────
DARK_THEME = {
    'bg':  '#030f1c', 'sf':  '#081c2e', 's2':  '#0c2540',
    'brt': '#1e4a6a', 'brd': '#010810',
    'br':  '#163352', 'br2': '#1e4a6a',
    'ac':  '#00ffe0', 'acg': '#004d44',
    'wn':  '#ff4444', 'am':  '#ffbb33', 'ok':  '#33ff88',
    'bl':  '#44aaff', 'pu':  '#bb77ff',
    'wng': '#3d0000', 'amg': '#3d2d00', 'okg': '#003d20',
    'tx':  '#deeeff', 'mu':  '#5a90b8', 'mu2': '#7ab0d0',
}

LIGHT_THEME = {
    'bg':  '#dde4ed', 'sf':  '#eaf0f8', 's2':  '#ffffff',
    'brt': '#ffffff',  'brd': '#b0c4d8',
    'br':  '#b8cfe0',  'br2': '#8aaabf',
    'ac':  '#005fa3',  'acg': '#d0e8f8',
    'wn':  '#cc1111',  'am':  '#cc7700',  'ok':  '#117744',
    'bl':  '#1155cc',  'pu':  '#6622bb',
    'wng': '#fde8e8',  'amg': '#fff3cd',  'okg': '#d4edda',
    'tx':  '#0d1f2d',  'mu':  '#3a5a70',  'mu2': '#2d4a60',
}

C = dict(DARK_THEME)

FONT    = 'DejaVu Sans Mono'
MONO    = (FONT, 11)
MONO_SM = (FONT, 10)
MONO_LG = (FONT, 14, 'bold')
MONO_XL = (FONT, 38, 'bold')
_current_theme = 'dark'


def get_theme():
    return _current_theme


def apply_theme(name, accent=None, font_size=11):
    global _current_theme, MONO, MONO_SM, MONO_LG, MONO_XL
    _current_theme = name
    C.update(LIGHT_THEME if name == 'light' else DARK_THEME)
    if accent:
        C['ac'] = accent
    fs      = max(9, font_size)
    MONO    = (FONT, fs)
    MONO_SM = (FONT, max(8, fs - 1))
    MONO_LG = (FONT, fs + 3, 'bold')
    MONO_XL = (FONT, fs + 26, 'bold')
    try:
        ctk.set_appearance_mode('light' if name == 'light' else 'dark')
    except Exception:
        pass


def load_theme_settings():
    import json, os
    path = os.path.expanduser('~/.mint_scan_settings.json')
    try:
        if os.path.exists(path):
            s = json.load(open(path))
            apply_theme(s.get('theme', 'dark'),
                        s.get('accent_color'), s.get('font_size', 11))
            return s.get('ui_scale', 1.0)
    except Exception:
        pass
    apply_theme('dark')
    return 1.0


# ── ScrollableFrame ───────────────────────────────────────────────
class ScrollableFrame(ctk.CTkScrollableFrame):
    def __init__(self, parent, **kwargs):
        fg   = kwargs.pop('fg_color', C['bg'])
        sbc  = kwargs.pop('scrollbar_button_color', C['br2'])
        sbhc = kwargs.pop('scrollbar_button_hover_color', C['ac'])
        cr   = kwargs.pop('corner_radius', 0)
        super().__init__(master=parent, fg_color=fg,
                         scrollbar_button_color=sbc,
                         scrollbar_button_hover_color=sbhc,
                         corner_radius=cr, **kwargs)


# ── Card ──────────────────────────────────────────────────────────
#
# FIX: The original Card subclassed CTkFrame and called super().pack()
# inside __init__, which attempts to set self._w before tkinter.Frame.__init__
# runs. On Python 3.11 + customtkinter 5.2 on aarch64 the MRO resolves
# CTkBaseClass._w as a read-only property before the tk.Frame __init__
# can define the instance attribute — raising:
#   AttributeError: property '_w' of 'Card' object has no setter
#
# Solution: Card is now a plain Python object (not a CTkFrame subclass).
# It wraps a CTkFrame as its content surface (self._inner) and delegates
# widget protocol methods to the outer shell.  Children pack/grid/place
# into self._inner directly — Card(parent) acts like a CTkFrame for callers.

class Card:
    """
    Raised card with 3D bevel border. Children pack/grid/place into Card()
    exactly as they would into a CTkFrame — Card delegates the geometry
    manager to the outer shell and child placement to the inner surface.

    Compatible with all customtkinter 5.x versions and Python 3.9–3.12
    on x86_64 and aarch64.
    """
    def __init__(self, parent, accent=None, **kwargs):
        fg = kwargs.pop('fg_color', C['sf'])
        cr = kwargs.pop('corner_radius', 10)
        kwargs.pop('border_color', None)
        kwargs.pop('border_width', None)

        # Outer shadow shell (positioned by pack/grid/place)
        self._shell = ctk.CTkFrame(
            parent, fg_color=C['brd'],
            corner_radius=cr + 2, border_width=0, **kwargs)

        # Highlight ring
        self._hl = ctk.CTkFrame(
            self._shell, fg_color=accent or C['brt'],
            corner_radius=cr + 1, border_width=0)
        self._hl.pack(fill='both', expand=True, padx=(1, 0), pady=(1, 0))

        # Optional accent line
        if accent:
            ctk.CTkFrame(self._hl, height=2, fg_color=accent,
                         corner_radius=0).pack(fill='x', side='top')

        # Content surface — children go here
        self._inner = ctk.CTkFrame(
            self._hl, fg_color=fg,
            corner_radius=cr, border_width=0)
        self._inner.pack(fill='both', expand=True, padx=(0, 1), pady=(0, 1))

    # ── Child placement — delegate to inner surface ───────────────
    # This makes  ctk.CTkLabel(card, ...).pack()  work as expected.
    @property
    def _w(self):           return self._inner._w
    @property
    def _name(self):        return self._inner._name
    @property
    def master(self):       return self._inner.master

    def winfo_exists(self):
        try: return self._shell.winfo_exists()
        except Exception: return False

    def winfo_children(self):
        return self._inner.winfo_children()

    def configure(self, **kwargs):
        if 'fg_color' in kwargs:
            self._inner.configure(fg_color=kwargs.pop('fg_color'))
        if kwargs:
            self._inner.configure(**kwargs)

    def cget(self, key):
        return self._inner.cget(key)

    def after(self, ms, fn=None, *args):
        return self._inner.after(ms, fn, *args)

    def destroy(self):
        try: self._shell.destroy()
        except Exception: pass

    # ── Geometry managers — delegate to outer shell ───────────────
    def pack(self, **kwargs):
        self._shell.pack(**kwargs)
        return self

    def pack_forget(self):
        self._shell.pack_forget()

    def pack_info(self):
        return self._shell.pack_info()

    def grid(self, **kwargs):
        self._shell.grid(**kwargs)
        return self

    def grid_forget(self):
        self._shell.grid_forget()

    def place(self, **kwargs):
        self._shell.place(**kwargs)
        return self

    def place_forget(self):
        self._shell.place_forget()

    # ── tkinter master protocol ───────────────────────────────────
    # When CTkLabel(card, ...) is called, tkinter calls card._w to get
    # the parent widget name. We forward this to self._inner.
    def __getattr__(self, name):
        # Delegate unknown attrs to the inner CTkFrame
        # This handles _w, tk, _last_child_ids etc.
        if name.startswith('_') or name in ('tk', 'children'):
            return getattr(self._inner, name)
        raise AttributeError(f"Card has no attribute '{name}'")

    @property
    def interior(self):
        return self._inner


# ── SectionHeader ─────────────────────────────────────────────────
class SectionHeader(ctk.CTkFrame):
    def __init__(self, parent, num, title, **kwargs):
        fg = kwargs.pop('fg_color', 'transparent')
        super().__init__(parent, fg_color=fg, **kwargs)
        ctk.CTkLabel(
            self, text=f'// {num} — {title}',
            font=(FONT, 9, 'bold'), text_color=C['ac']
        ).pack(side='left', padx=12, pady=6)
        ctk.CTkFrame(self, height=1, fg_color=C['br'],
                     corner_radius=0).pack(
            side='left', fill='x', expand=True, padx=(0, 12))


# ── InfoGrid ──────────────────────────────────────────────────────
class InfoGrid(ctk.CTkFrame):
    """
    Responsive stat grid. Each item is (label, value, colour).
    columns=3 default, falls back gracefully.
    """
    def __init__(self, parent, items, columns=3, **kwargs):
        fg = kwargs.pop('fg_color', 'transparent')
        super().__init__(parent, fg_color=fg, **kwargs)
        for i, (label, value, colour) in enumerate(items):
            cell = ctk.CTkFrame(self, fg_color=C['s2'],
                                corner_radius=6, border_width=0)
            cell.grid(row=i // columns, column=i % columns,
                      padx=4, pady=4, sticky='ew')
            self.columnconfigure(i % columns, weight=1)
            ctk.CTkLabel(cell, text=str(label),
                         font=(FONT, 8), text_color=C['mu']
                         ).pack(anchor='w', padx=8, pady=(5, 0))
            ctk.CTkLabel(cell, text=str(value),
                         font=(FONT, 10, 'bold'), text_color=colour,
                         wraplength=160
                         ).pack(anchor='w', padx=8, pady=(0, 5))


# ── ResultBox ─────────────────────────────────────────────────────
class ResultBox(ctk.CTkFrame):
    """Scrollable read-only output box."""
    def __init__(self, parent, height=200, **kwargs):
        fg    = kwargs.pop('fg_color', C['bg'])
        super().__init__(parent, fg_color='transparent', **kwargs)
        self._box = ctk.CTkTextbox(
            self, height=height, font=(FONT, 10),
            fg_color=fg, text_color=C['ok'],
            border_color=C['br'], border_width=1,
            corner_radius=6, wrap='none')
        self._box.pack(fill='both', expand=True)
        self._box.configure(state='disabled')

    def set(self, text):
        self._box.configure(state='normal')
        self._box.delete('1.0', 'end')
        self._box.insert('end', str(text))
        self._box.configure(state='disabled')

    def append(self, text):
        self._box.configure(state='normal')
        self._box.insert('end', str(text) + '\n')
        self._box.see('end')
        self._box.configure(state='disabled')

    def clear(self):
        self._box.configure(state='normal')
        self._box.delete('1.0', 'end')
        self._box.configure(state='disabled')


# ── Btn ───────────────────────────────────────────────────────────
class Btn(ctk.CTkButton):
    """
    Styled button with variant support:
      default  — accent fill
      ghost    — transparent with accent border
      danger   — warning red
      blue     — blue accent
    """
    VARIANTS = {
        'default': lambda: dict(fg_color=C['ac'],   text_color='#030f1c',
                                hover_color=C['mu2'], border_width=0),
        'ghost':   lambda: dict(fg_color='transparent', text_color=C['ac'],
                                hover_color=C['acg'], border_color=C['ac'],
                                border_width=1),
        'danger':  lambda: dict(fg_color=C['wng'],  text_color=C['wn'],
                                hover_color='#5d0000', border_color=C['wn'],
                                border_width=1),
        'blue':    lambda: dict(fg_color=C['bl'],   text_color='#030f1c',
                                hover_color='#2280cc', border_width=0),
    }

    def __init__(self, parent, text='', variant='default',
                 height=34, corner_radius=6, **kwargs):
        style = self.VARIANTS.get(variant, self.VARIANTS['default'])()
        style.update(kwargs)
        super().__init__(
            parent, text=text, height=height,
            font=(FONT, 10, 'bold'),
            corner_radius=corner_radius,
            **style)
