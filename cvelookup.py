"""
Mint Scan v8 — CVE Vulnerability Database Lookup
Queries the NIST NVD API (free, no key) for CVE data on detected services.
"""
import tkinter as tk
import customtkinter as ctk
import threading, json, time
import urllib.request, urllib.parse
from widgets import (C, MONO, MONO_SM, ScrollableFrame, Card,
                     SectionHeader, Btn, ResultBox, InfoGrid)
from logger import get_logger

log = get_logger('cvelookup')

NVD_API = 'https://services.nvd.nist.gov/rest/json/cves/2.0'


def search_cves(keyword: str, results: int = 10) -> list:
    """
    Query NIST NVD for CVEs matching keyword (e.g. 'openssh 9.0').
    Returns list of dicts: {id, description, severity, cvss, published, url}
    """
    params = urllib.parse.urlencode({
        'keywordSearch': keyword,
        'resultsPerPage': results,
    })
    url = f'{NVD_API}?{params}'
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'MintScan-CVE/8'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())

        items = []
        for vuln in data.get('vulnerabilities', []):
            cve  = vuln.get('cve', {})
            cve_id = cve.get('id', '?')
            desc = next(
                (d['value'] for d in cve.get('descriptions', [])
                 if d.get('lang') == 'en'),
                'No description')[:300]
            # CVSS
            metrics = cve.get('metrics', {})
            severity = cvss = '—'
            for key in ('cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2'):
                m_list = metrics.get(key, [])
                if m_list:
                    cvss_data = m_list[0].get('cvssData', {})
                    cvss      = str(cvss_data.get('baseScore', '—'))
                    severity  = cvss_data.get('baseSeverity', '—')
                    break
            pub = cve.get('published', '—')[:10]
            items.append({
                'id':          cve_id,
                'description': desc,
                'severity':    severity,
                'cvss':        cvss,
                'published':   pub,
                'url':         f'https://nvd.nist.gov/vuln/detail/{cve_id}',
            })
        log.info(f'CVE search "{keyword}": {len(items)} results')
        return items
    except Exception as e:
        log.warning(f'CVE lookup error: {e}')
        return []


def severity_color(sev: str) -> str:
    s = sev.upper()
    return (C['wn'] if s == 'CRITICAL' else
            C['am'] if s == 'HIGH'     else
            C['bl'] if s == 'MEDIUM'   else C['ok'])


class CVELookupScreen(ctk.CTkFrame):
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
        ctk.CTkLabel(hdr, text='🔍  CVE VULNERABILITY LOOKUP',
                     font=('Courier', 13, 'bold'),
                     text_color=C['ac']).pack(side='left', padx=16)

        body = ScrollableFrame(self)
        body.pack(fill='both', expand=True)

        # Search
        SectionHeader(body, '01', 'SEARCH').pack(
            fill='x', padx=14, pady=(14, 4))
        sc = Card(body)
        sc.pack(fill='x', padx=14, pady=(0, 8))
        sr = ctk.CTkFrame(sc, fg_color='transparent')
        sr.pack(fill='x', padx=12, pady=12)
        self._q = ctk.CTkEntry(
            sr, placeholder_text='service + version, e.g. "openssh 8.9" or "apache 2.4"',
            font=('Courier', 10), fg_color=C['bg'],
            border_color=C['br'], text_color=C['tx'], height=34)
        self._q.pack(side='left', fill='x', expand=True, padx=(0, 8))
        Btn(sr, '🔍 SEARCH', command=self._search,
            width=100).pack(side='left')
        self._q.bind('<Return>', lambda e: self._search())

        # Quick searches from open ports
        SectionHeader(body, '02', 'QUICK SCAN — LOCAL SERVICES').pack(
            fill='x', padx=14, pady=(8, 4))
        qc = Card(body)
        qc.pack(fill='x', padx=14, pady=(0, 8))
        Btn(qc, '⚡ SCAN LOCAL SERVICES FOR CVEs',
            command=self._quick_scan, width=240
            ).pack(pady=10)
        self._quick_lbl = ctk.CTkLabel(
            qc, text='Checks SSH, Apache, Nginx, MySQL on this machine.',
            font=MONO_SM, text_color=C['mu'])
        self._quick_lbl.pack(pady=(0, 10))

        # Results
        SectionHeader(body, '03', 'RESULTS').pack(
            fill='x', padx=14, pady=(8, 4))
        self._res_frame = ctk.CTkFrame(body, fg_color='transparent')
        self._res_frame.pack(fill='x', padx=14, pady=(0, 14))
        ctk.CTkLabel(self._res_frame,
            text='Search results appear here.',
            font=MONO_SM, text_color=C['mu']).pack(pady=12)

    def _search(self):
        q = self._q.get().strip()
        if not q:
            return
        for w in self._res_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._res_frame,
            text=f'Searching NVD for "{q}"...',
            font=MONO_SM, text_color=C['ac']).pack(pady=8)
        def _bg():
            results = search_cves(q)
            self._safe_after(0, self._show_results, results, q)
        threading.Thread(target=_bg, daemon=True).start()

    def _quick_scan(self):
        self._quick_lbl.configure(text='Detecting services...', text_color=C['ac'])
        def _bg():
            from utils import run_cmd
            services = []
            for cmd, svc in [
                ('ssh -V 2>&1 | head -1', 'OpenSSH'),
                ('apache2 -v 2>/dev/null | head -1', 'Apache'),
                ('nginx -v 2>&1 | head -1', 'Nginx'),
                ('mysql --version 2>/dev/null | head -1', 'MySQL'),
                ('python3 --version 2>/dev/null', 'Python'),
            ]:
                out, _, rc = run_cmd(cmd)
                if rc == 0 and out.strip():
                    services.append(f'{svc} {out.strip()[:40]}')
            self._safe_after(0, self._quick_lbl.configure,
                       {'text': f'Found: {", ".join(services) or "none"}',
                        'text_color': C['tx']})
            all_cves = []
            for svc in services[:4]:
                cves = search_cves(svc, results=3)
                all_cves.extend(cves)
            self._safe_after(0, self._show_results, all_cves, 'local services')
        threading.Thread(target=_bg, daemon=True).start()

    def _show_results(self, results, query):
        for w in self._res_frame.winfo_children():
            w.destroy()
        if not results:
            ctk.CTkLabel(self._res_frame,
                text=f'No CVEs found for "{query}".',
                font=MONO_SM, text_color=C['mu']).pack(pady=12)
            return
        ctk.CTkLabel(self._res_frame,
            text=f'{len(results)} CVE(s) for "{query}"',
            font=('Courier', 10, 'bold'),
            text_color=C['ac']).pack(anchor='w', pady=(4, 6))
        for cve in results:
            col = severity_color(cve['severity'])
            card = ctk.CTkFrame(
                self._res_frame, fg_color=C['sf'],
                border_color=col, border_width=1, corner_radius=6)
            card.pack(fill='x', pady=3)
            hr = ctk.CTkFrame(card, fg_color='transparent')
            hr.pack(fill='x', padx=10, pady=(8, 2))
            ctk.CTkLabel(hr, text=cve['id'],
                font=('Courier', 11, 'bold'), text_color=col
                ).pack(side='left')
            ctk.CTkLabel(hr,
                text=f"CVSS {cve['cvss']}  [{cve['severity']}]  {cve['published']}",
                font=('Courier', 8), text_color=C['mu']
                ).pack(side='right')
            ctk.CTkLabel(card, text=cve['description'],
                font=('Courier', 9), text_color=C['tx'],
                wraplength=700, justify='left'
                ).pack(anchor='w', padx=10, pady=(0, 4))
            ctk.CTkLabel(card, text=cve['url'],
                font=('Courier', 8), text_color=C['bl'],
                cursor='hand2'
                ).pack(anchor='w', padx=10, pady=(0, 8))

