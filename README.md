# Mint Scan v8.2 — World-Standard Linux Security Auditor
**Mint Projects PTY (Ltd) · Pretoria, South Africa · 2026**

Mint Scan v8.2 is an advanced security and system utility suite for Linux, featuring **comprehensive security hardening** against shell injection and unauthorized elevation.

## 🚀 NEW IN v8.2
- **Security Hardening:** Refactored `run_cmd` for list-based secure execution.
- **Injection Protection:** Sanitized inputs for VPN, IDS, and Malware modules.
- **Categorized UI:** 30+ screens organized into Health, Network, Security, and Tools.
- **API Optimization:** NIST NVD live lookups with exponential backoff and caching.

## 📖 Comprehensive Guide
For a full walkthrough of features and advanced setup, see: **[GUIDE.md](./GUIDE.md)**

```bash
git clone https://github.com/mintpro004/mint-scan-linux-V8.git ~/mint-scan-linux
cd ~/mint-scan-linux
bash install.sh
bash run.sh          # Never: sudo bash run.sh
```

## Update

```bash
cd ~/mint-scan-linux
bash update.sh       # git pull + re-install deps
```

## 31 Security Screens + 13 New Features

| Tab | Screen |
|-----|--------|
| Dashboard | Live score ring, CPU/RAM charts, threat status |
| Permissions | SUID/SGID audit, world-writable paths |
| Wi-Fi | Network scan, rogue AP detection |
| Calls | Active connections, socket audit |
| Network | **Analog speedometer gauges**, ping graph, clipboard traffic log |
| Battery | Health, cycles, charge history |
| Threats | 19 malware indicators, one-click fix |
| Guardian | **Real monitoring** — SSH brute-force, dangerous ports, auto-notify |
| Notifs | Security event history |
| Port Scan | Threaded scanner, service detection |
| USB Sync | Android data recovery, SQLite extraction |
| Wireless | Wi-Fi server, phone sync |
| Device Scan | IoT/CCTV fingerprinting, 30+ vendor MACs |
| Recovery | Deleted file recovery, WhatsApp DB |
| Net Scan | Subnet scanner, ARP table |
| Malware | ClamAV + rkhunter |
| Sys Fix | System repair, package resolver |
| Firewall | **Chromebook-fixed** UFW GUI |
| Toolbox | Security utilities |
| Investigate | IP intel, WHOIS, GeoIP |
| Auditor | POPIA compliance reports |
| CVE Lookup | **NIST NVD live lookup** |
| Secure Erase | **DoD 3-pass shred** |
| VPN | **WireGuard + OpenVPN** (auto-detect configs) |
| IDS/IPS | **Suricata + Snort** (auto-detect interface) |
| Web Monitor | **Remote browser dashboard** (port 7777) |
| Daemon | **systemd service** install/manage |
| Updater | **GitHub releases** auto-update |
| Plugins | Plugin manager |
| Marketplace | **Plugin marketplace** (GitHub catalogue) |
| Terminal | **Built-in PTY terminal** + history |
| Settings | Dark/light theme, instant apply |

## Mobile Apps

```bash
bash build_mobile.sh all          # Android · iOS · Windows · macOS
bash build_mobile.sh android      # Android only
```

## Requirements

- Python 3.8+
- Chromebook (Crostini), Ubuntu 20.04+, Debian 11+, Kali Linux, WSL2

## No direct downloads — git clone only

All updates via `bash update.sh` (git pull). No zip files distributed.

---
© 2026 Mint Projects PTY (Ltd) · github.com/mintpro004/mint-scan-linux-V8
