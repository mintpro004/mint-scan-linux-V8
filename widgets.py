"""
Mint Scan v7 — Shared Widgets
Uses CTkScrollableFrame (simple + reliable) with proper mouse wheel binding.
Dark / light theme support included.
"""
import tkinter as tk
import customtkinter as ctk

# ── Theme palettes ────────────────────────────────────────────────
DARK_THEME = {
    # Backgrounds
    'bg':  '#05111f', 'sf':  '#0a1f35', 's2':  '#0f2847',
    # Borders
    'br':  '#1a3f5c', 'br2': '#2a5a7a',
    # Accent
    'ac':  '#00ffe0',
    # Status
    'wn':  '#ff5555', 'am':  '#ffcc44', 'ok':  '#44ff99',
    'bl':  '#55aaff', 'pu':  '#cc88ff',
    # Text — high contrast for readability
    'tx':  '#e8f4ff',
    'mu':  '#7fb8d8',
    'mu2': '#9ecce8',
}
LIGHT_THEME = {
    'bg':  '#f0f4f8', 'sf':  '#e2e8f0', 's2':  '#ffffff',
    'br':  '#c0cfe0', 'br2': '#8aabb8', 'ac':  '#006ec0',
    'wn':  '#cc1111', 'am':  '#cc7700', 'ok':  '#117744',
    'bl':  '#1155cc', 'pu':  '#6622bb', 'tx':  '#0d1f2d',
    'mu':  '#3a5a70', 'mu2': '#2d4a60',
}

C = dict(DARK_THEME)
MONO    = ('Courier', 11)
MONO_SM = ('Courier', 10)
MONO_LG = ('Courier', 14, 'bold')
MONO_XL = ('Courier', 38, 'bold')
_current_theme = 'dark'


def get_theme():
    return _current_theme


def apply_theme(name, accent=None, font_size=10):
    global _current_theme, MONO, MONO_SM, MONO_LG, MONO_XL
    _current_theme = name
    
    # Update color dictionary
    base_colors = LIGHT_THEME if name == 'light' else DARK_THEME
    C.update(base_colors)
    if accent:
        C['ac'] = accent
        
    # Update font constants
    fs = font_size
    MONO    = ('Courier', fs)
    MONO_SM = ('Courier', max(7, fs - 1))
    MONO_LG = ('Courier', fs + 3, 'bold')
    MONO_XL = ('Courier', fs + 26, 'bold')
    
    try:
        ctk.set_appearance_mode('light' if name == 'light' else 'dark')
    except Exception:
        pass


def load_theme_settings():
    """Helper to load and apply all settings at once"""
    import json, os
    settings_file = os.path.expanduser('~/.mint_scan_settings.json')
    try:
        if os.path.exists(settings_file):
            with open(settings_file) as f:
                s = json.load(f)
                theme = s.get('theme', 'dark')
                accent = s.get('accent_color', None)
                font_size = s.get('font_size', 10)
                scale = s.get('ui_scale', 1.0)
                apply_theme(theme, accent, font_size)
                return scale
    except Exception:
        pass
    apply_theme('dark')
    return 1.0


# ── ScrollableFrame ───────────────────────────────────────────────
class ScrollableFrame(ctk.CTkScrollableFrame):
    """
    Scrollable container that works on Chromebook, Ubuntu, Kali, WSL.
    Mouse wheel and touchpad two-finger scroll both work.
    """
    def __init__(self, parent, **kwargs):
        fg = kwargs.pop('fg_color', C['bg'])
        sbc = kwargs.pop('scrollbar_button_color', C['br2'])
        sbhc = kwargs.pop('scrollbar_button_hover_color', C['ac'])
        cr = kwargs.pop('corner_radius', 0)
        super().__init__(
            master=parent,
            fg_color=fg,
            scrollbar_button_color=sbc,
            scrollbar_button_hover_color=sbhc,
            corner_radius=cr,
            **kwargs
        )
        # Bind mouse wheel when mouse enters this frame
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, event=None):
        # Bind to root window so scroll works anywhere inside
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
        # Windows/macOS: event.delta; Linux: Button-4/5
        try:
            if event.delta:
                self._canvas.yview_scroll(
                    int(-1 * (event.delta / 120)), 'units')
        except Exception:
            pass

    def _scroll_up(self, event):
        try:
            self._canvas.yview_scroll(-2, 'units')
        except Exception:
            pass

    def _scroll_down(self, event):
        try:
            self._canvas.yview_scroll(2, 'units')
        except Exception:
            pass


# ── Card ──────────────────────────────────────────────────────────
class Card(ctk.CTkFrame):
    def __init__(self, parent, accent=None, **kwargs):
        fg = kwargs.pop('fg_color', C['sf'])
        bc = kwargs.pop('border_color', accent or C['br'])
        bw = kwargs.pop('border_width', 1)
        cr = kwargs.pop('corner_radius', 8)
        super().__init__(
            parent,
            fg_color=fg,
            border_color=bc,
            border_width=bw,
            corner_radius=cr,
            **kwargs
        )


# ── SectionHeader ─────────────────────────────────────────────────
class SectionHeader(ctk.CTkFrame):
    def __init__(self, parent, num, title, **kwargs):
        fg = kwargs.pop('fg_color', 'transparent')
        super().__init__(parent, fg_color=fg, **kwargs)
        ctk.CTkLabel(
            self, text=f"[{num}]",
            font=MONO_SM, text_color=C['ac']
        ).pack(side='left', padx=(0, 6))
        ctk.CTkLabel(
            self, text=title,
            font=MONO_SM, text_color=C['mu2']
        ).pack(side='left')
        ctk.CTkFrame(
            self, height=1, fg_color=C['br']
        ).pack(side='left', fill='x', expand=True, padx=(8, 0))


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
            cell  = ctk.CTkFrame(
                self,
                fg_color=C['sf'],
                border_color=C['br'],
                border_width=1,
                corner_radius=6
            )
            cell.grid(row=row, column=col, padx=3, pady=3, sticky='nsew')
            ctk.CTkLabel(
                cell, text=label,
                font=('Courier', 7), text_color=C['mu']
            ).pack(anchor='w', padx=8, pady=(6, 0))
            ctk.CTkLabel(
                cell, text=value,
                font=MONO_SM, text_color=color, wraplength=200
            ).pack(anchor='w', padx=8, pady=(0, 6))
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
        fg = kwargs.pop('fg_color', C['s2'])
        bc = kwargs.pop('border_color', col)
        bw = kwargs.pop('border_width', 1)
        cr = kwargs.pop('corner_radius', 8)
        super().__init__(
            parent,
            fg_color=fg,
            border_color=bc,
            border_width=bw,
            corner_radius=cr,
            **kwargs
        )
        ctk.CTkLabel(
            self, text=title,
            font=('Courier', 10, 'bold'),
            text_color=col
        ).pack(anchor='w', padx=10, pady=(8, 2))
        if body:
            ctk.CTkLabel(
                self, text=body,
                font=MONO_SM, text_color=C['mu'],
                wraplength=640, justify='left'
            ).pack(anchor='w', padx=10, pady=(0, 8))


# ── Btn ───────────────────────────────────────────────────────────
class Btn(ctk.CTkButton):
    def __init__(self, parent, label, command=None,
                 variant='primary', width=140, **kwargs):
        VARIANTS = {
            'primary': (C['ac'], C['ac']),
            'danger':  (C['wn'], C['wn']),
            'warning': (C['am'], C['am']),
            'success': (C['ok'], C['ok']),
            'ghost':   (C['br'], C['mu']),
            'blue':    (C['bl'], C['bl']),
        }
        border_col, text_col = VARIANTS.get(variant, (C['ac'], C['ac']))
        
        fg = kwargs.pop('fg_color', 'transparent')
        bc = kwargs.pop('border_color', border_col)
        bw = kwargs.pop('border_width', 1)
        tc = kwargs.pop('text_color', text_col)
        hc = kwargs.pop('hover_color', C['br2'])
        cr = kwargs.pop('corner_radius', 4)
        ht = kwargs.pop('height', 36)
        wd = kwargs.pop('width', width)
        
        super().__init__(
            parent,
            text=label,
            font=('Courier', 9),
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
                'primary': (C['ac'], C['ac']),
                'danger':  (C['wn'], C['wn']),
                'warning': (C['am'], C['am']),
                'success': (C['ok'], C['ok']),
                'ghost':   (C['br'], C['mu']),
                'blue':    (C['bl'], C['bl']),
            }
            bc, tc = VARIANTS.get(variant, (C['ac'], C['ac']))
            kwargs['border_color'] = bc
            kwargs['text_color'] = tc
        super().configure(**kwargs)


# ── Badge ─────────────────────────────────────────────────────────
class Badge(ctk.CTkFrame):
    def __init__(self, parent, label, color, **kwargs):
        fg = kwargs.pop('fg_color', C['s2'])
        bc = kwargs.pop('border_color', color)
        bw = kwargs.pop('border_width', 1)
        cr = kwargs.pop('corner_radius', 3)
        super().__init__(
            parent,
            fg_color=fg,
            border_color=bc,
            border_width=bw,
            corner_radius=cr,
            **kwargs
        )
        ctk.CTkLabel(
            self, text=label,
            font=('Courier', 7, 'bold'),
            text_color=color
        ).pack(padx=6, pady=2)


# ── LiveBadge ─────────────────────────────────────────────────────
class LiveBadge(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        fg = kwargs.pop('fg_color', 'transparent')
        super().__init__(parent, fg_color=fg, **kwargs)
        self._dot = ctk.CTkLabel(
            self, text='●',
            font=('Courier', 10),
            text_color=C['ok']
        )
        self._dot.pack(side='left')
        ctk.CTkLabel(
            self, text='LIVE',
            font=('Courier', 8),
            text_color=C['ok']
        ).pack(side='left', padx=2)
        self._on = True
        self._pulse()

    def _pulse(self):
        self._on = not self._on
        self._dot.configure(text_color=C['ok'] if self._on else C['mu'])
        self.after(800, self._pulse)


# ── PortBar ───────────────────────────────────────────────────────
class PortBar(ctk.CTkFrame):
    def __init__(self, parent, port, proto, state, process, **kwargs):
        RISK = {'23': 'Telnet', '4444': 'Metasploit', '1337': 'Suspicious'}
        WARN = {'21': 'FTP', '25': 'SMTP', '3306': 'MySQL',
                '27017': 'MongoDB', '6379': 'Redis'}
        SVCS = {
            '20': 'FTP-Data', '21': 'FTP',      '22': 'SSH',
            '23': 'Telnet',   '25': 'SMTP',     '53': 'DNS',
            '80': 'HTTP',     '443': 'HTTPS',   '3306': 'MySQL',
            '5432': 'PgSQL',  '6379': 'Redis',  '8080': 'HTTP-Alt',
            '27017': 'MongoDB','4444': 'Meterp!','1337': 'Suspic!',
        }
        col = C['wn'] if port in RISK else C['am'] if port in WARN else C['mu']
        
        fg = kwargs.pop('fg_color', C['sf'])
        bc = kwargs.pop('border_color', col)
        bw = kwargs.pop('border_width', 1)
        cr = kwargs.pop('corner_radius', 6)
        
        super().__init__(
            parent,
            fg_color=fg,
            border_color=bc,
            border_width=bw,
            corner_radius=cr,
            **kwargs
        )
        top = ctk.CTkFrame(self, fg_color='transparent')
        top.pack(fill='x', padx=10, pady=(8, 2))
        ctk.CTkLabel(
            top, text=f":{port}",
            font=('Courier', 12, 'bold'),
            text_color=col
        ).pack(side='left')
        ctk.CTkLabel(
            top, text=f"  {SVCS.get(port, 'Unknown')}",
            font=MONO_SM, text_color=C['tx']
        ).pack(side='left')
        ctk.CTkLabel(
            top, text=proto,
            font=('Courier', 8),
            text_color=C['mu']
        ).pack(side='right')
        ctk.CTkLabel(
            self,
            text=f"Process: {process}  State: {state}",
            font=('Courier', 8),
            text_color=C['mu']
        ).pack(anchor='w', padx=10, pady=(0, 6))