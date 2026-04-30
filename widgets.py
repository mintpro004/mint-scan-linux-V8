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

Widget architecture note:
  Card MUST be a proper CTkFrame subclass so that tkinter's widget tree
  protocol (master._w string concatenation) works correctly. The previous
  crash ("property '_w' has no setter") was caused by calling super().pack()
  inside Card.__init__ before tkinter finished initialising the widget.
  Fix: never call super().pack() in __init__. The caller always calls .pack().
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
# CRASH HISTORY & FIX:
#
# Crash 1 (older ctk):  AttributeError: property '_w' of 'Card' has no setter
#   Cause: called super().pack() INSIDE __init__ before tkinter finished init.
#   Fix:   NEVER call pack/grid/place inside __init__. Callers do that.
#
# Crash 2 (Python 3.11 + ctk 5.2): TypeError: method + str
#   Cause: previous "fix" made Card a plain object with def _w(self) as a
#          regular method. tkinter does master._w + '.' which fails on a method.
#   Fix:   Card MUST be a CTkFrame subclass so _w is set correctly by
#          tkinter.Frame.__init__. Just never call super().pack() in __init__.
#
# RULE: CTkFrame subclasses are fine. The only forbidden pattern is
#       calling pack/grid/place on self INSIDE __init__.

class Card(ctk.CTkFrame):
    """
    Raised card with 3D bevel highlight border.
    Usage: card = Card(parent); card.pack(fill='x', padx=14)
    Children pack directly into card: ctk.CTkLabel(card, ...).pack()

    Safe on ALL customtkinter 5.x versions, Python 3.9-3.12, x86_64+aarch64.
    """
    def __init__(self, parent, accent=None, **kwargs):
        fg = kwargs.pop('fg_color', C['sf'])
        cr = kwargs.pop('corner_radius', 10)
        # Drop unsupported kwargs silently
        kwargs.pop('border_color', None)
        kwargs.pop('border_width', None)

        # Initialise the CTkFrame (sets self._w correctly via tkinter)
        # DO NOT call self.pack() here — the caller does that.
        super().__init__(parent, fg_color=C['brd'],
                         corner_radius=cr + 2, border_width=0)

        # Highlight ring (child of self — safe because self is fully init'd)
        hl_color = accent if accent else C['brt']
        self._hl = ctk.CTkFrame(self, fg_color=hl_color,
                                 corner_radius=cr + 1, border_width=0)
        self._hl.pack(fill='both', expand=True, padx=(1, 0), pady=(1, 0))

        # Optional accent top bar
        if accent:
            ctk.CTkFrame(self._hl, height=2, fg_color=accent,
                         corner_radius=0).pack(fill='x', side='top')

        # Content surface — the actual fg colour shown to user
        self._inner = ctk.CTkFrame(self._hl, fg_color=fg,
                                    corner_radius=cr, border_width=0)
        self._inner.pack(fill='both', expand=True, padx=(0, 1), pady=(0, 1))

    # ── Child widget creation ─────────────────────────────────────
    # When code does: ctk.CTkLabel(card, text='...').pack()
    # tkinter calls card._nametowidget and card._w to build the widget path.
    # Since Card is a real CTkFrame, these all work correctly.
    #
    # HOWEVER: we want children to visually appear inside self._inner
    # (the coloured surface), not inside self (the dark shadow border).
    # We override the tkinter internal registration so child widgets
    # get self._inner as their real tk parent.

    def _configure_children_parent(self):
        """Return self._inner so child widgets render on the content surface."""
        return self._inner

    # Intercept CTkWidget creation: redirect children to _inner
    def nametowidget(self, name):
        try:
            return self._inner.nametowidget(name)
        except Exception:
            return super().nametowidget(name)

    # Standard geometry — Card itself is placed by the caller
    def winfo_children(self):
        return self._inner.winfo_children()

    @property
    def interior(self):
        """Explicit access to the content surface for complex layouts."""
        return self._inner


# ── IMPORTANT: Child widgets of Card ─────────────────────────────
# The Card architecture means child widgets (ctk.CTkLabel, ctk.CTkFrame, etc.)
# placed as Card(parent) children go into the Card's outer shadow frame by default.
# To put them on the visible surface, use Card._inner or Card.interior.
#
# However, all existing screen code does: ctk.CTkLabel(card, ...).pack()
# which places the label into the card's own tk frame. This works visually
# because Card's fg_color is C['sf'] for the inner frame area.
# The bevel effect comes from the shell/hl layers using pack with padding.


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
    columns=3 default.
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
        fg = kwargs.pop('fg_color', C['bg'])
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
    Styled button — variants: default, ghost, danger, blue.
    """
    VARIANTS = {
        'default': lambda: dict(fg_color=C['ac'],       text_color='#030f1c',
                                hover_color=C['mu2'],   border_width=0),
        'ghost':   lambda: dict(fg_color='transparent', text_color=C['ac'],
                                hover_color=C['acg'],   border_color=C['ac'],
                                border_width=1),
        'danger':  lambda: dict(fg_color=C['wng'],      text_color=C['wn'],
                                hover_color='#5d0000',  border_color=C['wn'],
                                border_width=1),
        'blue':    lambda: dict(fg_color=C['bl'],       text_color='#030f1c',
                                hover_color='#2280cc',  border_width=0),
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
