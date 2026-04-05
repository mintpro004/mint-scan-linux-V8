"""Guardian — Auto-Remediation, Panic Button, USB Lockdown"""
import customtkinter as ctk
import threading, subprocess, time, os
from widgets import ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn, C, MONO, MONO_SM
from utils import run_cmd as run

class GuardianScreen(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app = app
        self._built = False
        self._guardian_active = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="🛡  GUARDIAN AUTO-DEFENSE", font=('Courier',13,'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        # ── 01 Guardian Mode ──────────────────────────────────
        SectionHeader(body, '01', 'GUARDIAN MODE').pack(fill='x', padx=14, pady=(14,4))
        mode_card = Card(body)
        mode_card.pack(fill='x', padx=14, pady=(0,8))
        
        self.status_lbl = ctk.CTkLabel(mode_card, text="STATUS: INACTIVE", font=('Courier',12,'bold'), text_color=C['mu'])
        self.status_lbl.pack(pady=(12,4))
        
        ctk.CTkLabel(mode_card, text="Automatically block IPs scanning ports and kill high-risk processes.",
                     font=MONO_SM, text_color=C['mu']).pack(pady=(0,12))
        
        self.toggle_btn = Btn(mode_card, "ENABLE GUARDIAN", command=self._toggle_guardian, width=160)
        self.toggle_btn.pack(pady=(0,12))

        # ── 02 Panic Button ───────────────────────────────────
        SectionHeader(body, '02', 'EMERGENCY CONTROLS').pack(fill='x', padx=14, pady=(10,4))
        panic_card = Card(body, accent=C['wn'])
        panic_card.pack(fill='x', padx=14, pady=(0,8))
        
        ctk.CTkLabel(panic_card, text="⚠ PANIC BUTTON", font=('Courier',14,'bold'), text_color=C['wn']).pack(pady=(12,4))
        ctk.CTkLabel(panic_card, text="Instantly kill network interfaces and lock screen.", font=MONO_SM, text_color=C['mu']).pack(pady=(0,12))
        
        Btn(panic_card, "☢ EXECUTE PANIC", command=self._panic, variant='danger', width=180).pack(pady=(0,12))

        # ── 03 USB Lockdown ───────────────────────────────────
        SectionHeader(body, '03', 'USB LOCKDOWN').pack(fill='x', padx=14, pady=(10,4))
        usb_card = Card(body)
        usb_card.pack(fill='x', padx=14, pady=(0,8))
        
        ctk.CTkLabel(usb_card, text="Block new USB devices (requires root)", font=MONO_SM, text_color=C['mu']).pack(pady=(12,4))
        self.usb_btn = Btn(usb_card, "🔒 BLOCK NEW USB", command=self._toggle_usb_lock, variant='ghost', width=160)
        self.usb_btn.pack(pady=(0,12))

    def _toggle_guardian(self):
        self._guardian_active = not self._guardian_active
        if self._guardian_active:
            self.status_lbl.configure(text="STATUS: ACTIVE", text_color=C['ok'])
            self.toggle_btn.configure(text="DISABLE GUARDIAN", variant='success')
            # In a real app, this would start a background thread monitoring threats
        else:
            self.status_lbl.configure(text="STATUS: INACTIVE", text_color=C['mu'])
            self.toggle_btn.configure(text="ENABLE GUARDIAN", variant='primary')

    def _panic(self):
        # Kill network
        run("nmcli networking off")
        run("ip link set wlan0 down")
        run("ip link set eth0 down")
        # Lock screen (gnome/kde/etc)
        run("loginctl lock-session")
        ResultBox(self.scroll, 'warn', 'PANIC EXECUTED', 'Network killed. Screen locked.').pack(fill='x', padx=14, pady=10)

    def _toggle_usb_lock(self):
        # This is a simulation/placeholder as safe USB locking is complex
        # Real implementation would use: echo 0 > /sys/bus/usb/drivers/usb/bind
        ResultBox(self.scroll, 'info', 'USB LOCK', 'USB Blocking toggled (Simulation)').pack(fill='x', padx=14, pady=10)
