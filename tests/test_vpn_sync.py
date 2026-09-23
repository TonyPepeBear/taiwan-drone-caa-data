import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import mock_open, patch

SPEC = importlib.util.spec_from_file_location("vpn_sync", Path(__file__).resolve().parents[1] / "scripts/vpn/sync.py")
assert SPEC is not None and SPEC.loader is not None
vpn = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vpn)


class VPNSyncTests(unittest.TestCase):
    def test_missing_config_fails_before_network_changes(self):
        for value in ("", "PrivateKey = <insert_your_private_key_here>"):
            with self.subTest(value=value), patch.object(vpn.sys, "stdin", io.StringIO(value)), patch.object(vpn, "run") as run:
                with self.assertRaises(SystemExit):
                    vpn.main()
                run.assert_not_called()

    def exercise(self, handshake="peer\t123\n", failure=None):
        config = "[Interface]\nPrivateKey = test-only\n"
        with patch.object(vpn.sys, "stdin", io.StringIO(config)), patch.object(vpn.sys, "argv", ["sync.py", "--layer", "county"]), patch.object(vpn.os, "umask", return_value=0o022) as umask, patch.object(vpn.Path, "write_text"), patch.object(vpn.Path, "unlink") as unlink, patch.object(vpn.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("192.0.2.1", 443))]), patch("builtins.open", mock_open()) as hosts, patch.object(vpn, "run", side_effect=failure) as run, patch.object(vpn.subprocess, "check_output", return_value=handshake):
            try:
                vpn.main()
            finally:
                unlink.assert_called_once_with(missing_ok=True)
                self.assertEqual(umask.call_args_list[0].args, (0o077,))
                self.assertEqual(umask.call_args_list[-1].args, (0o022,))
            return run, hosts

    def test_routes_only_caa_and_forwards_arguments(self):
        run, hosts = self.exercise()
        run.assert_any_call("ip", "route", "add", "192.0.2.1/32", "dev", "wg-caa")
        run.assert_any_call(vpn.sys.executable, "/workspace/scripts/sync_arcgis.py", "--layer", "county")
        hosts().write.assert_called_once_with("\n192.0.2.1 dronegis.caa.gov.tw\n")
        self.assertNotIn("test-only", str(run.call_args_list))

    def test_missing_handshake_is_failure(self):
        with self.assertRaises(SystemExit):
            self.exercise(handshake="peer\t0\n")

    def test_configuration_removed_after_setup_failure(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.exercise(failure=subprocess.CalledProcessError(1, "ip"))


if __name__ == "__main__":
    unittest.main()
