"""
Mint Scan — In-App Installer
Runs apt/pip commands directly inside the app with live progress output.
Works on Chromebook (passwordless sudo), Ubuntu, Kali, WSL2.
"""
import tkinter as tk
import customtkinter as ctk
import subprocess, threading, time, os, sys, shutil, shlex
from widgets import C, MONO_SM, Btn
from utils import run_cmd


class InstallerPopup(ctk.CTkToplevel):
    """
    A self-contained popup that runs installation commands with live output.
    Handles Chromebook Crostini (passwordless sudo) and desktop Linux.
    """
    def __init__(self, parent, title="Installing...", commands=None,
                 success_msg="Installation complete!", on_done=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("660x460")
        self.configure(fg_color=C['bg'])
        self.resizable(True, True)
        self._commands  = commands or []
        self._on_done   = on_done
        self._success   = success_msg
        self._cancelled = False
        self.lift()
        self.focus_force()
        self._build()
        self.after(200, self._start)

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=44, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        self._title_lbl = ctk.CTkLabel(hdr, text="⟳ Preparing...",
                                        font=('Courier', 11, 'bold'),
                                        text_color=C['ac'])
        self._title_lbl.pack(side='left', padx=14)

        self._prog = ctk.CTkProgressBar(self, height=6,
                                         progress_color=C['ac'],
                                         fg_color=C['br'])
        self._prog.pack(fill='x')
        self._prog.set(0)
        self._prog.configure(mode='indeterminate')

        self._log = ctk.CTkTextbox(self, font=('Courier', 10),
                                    fg_color=C['s2'], text_color=C['ok'],
                                    border_color=C['br'], border_width=1,
                                    corner_radius=0)
        self._log.pack(fill='both', expand=True)
        self._log.configure(state='normal')

        bot = ctk.CTkFrame(self, fg_color=C['sf'], height=44, corner_radius=0)
        bot.pack(fill='x')
        bot.pack_propagate(False)

        self._status_lbl = ctk.CTkLabel(bot, text="Starting...",
                                         font=MONO_SM, text_color=C['mu'])
        self._status_lbl.pack(side='left', padx=14)

        self._close_btn = Btn(bot, "CLOSE", command=self._close,
                              variant='ghost', width=80)
        self._close_btn.pack(side='right', padx=10, pady=6)
        self._close_btn.configure(state='disabled')

        Btn(bot, "CANCEL", command=self._cancel,
            variant='danger', width=80).pack(side='right', padx=4, pady=6)

    def _log_line(self, msg):
        def _do():
            try:
                self._log.insert('end', msg + '\n')
                self._log.see('end')
            except Exception:
                pass
        self.after(0, _do)

    def _set_title(self, msg):
        def _do():
            try:
                if self.winfo_exists():
                    self._title_lbl.configure(text=msg)
            except Exception:
                pass
        self.after(0, _do)

    def _set_status(self, msg, color=None):
        def _do():
            try:
                if self.winfo_exists():
                    self._status_lbl.configure(text=msg, text_color=color or C['mu'])
            except Exception:
                pass
        self.after(0, _do)

    def _start(self):
        self._prog.start()
        threading.Thread(target=self._run_all, daemon=True).start()

    def _run_all(self):
        total = len(self._commands)
        failed = []

        for i, cmd in enumerate(self._commands):
            if self._cancelled:
                self._log_line("⚠ Cancelled.")
                break
            self._set_title(f"⟳ Step {i+1}/{total}: {cmd[:55]}...")
            self._set_status(f"Step {i+1} of {total}...")
            self._log_line(f"\n$ {cmd}")
            self._log_line("─" * 58)
            ok = self._execute_step(cmd)
            if not ok:
                failed.append(cmd)
                self._log_line(f"⚠ Step {i+1} had errors — continuing...")

        if not self._cancelled:
            if not failed:
                self._log_line(f"\n{'='*58}\n✓ {self._success}")
                self._set_title(f"✓ {self._success}")
                self._set_status("Done!", C['ok'])
            else:
                self._log_line(f"\n{'='*58}\n⚠ {len(failed)} step(s) had errors")
                self._set_title("⚠ Completed with errors")
                self._set_status("Check output above", C['am'])

        def _finish():
            try:
                if self.winfo_exists():
                    self._prog.stop()
                    self._prog.set(1.0 if not failed else 0.6)
                    self._close_btn.configure(state='normal')
            except Exception:
                pass
        self.after(0, _finish)
        if self._on_done:
            self.after(500, self._on_done)

    def _execute_step(self, cmd):
        """
        Run one command with streaming output using the centralized run_cmd
        concept but adapted for streaming.
        """
        original = cmd.strip()
        
        # Hardened sudo handling for streaming
        if original.startswith('sudo ') and os.geteuid() != 0:
            inner   = original[5:].strip()
            # Wrap in bash -c with proper escaping using shlex
            run_cmd_str = f"sudo -n bash -c {shlex.quote(inner)}"
        else:
            run_cmd_str = original

        run_env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}

        try:
            proc = subprocess.Popen(
                run_cmd_str, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                env=run_env)
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self._log_line(line)
            proc.wait()
            
            if proc.returncode != 0:
                self._log_line(f"Command exited with code {proc.returncode}")
                
            return proc.returncode == 0
        except Exception as e:
            self._log_line(f"Error: {e}")
            return False

    def _cancel(self):
        self._cancelled = True
        self._set_title("Cancelled")
        self._set_status("Cancelled", C['wn'])
        def _en():
            try:
                if self.winfo_exists():
                    self._close_btn.configure(state='normal')
            except Exception:
                pass
        self.after(0, _en)

    def _close(self):
        try:
            self.destroy()
        except Exception:
            pass


# ── Preset installer functions ────────────────────────────────────

def install_adb(parent, on_done=None):
    InstallerPopup(parent, title="Install ADB — Android Debug Bridge",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y adb",
            "adb version",
        ],
        success_msg="ADB installed! Connect your phone and tap RESCAN.",
        on_done=on_done)


def install_clamav(parent, on_done=None):
    InstallerPopup(parent, title="Install ClamAV Antivirus",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y clamav clamav-daemon",
            "sudo systemctl stop clamav-freshclam 2>/dev/null || true",
            "sudo freshclam",
        ],
        success_msg="ClamAV installed and virus definitions updated!",
        on_done=on_done)


def install_kdeconnect(parent, on_done=None):
    InstallerPopup(parent, title="Install KDE Connect",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y kdeconnect",
        ],
        success_msg="KDE Connect installed!",
        on_done=on_done)


def install_nmap(parent, on_done=None):
    InstallerPopup(parent, title="Install nmap",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y nmap",
            "nmap --version",
        ],
        success_msg="nmap installed!",
        on_done=on_done)


def install_tcpdump(parent, on_done=None):
    InstallerPopup(parent, title="Install tcpdump",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y tcpdump",
            "tcpdump --version 2>&1 | head -1",
        ],
        success_msg="tcpdump installed!",
        on_done=on_done)


def install_rkhunter(parent, on_done=None):
    InstallerPopup(parent, title="Install rkhunter",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y rkhunter",
            "rkhunter --version 2>&1 | head -1",
        ],
        success_msg="rkhunter installed!",
        on_done=on_done)


def install_all_tools(parent, on_done=None):
    InstallerPopup(parent, title="Install All Security Tools",
        commands=[
            'echo "iptables-persistent iptables-persistent/autosave_v4 boolean true" | sudo debconf-set-selections',
            'echo "iptables-persistent iptables-persistent/autosave_v6 boolean true" | sudo debconf-set-selections',
            "sudo apt-get update -q",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "
            "adb nmap tcpdump clamav clamav-daemon rkhunter "
            "net-tools wireless-tools iw dbus ufw",
            "sudo systemctl stop clamav-freshclam 2>/dev/null || true",
            "sudo freshclam 2>/dev/null || echo 'freshclam: will retry later'",
            "sudo ufw --force enable",
            "echo '✓ All tools installed'",
        ],
        success_msg="All tools installed successfully!",
        on_done=on_done)
