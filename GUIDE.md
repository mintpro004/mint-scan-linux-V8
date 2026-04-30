<div style="background-color: #ffffff; color: #000000; padding: 40px; font-family: sans-serif;">

<h1 style="color: #0056b3; border-bottom: 2px solid #0056b3;">MINT SCAN v8.3.0 — USER GUIDE</h1>

<p>Welcome to <strong>Mint Scan v8.3.0</strong>, the world-standard security auditing and system utility suite for Linux. This guide provides comprehensive instructions for installation, usage, and optimization.</p>

<h2 style="color: #0056b3;">1. Installation & Setup</h2>
<p>Mint Scan is designed to run on Debian-based distributions, including Ubuntu, Kali Linux, and ChromeOS (Crostini).</p>

<pre style="background-color: #f8f9fa; color: #333; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
git clone https://github.com/mintpro004/mint-scan-linux-V8.git ~/mint-scan-linux
cd ~/mint-scan-linux
bash install.sh
bash run.sh
</pre>

<h2 style="color: #0056b3;">2. Core Modules</h2>

<h3 style="color: #007bff;">🛡️ Security & Auditing</h3>
<ul>
    <li><strong>IDS/IPS:</strong> Real-time intrusion detection using Suricata and Snort. Automatically detects your active network interface.</li>
    <li><strong>Malware Scanner:</strong> Integrated ClamAV and rkhunter for deep system scanning and threat removal.</li>
    <li><strong>CVE Lookup:</strong> Live queries to the NIST NVD database for vulnerability assessment of local services.</li>
</ul>

<h3 style="color: #007bff;">📡 Network Intelligence</h3>
<ul>
    <li><strong>Analog Speedometer:</strong> High-precision real-time bandwidth monitoring.</li>
    <li><strong>VPN Client:</strong> Securely manage WireGuard and OpenVPN connections with one-click connectivity.</li>
    <li><strong>Port Scanner:</strong> Multi-threaded local and remote port scanning with service fingerprinting.</li>
</ul>

<h3 style="color: #007bff;">🔧 System Health</h3>
<ul>
    <li><strong>Sys Fix:</strong> Automated repair of common package issues, permission errors, and system bloat.</li>
    <li><strong>Guardian:</strong> Background monitor that watches for brute-force attempts and suspicious connections.</li>
</ul>

<h2 style="color: #0056b3;">3. Security Hardening</h2>
<p>Version 8.3.0 includes <strong>advanced security hardening</strong>:</p>
<ul>
    <li><strong>Shell Injection Protection:</strong> All system commands now use list-based execution to prevent exploitation.</li>
    <li><strong>Input Validation:</strong> All user inputs are sanitized via strict regex filters.</li>
    <li><strong>Non-interactive Elevation:</strong> Background tasks use secure elevation protocols to prevent UI hangs.</li>
</ul>

<h2 style="color: #0056b3;">4. Troubleshooting</h2>
<p>If you encounter issues with package installation, ensure your user has sudo privileges. Run <code>bash update.sh</code> to synchronize your local environment with the latest security patches.</p>

<hr style="border: 1px solid #ddd;">
<p style="font-size: 0.8em; color: #666;">© 2026 Mint Projects PTY (Ltd) · Pretoria, South Africa</p>

</div>
