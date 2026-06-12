import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils import ping, get_system_info, analyse_phone_number

class TestUtils(unittest.TestCase):

    @patch('utils.run_cmd')
    def test_ping_success(self, mock_run):
        # Mock successful ping output
        mock_run.return_value = ("PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.\n"
                                 "64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=14.2 ms\n"
                                 "\n"
                                 "--- 1.1.1.1 ping statistics ---\n"
                                 "1 packets transmitted, 1 received, 0% packet loss, time 0ms\n"
                                 "rtt min/avg/max/mdev = 14.162/14.162/14.162/0.000 ms", "", 0)
        
        result = ping('1.1.1.1')
        self.assertEqual(result, 14.162)
        mock_run.assert_called_once()

    @patch('utils.run_cmd')
    def test_ping_failure(self, mock_run):
        # Mock failed ping
        mock_run.return_value = ("", "Network is unreachable", 1)
        result = ping('1.1.1.1')
        self.assertIsNone(result)

    @patch('utils.run_cmd')
    def test_get_system_info(self, mock_run):
        # Mock various system commands
        def side_effect(cmd, timeout=8):
            if cmd == ['uname', '-r']:
                return ("6.1.0-21-amd64", "", 0)
            if cmd == ['grep', 'model name', '/proc/cpuinfo']:
                return ("model name	: Intel(R) Core(TM) i7-10710U CPU @ 1.10GHz", "", 0)
            if cmd == ['nproc']:
                return ("12", "", 0)
            if cmd == ['free', '-h']:
                return ("              total        used        free      shared  buff/cache   available\n"
                        "Mem:            15Gi       4.2Gi       6.1Gi       456Mi       5.1Gi        10Gi\n"
                        "Swap:          2.0Gi          0B       2.0Gi", "", 0)
            if cmd == ['uptime', '-p']:
                return ("up 2 hours, 30 minutes", "", 0)
            if cmd == ['df', '-h', '/']:
                return ("Filesystem      Size  Used Avail Use% Mounted on\n"
                        "/dev/sda1       100G   20G   75G  21% /", "", 0)
            if cmd == ['lspci']:
                return ("00:02.0 VGA compatible controller: Intel Corporation UHD Graphics (rev 02)", "", 0)
            return ("", "", 0)

        mock_run.side_effect = side_effect
        
        info = get_system_info()
        
        self.assertEqual(info['kernel'], "6.1.0-21-amd64")
        self.assertEqual(info['cpu_model'], "Intel(R) Core(TM) i7-10710U CPU @ 1.10GHz")
        self.assertEqual(info['cpu_cores'], "12")
        self.assertEqual(info['ram_total'], "15Gi")
        self.assertEqual(info['disk_pct'], "21%")
        self.assertIn("Intel Corporation UHD Graphics", info['gpu'])

    def test_analyse_phone_number(self):
        # Test SA phone number analysis
        res = analyse_phone_number("0821234567")
        self.assertEqual(res['operator'], "Vodacom")
        self.assertEqual(res['risk'], "LOW")
        
        res_risk = analyse_phone_number("0821111111")
        self.assertEqual(res_risk['risk'], "HIGH")
        self.assertIn("Repeating digits", res_risk['reasons'])

if __name__ == '__main__':
    unittest.main()
