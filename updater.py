"""
Mint Scan v8.2 — Software Updater
Checks GitHub for updates via Releases API → Tags API → git log.
Update delivery: git pull (auto-detects branch) OR zip download fallback.
"""
import threading, subprocess, os, json, shutil, tempfile, zipfile
import urllib.request
import tkinter as tk
import customtkinter as ctk
from widgets import C, MONO, MONO_SM, Card, SectionHeader, Btn, ResultBox, ScrollableFrame
from widgets import InfoGrid
from logger import get_logger

log = get_logger('updater')

REPO_OWNER  = 'mintpro004'
REPO_NAME   = 'mint-scan-linux-V8'
REPO_API    = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}'
CURRENT_VER = '8.2.0'
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


def _get_default_branch(timeout=8):
    """Detect the repo's default branch (main / master / etc.)."""
    # Check local git first (fast, no network)
    try:
        r = subprocess.run('git remote show origin 2>/dev/null | grep "HEAD branch"',
                           shell=True, capture_output=True, text=True,
                           cwd=BASE_DIR, timeout=10)
        for line in r.stdout.splitlines():
            if 'HEAD branch' in line:
                branch = line.split(':', 1)[1].strip()
                if branch and branch != '(unknown)':
                    return branch
    except Exception:
        pass
    # Ask GitHub API
    try:
        req = urllib.request.Request(
            REPO_API, headers={'User-Agent': 'MintScan-Updater/8.1'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        return data.get('default_branch', 'main')
    except Exception:
        pass
    # Last resort: check local branches
    try:
        r = subprocess.run('git branch -r 2>/dev/null', shell=True,
                           capture_output=True, text=True, cwd=BASE_DIR, timeout=5)
        for line in r.stdout.splitlines():
            line = line.strip()
            if 'origin/main' in line:
                return 'main'
            if 'origin/master' in line:
                return 'master'
    except Exception:
        pass
    return 'main'


def check_for_update(timeout=10):
    """
    Check GitHub for a newer version.
    Returns dict: {available, current, latest, url, notes, method, zip_url}
    """
    current = _parse_ver(CURRENT_VER)

    # ── Method 1: GitHub Releases API ────────────────────────
    try:
        req = urllib.request.Request(
            f'{REPO_API}/releases/latest',
            headers={'User-Agent': 'MintScan-Updater/8.1'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        if 'tag_name' in data:
            tag    = data['tag_name']
            latest = _parse_ver(tag)
            notes  = (data.get('body') or '')[:800]
            url    = data.get('html_url', '')
            # Find zip asset
            zip_url = ''
            for asset in data.get('assets', []):
                if asset.get('name','').endswith('.zip'):
                    zip_url = asset.get('browser_download_url','')
                    break
            if not zip_url:
                zip_url = data.get('zipball_url', '')
            log.info(f'Releases API: current={CURRENT_VER} latest={tag}')
            return {'available': latest > current, 'current': CURRENT_VER,
                    'latest': tag, 'url': url, 'notes': notes,
                    'zip_url': zip_url, 'method': 'releases'}
        # Repo exists but no releases
        log.info('No releases yet — checking tags')
    except Exception as e:
        log.info(f'Releases API error: {e}')

    # ── Method 2: Tags API ────────────────────────────────────
    try:
        req = urllib.request.Request(
            f'{REPO_API}/tags',
            headers={'User-Agent': 'MintScan-Updater/8.1'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            tags = json.loads(r.read().decode())
        if tags:
            tag    = tags[0].get('name', CURRENT_VER)
            latest = _parse_ver(tag)
            url    = f'https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/tag/{tag}'
            zip_url = f'https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/tags/{tag}.zip'
            log.info(f'Tags API: current={CURRENT_VER} latest={tag}')
            return {'available': latest > current, 'current': CURRENT_VER,
                    'latest': tag, 'url': url, 'zip_url': zip_url,
                    'notes': 'Update available.', 'method': 'tags'}
    except Exception as e:
        log.info(f'Tags API error: {e}')

    # ── Method 3: git log (local repo) ───────────────────────
    git_dir = os.path.join(BASE_DIR, '.git')
    if os.path.isdir(git_dir):
        try:
            branch = _get_default_branch()
            subprocess.run(f'git fetch origin {branch} 2>/dev/null',
                           shell=True, cwd=BASE_DIR, timeout=20,
                           capture_output=True)
            r = subprocess.run(
                f'git rev-list HEAD..origin/{branch} --count 2>/dev/null',
                shell=True, capture_output=True, text=True,
                cwd=BASE_DIR, timeout=10)
            behind = int(r.stdout.strip() or '0')
            if behind > 0:
                log.info(f'Git: {behind} commits behind origin/{branch}')
                return {
                    'available': True, 'current': CURRENT_VER,
                    'latest': f'{CURRENT_VER}+{behind}',
                    'url': f'https://github.com/{REPO_OWNER}/{REPO_NAME}',
                    'zip_url': '',
                    'notes': f'{behind} new commit(s) on {branch}. '
                             f'Run: bash update.sh',
                    'method': 'git'}
            return {'available': False, 'current': CURRENT_VER,
                    'latest': CURRENT_VER, 'zip_url': '',
                    'notes': 'Already up to date with remote.', 'method': 'git'}
        except Exception as e:
            log.info(f'Git method: {e}')

    return {'available': False, 'current': CURRENT_VER, 'latest': '—',
            'zip_url': '',
            'notes': 'Could not reach GitHub. Check your internet connection.',
            'error': 'All update checks failed'}


def do_git_update(log_fn=None):
    """
    Pull latest via git. Auto-detects branch.
    Returns True on success.
    """
    def _l(msg):
        log.info(f'[update] {msg}')
        if log_fn:
            log_fn(msg)

    git_dir = os.path.join(BASE_DIR, '.git')
    if not os.path.isdir(git_dir):
        _l('ERROR: Not a git repository.')
        _l(f'  Clone: git clone https://github.com/{REPO_OWNER}/{REPO_NAME}.git')
        return False

    # Fix ownership (Crostini common issue)
    _l('Checking ownership...')
    subprocess.run(f'sudo chown -R "$USER:$USER" "{BASE_DIR}" 2>/dev/null || true',
                   shell=True, timeout=15, capture_output=True)

    # Detect branch
    branch = _get_default_branch()
    _l(f'Target branch: {branch}')

    # Fetch
    _l(f'Fetching from origin...')
    r = subprocess.run(f'git fetch origin {branch}',
                       shell=True, capture_output=True, text=True,
                       cwd=BASE_DIR, timeout=60)
    if r.returncode != 0:
        _l(f'Fetch failed: {r.stderr.strip()}')
        _l('Tip: check internet / git remote with: git remote -v')
        return False
    _l(r.stdout.strip() or '(fetch ok)')

    # Show what's coming
    r2 = subprocess.run(f'git log HEAD..origin/{branch} --oneline 2>/dev/null | head -8',
                        shell=True, capture_output=True, text=True,
                        cwd=BASE_DIR, timeout=10)
    if r2.stdout.strip():
        _l('Incoming changes:')
        for line in r2.stdout.strip().splitlines():
            _l(f'  {line}')

    # Pull with rebase
    _l(f'Pulling origin/{branch} --rebase...')
    r = subprocess.run(f'git pull origin {branch} --rebase',
                       shell=True, capture_output=True, text=True,
                       cwd=BASE_DIR, timeout=120)
    for line in (r.stdout + r.stderr).splitlines():
        if line.strip():
            _l(line)

    if r.returncode != 0:
        _l('Pull/rebase failed. Trying merge instead...')
        r = subprocess.run(f'git pull origin {branch} --no-rebase',
                           shell=True, capture_output=True, text=True,
                           cwd=BASE_DIR, timeout=60)
        for line in (r.stdout + r.stderr).splitlines():
            if line.strip():
                _l(line)
        if r.returncode != 0:
            _l('Pull failed. Try: bash update.sh  or  bash install.sh')
            return False

    # Update pip packages
    _l('Updating Python dependencies...')
    venv_pip = os.path.join(BASE_DIR, 'venv', 'bin', 'pip')
    req_file = os.path.join(BASE_DIR, 'requirements.txt')
    if os.path.exists(venv_pip) and os.path.exists(req_file):
        r = subprocess.run(
            f'"{venv_pip}" install -r "{req_file}" -q '
            '--break-system-packages 2>/dev/null || '
            f'"{venv_pip}" install -r "{req_file}" -q',
            shell=True, capture_output=True, text=True,
            cwd=BASE_DIR, timeout=120)
        if r.returncode == 0:
            _l('Python packages updated.')
        else:
            _l(f'pip warning: {r.stderr.strip()[:200]}')

    _l('✓ Update complete. Restart Mint Scan to apply changes.')
    _l(f'  Run: bash run.sh')
    return True


def do_zip_update(zip_url, log_fn=None):
    """
    Download a zip release and extract over the current installation.
    Used as fallback when git is not available.
    Returns True on success.
    """
    def _l(msg):
        log.info(f'[zip-update] {msg}')
        if log_fn:
            log_fn(msg)

    if not zip_url:
        _l('No zip URL available.')
        return False

    tmp_dir = tempfile.mkdtemp(prefix='mint_scan_update_')
    zip_path = os.path.join(tmp_dir, 'update.zip')

    try:
        _l(f'Downloading: {zip_url}')
        req = urllib.request.Request(
            zip_url,
            headers={'User-Agent': 'MintScan-Updater/8.1'})

        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            with open(zip_path, 'wb') as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded / total * 100)
                        _l(f'  {pct}%  ({downloaded//1024} KB / {total//1024} KB)')

        _l(f'Downloaded {os.path.getsize(zip_path)//1024} KB')
        _l('Extracting...')

        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            # GitHub zips have a top-level dir like  repo-name-v8.1.0/
            prefix = names[0].split('/')[0] + '/' if names else ''
            extracted = 0
            for name in names:
                target_rel = name[len(prefix):] if prefix else name
                if not target_rel:
                    continue
                target_path = os.path.join(BASE_DIR, target_rel)
                if name.endswith('/'):
                    os.makedirs(target_path, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(name) as src, open(target_path, 'wb') as dst:
                        dst.write(src.read())
                    extracted += 1
            _l(f'Extracted {extracted} files.')

        # Re-run install.sh to update deps
        install_sh = os.path.join(BASE_DIR, 'install.sh')
        if os.path.exists(install_sh):
            _l('Running install.sh to update dependencies...')
            r = subprocess.run('bash install.sh', shell=True,
                               capture_output=True, text=True,
                               cwd=BASE_DIR, timeout=300)
            for line in r.stdout.splitlines()[-10:]:
                _l(line)

        _l('✓ Zip update complete. Restart Mint Scan to apply.')
        return True

    except Exception as e:
        _l(f'Zip update failed: {e}')
        return False
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


class UpdaterScreen(ctk.CTkFrame):
    def _safe_after(self, delay, fn, *args):
        def _g():
            try:
                if self.winfo_exists():
                    fn(*args)
            except Exception:
                pass
        try:
            self.after(delay, _g)
        except Exception:
            pass

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C['bg'], corner_radius=0)
        self.app      = app
        self._built   = False
        self._result  = None   # last check result

    def on_focus(self):
        if not self._built:
            self._build()
            self._built = True

    def on_blur(self):
        pass

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['sf'], height=48, corner_radius=0)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text='🔄  SOFTWARE UPDATER  —  v' + CURRENT_VER,
                     font=('DejaVu Sans Mono', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)
        Btn(hdr, '🔍 CHECK NOW', command=self._check,
            width=130).pack(side='right', padx=8, pady=6)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)
        self._body = body

        # Version info
        SectionHeader(body, '01', 'CURRENT VERSION').pack(
            fill='x', padx=14, pady=(14, 4))
        vc = Card(body)
        vc.pack(fill='x', padx=14, pady=(0, 8))
        self._ver_grid = InfoGrid(vc, [
            ('VERSION',  CURRENT_VER,                             C['ac']),
            ('REPO',     f'{REPO_OWNER}/{REPO_NAME}',             C['tx']),
            ('INSTALL',  'git clone' if os.path.isdir(
                          os.path.join(BASE_DIR, '.git')) else 'zip install', C['ok']),
            ('BASE DIR', BASE_DIR[:40],                           C['mu']),
        ], columns=2)
        self._ver_grid.pack(fill='x', padx=8, pady=8)

        # Git status
        git_dir = os.path.join(BASE_DIR, '.git')
        if os.path.isdir(git_dir):
            r = subprocess.run('git log --oneline -1 2>/dev/null',
                               shell=True, capture_output=True, text=True,
                               cwd=BASE_DIR, timeout=5)
            commit = r.stdout.strip() or 'unknown'
            ctk.CTkLabel(vc, text=f'Git commit: {commit[:72]}',
                         font=('DejaVu Sans Mono', 8), text_color=C['mu']
                         ).pack(anchor='w', padx=12, pady=(0, 8))

        # Status card — use a plain frame (NOT Card) so button children are reliable
        SectionHeader(body, '02', 'UPDATE STATUS').pack(
            fill='x', padx=14, pady=(8, 4))
        self._status_outer = ctk.CTkFrame(body, fg_color=C['sf'],
                                          border_color=C['br'], border_width=1,
                                          corner_radius=8)
        self._status_outer.pack(fill='x', padx=14, pady=(0, 8))
        self._status_lbl = ctk.CTkLabel(
            self._status_outer,
            text='Tap CHECK NOW to query GitHub releases.',
            font=MONO_SM, text_color=C['mu'])
        self._status_lbl.pack(padx=12, pady=(12, 4))
        # Placeholder for action buttons — always a fresh inner frame
        self._action_frame = ctk.CTkFrame(self._status_outer, fg_color='transparent')
        self._action_frame.pack(fill='x', padx=12, pady=(0, 12))

        # Update log
        SectionHeader(body, '03', 'UPDATE LOG').pack(
            fill='x', padx=14, pady=(8, 4))
        log_card = Card(body)
        log_card.pack(fill='x', padx=14, pady=(0, 8))
        self._log_box = ctk.CTkTextbox(
            log_card, height=200,
            font=('DejaVu Sans Mono', 9),
            fg_color=C['bg'], text_color=C['ok'], border_width=0)
        self._log_box.pack(fill='x', padx=8, pady=8)
        self._log_box.configure(state='disabled')

        # Manual instructions
        SectionHeader(body, '04', 'MANUAL UPDATE COMMANDS').pack(
            fill='x', padx=14, pady=(8, 4))
        mc = Card(body)
        mc.pack(fill='x', padx=14, pady=(0, 14))
        ctk.CTkLabel(mc,
            text='# If installed via git:\n'
                 'cd ~/mint-scan-linux-V8\n'
                 'bash update.sh\n\n'
                 '# Or manually:\n'
                 'git pull origin main   # or: git pull origin master\n'
                 'bash install.sh\n'
                 'bash run.sh',
            font=('DejaVu Sans Mono', 9), text_color=C['ac'],
            justify='left').pack(anchor='w', padx=12, pady=12)

    def _ulog(self, msg):
        def _do():
            try:
                self._log_box.configure(state='normal')
                self._log_box.insert('end', msg + '\n')
                self._log_box.see('end')
                self._log_box.configure(state='disabled')
            except Exception:
                pass
        self._safe_after(0, _do)

    def _check(self):
        if not hasattr(self, '_status_lbl'): return
        self._status_lbl.configure(text='Checking GitHub…', text_color=C['ac'])
        for w in self._action_frame.winfo_children():
            w.destroy()
        self._ulog('─' * 50)
        self._ulog('Connecting to GitHub…')

        def _bg():
            result = check_for_update()
            self._result = result
            self._safe_after(0, self._show_result, result)
        threading.Thread(target=_bg, daemon=True).start()

    def _show_result(self, result):
        # Clear old action buttons
        for w in self._action_frame.winfo_children():
            w.destroy()

        method = result.get('method', 'unknown')
        self._ulog(f'Method used: {method}')

        if result.get('error') and not result.get('available'):
            self._status_lbl.configure(
                text=f'⚠ Check failed — {result.get("notes", "See log")}',
                text_color=C['am'])
            self._ulog(result.get('notes', result.get('error', '')))
            return

        if result['available']:
            self._status_lbl.configure(
                text=f'⬆  UPDATE AVAILABLE  ·  v{result["latest"]}',
                text_color=C['am'])
            self._ulog(f'Current: {result["current"]}  →  Latest: {result["latest"]}')
            notes = result.get('notes', '')
            if notes:
                for line in notes.splitlines()[:8]:
                    self._ulog(f'  {line}')

            # Action buttons row
            has_git  = os.path.isdir(os.path.join(BASE_DIR, '.git'))
            has_zip  = bool(result.get('zip_url'))

            if has_git:
                Btn(self._action_frame, '⬇ GIT PULL UPDATE',
                    command=self._do_git_update,
                    variant='primary', width=190).pack(side='left', padx=(0, 8))
            if has_zip:
                Btn(self._action_frame, '📦 DOWNLOAD ZIP',
                    command=self._do_zip_update,
                    variant='ghost', width=160).pack(side='left', padx=(0, 8))
            if not has_git and not has_zip:
                self._ulog('No automated update available. Use manual commands above.')
        else:
            self._status_lbl.configure(
                text=f'✓ Up to date  (v{result["current"]})',
                text_color=C['ok'])
            self._ulog(result.get('notes', 'Already at latest version.'))

    def _do_git_update(self):
        for w in self._action_frame.winfo_children():
            w.destroy()
        self._ulog('─' * 50)
        self._ulog('Starting git pull update…')
        self._status_lbl.configure(text='Updating via git…', text_color=C['ac'])

        def _bg():
            ok = do_git_update(self._ulog)
            def _done():
                try:
                    if ok:
                        self._status_lbl.configure(
                            text='✓ Update complete — restart app to apply',
                            text_color=C['ok'])
                    else:
                        self._status_lbl.configure(
                            text='⚠ Update had errors — check log',
                            text_color=C['wn'])
                        # Offer zip fallback
                        if self._result and self._result.get('zip_url'):
                            Btn(self._action_frame, '📦 TRY ZIP FALLBACK',
                                command=self._do_zip_update,
                                variant='warning', width=180).pack(pady=4)
                except Exception:
                    pass
            self._safe_after(0, _done)
        threading.Thread(target=_bg, daemon=True).start()

    def _do_zip_update(self):
        for w in self._action_frame.winfo_children():
            w.destroy()
        if not self._result or not self._result.get('zip_url'):
            self._ulog('No zip URL. Run CHECK NOW first.')
            return
        self._ulog('─' * 50)
        self._ulog('Starting zip download update…')
        self._status_lbl.configure(text='Downloading update…', text_color=C['ac'])

        def _bg():
            ok = do_zip_update(self._result['zip_url'], self._ulog)
            def _done():
                try:
                    self._status_lbl.configure(
                        text='✓ Zip update done — restart to apply' if ok
                             else '⚠ Zip update failed — check log',
                        text_color=C['ok'] if ok else C['wn'])
                except Exception:
                    pass
            self._safe_after(0, _done)
        threading.Thread(target=_bg, daemon=True).start()
