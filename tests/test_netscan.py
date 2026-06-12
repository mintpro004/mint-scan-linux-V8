import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import re

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 1. Mock UI modules before importing logic
class MockCTkFrame:
    def __init__(self, *args, **kwargs): pass
    def pack(self, *args, **kwargs): pass
    def grid(self, *args, **kwargs): pass
    def winfo_exists(self): return True
    def after(self, delay, fn, *args, **kwargs):
        if fn: fn(*args, **kwargs)
    def configure(self, *args, **kwargs): pass
    def winfo_children(self): return []
    def destroy(self): pass

mock_ctk = MagicMock()
mock_ctk.CTkFrame = MockCTkFrame
sys.modules['customtkinter'] = mock_ctk

mock_widgets = MagicMock()
mock_widgets.CTkFrame = MockCTkFrame
mock_widgets.Card = MockCTkFrame
mock_widgets.ScrollableFrame = MockCTkFrame
mock_widgets.SectionHeader = MockCTkFrame
mock_widgets.ResultBox = MockCTkFrame
mock_widgets.InfoGrid = MockCTkFrame
mock_widgets.Btn = MagicMock
mock_widgets.C = {'bg': '#000000', 'sf': '#111111', 'ac': '#00ffff', 'ok': '#00ff00', 'wn': '#ffff00', 'br': '#222222', 'mu': '#888888', 'bl': '#0000ff', 'am': '#ff8800'}
mock_widgets.MONO_SM = ('Courier', 10)
sys.modules['widgets'] = mock_widgets

sys.modules['reports'] = MagicMock()
sys.modules['installer'] = MagicMock()

# Now we can import the screen class
from netscan import NetScanScreen

class MockApp:
    def __init__(self):
        self._frames = {}
    def _switch_tab(self, name):
        pass

class TestNetScanLogic(unittest.TestCase):

    def setUp(self):
        self.app = MockApp()
        self.parent = MagicMock()
        self.screen = NetScanScreen(self.parent, self.app)

    @patch('netscan.run')
    def test_do_scan_nmap(self, mock_run):
        # Mock responses
        def side_effect(cmd, timeout=30):
            if cmd == ["ip", "route"]:
                return ("default via 192.168.1.1 dev eth0 proto dhcp metric 100\n"
                        "192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.10 metric 100", "", 0)
            if cmd == ["nmap", "-sn", "192.168.1.0/24"]:
                return ("Nmap scan report for router.home (192.168.1.1)\n"
                        "Host is up (0.0010s latency).\n"
                        "MAC Address: AA:BB:CC:DD:EE:FF (TP-Link)\n"
                        "Nmap scan report for mint-laptop (192.168.1.10)\n"
                        "Host is up (0.00010s latency).", "", 0)
            return ("", "", 0)

        mock_run.side_effect = side_effect
        
        with patch.object(self.screen, '_render_devices') as mock_render:
            self.screen._do_scan()
            
            args, _ = mock_render.call_args
            devices = args[0]
            subnet = args[1]
            
            self.assertEqual(subnet, "192.168.1.0/24")
            self.assertEqual(len(devices), 2)
            self.assertEqual(devices[0]['ip'], "192.168.1.1")
            self.assertEqual(devices[0]['mac'], "AA:BB:CC:DD:EE:FF")
            self.assertEqual(devices[0]['vendor'], "TP-Link")

    @patch('netscan.run')
    def test_do_vuln_logic(self, mock_run):
        # Mock responses showing vulnerabilities
        def side_effect(cmd, timeout=30):
            if cmd == ["sudo", "ufw", "status"]:
                return ("Status: inactive", "", 0)
            if cmd == ["ss", "-tlnp"]:
                return ("State  Recv-Q Send-Q Local Address:Port  Peer Address:Port\n"
                        "LISTEN 0      128          0.0.0.0:23          0.0.0.0:*\n"
                        "LISTEN 0      128          0.0.0.0:4444        0.0.0.0:*", "", 0)
            if cmd == ["grep", "-E", "PermitRootLogin|PasswordAuthentication|Port", "/etc/ssh/sshd_config"]:
                return ("PermitRootLogin yes\nPasswordAuthentication yes", "", 0)
            if cmd == ["resolvectl", "status"]:
                return ("Global\n         Protocols: -LLMNR -mDNS -DNSOverTLS DNSSEC=no/unsupported\n"
                        "  current DNS Server: 8.8.8.8", "", 0)
            if cmd == ["nmcli", "-t", "-f", "ACTIVE,SECURITY", "dev", "wifi"]:
                return ("yes:WEP", "", 0)
            return ("", "", 0)

        mock_run.side_effect = side_effect
        
        with patch.object(self.screen, '_render_vulns') as mock_render:
            self.screen._do_vuln()
            
            args, _ = mock_render.call_args
            vulns = args[0]
            
            vuln_titles = [v[1] for v in vulns]
            self.assertIn('Firewall (UFW) is INACTIVE', vuln_titles)
            self.assertIn('Dangerous port open: 23 (Telnet)', vuln_titles)
            self.assertIn('SSH allows root login', vuln_titles)
            self.assertIn('Using plain DNS (not encrypted)', vuln_titles)
            self.assertIn('Connected to WEP-encrypted network', vuln_titles)

if __name__ == '__main__':
    unittest.main()
