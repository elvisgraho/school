"""LAN lifecycle regressions without Streamlit or Windows dependencies."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    'local_server', Path(__file__).resolve().parents[1] / 'utils/local_server.py'
)
lan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lan)


class LocalServerTest(unittest.TestCase):
    def setUp(self):
        with patch.object(lan.atexit, 'register'):
            self.server = lan.LocalServer()

    def test_selected_adapter_overrides_route_and_shares_database_and_stops(self):
        child = Mock(pid=123)
        child.poll.return_value = None
        response = Mock(status=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(lan.sys, 'platform', 'linux'), \
                patch.object(lan, '_free_port', return_value=8502), \
                patch.object(lan, 'lan_address', return_value='10.8.0.2') as detected_address, \
                patch.object(lan.subprocess, 'Popen', return_value=child) as popen, \
                patch.object(lan.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value = response
            try:
                self.server.start(address='192.168.1.20')
                detected_address.assert_not_called()
                directory = self.server.directory
                self.assertTrue(self.server.running)
                self.assertEqual(self.server.url, 'http://192.168.1.20:8502')
                command = popen.call_args.args[0]
                self.assertEqual(command[command.index('--server.address') + 1], '192.168.1.20')
                self.assertEqual(popen.call_args.kwargs['cwd'], Path.cwd())
                self.assertEqual(popen.call_args.kwargs['env'][lan.LAN_CHILD], '1')
                self.assertNotEqual(popen.call_args.kwargs['stdout'], subprocess.PIPE)
                self.server.start()
                popen.assert_called_once()
            finally:
                self.server.stop()
            child.terminate.assert_called_once()
            child.wait.assert_called_once()
            self.assertFalse(directory.exists())
            self.assertFalse(self.server.running)

    def test_failed_start_stops_child_and_cleans_temporary_files(self):
        child = Mock(pid=123)
        child.poll.return_value = 1
        with patch.object(lan.sys, 'platform', 'win32'), \
                patch.object(lan.subprocess, 'CREATE_NO_WINDOW', 0, create=True), \
                patch.object(lan, '_free_port', return_value=8502), \
                patch.object(lan, 'lan_address', return_value='192.168.1.20'), \
                patch.object(lan.subprocess, 'Popen', return_value=child):
            with self.assertRaisesRegex(RuntimeError, 'failed to start'):
                self.server.start()
        self.assertIsNone(self.server.directory)
        self.assertFalse(self.server.running)

    def test_firewall_failure_rolls_back_server(self):
        child = Mock(pid=123)
        child.poll.return_value = None
        response = Mock(status=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(lan.sys, 'platform', 'win32'), \
                patch.object(lan.subprocess, 'CREATE_NO_WINDOW', 0, create=True), \
                patch.object(lan, '_free_port', return_value=8502), \
                patch.object(lan, 'lan_address', return_value='192.168.1.20'), \
                patch.object(lan.subprocess, 'Popen', return_value=child), \
                patch.object(lan.urllib.request, 'build_opener') as opener, \
                patch.object(lan.subprocess, 'run', return_value=Mock(returncode=1)):
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(RuntimeError, 'administrator prompt'):
                self.server.start()
        child.terminate.assert_called_once()
        self.assertIsNone(self.server.directory)

    def test_cleanup_waits_for_firewall_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            self.server.directory = Path(directory)
            self.server.firewall_requested = True
            with patch.object(lan.time, 'monotonic', side_effect=[0, 11]):
                with self.assertRaisesRegex(RuntimeError, 'cleanup is not confirmed'):
                    self.server.stop()
            self.assertTrue((Path(directory) / 'stop').exists())
            self.assertTrue(self.server.firewall_requested)
            (Path(directory) / 'removed').touch()
            self.server.stop()
            self.assertFalse(self.server.firewall_requested)

    def test_firewall_is_private_subnet_scoped_and_watches_both_processes(self):
        script = lan._firewall_script("C:/User's folder", 'unique-rule', 8502, 123, '192.168.178.20')
        self.assertIn('-Profile Private -RemoteAddress LocalSubnet', script)
        self.assertIn('-LocalPort 8502', script)
        self.assertIn("-LocalAddress '192.168.178.20'", script)
        self.assertIn("$rule = 'unique-rule'", script)
        self.assertIn("'C:/User''s folder'", script)
        self.assertIn('$owner.HasExited', script)
        self.assertIn('$child.HasExited', script)
        self.assertIn('Remove-NetFirewallRule', script)
        self.assertIn('$child.Kill()', script)
        self.assertIn('finally', script)


class NetworkAddressTest(unittest.TestCase):
    def test_physical_home_adapter_beats_vpn_and_virtual_adapters(self):
        records = [
            {'Address': '10.8.0.2', 'Adapter': 'VPN', 'Physical': False, 'Private': True, 'Gateway': True},
            {'Address': '172.24.64.1', 'Adapter': 'vEthernet', 'Physical': False, 'Private': True},
            {'Address': '192.168.178.20', 'Adapter': 'Wi-Fi', 'Physical': True, 'Private': True, 'Gateway': True},
            {'Address': '169.254.10.2', 'Adapter': 'Ethernet', 'Physical': True},
            {'Address': '127.0.0.1', 'Adapter': 'Loopback'},
        ]
        with patch.object(lan.sys, 'platform', 'win32'), \
                patch.object(lan, '_windows_addresses', return_value=records):
            options = lan.network_addresses()
            self.assertEqual(lan.lan_address(), '192.168.178.20')
        self.assertIn(('10.8.0.2', 'VPN — 10.8.0.2'), options)
        self.assertFalse(any(ip == '127.0.0.1' for ip, _ in options))

    def test_single_adapter_json_and_duplicate_ips_are_supported(self):
        record = {'Address': '192.168.178.20', 'Adapter': 'Ethernet', 'Physical': True}
        with patch.object(lan.sys, 'platform', 'win32'), \
                patch.object(lan, '_windows_addresses', return_value=record):
            self.assertEqual(lan.network_addresses(), [('192.168.178.20', 'Ethernet — 192.168.178.20')])
        with patch.object(lan.sys, 'platform', 'win32'), \
                patch.object(lan, '_windows_addresses', return_value=[record, record]):
            self.assertEqual(len(lan.network_addresses()), 1)

    def test_failed_adapter_query_falls_back_to_route_detection(self):
        with patch.object(lan.sys, 'platform', 'win32'), \
                patch.object(lan, '_windows_addresses', side_effect=subprocess.TimeoutExpired('powershell', 10)), \
                patch.object(lan, '_route_address', return_value='192.168.178.20'):
            self.assertEqual(lan.network_addresses(), [('192.168.178.20', 'Automatic — 192.168.178.20')])


if __name__ == '__main__':
    unittest.main()
