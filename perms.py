"""Permissions Screen — Linux file/device/network permissions"""
from widgets import C, MONO, MONO_SM, ScrollableFrame, Card, SectionHeader, InfoGrid, ResultBox, Btn
import tkinter as tk
import customtkinter as ctk
import threading, os, stat
from utils import run_cmd, check_root


class PermsScreen(ctk.CTkFrame):
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

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True
        threading.Thread(target=self._load, daemon=True).start()

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text="🔑  PERMISSIONS", font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, "↺  REFRESH", command=lambda: threading.Thread(
            target=self._load, daemon=True).start(),
            variant='ghost', width=100).pack(side='right', padx=12, pady=6)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True)
        body = self.scroll

        SectionHeader(body, '01', 'SYSTEM ACCESS').pack(fill='x', padx=14, pady=(14,4))
        self.sys_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.sys_frame.pack(fill='x', padx=14, pady=(0,8))

        SectionHeader(body, '02', 'DEVICE FILES').pack(fill='x', padx=14, pady=(10,4))
        self.dev_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.dev_frame.pack(fill='x', padx=14, pady=(0,8))

        SectionHeader(body, '03', 'SUDO / ROOT CAPABILITIES').pack(fill='x', padx=14, pady=(10,4))
        self.sudo_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.sudo_frame.pack(fill='x', padx=14, pady=(0,8))

        SectionHeader(body, '04', 'RUNNING AS').pack(fill='x', padx=14, pady=(10,4))
        self.user_frame = ctk.CTkFrame(body, fg_color='transparent')
        self.user_frame.pack(fill='x', padx=14, pady=(0,14))

    def _load(self):
        results = {}

        # User info
        results['user'] = run_cmd('whoami')[0]
        results['uid']  = str(os.getuid())
        results['gid']  = str(os.getgid())
        results['groups'] = run_cmd('groups')[0]
        results['is_root'] = check_root()
        results['sudo_access'] = run_cmd('sudo -n true 2>/dev/null && echo yes || echo no')[0] == 'yes'

        # Sudo rules
        sudo_out, _, rc = run_cmd('sudo -l 2>/dev/null')
        results['sudo_rules'] = sudo_out if rc == 0 else 'No sudo access or password required'

        # Device files access
        devices = {
            '/dev/sda':    'HDD/SSD',
            '/dev/video0': 'Camera',
            '/dev/snd':    'Audio',
            '/dev/tty0':   'Terminal',
            '/dev/net/tun':'VPN/TUN',
            '/dev/rfkill': 'RF Kill (WiFi/BT)',
            '/dev/input':  'Input Devices',
        }
        results['devices'] = {}
        for dev, label in devices.items():
            if os.path.exists(dev):
                readable = os.access(dev, os.R_OK)
                writable = os.access(dev, os.W_OK)
                results['devices'][dev] = {'label': label, 'read': readable, 'write': writable}

        # Firewall
        ufw_out, _, ufw_rc = run_cmd('sudo ufw status 2>/dev/null || ufw status 2>/dev/null')
        results['firewall'] = ufw_out.split('\n')[0] if ufw_out else 'Unknown'

        # SELinux/AppArmor
        aa_out, _, _ = run_cmd('aa-status --brief 2>/dev/null || apparmor_status 2>/dev/null | head -2')
        results['apparmor'] = aa_out[:80] if aa_out else 'Not active'

        self._safe_after(0, self._render, results)

    def _render(self, r):
        for w in self.sys_frame.winfo_children(): w.destroy()
        is_root = r['is_root']
        InfoGrid(self.sys_frame, [
            ('RUNNING AS',   r['user'],                   C['wn'] if is_root else C['ok']),
            ('UID / GID',    f"{r['uid']} / {r['gid']}"),
            ('ROOT ACCESS',  '⚠ YES' if is_root else '✓ No', C['wn'] if is_root else C['ok']),
            ('SUDO ACCESS',  '✓ Yes' if r['sudo_access'] else 'No', C['am'] if r['sudo_access'] else C['mu']),
            ('FIREWALL',     r['firewall'],               C['ok'] if 'active' in r['firewall'].lower() else C['wn']),
            ('APPARMOR',     r['apparmor'][:30],          C['ok'] if 'profiles' in r['apparmor'] else C['mu']),
        ], columns=3).pack(fill='x')

        if is_root:
            ResultBox(self.sys_frame, 'warn', '⚠ RUNNING AS ROOT',
                      'Running security tools as root can be dangerous. Use a regular user account.').pack(fill='x', pady=4)

        # Device files
        if not hasattr(self,"dev_frame"): return
        for w in self.dev_frame.winfo_children(): w.destroy()
        items = []
        for dev, info in r['devices'].items():
            access = ('R+W' if info['write'] else 'READ') if info['read'] else 'NO ACCESS'
            col = C['wn'] if info['write'] else C['am'] if info['read'] else C['mu']
            items.append((info['label'], f"{dev}\n{access}", col))
        if items:
            InfoGrid(self.dev_frame, items, columns=3).pack(fill='x')
        else:
            ctk.CTkLabel(self.dev_frame, text="No device files detected",
                         font=MONO_SM, text_color=C['mu']).pack()

        # Sudo
        for w in self.sudo_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.sudo_frame, text=r['sudo_rules'],
                     font=('Courier', 9), text_color=C['mu'],
                     justify='left', wraplength=700).pack(anchor='w')

        # User
        for w in self.user_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.user_frame, text=f"Groups: {r['groups']}",
                     font=MONO_SM, text_color=C['mu'],
                     wraplength=700, justify='left').pack(anchor='w')
