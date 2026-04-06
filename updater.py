"""
Mint Scan v8 — Software Updater
Checks GitHub Releases API for newer versions and updates via git pull.
"""
import threading, subprocess, os, json
import tkinter as tk
import customtkinter as ctk
from widgets import C, MONO, MONO_SM, Card, SectionHeader, Btn, ResultBox
from logger import get_logger

log = get_logger('updater')

REPO_API   = 'https://api.github.com/repos/mintpro004/mint-scan-linux-V8/releases/latest'
CURRENT_VER = '8.0.0'
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))


def _parse_ver(s):
    """Parse 'v8.1.2' or '8.1.2' → (8,1,2)."""
    s = s.lstrip('vV').strip()
    try:
        parts = [int(x) for x in s.split('.')]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)


def check_for_update(timeout=8):
    """
    Query GitHub releases API.
    Returns dict: {available, current, latest, tag, url, notes} or error str.
    """
    try:
        import urllib.request, urllib.error
        req = urllib.request.Request(
            REPO_API, headers={'User-Agent': 'MintScan-Updater/8'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        tag   = data.get('tag_name', CURRENT_VER)
        notes = (data.get('body') or '')[:600]
        url   = data.get('html_url', '')
        latest  = _parse_ver(tag)
        current = _parse_ver(CURRENT_VER)
        log.info(f'Update check: current={CURRENT_VER} latest={tag}')
        return {
            'available': latest > current,
            'current':   CURRENT_VER,
            'latest':    tag,
            'url':       url,
            'notes':     notes,
        }
    except Exception as e:
        log.warning(f'Update check failed: {e}')
        return {'error': str(e), 'available': False,
                'current': CURRENT_VER, 'latest': '—'}


def do_git_update(log_fn=None):
    """
    Pull latest from GitHub via git.
    Streams output lines to log_fn(str) if provided.
    Returns True on success.
    """
    def _l(msg):
        log.info(f'[git] {msg}')
        if log_fn:
            log_fn(msg)

    # Must be a git repo
    git_dir = os.path.join(BASE_DIR, '.git')
    if not os.path.isdir(git_dir):
        _l('ERROR: Not a git repository — update requires git clone installation.')
        _l('  Run:  git clone https://github.com/mintpro004/mint-scan-linux-V8.git')
        return False

    _l('Fixing ownership...')
    subprocess.run(f'sudo chown -R $USER:$USER "{BASE_DIR}"',
                   shell=True, capture_output=True)

    _l('Fetching from GitHub...')
    r = subprocess.run('git fetch origin', shell=True,
                       capture_output=True, text=True, cwd=BASE_DIR, timeout=60)
    _l(r.stdout.strip() or '(no output)')
    if r.returncode != 0:
        _l(f'Fetch failed: {r.stderr.strip()}')
        return False

    _l('Pulling latest commits...')
    r = subprocess.run('git pull origin main --rebase',
                       shell=True, capture_output=True, text=True,
                       cwd=BASE_DIR, timeout=120)
    for line in (r.stdout + r.stderr).splitlines():
        _l(line)

    if r.returncode != 0:
        _l('Pull failed — running self-heal...')
        subprocess.run('bash install.sh', shell=True, cwd=BASE_DIR)
        return False

    _l('Updating Python packages...')
    venv_pip = os.path.join(BASE_DIR, 'venv', 'bin', 'pip')
    if os.path.exists(venv_pip):
        subprocess.run(f'{venv_pip} install -r requirements.txt -q',
                       shell=True, cwd=BASE_DIR, capture_output=True)

    _l('✓ Update complete — restart Mint Scan to apply.')
    return True


class UpdaterScreen(ctk.CTkFrame):
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
        self.app    = app
        self._built = False

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True

    def on_blur(self):
        """Called when switching away from this tab — stop background work."""
        pass


    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        ctk.CTkLabel(hdr, text='🔄  SOFTWARE UPDATER',
                     font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, '🔍 CHECK NOW', command=self._check,
            width=130).pack(side='right', padx=8, pady=6)

        from widgets import ScrollableFrame
        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)
        self._body = body

        # Current version card
        SectionHeader(body, '01', 'CURRENT VERSION').pack(
            fill='x', padx=14, pady=(14, 4))
        vc = Card(body)
        vc.pack(fill='x', padx=14, pady=(0, 8))
        from widgets import InfoGrid
        InfoGrid(vc, [
            ('VERSION',    CURRENT_VER,   C['ac']),
            ('REPO',       'mintpro004/mint-scan-linux-V8', C['tx']),
            ('INSTALL',    'git clone method', C['ok']),
            ('LOG FILE',   '~/.mint_scan_v8.log', C['mu']),
        ], columns=2).pack(fill='x', padx=8, pady=8)

        # Status
        SectionHeader(body, '02', 'UPDATE STATUS').pack(
            fill='x', padx=14, pady=(8, 4))
        self._status_card = Card(body)
        self._status_card.pack(fill='x', padx=14, pady=(0, 8))
        self._status_lbl = ctk.CTkLabel(
            self._status_card,
            text='Tap CHECK NOW to query GitHub releases.',
            font=MONO_SM, text_color=C['mu'])
        self._status_lbl.pack(padx=12, pady=16)

        # Update log
        SectionHeader(body, '03', 'UPDATE LOG').pack(
            fill='x', padx=14, pady=(8, 4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0, 8))
        self._log_box = ctk.CTkTextbox(
            log_card, height=160, font=('Courier', 9),
            fg_color=C['bg'], text_color=C['ok'], border_width=0)
        self._log_box.pack(fill='x', padx=8, pady=8)
        self._log_box.configure(state='disabled')

        # Git instructions
        SectionHeader(body, '04', 'MANUAL UPDATE').pack(
            fill='x', padx=14, pady=(8, 4))
        mc = Card(body)
        mc.pack(fill='x', padx=14, pady=(0, 14))
        ctk.CTkLabel(mc,
            text='cd ~/mint-scan-linux\ngit pull origin main\nbash install.sh\nbash run.sh',
            font=('Courier', 10), text_color=C['ac'], justify='left'
            ).pack(anchor='w', padx=12, pady=12)

    def _ulog(self, msg):
        def _do():
            self._log_box.configure(state='normal')
            self._log_box.insert('end', msg + '\n')
            self._log_box.see('end')
            self._log_box.configure(state='disabled')
        self._safe_after(0, _do)

    def _check(self):
        self._status_lbl.configure(text='Checking GitHub...', text_color=C['ac'])
        self._ulog('Connecting to GitHub API...')
        def _bg():
            result = check_for_update()
            self._safe_after(0, self._show_result, result)
        threading.Thread(target=_bg, daemon=True).start()

    def _show_result(self, result):
        if 'error' in result:
            self._status_lbl.configure(
                text=f'✗ Check failed: {result["error"]}',
                text_color=C['wn'])
            self._ulog(f'Error: {result["error"]}')
            return

        if result['available']:
            self._status_lbl.configure(
                text=f'⬆ UPDATE AVAILABLE: {result["latest"]} (current: {result["current"]})',
                text_color=C['am'])
            self._ulog(f'New version: {result["latest"]}')
            self._ulog(result.get('notes', '')[:200])
            Btn(self._status_card, '⬇ INSTALL UPDATE',
                command=self._do_update, variant='primary', width=180
                ).pack(pady=8)
        else:
            self._status_lbl.configure(
                text=f'✓ Up to date — v{result["current"]} is latest',
                text_color=C['ok'])
            self._ulog('No update available.')

    def _do_update(self):
        self._ulog('Starting git update...')
        threading.Thread(
            target=lambda: do_git_update(self._ulog), daemon=True).start()

