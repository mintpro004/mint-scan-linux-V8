"""
Mint Scan v8 — Shared Widgets
3D-depth visual system: raised surfaces, bevel highlights, glow accents, deep shadows.
Crisp DejaVu Sans Mono fonts throughout.
"""
import tkinter as tk
import customtkinter as ctk

# ── Theme palettes ────────────────────────────────────────────────
# 3D depth model:
#   bg   = deepest base layer
#   sf   = raised surface (cards, panels) — lighter than bg
#   s2   = highest surface — inputs, inner cards
#   brt  = top-edge highlight (bevel light edge)
#   brd  = bottom-edge shadow (bevel dark edge)
#   br   = mid border
#   br2  = slightly brighter border / dividers

DARK_THEME = {
    # Depth layers
    'bg':  '#030f1c',   # deep base
    'sf':  '#081c2e',   # raised panel
    's2':  '#0c2540',   # top-surface / inputs
    # Bevel edges — give the 3D raised look
    'brt': '#1e4a6a',   # bright top-left bevel edge
    'brd': '#010810',   # dark bottom-right shadow edge
    # Borders
    'br':  '#163352',
    'br2': '#1e4a6a',
    # Accent / glow
    'ac':  '#00ffe0',
    'acg': '#004d44',   # accent glow (dark tint for backgrounds)
    # Status
    'wn':  '#ff4444', 'am':  '#ffbb33', 'ok':  '#33ff88',
    'bl':  '#44aaff', 'pu':  '#bb77ff',
    # Status glows
    'wng': '#3d0000', 'amg': '#3d2d00', 'okg': '#003d20',
    # Text
    'tx':  '#deeeff',
    'mu':  '#5a90b8',
    'mu2': '#7ab0d0',
}

LIGHT_THEME = {
    'bg':  '#dde4ed', 'sf':  '#eaf0f8', 's2':  '#ffffff',
    'brt': '#ffffff',  'brd': '#b0c4d8',
    'br':  '#b8cfe0',  'br2': '#8aaabf',
    'ac':  '#005fa3',  'acg': '#d0e8f8',
    'wn':  '#cc1111',  'am':  '#cc7700',  'ok':  '#117744',
    'bl':  '#1155cc',  'pu':  '#6622bb',
    'wng': '#fde8e8',  'amg': '#fff3cd',  'okg': '#d4edda',
    'tx':  '#0d1f2d',
    'mu':  '#3a5a70',  'mu2': '#2d4a60',
}

C = dict(DARK_THEME)

# DejaVu Sans Mono — crisp, hinted, designed for screens
FONT       = 'DejaVu Sans Mono'
MONO    = (FONT, 11)
MONO_SM = (FONT, 10)
MONO_LG = (FONT, 14, 'bold')
MONO_XL = (FONT, 38, 'bold')
_current_theme = 'dark'


def get_theme():
    return _current_theme


def apply_theme(name, accent=None, font_size=11):
    global _current_theme, MONO, MONO_SM, MONO_LG, MONO_XL, FONT
    _current_theme = name
    base_colors = LIGHT_THEME if name == 'light' else DARK_THEME
    C.update(base_colors)
    if accent:
        C['ac'] = accent
    fs = max(9, font_size)
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
    settings_file = os.path.expanduser('~/.mint_scan_settings.json')
    try:
        if os.path.exists(settings_file):
            with open(settings_file) as f:
                s = json.load(f)
                apply_theme(s.get('theme', 'dark'),
                            s.get('accent_color', None),
                            s.get('font_size', 11))
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
        super().__init__(
            master=parent,
            fg_color=fg,
            scrollbar_button_color=sbc,
            scrollbar_button_hover_color=sbhc,
            corner_radius=cr,
            **kwargs
        )
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, event=None):
        self._toplevel = self.winfo_toplevel()
        self._toplevel.bind_all('<MouseWheel>', self._on_mousewheel, add='+')
        self._toplevel.bind_all('<Button-4>',   self._scroll_up,    add='+')
        self._toplevel.bind_all('<Button-5>',   self._scroll_down,  add='+')

    def _on_leave(self, event=None):
        try:
            self._toplevel.unbind_all('<MouseWheel>')
            self._toplevel.unbind_all('<Button-4>')
            self._toplevel.unbind_all('<Button-5>')
        except Exception:
            pass

    def _on_mousewheel(self, event):
        try:
            if event.delta:
                self._parent_canvas.yview_scroll(int(-1*(event.delta/120)), 'units')
        except Exception:
            pass

    def _scroll_up(self, event):
        try: self._parent_canvas.yview_scroll(-2, 'units')
        except Exception: pass

    def _scroll_down(self, event):
        try: self._parent_canvas.yview_scroll(2, 'units')
        except Exception: pass


# ── 3D Bevel Frame (core 3D primitive) ───────────────────────────
# Simulates a raised surface using a 1px top/left highlight and
# 1px bottom/right shadow drawn as thin frames around the content.

class BevelFrame(ctk.CTkFrame):
    """
    Raised 3D panel: outer shadow layer → highlight ring → content bg.
    Creates genuine depth even without real gradients.
    """
    def __init__(self, parent, depth='raised', **kwargs):
        # depth: 'raised' (button-like) | 'sunken' (input-like) | 'flat'
        fg   = kwargs.pop('fg_color', C['sf'])
        cr   = kwargs.pop('corner_radius', 8)
        bw   = kwargs.pop('border_width', 0)

        if depth == 'raised':
            outer_col = C['brd']    # shadow wraps whole widget
            inner_col = C['brt']    # highlight on top/left
        elif depth == 'sunken':
            outer_col = C['brt']
            inner_col = C['brd']
        else:
            outer_col = C['br']
            inner_col = C['br']

        # Outer shadow shell
        super().__init__(
            parent,
            fg_color=outer_col,
            corner_radius=cr + 1,
            border_width=0,
            **kwargs
        )
        # Highlight ring inside shadow
        self._mid = ctk.CTkFrame(
            self, fg_color=inner_col,
            corner_radius=cr, border_width=0)
        self._mid.pack(fill='both', expand=True,
                       padx=(1, 0), pady=(1, 0))   # top-left highlight offset
        # Content surface
        self._inner = ctk.CTkFrame(
            self._mid, fg_color=fg,
            corner_radius=max(0, cr - 1), border_width=0)
        self._inner.pack(fill='both', expand=True,
                         padx=(0, 1), pady=(0, 1))  # bottom-right shadow offset

    def get_content(self):
        """Return the inner content frame to pack children into."""
        return self._inner


# ── Card ──────────────────────────────────────────────────────────

class Card(ctk.CTkFrame):
    """
    Raised card with 3D bevel border: bright top edge, dark bottom edge.
    Card IS the content surface — bevel layers are sibling frames managed
    by a transparent outer shell stored on self._shell.
    Children placed into Card() land directly on the styled content surface.
    """
    def __init__(self, parent, accent=None, **kwargs):
        fg = kwargs.pop('fg_color', C['sf'])
        cr = kwargs.pop('corner_radius', 10)
        kwargs.pop('border_color', None)
        kwargs.pop('border_width', None)

        # Outer shadow shell (holds bevel layers + content, NOT a tkinter master for children)
        self._shell = ctk.CTkFrame(
            parent,
            fg_color=C['brd'],
            corner_radius=cr + 2,
            border_width=0,
        )

        # Top-left highlight ring inside shell
        self._hl = ctk.CTkFrame(
            self._shell,
            fg_color=accent or C['brt'],
            corner_radius=cr + 1,
            border_width=0
        )
        self._hl.pack(fill='both', expand=True, padx=(1, 0), pady=(1, 0))

        # Accent line (1px top) if accent colour given
        if accent:
            ctk.CTkFrame(self._hl, height=2,
                         fg_color=accent,
                         corner_radius=0).pack(fill='x', side='top')

        # Card IS the content surface — children pack into self directly
        super().__init__(
            self._hl,
            fg_color=fg,
            corner_radius=cr,
            border_width=0
        )
        super().pack(fill='both', expand=True, padx=(0, 1), pady=(0, 1))

    # pack/grid/place operate on the outer shell so the full bevel is positioned
    def pack(self, **kwargs):
        self._shell.pack(**kwargs)
        return self

    def pack_forget(self):
        self._shell.pack_forget()

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

    def configure(self, **kwargs):
        # Route fg_color to the content surface (self)
        super().configure(**kwargs)

    @property
    def interior(self):
        """Convenience — Card itself is the content surface."""
        return self


# ── SectionHeader ─────────────────────────────────────────────────

class SectionHeader(ctk.CTkFrame):
    def __init__(self, parent, num, title, **kwargs):
        fg = kwargs.pop('fg_color', 'transparent')
        super().__init__(parent, fg_color=fg, **kwargs)

        # Number badge — raised pill
        num_bg = ctk.CTkFrame(
            self,
            fg_color=C['acg'],
            corner_radius=4,
            border_color=C['ac'],
            border_width=1
        )
        num_bg.pack(side='left', padx=(0, 8))
        ctk.CTkLabel(
            num_bg, text=f' {num} ',
            font=(FONT, 8, 'bold'), text_color=C['ac']
        ).pack(padx=2, pady=1)

        ctk.CTkLabel(
            self, text=title,
            font=(FONT, 10, 'bold'), text_color=C['mu2']
        ).pack(side='left')

        # Separator line with slight 3D sunken look
        sep = ctk.CTkFrame(self, fg_color='transparent')
        sep.pack(side='left', fill='x', expand=True, padx=(10, 0))
        ctk.CTkFrame(sep, height=1, fg_color=C['brd'],
                     corner_radius=0).pack(fill='x')
        ctk.CTkFrame(sep, height=1, fg_color=C['brt'],
                     corner_radius=0).pack(fill='x')


# ── InfoGrid ──────────────────────────────────────────────────────

class InfoGrid(ctk.CTkFrame):
    def __init__(self, parent, items, columns=2, **kwargs):
        fg = kwargs.pop('fg_color', 'transparent')
        super().__init__(parent, fg_color=fg, **kwargs)
        for i, item in enumerate(items):
            label = item[0]
            value = str(item[1]) if item[1] is not None else '—'
            color = item[2] if len(item) > 2 and item[2] else C['tx']
            col   = i % columns
            row   = i // columns

            # Outer shadow
            outer = ctk.CTkFrame(
                self, fg_color=C['brd'],
                corner_radius=8, border_width=0)
            outer.grid(row=row, column=col, padx=4, pady=4, sticky='nsew')
            # Highlight
            hl = ctk.CTkFrame(
                outer, fg_color=C['brt'],
                corner_radius=7, border_width=0)
            hl.pack(fill='both', expand=True, padx=(1,0), pady=(1,0))
            # Surface
            cell = ctk.CTkFrame(
                hl, fg_color=C['sf'],
                corner_radius=6, border_width=0)
            cell.pack(fill='both', expand=True, padx=(0,1), pady=(0,1))

            ctk.CTkLabel(
                cell, text=label,
                font=(FONT, 8), text_color=C['mu']
            ).pack(anchor='w', padx=10, pady=(7, 0))
            ctk.CTkLabel(
                cell, text=value,
                font=(FONT, 11, 'bold'), text_color=color, wraplength=200
            ).pack(anchor='w', padx=10, pady=(0, 7))

        for c in range(columns):
            self.grid_columnconfigure(c, weight=1)


# ── ResultBox ─────────────────────────────────────────────────────

class ResultBox(ctk.CTkFrame):
    def __init__(self, parent, rtype='ok', title='', body='', **kwargs):
        col = {
            'ok':   C['ok'],
            'warn': C['wn'],
            'info': C['bl'],
            'med':  C['am'],
        }.get(rtype, C['am'])
        glow = {
            'ok':   C['okg'],
            'warn': C['wng'],
            'info': C['acg'],
            'med':  C['amg'],
        }.get(rtype, C['amg'])

        kwargs.pop('fg_color', None)
        kwargs.pop('border_color', None)
        kwargs.pop('border_width', None)
        kwargs.pop('corner_radius', None)

        # Outer glow shadow
        super().__init__(
            parent,
            fg_color=col,
            corner_radius=10,
            border_width=0,
            **kwargs
        )
        # Inner tinted surface
        inner = ctk.CTkFrame(
            self, fg_color=glow,
            corner_radius=9, border_width=0)
        inner.pack(fill='both', expand=True, padx=1, pady=1)

        # Left accent bar
        bar_row = ctk.CTkFrame(inner, fg_color='transparent')
        bar_row.pack(fill='both', expand=True)
        ctk.CTkFrame(
            bar_row, width=3, fg_color=col,
            corner_radius=0
        ).pack(side='left', fill='y', padx=(8, 0))
        text_col = ctk.CTkFrame(bar_row, fg_color='transparent')
        text_col.pack(side='left', fill='both', expand=True, padx=8)
        ctk.CTkLabel(
            text_col, text=title,
            font=(FONT, 10, 'bold'), text_color=col
        ).pack(anchor='w', pady=(8, 2))
        if body:
            ctk.CTkLabel(
                text_col, text=body,
                font=(FONT, 10), text_color=C['mu2'],
                wraplength=640, justify='left'
            ).pack(anchor='w', pady=(0, 8))


# ── Btn ───────────────────────────────────────────────────────────

class Btn(ctk.CTkButton):
    """
    3D-raised button: uses fg_color fill + bottom shadow via border trick.
    Primary and status buttons show a solid raised look.
    Ghost buttons appear as flat inset panels.
    """
    def __init__(self, parent, label, command=None,
                 variant='primary', width=140, **kwargs):
        VARIANTS = {
            'primary': {'fg': C['acg'],  'bc': C['ac'],  'tc': C['ac'],  'hc': C['br2']},
            'danger':  {'fg': C['wng'],  'bc': C['wn'],  'tc': C['wn'],  'hc': '#5a0000'},
            'warning': {'fg': C['amg'],  'bc': C['am'],  'tc': C['am'],  'hc': '#5a3d00'},
            'success': {'fg': C['okg'],  'bc': C['ok'],  'tc': C['ok'],  'hc': '#004d20'},
            'ghost':   {'fg': C['bg'],   'bc': C['br'],  'tc': C['mu'],  'hc': C['sf']},
            'blue':    {'fg': C['acg'],  'bc': C['bl'],  'tc': C['bl'],  'hc': C['br2']},
        }
        v = VARIANTS.get(variant, VARIANTS['primary'])

        fg = kwargs.pop('fg_color',    v['fg'])
        bc = kwargs.pop('border_color', v['bc'])
        bw = kwargs.pop('border_width', 1)
        tc = kwargs.pop('text_color',   v['tc'])
        hc = kwargs.pop('hover_color',  v['hc'])
        cr = kwargs.pop('corner_radius', 6)
        ht = kwargs.pop('height', 34)
        wd = kwargs.pop('width', width)

        super().__init__(
            parent,
            text=label,
            font=(FONT, 9, 'bold'),
            fg_color=fg,
            border_color=bc,
            border_width=bw,
            text_color=tc,
            hover_color=hc,
            corner_radius=cr,
            height=ht,
            width=wd,
            command=command,
            **kwargs
        )

    def configure(self, **kwargs):
        if 'variant' in kwargs:
            variant = kwargs.pop('variant')
            VARIANTS = {
                'primary': (C['acg'], C['ac'],  C['ac']),
                'danger':  (C['wng'], C['wn'],  C['wn']),
                'warning': (C['amg'], C['am'],  C['am']),
                'success': (C['okg'], C['ok'],  C['ok']),
                'ghost':   (C['bg'],  C['br'],  C['mu']),
                'blue':    (C['acg'], C['bl'],  C['bl']),
            }
            fg, bc, tc = VARIANTS.get(variant, (C['acg'], C['ac'], C['ac']))
            kwargs['fg_color']    = fg
            kwargs['border_color'] = bc
            kwargs['text_color']   = tc
        super().configure(**kwargs)


# ── Badge ─────────────────────────────────────────────────────────

class Badge(ctk.CTkFrame):
    def __init__(self, parent, label, color, **kwargs):
        kwargs.pop('fg_color', None)
        kwargs.pop('border_color', None)
        kwargs.pop('border_width', None)
        kwargs.pop('corner_radius', None)

        # Glow outer
        glow = {C['ok']: C['okg'], C['wn']: C['wng'],
                C['am']: C['amg'], C['bl']: C['acg']}.get(color, C['acg'])
        super().__init__(
            parent, fg_color=color,
            corner_radius=5, border_width=0, **kwargs)
        inner = ctk.CTkFrame(
            self, fg_color=glow,
            corner_radius=4, border_width=0)
        inner.pack(fill='both', expand=True, padx=1, pady=1)
        ctk.CTkLabel(
            inner, text=label,
            font=(FONT, 8, 'bold'), text_color=color
        ).pack(padx=6, pady=2)


# ── LiveBadge ─────────────────────────────────────────────────────

class LiveBadge(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        fg = kwargs.pop('fg_color', 'transparent')
        super().__init__(parent, fg_color=fg, **kwargs)
        # Pulsing glow dot
        self._dot_frame = ctk.CTkFrame(
            self, fg_color=C['okg'],
            corner_radius=6, width=12, height=12)
        self._dot_frame.pack(side='left', padx=(0, 4))
        self._dot_frame.pack_propagate(False)
        self._dot = ctk.CTkLabel(
            self._dot_frame, text='●',
            font=(FONT, 8), text_color=C['ok'])
        self._dot.pack(expand=True)
        ctk.CTkLabel(
            self, text='LIVE',
            font=(FONT, 8, 'bold'), text_color=C['ok']
        ).pack(side='left')
        self._on = True
        self._pulse()

    def _pulse(self):
        self._on = not self._on
        col = C['ok'] if self._on else C['mu']
        self._dot.configure(text_color=col)
        try:
            self.after(800, self._pulse)
        except Exception:
            pass


# ── PortBar ───────────────────────────────────────────────────────

class PortBar(ctk.CTkFrame):
    def __init__(self, parent, port, proto, state, process, **kwargs):
        RISK = {'23': 'Telnet', '4444': 'Metasploit', '1337': 'Suspicious'}
        WARN = {'21': 'FTP', '25': 'SMTP', '3306': 'MySQL',
                '27017': 'MongoDB', '6379': 'Redis'}
        SVCS = {
            '20': 'FTP-Data', '21': 'FTP',    '22': 'SSH',
            '23': 'Telnet',   '25': 'SMTP',   '53': 'DNS',
            '80': 'HTTP',     '443': 'HTTPS', '3306': 'MySQL',
            '5432': 'PgSQL',  '6379': 'Redis','8080': 'HTTP-Alt',
            '27017': 'MongoDB','4444': 'Meterp!','1337': 'Suspic!',
        }
        col  = C['wn'] if port in RISK else C['am'] if port in WARN else C['mu']
        glow = C['wng'] if port in RISK else C['amg'] if port in WARN else C['sf']

        kwargs.pop('fg_color', None)
        kwargs.pop('border_color', None)
        kwargs.pop('border_width', None)
        kwargs.pop('corner_radius', None)

        # Outer glow border
        super().__init__(
            parent, fg_color=col,
            corner_radius=9, border_width=0, **kwargs)
        inner = ctk.CTkFrame(
            self, fg_color=glow,
            corner_radius=8, border_width=0)
        inner.pack(fill='both', expand=True, padx=1, pady=1)

        top = ctk.CTkFrame(inner, fg_color='transparent')
        top.pack(fill='x', padx=10, pady=(8, 2))
        ctk.CTkLabel(
            top, text=f':{port}',
            font=(FONT, 13, 'bold'), text_color=col
        ).pack(side='left')
        ctk.CTkLabel(
            top, text=f"  {SVCS.get(port, 'Unknown')}",
            font=(FONT, 10), text_color=C['tx']
        ).pack(side='left')
        ctk.CTkLabel(
            top, text=proto,
            font=(FONT, 9), text_color=C['mu']
        ).pack(side='right')
        ctk.CTkLabel(
            inner,
            text=f'Process: {process}  State: {state}',
            font=(FONT, 9), text_color=C['mu']
        ).pack(anchor='w', padx=10, pady=(0, 7))


# ═══════════════════════════════════════════════════════════════════
#  ENHANCED UI COMPONENTS  — animations, glows, sparklines
# ═══════════════════════════════════════════════════════════════════

import math as _math


class PulseIndicator(ctk.CTkFrame):
    """
    Animated pulsing status dot.
    Colors: use C['ok'], C['wn'], C['am'], C['ac'], C['mu'].
    """
    def __init__(self, parent, color=None, size=10, **kw):
        super().__init__(parent, fg_color='transparent',
                         width=size+6, height=size+6, **kw)
        self._color  = color or C['ok']
        self._size   = size
        self._on     = True
        self._dot    = ctk.CTkFrame(self, width=size, height=size,
                                    fg_color=self._color, corner_radius=size)
        self._dot.place(relx=0.5, rely=0.5, anchor='center')
        self._tick()

    def set_color(self, color):
        self._color = color
        self._dot.configure(fg_color=color)

    def _tick(self):
        try:
            if not self.winfo_exists(): return
            self._on = not self._on
            self._dot.configure(fg_color=self._color if self._on else C['br'])
            self.after(600, self._tick)
        except Exception: pass


class SparkLine(tk.Canvas):
    """
    Tiny rolling line chart for CPU/memory history.
    """
    def __init__(self, parent, width=80, height=28, color=None, **kw):
        bg = C['bg']
        super().__init__(parent, width=width, height=height,
                         bg=bg, highlightthickness=0, **kw)
        self._w      = width
        self._h      = height
        self._color  = color or C['ac']
        self._data   = []
        self._max    = 100

    def push(self, value):
        self._data.append(float(value))
        if len(self._data) > self._w // 3:
            self._data.pop(0)
        self._draw()

    def _draw(self):
        self.delete('all')
        if len(self._data) < 2:
            return
        mx  = max(self._data) or 1
        pts = []
        n   = len(self._data)
        for i, v in enumerate(self._data):
            x = int(i * (self._w / (n - 1)))
            y = int(self._h - (v / mx) * (self._h - 4) - 2)
            pts.append((x, y))
        # Fill area under line
        fill_pts = [(0, self._h)] + pts + [(self._w, self._h)]
        flat = [c for xy in fill_pts for c in xy]
        try:
            # Dim fill color
            r, g, b = int(self._color[1:3],16), int(self._color[3:5],16), int(self._color[5:7],16)
            fill_col = f'#{r//5:02x}{g//5:02x}{b//5:02x}'
            self.create_polygon(flat, fill=fill_col, outline='')
        except Exception:
            pass
        # Line
        flat_line = [c for xy in pts for c in xy]
        if len(flat_line) >= 4:
            self.create_line(flat_line, fill=self._color, width=1, smooth=True)


class AnimatedProgressBar(ctk.CTkFrame):
    """
    Progress bar that animates smoothly to target value.
    """
    def __init__(self, parent, color=None, height=6, **kw):
        super().__init__(parent, fg_color='transparent', **kw)
        self._target = 0.0
        self._current = 0.0
        self._bar = ctk.CTkProgressBar(self, height=height,
                                        progress_color=color or C['ac'],
                                        fg_color=C['br'])
        self._bar.pack(fill='x')
        self._bar.set(0)

    def set_value(self, v):
        self._target = max(0.0, min(1.0, float(v)))
        self._animate()

    def _animate(self):
        diff = self._target - self._current
        if abs(diff) > 0.005:
            self._current += diff * 0.18
            try:
                self._bar.set(self._current)
                self.after(16, self._animate)
            except Exception:
                pass
        else:
            self._current = self._target
            try:
                self._bar.set(self._current)
            except Exception:
                pass


class GlowLabel(ctk.CTkLabel):
    """
    Label that fades in from transparent to full color.
    Call .fade_in() to trigger animation.
    """
    def __init__(self, parent, text, color=None, fade=True, **kw):
        self._target_color = color or C['tx']
        kw.setdefault('text_color', C['bg'])   # start invisible
        super().__init__(parent, text=text, **kw)
        if fade:
            self._step = 0
            self.after(30, self._do_fade)

    def fade_in(self):
        self._step = 0
        self.after(30, self._do_fade)

    def _do_fade(self):
        try:
            if not self.winfo_exists(): return
            self._step = min(self._step + 0.08, 1.0)
            col  = self._target_color
            bg   = C['bg']
            # Lerp bg→col
            def _lerp(a, b, t):
                return int(int(a,16) + (int(b,16)-int(a,16))*t)
            r = _lerp(bg[1:3], col[1:3], self._step)
            g = _lerp(bg[3:5], col[3:5], self._step)
            b_ = _lerp(bg[5:7], col[5:7], self._step)
            self.configure(text_color=f'#{r:02x}{g:02x}{b_:02x}')
            if self._step < 1.0:
                self.after(16, self._do_fade)
        except Exception:
            pass


class StatusChip(ctk.CTkFrame):
    """
    Compact status chip: colored border + icon + text.
    status: 'ok' | 'warn' | 'error' | 'info' | 'active'
    """
    _STATUS = {
        'ok':     (C['ok'],  C['okg'],  '✓'),
        'warn':   (C['am'],  C['amg'],  '⚠'),
        'error':  (C['wn'],  C['wng'],  '✗'),
        'info':   (C['bl'],  C['acg'],  'ℹ'),
        'active': (C['ac'],  C['acg'],  '●'),
    }

    def __init__(self, parent, status='ok', text='', **kw):
        col, bg, icon = self._STATUS.get(status, self._STATUS['info'])
        kw.pop('fg_color', None)
        super().__init__(parent, fg_color=bg,
                         border_color=col, border_width=1,
                         corner_radius=5, **kw)
        row = ctk.CTkFrame(self, fg_color='transparent')
        row.pack(padx=8, pady=3)
        ctk.CTkLabel(row, text=icon, font=(FONT, 9, 'bold'),
                     text_color=col).pack(side='left', padx=(0,4))
        ctk.CTkLabel(row, text=text, font=(FONT, 9, 'bold'),
                     text_color=col).pack(side='left')


class ScannerRow(ctk.CTkFrame):
    """
    Animated scan-progress row for device/network scanners.
    Shows IP + a moving progress line while scanning.
    """
    def __init__(self, parent, ip, **kw):
        super().__init__(parent, fg_color=C['sf'],
                         border_color=C['br'], border_width=1,
                         corner_radius=6, **kw)
        self._scanning = True
        self._pos      = 0

        row = ctk.CTkFrame(self, fg_color='transparent')
        row.pack(fill='x', padx=10, pady=4)

        ctk.CTkLabel(row, text='⟳', font=(FONT, 11),
                     text_color=C['ac']).pack(side='left', padx=(0,6))
        ctk.CTkLabel(row, text=ip, font=(FONT, 10, 'bold'),
                     text_color=C['tx']).pack(side='left')
        self._status = ctk.CTkLabel(row, text='scanning…',
                                     font=(FONT, 9), text_color=C['mu'])
        self._status.pack(side='right')

        self._prog = ctk.CTkProgressBar(self, height=2,
                                         progress_color=C['ac'],
                                         fg_color=C['br'])
        self._prog.pack(fill='x', padx=0, pady=0)
        self._prog.set(0)
        self._tick()

    def done(self, text='done', color=None):
        self._scanning = False
        try:
            self._status.configure(text=text, text_color=color or C['ok'])
            self._prog.set(1.0)
        except Exception: pass

    def _tick(self):
        if not self._scanning: return
        try:
            if not self.winfo_exists(): return
            self._pos = (self._pos + 0.03) % 1.0
            # ping-pong
            v = abs(_math.sin(self._pos * _math.pi))
            self._prog.set(v)
            self.after(40, self._tick)
        except Exception: pass


class ToastNotification(ctk.CTkFrame):
    """
    Slide-in toast notification that auto-dismisses.
    """
    def __init__(self, parent, message, status='info', duration=4000):
        col = {'ok': C['ok'], 'warn': C['am'], 'error': C['wn'],
               'info': C['ac']}.get(status, C['ac'])
        super().__init__(parent, fg_color=C['sf'],
                         border_color=col, border_width=1,
                         corner_radius=8)
        ctk.CTkLabel(self, text=message, font=(FONT, 10),
                     text_color=col, wraplength=300).pack(padx=16, pady=10)
        # Auto-destroy
        self.after(duration, self._dismiss)

    def _dismiss(self):
        try:
            self.destroy()
        except Exception:
            pass


class DeviceCard(ctk.CTkFrame):
    """
    Rich device card for the device scanner with icon, IP, vendor, risk badge.
    """
    def __init__(self, parent, device: dict, **kw):
        risk_col = C['wn'] if device.get('infected') else C['ok']
        kw.pop('fg_color', None)
        super().__init__(parent, fg_color=C['sf'],
                         border_color=risk_col, border_width=1,
                         corner_radius=8, **kw)
        # Top row: icon + IP + hostname
        top = ctk.CTkFrame(self, fg_color='transparent')
        top.pack(fill='x', padx=10, pady=(8,4))

        icon = device.get('icon', '❓')
        ctk.CTkLabel(top, text=icon,
                     font=(FONT, 22)).pack(side='left', padx=(0,10))

        info = ctk.CTkFrame(top, fg_color='transparent')
        info.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(info, text=device.get('ip','—'),
                     font=(FONT, 13, 'bold'),
                     text_color=C['ac']).pack(anchor='w')
        host = device.get('host') or device.get('vendor') or device.get('type','Unknown')
        ctk.CTkLabel(info, text=host,
                     font=(FONT, 9), text_color=C['mu']).pack(anchor='w')

        # Risk badge
        if device.get('infected'):
            StatusChip(top, status='error', text='RISK').pack(side='right')
        else:
            StatusChip(top, status='ok', text='CLEAN').pack(side='right')

        # Details row
        det = ctk.CTkFrame(self, fg_color='transparent')
        det.pack(fill='x', padx=10, pady=(0,6))

        for label, val in [
            ('TYPE',   device.get('type','Unknown')),
            ('MAC',    device.get('mac','—')    or '—'),
            ('VENDOR', device.get('vendor','—') or '—'),
            ('PORTS',  str(len(device.get('ports',[]))) + ' open'),
        ]:
            c2 = ctk.CTkFrame(det, fg_color='transparent')
            c2.pack(side='left', padx=10)
            ctk.CTkLabel(c2, text=label,
                         font=(FONT, 7, 'bold'), text_color=C['mu']).pack(anchor='w')
            ctk.CTkLabel(c2, text=val,
                         font=(FONT, 9, 'bold'), text_color=C['tx']).pack(anchor='w')

        # Infection warnings
        for reason in device.get('infect_reasons', [])[:3]:
            ctk.CTkFrame(self, height=1, fg_color=C['br']).pack(fill='x', padx=10)
            ctk.CTkLabel(self, text=f'⚠  {reason}',
                         font=(FONT, 8), text_color=C['wn']
                         ).pack(anchor='w', padx=12, pady=2)
