"""
Mint Scan v8 — Shared Widgets
3D visual system: bevel borders via Canvas overlays, glow accents, raised surfaces.
All widget classes are standard CTkFrame subclasses — no delegation tricks.
DejaVu Sans Mono throughout for crisp rendering.
"""
import tkinter as tk
import customtkinter as ctk

# ── Theme palettes ────────────────────────────────────────────────
DARK_THEME = {
    # Depth layers
    'bg':  '#030f1c',
    'sf':  '#081c2e',
    's2':  '#0c2540',
    # Bevel edges
    'brt': '#1e4a6a',
    'brd': '#010810',
    # Borders
    'br':  '#163352',
    'br2': '#1e4a6a',
    # Accent
    'ac':  '#00ffe0',
    'acg': '#00241e',
    # Status
    'wn':  '#ff4444', 'am':  '#ffbb33', 'ok':  '#33ff88',
    'bl':  '#44aaff', 'pu':  '#bb77ff',
    # Status glows
    'wng': '#2a0000', 'amg': '#2a1e00', 'okg': '#002a14',
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
    sf = os.path.expanduser('~/.mint_scan_settings.json')
    try:
        if os.path.exists(sf):
            with open(sf) as f:
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
        super().__init__(master=parent, fg_color=fg,
                         scrollbar_button_color=sbc,
                         scrollbar_button_hover_color=sbhc,
                         corner_radius=cr, **kwargs)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, event=None):
        self._tl = self.winfo_toplevel()
        self._tl.bind_all('<MouseWheel>', self._on_mw,  add='+')
        self._tl.bind_all('<Button-4>',   self._scroll_up,   add='+')
        self._tl.bind_all('<Button-5>',   self._scroll_down, add='+')

    def _on_leave(self, event=None):
        try:
            self._tl.unbind_all('<MouseWheel>')
            self._tl.unbind_all('<Button-4>')
            self._tl.unbind_all('<Button-5>')
        except Exception:
            pass

    def _on_mw(self, event):
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


# ── Card ─────────────────────────────────────────────────────────
# IMPORTANT: Card IS a direct CTkFrame subclass.
# No __getattr__, no _w property — children pack directly into it.
# 3D bevel is drawn by a transparent Canvas overlay on top.

class Card(ctk.CTkFrame):
    """
    Raised card with 3D bevel effect.
    Children pack/grid directly into this frame (standard CTkFrame behaviour).
    The 3D bevel is a Canvas drawn on top of the content, pointer-transparent.
    """
    def __init__(self, parent, accent=None, **kwargs):
        fg = kwargs.pop('fg_color', C['sf'])
        kwargs.pop('border_color', None)
        kwargs.pop('border_width', None)
        cr = kwargs.pop('corner_radius', 8)

        super().__init__(parent,
                         fg_color=fg,
                         border_color=C['brt'],
                         border_width=1,
                         corner_radius=cr,
                         **kwargs)
        self._accent = accent
        self._cr     = cr

        # Accent stripe at top (if accent colour given)
        if accent:
            self._stripe = ctk.CTkFrame(self, height=2,
                                        fg_color=accent,
                                        corner_radius=0)
            self._stripe.place(relx=0, rely=0, relwidth=1)

        # Bottom shadow line
        self._shadow = ctk.CTkFrame(self, height=1,
                                    fg_color=C['brd'],
                                    corner_radius=0)
        self._shadow.place(relx=0, rely=1.0, anchor='sw', relwidth=1)


# ── SectionHeader ─────────────────────────────────────────────────

class SectionHeader(ctk.CTkFrame):
    def __init__(self, parent, num, title, **kwargs):
        fg = kwargs.pop('fg_color', 'transparent')
        super().__init__(parent, fg_color=fg, **kwargs)

        # Raised number badge
        badge = ctk.CTkFrame(self,
                             fg_color=C['acg'],
                             corner_radius=4,
                             border_color=C['ac'],
                             border_width=1)
        badge.pack(side='left', padx=(0, 8))
        ctk.CTkLabel(badge, text=f' {num} ',
                     font=(FONT, 8, 'bold'),
                     text_color=C['ac']).pack(padx=2, pady=1)

        ctk.CTkLabel(self, text=title,
                     font=(FONT, 10, 'bold'),
                     text_color=C['mu2']).pack(side='left')

        # Double-line sunken separator
        sep = ctk.CTkFrame(self, fg_color='transparent')
        sep.pack(side='left', fill='x', expand=True, padx=(10, 0))
        ctk.CTkFrame(sep, height=1, fg_color=C['brd'], corner_radius=0).pack(fill='x')
        ctk.CTkFrame(sep, height=1, fg_color=C['brt'], corner_radius=0).pack(fill='x')


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

            cell = ctk.CTkFrame(self,
                                fg_color=C['sf'],
                                border_color=C['brt'],
                                border_width=1,
                                corner_radius=7)
            cell.grid(row=row, column=col, padx=4, pady=4, sticky='nsew')

            # Bottom shadow on each cell
            ctk.CTkFrame(cell, height=1, fg_color=C['brd'],
                         corner_radius=0).place(relx=0, rely=1.0,
                                                anchor='sw', relwidth=1)

            ctk.CTkLabel(cell, text=label,
                         font=(FONT, 8),
                         text_color=C['mu']).pack(anchor='w', padx=10, pady=(7, 0))
            ctk.CTkLabel(cell, text=value,
                         font=(FONT, 11, 'bold'),
                         text_color=color,
                         wraplength=200).pack(anchor='w', padx=10, pady=(0, 7))

        for c in range(columns):
            self.grid_columnconfigure(c, weight=1)


# ── ResultBox ─────────────────────────────────────────────────────

class ResultBox(ctk.CTkFrame):
    def __init__(self, parent, rtype='ok', title='', body='', **kwargs):
        col = {'ok': C['ok'], 'warn': C['wn'],
               'info': C['bl'], 'med': C['am']}.get(rtype, C['am'])
        glow = {'ok': C['okg'], 'warn': C['wng'],
                'info': C['acg'], 'med': C['amg']}.get(rtype, C['amg'])

        kwargs.pop('fg_color', None)
        kwargs.pop('border_color', None)
        kwargs.pop('border_width', None)
        kwargs.pop('corner_radius', None)

        super().__init__(parent,
                         fg_color=glow,
                         border_color=col,
                         border_width=1,
                         corner_radius=9,
                         **kwargs)
        # Left accent bar
        ctk.CTkFrame(self, width=3, fg_color=col,
                     corner_radius=0).place(x=0, rely=0,
                                            relheight=1)
        inner = ctk.CTkFrame(self, fg_color='transparent')
        inner.pack(fill='both', expand=True, padx=(10, 4))
        ctk.CTkLabel(inner, text=title,
                     font=(FONT, 10, 'bold'),
                     text_color=col).pack(anchor='w', pady=(8, 2))
        if body:
            ctk.CTkLabel(inner, text=body,
                         font=(FONT, 10),
                         text_color=C['mu2'],
                         wraplength=640,
                         justify='left').pack(anchor='w', pady=(0, 8))


# ── Btn ───────────────────────────────────────────────────────────

class Btn(ctk.CTkButton):
    def __init__(self, parent, label, command=None,
                 variant='primary', width=140, **kwargs):
        V = {
            'primary': (C['acg'], C['ac'],  C['ac'],  C['br2']),
            'danger':  (C['wng'], C['wn'],  C['wn'],  '#3a0000'),
            'warning': (C['amg'], C['am'],  C['am'],  '#3a2800'),
            'success': (C['okg'], C['ok'],  C['ok'],  '#003a18'),
            'ghost':   (C['bg'],  C['br'],  C['mu'],  C['sf']),
            'blue':    (C['acg'], C['bl'],  C['bl'],  C['br2']),
        }
        fg, bc, tc, hc = V.get(variant, V['primary'])
        fg = kwargs.pop('fg_color',     fg)
        bc = kwargs.pop('border_color', bc)
        bw = kwargs.pop('border_width', 1)
        tc = kwargs.pop('text_color',   tc)
        hc = kwargs.pop('hover_color',  hc)
        cr = kwargs.pop('corner_radius', 6)
        ht = kwargs.pop('height', 34)
        wd = kwargs.pop('width', width)
        super().__init__(parent,
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
                         **kwargs)

    def configure(self, **kwargs):
        if 'variant' in kwargs:
            v = kwargs.pop('variant')
            V = {
                'primary': (C['acg'], C['ac'],  C['ac']),
                'danger':  (C['wng'], C['wn'],  C['wn']),
                'warning': (C['amg'], C['am'],  C['am']),
                'success': (C['okg'], C['ok'],  C['ok']),
                'ghost':   (C['bg'],  C['br'],  C['mu']),
                'blue':    (C['acg'], C['bl'],  C['bl']),
            }
            fg, bc, tc = V.get(v, V['primary'])
            kwargs.update(fg_color=fg, border_color=bc, text_color=tc)
        super().configure(**kwargs)


# ── Badge ─────────────────────────────────────────────────────────

class Badge(ctk.CTkFrame):
    def __init__(self, parent, label, color, **kwargs):
        _gmap = {C['ok']: C['okg'], C['wn']: C['wng'],
                 C['am']: C['amg'], C['bl']: C['acg']}
        glow = _gmap.get(color, C['acg'])
        kwargs.pop('fg_color', None); kwargs.pop('border_color', None)
        kwargs.pop('border_width', None); kwargs.pop('corner_radius', None)
        super().__init__(parent, fg_color=glow,
                         border_color=color, border_width=1,
                         corner_radius=5, **kwargs)
        ctk.CTkLabel(self, text=label,
                     font=(FONT, 8, 'bold'),
                     text_color=color).pack(padx=6, pady=2)


# ── LiveBadge ─────────────────────────────────────────────────────

class LiveBadge(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        fg = kwargs.pop('fg_color', 'transparent')
        super().__init__(parent, fg_color=fg, **kwargs)
        self._dot = ctk.CTkLabel(self, text='●',
                                  font=(FONT, 10), text_color=C['ok'])
        self._dot.pack(side='left')
        ctk.CTkLabel(self, text='LIVE',
                     font=(FONT, 8, 'bold'),
                     text_color=C['ok']).pack(side='left', padx=2)
        self._on = True
        self._pulse()

    def _pulse(self):
        self._on = not self._on
        self._dot.configure(text_color=C['ok'] if self._on else C['mu'])
        try: self.after(800, self._pulse)
        except Exception: pass


# ── PortBar ───────────────────────────────────────────────────────

class PortBar(ctk.CTkFrame):
    def __init__(self, parent, port, proto, state, process, **kwargs):
        RISK = {'23', '4444', '1337'}
        WARN = {'21', '25', '3306', '27017', '6379'}
        SVCS = {
            '20': 'FTP-Data', '21': 'FTP',    '22': 'SSH',
            '23': 'Telnet',   '25': 'SMTP',   '53': 'DNS',
            '80': 'HTTP',     '443': 'HTTPS', '3306': 'MySQL',
            '5432': 'PgSQL',  '6379': 'Redis','8080': 'HTTP-Alt',
            '27017': 'MongoDB','4444':'Meterp!','1337':'Suspic!',
        }
        col  = C['wn'] if port in RISK else C['am'] if port in WARN else C['mu']
        glow = C['wng'] if port in RISK else C['amg'] if port in WARN else C['sf']

        kwargs.pop('fg_color', None); kwargs.pop('border_color', None)
        kwargs.pop('border_width', None); kwargs.pop('corner_radius', None)

        super().__init__(parent, fg_color=glow,
                         border_color=col, border_width=1,
                         corner_radius=8, **kwargs)
        top = ctk.CTkFrame(self, fg_color='transparent')
        top.pack(fill='x', padx=10, pady=(8, 2))
        ctk.CTkLabel(top, text=f':{port}',
                     font=(FONT, 13, 'bold'),
                     text_color=col).pack(side='left')
        ctk.CTkLabel(top, text=f"  {SVCS.get(port, 'Unknown')}",
                     font=(FONT, 10),
                     text_color=C['tx']).pack(side='left')
        ctk.CTkLabel(top, text=proto,
                     font=(FONT, 9),
                     text_color=C['mu']).pack(side='right')
        ctk.CTkLabel(self,
                     text=f'Process: {process}  State: {state}',
                     font=(FONT, 9),
                     text_color=C['mu']).pack(anchor='w', padx=10, pady=(0, 7))
