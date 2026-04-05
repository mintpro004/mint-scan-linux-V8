# Mint Scan v8 — Advanced Linux Security Auditor
**By Mint Projects PTY (Ltd) · Pretoria, South Africa**

> **GitHub repo:** https://github.com/mintpro004/mint-scan-linux

## Quick Install (no git required)

```bash
# Chromebook / Ubuntu / Kali / WSL2
cd ~
curl -L https://mintscan.mintprojects.co.za/assets/mint-scan-v8.zip -o mint-scan-v8.zip
unzip mint-scan-v8.zip && mv mint-scan-v8 mint-scan-linux
cd ~/mint-scan-linux
bash install.sh
bash run.sh   # Never use sudo
```

**Alternative (if git is available):**
```bash
git clone https://github.com/mintpro004/mint-scan-linux.git ~/mint-scan-linux
cd ~/mint-scan-linux && bash install.sh && bash run.sh
```

## What's New in v8

### 🔧 Bug Fixes
- **Chromebook UFW fix** — Installer detects Crostini at runtime via `crosh`, kernel string,
  and `/proc/version`. Skips `iptables-persistent` and runs a stripped-down install that succeeds.
- **Sudo hang eliminated** — `DEBIAN_FRONTEND=noninteractive` injected into the subprocess
  environment dict, not just as a shell prefix. Fully unattended on all platforms.

### ✨ New Features
- **Traffic Log clipboard operations** — Copy All, Copy Selection (Ctrl+C), Paste (Ctrl+V /
  PASTE button), Select All (Ctrl+A), Clear, Find/Search (↓↑ with all-match highlighting),
  Save as TXT (timestamped), Save as CSV (Excel/LibreOffice). Log always editable.
- **4-platform mobile apps** — `mint_scan_android.html` (42KB, self-contained):
  8 tabs, 0–100 security score, WebRTC leak detection, port scanner, DNS/GeoIP/SSL,
  bi-directional sync, offline service worker.
  `bash build_mobile.sh all` → Android APK + iOS PWA + Windows Electron + macOS Electron

## Supported Platforms
| Platform | Status |
|---|---|
| Chromebook (Crostini) | ✅ Fixed in v8 |
| Ubuntu 20.04+ | ✅ |
| Debian 11/12 | ✅ |
| Kali Linux | ✅ |
| Windows WSL2 | ✅ |

## 22 Screens
Dashboard · Permissions · Wi-Fi · Calls · Network · Battery · Threats · Guardian ·
Notifs · Port Scan · USB Sync · Wireless · Device Scan · Recovery · Net Scan ·
Malware · Sys Fix · Firewall · Toolbox · Investigate · Auditor · Settings

## Updating
```bash
cd ~/mint-scan-linux && bash update.sh
```

## Daemon mode
Not available in v8. Coming in v9.

## Support
- Email: support@mintprojects.co.za
- Website: https://mintprojects.co.za
- GitHub: https://github.com/mintpro004/mint-scan-linux

🇿🇦 Proudly South African
