"""
Mint Scan — In-App Installer
Runs apt/pip commands directly inside the app with live progress output.
No external terminal needed — works on Chromebook, Ubuntu, Kali, WSL, macOS.
"""
import tkinter as tk
import customtkinter as ctk
import subprocess, threading, time, os, sys, shutil
from widgets import C, MONO_SM, Btn


class InstallerPopup(ctk.CTkToplevel):
    """
    A self-contained popup that runs installation commands with live output.
    Usage:
        InstallerPopup(parent, title="Install ADB", commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y adb",
        ])
    """
    def __init__(self, parent, title="Installing...", commands=None,
                 success_msg="Installation complete!", on_done=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("620x420")
        self.configure(fg_color=C['bg'])
        self.resizable(True, True)
        self._commands  = commands or []
        self._on_done   = on_done
        self._success   = success_msg
        self._cancelled = False

        # Bring to front
        self.lift()
        self.focus_force()

        self._build()
        # Start after window is drawn
        self.after(200, self._start)

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=44, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        self._title_lbl = ctk.CTkLabel(hdr, text="⟳ Preparing...",
                                        font=('Courier', 11, 'bold'),
                                        text_color=C['ac'])
        self._title_lbl.pack(side='left', padx=14)

        # Progress bar
        self._prog = ctk.CTkProgressBar(self, height=6,
                                         progress_color=C['ac'],
                                         fg_color=C['br'])
        self._prog.pack(fill='x', padx=0, pady=0)
        self._prog.set(0)
        self._prog.configure(mode='indeterminate')

        # Log area
        self._log = ctk.CTkTextbox(self, font=('Courier', 10),
                                    fg_color=C['s2'],
                                    text_color=C['ok'],
                                    border_color=C['br'], border_width=1,
                                    corner_radius=0)
        self._log.pack(fill='both', expand=True, padx=0, pady=0)
        # Keep it normal state so user can select/copy
        self._log.configure(state='normal')

        # Bottom bar
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

    def _log_line(self, msg, color=None):
        """Thread-safe log append"""
        def _do():
            self._log.insert('end', msg + '\n')
            self._log.see('end')
        self.after(0, _do)

    def _set_title(self, msg):
        self.after(0, lambda: self._title_lbl.configure(text=msg))

    def _set_status(self, msg, color=None):
        self.after(0, lambda: self._status_lbl.configure(
            text=msg, text_color=color or C['mu']))

    def _start(self):
        self._prog.start()
        threading.Thread(target=self._run_all, daemon=True).start()

    def _run_all(self):
        total = len(self._commands)
        failed_cmds = []

        for i, cmd in enumerate(self._commands):
            if self._cancelled:
                self._log_line("⚠ Cancelled by user.")
                break

            self._set_title(f"⟳ Step {i+1}/{total}: {cmd[:50]}...")
            self._set_status(f"Running step {i+1} of {total}...")
            self._log_line(f"\n$ {cmd}")
            self._log_line("─" * 55)

            ok = self._run_cmd(cmd)
            if not ok:
                failed_cmds.append(cmd)
                self._log_line(f"✗ Step {i+1} failed — see output above")
                # Don't abort — try remaining steps
                self._log_line("Continuing with next step...")

        if not self._cancelled:
            if not failed_cmds:
                self._log_line(f"\n{'='*55}")
                self._log_line(f"✓ {self._success}")
                self._set_title(f"✓ {self._success}")
                self._set_status("Done!", C['ok'])
            else:
                self._log_line(f"\n{'='*55}")
                self._log_line(f"⚠ {len(failed_cmds)} step(s) had errors:")
                for fc in failed_cmds:
                    self._log_line(f"  - {fc[:60]}...")
                self._set_title("⚠ Completed with errors")
                self._set_status("Completed with errors", C['am'])

        self.after(0, lambda: self._prog.stop())
        self.after(0, lambda: self._prog.set(1.0 if not failed_cmds else 0.6))
        self.after(0, lambda: self._close_btn.configure(state='normal'))

        if self._on_done:
            self.after(500, self._on_done)

    def _run_cmd(self, cmd):
        """Run command with robust sudo handling for Chromebook/Ubuntu/Kali/WSL."""
        import shlex

        original = cmd.strip()

        if original.startswith('sudo ') and os.geteuid() != 0:
            inner = original[5:].strip()
            inner_q = inner.replace("'", "'\''")

            if shutil.which('pkexec'):
                # GUI password prompt — works on GNOME desktops
                cmd = f"pkexec bash -c '{inner_q}'"
            else:
                # Chromebook Crostini / headless: try passwordless sudo first,
                # then regular sudo (will prompt in the terminal that launched run.sh)
                cmd = f"sudo -n bash -c '{inner_q}' 2>/dev/null || sudo bash -c '{inner_q}'"

        # Always set DEBIAN_FRONTEND so apt never hangs on prompts
        run_env = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}

        try:
            proc = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=run_env
            )
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self._log_line(line)
            proc.wait()
            return proc.returncode == 0
        except Exception as e:
            self._log_line(f"Error: {e}")
            return False

    def _cancel(self):
        self._cancelled = True
        self._set_title("Cancelled")
        self._set_status("Cancelled", C['wn'])
        self._close_btn.configure(state='normal')

    def _close(self):
        self.destroy()


# ── Preset installer functions ────────────────────────────────────

def install_adb(parent, on_done=None):
    """Install ADB (Android Debug Bridge)"""
    InstallerPopup(parent,
        title="Install ADB — Android Debug Bridge",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y adb",
            "adb version",
        ],
        success_msg="ADB installed! Connect your phone and tap RESCAN.",
        on_done=on_done
    )


def install_clamav(parent, on_done=None):
    """Install ClamAV antivirus"""
    InstallerPopup(parent,
        title="Install ClamAV Antivirus",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y clamav clamav-daemon",
            "sudo systemctl stop clamav-freshclam 2>/dev/null || true",
            "sudo freshclam",
        ],
        success_msg="ClamAV installed and virus definitions updated!",
        on_done=on_done
    )


def install_kdeconnect(parent, on_done=None):
    """Install KDE Connect"""
    InstallerPopup(parent,
        title="Install KDE Connect",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y kdeconnect",
        ],
        success_msg="KDE Connect installed! Open it and pair with your phone.",
        on_done=on_done
    )


def install_nmap(parent, on_done=None):
    """Install nmap"""
    InstallerPopup(parent,
        title="Install nmap Network Scanner",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y nmap",
            "nmap --version",
        ],
        success_msg="nmap installed!",
        on_done=on_done
    )


def install_tcpdump(parent, on_done=None):
    """Install tcpdump"""
    InstallerPopup(parent,
        title="Install tcpdump",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y tcpdump",
            "tcpdump --version 2>&1 | head -1",
        ],
        success_msg="tcpdump installed!",
        on_done=on_done
    )


def install_rkhunter(parent, on_done=None):
    """Install rkhunter"""
    InstallerPopup(parent,
        title="Install rkhunter Rootkit Scanner",
        commands=[
            "sudo apt-get update -qq",
            "sudo apt-get install -y rkhunter",
            "rkhunter --version 2>&1 | head -1",
        ],
        success_msg="rkhunter installed!",
        on_done=on_done
    )


def install_all_tools(parent, on_done=None):
    """Install all optional tools at once"""
    InstallerPopup(parent,
        title="Install All Security Tools",
        commands=[
            'echo "iptables-persistent iptables-persistent/autosave_v4 boolean true" | sudo debconf-set-selections',
            'echo "iptables-persistent iptables-persistent/autosave_v6 boolean true" | sudo debconf-set-selections',
            "sudo apt-get update -q",
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y adb nmap tcpdump clamav clamav-daemon rkhunter kdeconnect net-tools wireless-tools iw dbus ufw iptables-persistent",
            "sudo systemctl stop clamav-freshclam 2>/dev/null || true",
            "sudo freshclam 2>/dev/null || echo 'freshclam: will retry later'",
            "sudo ufw --force enable",
            "echo '✓ All tools installed'",
        ],
        success_msg="All tools installed successfully!",
        on_done=on_done
    )
