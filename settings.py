"""Settings Screen — font size, UI scale, theme (dark/light), accent colour"""
import tkinter as tk
import customtkinter as ctk
import json, os, threading
from widgets import ScrollableFrame, Card, SectionHeader, ResultBox, Btn, C, MONO, MONO_SM
import widgets as _widgets

SETTINGS_FILE = os.path.expanduser('~/.mint_scan_settings.json')

DEFAULTS = {
    'font_size':     11,
    'ui_scale':      1.0,
    'theme':         'dark',
    'accent_color':  '#00ffe0',
    'show_clock':    True,
    'ping_interval': 3,
    'scan_on_start': True,
}


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return {**DEFAULTS, **json.load(f)}
    except Exception:
        return dict(DEFAULTS)


def save_settings(s):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(s, f, indent=2)
        return True
    except Exception:
        return False


class SettingsScreen(ctk.CTkFrame):
    def _safe_after(self, delay, fn, *args):
        """Thread-safe after() that guards against destroyed widgets."""
        def _guarded():
            try:
                if self.winfo_exists():
                    fn(*args)
            except Exception:
                pass
        try:
            self.after(delay, _guarded)
        except Exception:
            pass


    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False
        self.settings = load_settings()

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        self._load_values()

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="⚙  SETTINGS",
                     font=('DejaVu Sans Mono',13,'bold'), text_color=C['ac']
                     ).pack(side='left', padx=16)
        Btn(hdr, "💾 SAVE & APPLY", command=self._save,
            variant='success', width=160).pack(side='right', padx=12, pady=6)
        Btn(hdr, "↺ RESET",         command=self._reset,
            variant='ghost',   width=80).pack(side='right', padx=4, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── THEME ─────────────────────────────────────────────
        SectionHeader(body, '01', 'THEME').pack(fill='x', padx=14, pady=(14,4))
        theme_card = Card(body)
        theme_card.pack(fill='x', padx=14, pady=(0,8))

        theme_row = ctk.CTkFrame(theme_card, fg_color='transparent')
        theme_row.pack(fill='x', padx=12, pady=(12,8))
        ctk.CTkLabel(theme_row, text="COLOUR THEME",
                     font=('DejaVu Sans Mono',9,'bold'), text_color=C['ac'],
                     width=150).pack(side='left')

        self._theme_var = tk.StringVar(value=self.settings.get('theme','dark'))

        # Dark button
        self._dark_btn = ctk.CTkButton(theme_row,
            text="🌙  DARK",
            font=('DejaVu Sans Mono',10,'bold'),
            width=140, height=40,
            fg_color=C['br2'],
            border_color=C['ac'],
            border_width=2,
            hover_color=C['br'],
            text_color=C['ac'],
            command=lambda: self._set_theme('dark'))
        self._dark_btn.pack(side='left', padx=6)

        # Light button
        self._light_btn = ctk.CTkButton(theme_row,
            text="☀  LIGHT",
            font=('DejaVu Sans Mono',10,'bold'),
            width=140, height=40,
            fg_color='#e2e8f0',
            border_color='#94a3b8',
            border_width=2,
            hover_color='#cbd5e1',
            text_color='#1e293b',
            command=lambda: self._set_theme('light'))
        self._light_btn.pack(side='left', padx=6)

        self._theme_status = ctk.CTkLabel(theme_card,
            text="Current: DARK theme",
            font=MONO_SM, text_color=C['mu'])
        self._theme_status.pack(anchor='w', padx=12, pady=(0,10))

        # ── ACCENT COLOUR ─────────────────────────────────────
        SectionHeader(body, '02', 'ACCENT COLOUR').pack(fill='x', padx=14, pady=(8,4))
        accent_card = Card(body)
        accent_card.pack(fill='x', padx=14, pady=(0,8))

        acc_row = ctk.CTkFrame(accent_card, fg_color='transparent')
        acc_row.pack(fill='x', padx=12, pady=(10,10))
        ctk.CTkLabel(acc_row, text="ACCENT",
                     font=('DejaVu Sans Mono',9,'bold'), text_color=C['ac'],
                     width=80).pack(side='left')

        self._accent_var = tk.StringVar(value=self.settings.get('accent_color','#00ffe0'))
        accent_options = [
            ('#00ffe0', 'Cyan'),    ('#39ff88', 'Green'),
            ('#4d9fff', 'Blue'),    ('#ffb830', 'Amber'),
            ('#ff4c4c', 'Red'),     ('#c084fc', 'Purple'),
        ]
        for hex_col, name in accent_options:
            btn = ctk.CTkButton(acc_row,
                text=name, width=70, height=32,
                fg_color=hex_col,
                hover_color=hex_col,
                text_color='#000000',
                font=('DejaVu Sans Mono',8,'bold'),
                corner_radius=4,
                border_width=2,
                border_color=hex_col,
                command=lambda c=hex_col: self._set_accent(c))
            btn.pack(side='left', padx=3)

        self._accent_preview = ctk.CTkLabel(accent_card,
            text="● Selected: #00ffe0",
            font=('DejaVu Sans Mono',9), text_color=C['ac'])
        self._accent_preview.pack(anchor='w', padx=12, pady=(0,8))

        # ── FONT SIZE ─────────────────────────────────────────
        SectionHeader(body, '03', 'FONT SIZE').pack(fill='x', padx=14, pady=(8,4))
        font_card = Card(body)
        font_card.pack(fill='x', padx=14, pady=(0,8))

        font_row = ctk.CTkFrame(font_card, fg_color='transparent')
        font_row.pack(fill='x', padx=12, pady=(10,4))
        ctk.CTkLabel(font_row, text="SIZE",
                     font=('DejaVu Sans Mono',9,'bold'), text_color=C['ac'],
                     width=80).pack(side='left')
        self.font_lbl = ctk.CTkLabel(font_row, text="10px",
                                      font=MONO_SM, text_color=C['tx'], width=40)
        self.font_lbl.pack(side='right')
        self.font_slider = ctk.CTkSlider(font_row, from_=8, to=16, number_of_steps=8,
                                          command=self._on_font_change,
                                          button_color=C['ac'],
                                          progress_color=C['ac'],
                                          fg_color=C['br'])
        self.font_slider.pack(side='left', fill='x', expand=True, padx=8)
        ctk.CTkLabel(font_card, text="Adjusts text size — restart fully applies",
                     font=('DejaVu Sans Mono',8), text_color=C['mu']).pack(anchor='w', padx=12, pady=(0,4))

        # ── UI SCALE ──────────────────────────────────────────
        SectionHeader(body, '04', 'UI SCALE').pack(fill='x', padx=14, pady=(8,4))
        scale_card = Card(body)
        scale_card.pack(fill='x', padx=14, pady=(0,8))

        scale_row = ctk.CTkFrame(scale_card, fg_color='transparent')
        scale_row.pack(fill='x', padx=12, pady=(10,4))
        ctk.CTkLabel(scale_row, text="SCALE",
                     font=('DejaVu Sans Mono',9,'bold'), text_color=C['ac'],
                     width=80).pack(side='left')
        self.scale_lbl = ctk.CTkLabel(scale_row, text="100%",
                                       font=MONO_SM, text_color=C['tx'], width=45)
        self.scale_lbl.pack(side='right')
        self.scale_slider = ctk.CTkSlider(scale_row, from_=0.7, to=1.5, number_of_steps=16,
                                           command=self._on_scale_change,
                                           button_color=C['ac'],
                                           progress_color=C['ac'],
                                           fg_color=C['br'])
        self.scale_slider.pack(side='left', fill='x', expand=True, padx=8)
        ctk.CTkLabel(scale_card,
                     text="Makes all interface elements larger or smaller (restart to apply fully)",
                     font=('DejaVu Sans Mono',8), text_color=C['mu']).pack(anchor='w', padx=12, pady=(0,10))

        # ── PERFORMANCE ───────────────────────────────────────
        SectionHeader(body, '05', 'PERFORMANCE').pack(fill='x', padx=14, pady=(8,4))
        perf = Card(body)
        perf.pack(fill='x', padx=14, pady=(0,8))

        ping_row = ctk.CTkFrame(perf, fg_color='transparent')
        ping_row.pack(fill='x', padx=12, pady=(10,4))
        ctk.CTkLabel(ping_row, text="PING INTERVAL",
                     font=('DejaVu Sans Mono',9,'bold'), text_color=C['ac'],
                     width=140).pack(side='left')
        self.ping_lbl = ctk.CTkLabel(ping_row, text="3s",
                                      font=MONO_SM, text_color=C['tx'], width=35)
        self.ping_lbl.pack(side='right')
        self.ping_slider = ctk.CTkSlider(ping_row, from_=1, to=10, number_of_steps=9,
                                          command=self._on_ping_change,
                                          button_color=C['ac'],
                                          progress_color=C['ac'],
                                          fg_color=C['br'])
        self.ping_slider.pack(side='left', fill='x', expand=True, padx=8)
        ctk.CTkLabel(perf, text="How often the network graph refreshes",
                     font=('DejaVu Sans Mono',8), text_color=C['mu']).pack(anchor='w', padx=12, pady=(0,4))

        sw_row = ctk.CTkFrame(perf, fg_color='transparent')
        sw_row.pack(fill='x', padx=12, pady=(4,10))
        ctk.CTkLabel(sw_row, text="AUTO-SCAN ON START",
                     font=('DejaVu Sans Mono',9,'bold'), text_color=C['ac'],
                     width=200).pack(side='left')
        self.scan_start_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(sw_row, text='', variable=self.scan_start_var,
                      onvalue=True, offvalue=False,
                      button_color=C['ac'],
                      progress_color=C['br2']).pack(side='left', padx=8)
        ctk.CTkLabel(sw_row, text="Load dashboard data on launch",
                     font=('DejaVu Sans Mono',8), text_color=C['mu']).pack(side='left')

        # ── SYSTEM TWEAKS ─────────────────────────────────────
        SectionHeader(body, '06', 'SYSTEM TWEAKS').pack(fill='x', padx=14, pady=(8,4))
        tweaks = Card(body)
        tweaks.pack(fill='x', padx=14, pady=(0,8))
        
        tw_grid = ctk.CTkFrame(tweaks, fg_color='transparent')
        tw_grid.pack(fill='x', padx=12, pady=12)
        
        Btn(tw_grid, "🧹 OPTIMISE RAM", 
            command=lambda: self._run_tweak("sudo sync; echo 3 | sudo tee /proc/sys/vm/drop_caches"),
            variant='ghost', width=160).grid(row=0, column=0, padx=4, pady=4)
        Btn(tw_grid, "🗑 CLEAR LOGS", 
            command=lambda: self._run_tweak("sudo journalctl --vacuum-time=1d"),
            variant='ghost', width=160).grid(row=0, column=1, padx=4, pady=4)
        Btn(tw_grid, "🚫 STOP TELEMETRY", 
            command=lambda: self._run_tweak("sudo systemctl disable --now apport.service || true"),
            variant='ghost', width=160).grid(row=1, column=0, padx=4, pady=4)
        Btn(tw_grid, "🛡 HARDEN KERNEL", 
            command=lambda: self._run_tweak("echo 'kernel.kptr_restrict=2' | sudo tee -a /etc/sysctl.conf && sudo sysctl -p"),
            variant='ghost', width=160).grid(row=1, column=1, padx=4, pady=4)
        tw_grid.columnconfigure(0, weight=1)
        tw_grid.columnconfigure(1, weight=1)

        # ── LIVE PREVIEW ──────────────────────────────────────
        SectionHeader(body, '07', 'LIVE PREVIEW').pack(fill='x', padx=14, pady=(8,4))
        self.preview = Card(body)
        self.preview.pack(fill='x', padx=14, pady=(0,8))
        self.prev_title = ctk.CTkLabel(self.preview,
            text="[ MINT SCAN ]",
            font=('DejaVu Sans Mono',14,'bold'), text_color=C['ac'])
        self.prev_title.pack(anchor='w', padx=12, pady=(10,4))
        self.prev_body = ctk.CTkLabel(self.preview,
            text="Sample text — this shows your font size setting.",
            font=('DejaVu Sans Mono',10), text_color=C['tx'])
        self.prev_body.pack(anchor='w', padx=12, pady=(0,4))
        self.prev_sub = ctk.CTkLabel(self.preview,
            text="Status bar text — secondary information",
            font=('DejaVu Sans Mono',9), text_color=C['mu'])
        self.prev_sub.pack(anchor='w', padx=12, pady=(0,10))

        self.status_lbl = ctk.CTkLabel(body, text="",
                                        font=MONO_SM, text_color=C['ok'])
        self.status_lbl.pack(pady=8)
        ctk.CTkLabel(body, text="", height=20).pack()

    def _run_tweak(self, cmd):
        self.status_lbl.configure(text="Running tweak...", text_color=C['ac'])
        def _do():
            from utils import run_cmd
            out, err, rc = run_cmd(cmd)
            msg = "✓ Tweak applied" if rc == 0 else f"✗ Failed: {err or out}"
            self._safe_after(0, lambda m=msg: self.status_lbl.configure(
                text=m, text_color=C['ok'] if rc==0 else C['wn']))
        threading.Thread(target=_do, daemon=True).start()

    def _load_values(self):
        s = self.settings
        try:
            self.font_slider.set(s.get('font_size', 10))
            self.font_lbl.configure(text=f"{int(s.get('font_size',10))}px")
            self.scale_slider.set(s.get('ui_scale', 1.0))
            self.scale_lbl.configure(text=f"{int(s.get('ui_scale',1.0)*100)}%")
            self.ping_slider.set(s.get('ping_interval', 3))
            self.ping_lbl.configure(text=f"{int(s.get('ping_interval',3))}s")
            self.scan_start_var.set(s.get('scan_on_start', True))
            theme = s.get('theme', 'dark')
            self._theme_var.set(theme)
            self._update_theme_buttons(theme)
        except Exception:
            pass

    def _on_font_change(self, val):
        size = int(val)
        self.font_lbl.configure(text=f"{size}px")
        self.prev_title.configure(font=('DejaVu Sans Mono', size+4, 'bold'))
        self.prev_body.configure(font=('DejaVu Sans Mono', size))
        self.prev_sub.configure(font=('DejaVu Sans Mono', max(8, size-1)))

    def _on_scale_change(self, val):
        self.scale_lbl.configure(text=f"{int(float(val)*100)}%")

    def _on_ping_change(self, val):
        self.ping_lbl.configure(text=f"{int(val)}s")

    def _set_theme(self, theme_name):
        self._theme_var.set(theme_name)
        self._update_theme_buttons(theme_name)
        # Apply immediately for preview
        acc = self._accent_var.get() if hasattr(self, '_accent_var') else '#00ffe0'
        fs = int(self.font_slider.get()) if hasattr(self, 'font_slider') else 10
        _widgets.apply_theme(theme_name, accent=acc, font_size=fs)
        self._theme_status.configure(
            text=f"Current: {'DARK 🌙' if theme_name=='dark' else 'LIGHT ☀'} theme — tap SAVE to keep")
        self.status_lbl.configure(
            text=f"Theme changed to {theme_name.upper()} — tap SAVE to save",
            text_color=_widgets.C['ok'])

    def _update_theme_buttons(self, theme):
        try:
            acc = self._accent_var.get() if hasattr(self, '_accent_var') else '#00ffe0'
            if theme == 'dark':
                self._dark_btn.configure(border_width=3, border_color=acc)
                self._light_btn.configure(border_width=1, border_color='#94a3b8')
            else:
                self._dark_btn.configure(border_width=1, border_color='#1a3a52')
                self._light_btn.configure(border_width=3, border_color='#0077cc')
            self._theme_status.configure(
                text=f"Current: {'DARK 🌙' if theme=='dark' else 'LIGHT ☀'} theme")
        except Exception:
            pass

    def _set_accent(self, colour):
        self._accent_var.set(colour)
        self._accent_preview.configure(
            text=f"● Selected: {colour}", text_color=colour)
        self.prev_title.configure(text_color=colour)
        self.status_lbl.configure(
            text=f"Accent set to {colour} — tap SAVE",
            text_color=colour)
        # Update theme buttons to show new accent
        self._update_theme_buttons(self._theme_var.get())
        # Apply to live dict
        _widgets.C['ac'] = colour

    def _save(self):
        self.settings = {
            'font_size':     int(self.font_slider.get()),
            'ui_scale':      round(float(self.scale_slider.get()), 1),
            'theme':         self._theme_var.get(),
            'accent_color':  self._accent_var.get() if hasattr(self,'_accent_var') else '#00ffe0',
            'ping_interval': int(self.ping_slider.get()),
            'scan_on_start': bool(self.scan_start_var.get()),
            'show_clock':    True,
        }
        if save_settings(self.settings):
            # Step 1: Apply theme colours to the global palette
            _widgets.apply_theme(
                self.settings['theme'],
                self.settings['accent_color'],
                self.settings['font_size'])

            # Step 2: Apply UI scale (customtkinter handles this globally)
            try:
                ctk.set_widget_scaling(self.settings['ui_scale'])
            except Exception:
                pass

            # Step 3: Tell app to recolour existing widgets — no rebuild
            if hasattr(self.app, 'refresh_ui'):
                self.app.refresh_ui()

            # Step 4: Update status — widget still exists because we didn't destroy anything
            try:
                self.status_lbl.configure(
                    text="✓ Saved — theme applied immediately. No restart needed.",
                    text_color=_widgets.C['ok'])
            except Exception:
                pass
        else:
            try:
                self.status_lbl.configure(
                    text="✗ Could not save settings file", text_color=_widgets.C['wn'])
            except Exception:
                pass

    def _reset(self):
        self.settings = dict(DEFAULTS)
        self._load_values()
        self.status_lbl.configure(
            text="Reset to defaults — tap SAVE to apply", text_color=C['am'])
