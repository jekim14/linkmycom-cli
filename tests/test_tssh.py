# tssh 의 이름 해석·설정 병합·명령 조립·export 블록을 검사하는 단위 테스트.
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tssh  # noqa: E402

STATUS = {
    "BackendState": "Running",
    "MagicDNSSuffix": "example.ts.net",
    "Peer": {
        "a": {"HostName": "jekim", "DNSName": "jekim-1.example.ts.net.", "TailscaleIPs": ["100.1.1.1", "fd7a::1"],
              "OS": "windows", "Online": False, "LastSeen": "2026-10-01T00:00:00Z"},
        "b": {"HostName": "macmini", "DNSName": "miniui-macmini.example.ts.net.", "TailscaleIPs": ["100.2.2.2"],
              "OS": "macOS", "Online": True, "LastSeen": "0001-01-01T00:00:00Z"},
        "c": {"HostName": "pfl", "DNSName": "pfl.example.ts.net.", "TailscaleIPs": ["100.3.3.3"],
              "OS": "linux", "Online": True},
        "d": {"HostName": "pfl-server", "DNSName": "pfl-server.example.ts.net.", "TailscaleIPs": ["100.4.4.4"],
              "OS": "windows", "Online": True},
        "bad": {"HostName": "", "DNSName": "", "TailscaleIPs": []},
    },
}

SSH_CONFIG = """Host knut
  HostName gpu.example.org
  Port 30552
  User work

Host mac
  HostName 100.2.2.2
  User jemac
  IdentityFile ~/.ssh/mac_key
"""


class PeerTests(unittest.TestCase):
    def setUp(self):
        self.peers = tssh.load_peers(STATUS)
        self.blocks = tssh.parse_ssh_config(SSH_CONFIG)
        self.cfg = {"hosts": {}, "use_magicdns": False, "ssh_options": {"ServerAliveInterval": "60"}}

    def test_load_peers_sorted_online_first_and_skips_invalid(self):
        names = [p["name"] for p in self.peers]
        self.assertEqual(names, ["miniui-macmini", "pfl", "pfl-server", "jekim-1"])
        self.assertEqual(self.peers[-1]["ip"], "100.1.1.1")

    def test_resolve_exact_prefix_substring_fuzzy(self):
        self.assertEqual([p["name"] for p in tssh.resolve(self.peers, "pfl")], ["pfl"])
        self.assertEqual([p["name"] for p in tssh.resolve(self.peers, "jekim")], ["jekim-1"])  # HostName 일치
        self.assertEqual([p["name"] for p in tssh.resolve(self.peers, "pf")], ["pfl", "pfl-server"])
        self.assertEqual([p["name"] for p in tssh.resolve(self.peers, "macmini")], ["miniui-macmini"])
        self.assertEqual([p["name"] for p in tssh.resolve(self.peers, "100.3.3.3")], ["pfl"])
        self.assertEqual([p["name"] for p in tssh.resolve(self.peers, "pfl-servr")], ["pfl-server"])
        self.assertEqual(tssh.resolve(self.peers, "zzzzzz"), [])
        self.assertEqual(tssh.resolve(self.peers, "   "), [])

    def test_resolve_alias_from_ssh_config_and_saved(self):
        found = tssh.resolve(self.peers, "mac", self.cfg, self.blocks)
        self.assertEqual([p["name"] for p in found], ["miniui-macmini"])
        cfg = dict(self.cfg, hosts={"pfl": {"alias": "srv,box"}})
        self.assertEqual(tssh.resolve(self.peers, "box", cfg, [])[0]["name"], "pfl")

    def test_host_settings_merge_order(self):
        mac = tssh.resolve(self.peers, "macmini")[0]
        st = tssh.host_settings(mac, self.cfg, self.blocks)
        self.assertEqual(st["user"], "jemac")
        self.assertEqual(st["key"], "~/.ssh/mac_key")
        self.assertEqual(st["from_ssh_config"], "mac")
        cfg = dict(self.cfg, hosts={"miniui-macmini": {"user": "admin", "port": "2222"}}, default_user="dflt")
        st = tssh.host_settings(mac, cfg, self.blocks)
        self.assertEqual((st["user"], st["port"]), ("admin", "2222"))
        pfl = tssh.resolve(self.peers, "pfl")[0]
        self.assertEqual(tssh.host_settings(pfl, cfg, self.blocks)["user"], "dflt")

    def test_build_ssh_cmd(self):
        pfl = tssh.resolve(self.peers, "pfl")[0]
        cmd = tssh.build_ssh_cmd(pfl, {"user": "u", "port": "22", "key": "k", "args": ["-A"]}, self.cfg,
                                 extra=["-L", "80:localhost:80"], ssh_path="ssh")
        self.assertEqual(cmd, ["ssh", "-o", "ServerAliveInterval=60", "-p", "22", "-i", "k", "-A",
                               "-L", "80:localhost:80", "u@100.3.3.3"])
        cmd = tssh.build_ssh_cmd(pfl, {"user": "u"}, self.cfg, user="root", port="2200", use_dns=True)
        self.assertEqual(cmd[-1], "root@pfl.example.ts.net")
        self.assertIn("2200", cmd)
        # 원격 명령은 호스트 뒤에, ssh 옵션은 호스트 앞에 놓인다.
        cmd = tssh.build_ssh_cmd(pfl, {}, self.cfg, extra=["-o", "BatchMode=yes", "-t", "echo", "-n", "hi"],
                                 user="u", ssh_path="ssh")
        self.assertEqual(cmd, ["ssh", "-o", "ServerAliveInterval=60", "-o", "BatchMode=yes", "-t",
                               "u@100.3.3.3", "echo", "-n", "hi"])

    def test_split_ssh_args(self):
        self.assertEqual(tssh.split_ssh_args([]), ([], []))
        self.assertEqual(tssh.split_ssh_args(["uptime"]), ([], ["uptime"]))
        self.assertEqual(tssh.split_ssh_args(["-L", "80:h:80", "-A", "ls", "-la"]),
                         (["-L", "80:h:80", "-A"], ["ls", "-la"]))
        self.assertEqual(tssh.split_ssh_args(["-p2222", "-vvv", "cmd"]), (["-p2222", "-vvv"], ["cmd"]))
        self.assertEqual(tssh.split_ssh_args(["-X", "--", "-weird"]), (["-X"], ["-weird"]))
        self.assertEqual(tssh.split_ssh_args(["-J", "jump", "-o", "A=b"]), (["-J", "jump", "-o", "A=b"], []))

    def test_parse_connect_args(self):
        o = tssh.parse_connect_args(["-u", "bob", "--dns", "-n", "pfl", "-p", "9", "uptime"])
        self.assertEqual((o["user"], o["use_dns"], o["dry_run"], o["host"]), ("bob", True, True, "pfl"))
        self.assertEqual(o["extra"], ["-p", "9", "uptime"])
        o = tssh.parse_connect_args(["root@pfl"])
        self.assertEqual((o["user"], o["host"]), ("root", "pfl"))
        o = tssh.parse_connect_args(["-u", "x", "y@pfl"])
        self.assertEqual(o["user"], "x")

    def test_managed_block_and_replace(self):
        cfg = dict(self.cfg, hosts={"pfl": {"user": "u", "port": "2222"}})
        block = tssh.managed_block(self.peers, cfg, self.blocks)
        self.assertIn("Host pfl\n    HostName 100.3.3.3\n    User u\n    Port 2222\n", block)
        self.assertIn("Host miniui-macmini\n    HostName 100.2.2.2\n    User jemac\n", block)
        self.assertTrue(block.startswith(tssh.MANAGED_BEGIN))
        self.assertTrue(block.endswith(tssh.MANAGED_END + "\n"))
        first = tssh.replace_managed_block(SSH_CONFIG, block)
        self.assertEqual(first.count(tssh.MANAGED_BEGIN), 1)
        self.assertTrue(first.startswith(SSH_CONFIG))
        again = tssh.replace_managed_block(first, block.replace("Port 2222", "Port 3333"))
        self.assertEqual(again.count(tssh.MANAGED_BEGIN), 1)
        self.assertIn("Port 3333", again)
        self.assertNotIn("Port 2222", again)
        self.assertEqual(tssh.replace_managed_block("", block), block)
        # 관리 블록 안의 Host 는 기존 항목으로 취급하지 않는다.
        blocks2 = tssh.parse_ssh_config(first)
        self.assertTrue(all(b["managed"] for b in blocks2 if b["host"] == "pfl"))
        self.assertFalse([b for b in blocks2 if b["host"] == "mac"][0]["managed"])

    def test_managed_block_skips_existing_alias_clash(self):
        blocks = tssh.parse_ssh_config("Host pfl\n  HostName 1.2.3.4\n")
        warnings = []
        original = tssh.warn
        tssh.warn = warnings.append
        try:
            block = tssh.managed_block(self.peers, self.cfg, blocks)
        finally:
            tssh.warn = original
        self.assertEqual(len(warnings), 1)
        self.assertNotIn("Host pfl\n", block)
        self.assertIn("Host pfl-server\n", block)

    def test_version_helpers(self):
        self.assertEqual(tssh.parse_version("v1.2.10"), (1, 2, 10))
        self.assertGreater(tssh.parse_version("0.2.0"), tssh.parse_version("0.1.9"))
        self.assertEqual(tssh.version_in_source('x\n__version__ = "3.4.5"\n'), "3.4.5")
        self.assertEqual(tssh.version_in_source("nothing"), "")

    def test_humanize_last_seen(self):
        now = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(tssh.humanize_last_seen("2026-10-11T23:30:00Z", now), "30분 전")
        self.assertEqual(tssh.humanize_last_seen("2026-10-01T00:00:00Z", now), "11일 전")
        self.assertEqual(tssh.humanize_last_seen("0001-01-01T00:00:00Z", now), "")
        self.assertEqual(tssh.humanize_last_seen("", now), "")


if __name__ == "__main__":
    unittest.main()
