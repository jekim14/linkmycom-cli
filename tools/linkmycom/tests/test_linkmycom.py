# linkmycom(옛 tssh) 의 이름 해석·설정 병합·명령 조립·export 블록을 검사하는 단위 테스트.
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import linkmycom  # noqa: E402

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
        self.peers = linkmycom.load_peers(STATUS)
        self.blocks = linkmycom.parse_ssh_config(SSH_CONFIG)
        self.cfg = {"hosts": {}, "use_magicdns": False, "ssh_options": {"ServerAliveInterval": "60"}}

    def test_load_peers_sorted_online_first_and_skips_invalid(self):
        names = [p["name"] for p in self.peers]
        self.assertEqual(names, ["miniui-macmini", "pfl", "pfl-server", "jekim-1"])
        self.assertEqual(self.peers[-1]["ip"], "100.1.1.1")

    def test_resolve_exact_prefix_substring_fuzzy(self):
        self.assertEqual([p["name"] for p in linkmycom.resolve(self.peers, "pfl")], ["pfl"])
        self.assertEqual([p["name"] for p in linkmycom.resolve(self.peers, "jekim")], ["jekim-1"])  # HostName 일치
        self.assertEqual([p["name"] for p in linkmycom.resolve(self.peers, "pf")], ["pfl", "pfl-server"])
        self.assertEqual([p["name"] for p in linkmycom.resolve(self.peers, "macmini")], ["miniui-macmini"])
        self.assertEqual([p["name"] for p in linkmycom.resolve(self.peers, "100.3.3.3")], ["pfl"])
        self.assertEqual([p["name"] for p in linkmycom.resolve(self.peers, "pfl-servr")], ["pfl-server"])
        self.assertEqual(linkmycom.resolve(self.peers, "zzzzzz"), [])
        self.assertEqual(linkmycom.resolve(self.peers, "   "), [])

    def test_resolve_alias_from_ssh_config_and_saved(self):
        found = linkmycom.resolve(self.peers, "mac", self.cfg, self.blocks)
        self.assertEqual([p["name"] for p in found], ["miniui-macmini"])
        cfg = dict(self.cfg, hosts={"pfl": {"alias": "srv,box"}})
        self.assertEqual(linkmycom.resolve(self.peers, "box", cfg, [])[0]["name"], "pfl")

    def test_host_settings_merge_order(self):
        mac = linkmycom.resolve(self.peers, "macmini")[0]
        st = linkmycom.host_settings(mac, self.cfg, self.blocks)
        self.assertEqual(st["user"], "jemac")
        self.assertEqual(st["key"], "~/.ssh/mac_key")
        self.assertEqual(st["from_ssh_config"], "mac")
        cfg = dict(self.cfg, hosts={"miniui-macmini": {"user": "admin", "port": "2222"}}, default_user="dflt")
        st = linkmycom.host_settings(mac, cfg, self.blocks)
        self.assertEqual((st["user"], st["port"]), ("admin", "2222"))
        pfl = linkmycom.resolve(self.peers, "pfl")[0]
        self.assertEqual(linkmycom.host_settings(pfl, cfg, self.blocks)["user"], "dflt")

    def test_build_ssh_cmd(self):
        pfl = linkmycom.resolve(self.peers, "pfl")[0]
        cmd = linkmycom.build_ssh_cmd(pfl, {"user": "u", "port": "22", "key": "k", "args": ["-A"]}, self.cfg,
                                 extra=["-L", "80:localhost:80"], ssh_path="ssh")
        self.assertEqual(cmd, ["ssh", "-o", "ServerAliveInterval=60", "-p", "22", "-i", "k", "-A",
                               "-L", "80:localhost:80", "u@100.3.3.3"])
        cmd = linkmycom.build_ssh_cmd(pfl, {"user": "u"}, self.cfg, user="root", port="2200", use_dns=True)
        self.assertEqual(cmd[-1], "root@pfl.example.ts.net")
        self.assertIn("2200", cmd)
        # 원격 명령은 호스트 뒤에, ssh 옵션은 호스트 앞에 놓인다.
        cmd = linkmycom.build_ssh_cmd(pfl, {}, self.cfg, extra=["-o", "BatchMode=yes", "-t", "echo", "-n", "hi"],
                                 user="u", ssh_path="ssh")
        self.assertEqual(cmd, ["ssh", "-o", "ServerAliveInterval=60", "-o", "BatchMode=yes", "-t",
                               "u@100.3.3.3", "echo", "-n", "hi"])

    def test_split_ssh_args(self):
        self.assertEqual(linkmycom.split_ssh_args([]), ([], []))
        self.assertEqual(linkmycom.split_ssh_args(["uptime"]), ([], ["uptime"]))
        self.assertEqual(linkmycom.split_ssh_args(["-L", "80:h:80", "-A", "ls", "-la"]),
                         (["-L", "80:h:80", "-A"], ["ls", "-la"]))
        self.assertEqual(linkmycom.split_ssh_args(["-p2222", "-vvv", "cmd"]), (["-p2222", "-vvv"], ["cmd"]))
        self.assertEqual(linkmycom.split_ssh_args(["-X", "--", "-weird"]), (["-X"], ["-weird"]))
        self.assertEqual(linkmycom.split_ssh_args(["-J", "jump", "-o", "A=b"]), (["-J", "jump", "-o", "A=b"], []))

    def test_parse_connect_args(self):
        o = linkmycom.parse_connect_args(["-u", "bob", "--dns", "-n", "pfl", "-p", "9", "uptime"])
        self.assertEqual((o["user"], o["use_dns"], o["dry_run"], o["host"]), ("bob", True, True, "pfl"))
        self.assertEqual(o["extra"], ["-p", "9", "uptime"])
        o = linkmycom.parse_connect_args(["root@pfl"])
        self.assertEqual((o["user"], o["host"]), ("root", "pfl"))
        o = linkmycom.parse_connect_args(["-u", "x", "y@pfl"])
        self.assertEqual(o["user"], "x")

    def test_managed_block_and_replace(self):
        cfg = dict(self.cfg, hosts={"pfl": {"user": "u", "port": "2222"}})
        block = linkmycom.managed_block(self.peers, cfg, self.blocks)
        self.assertIn("Host pfl\n    HostName 100.3.3.3\n    User u\n    Port 2222\n", block)
        self.assertIn("Host miniui-macmini\n    HostName 100.2.2.2\n    User jemac\n", block)
        self.assertTrue(block.startswith(linkmycom.MANAGED_BEGIN))
        self.assertTrue(block.endswith(linkmycom.MANAGED_END + "\n"))
        first = linkmycom.replace_managed_block(SSH_CONFIG, block)
        self.assertEqual(first.count(linkmycom.MANAGED_BEGIN), 1)
        self.assertTrue(first.startswith(SSH_CONFIG))
        again = linkmycom.replace_managed_block(first, block.replace("Port 2222", "Port 3333"))
        self.assertEqual(again.count(linkmycom.MANAGED_BEGIN), 1)
        self.assertIn("Port 3333", again)
        self.assertNotIn("Port 2222", again)
        self.assertEqual(linkmycom.replace_managed_block("", block), block)
        # 관리 블록 안의 Host 는 기존 항목으로 취급하지 않는다.
        blocks2 = linkmycom.parse_ssh_config(first)
        self.assertTrue(all(b["managed"] for b in blocks2 if b["host"] == "pfl"))
        self.assertFalse([b for b in blocks2 if b["host"] == "mac"][0]["managed"])

    def test_managed_block_skips_existing_alias_clash(self):
        blocks = linkmycom.parse_ssh_config("Host pfl\n  HostName 1.2.3.4\n")
        warnings = []
        original = linkmycom.warn
        linkmycom.warn = warnings.append
        try:
            block = linkmycom.managed_block(self.peers, self.cfg, blocks)
        finally:
            linkmycom.warn = original
        self.assertEqual(len(warnings), 1)
        self.assertNotIn("Host pfl\n", block)
        self.assertIn("Host pfl-server\n", block)

    def test_tailscale_candidates(self):
        import os
        old = os.environ.get("TSSH_TAILSCALE")
        os.environ["TSSH_TAILSCALE"] = "/tmp/forced-tailscale"
        try:
            self.assertEqual(linkmycom.tailscale_candidates(), ["/tmp/forced-tailscale"])
        finally:
            if old is None:
                del os.environ["TSSH_TAILSCALE"]
            else:
                os.environ["TSSH_TAILSCALE"] = old
        cands = linkmycom.tailscale_candidates()
        self.assertEqual(len(cands), len({os.path.normcase(os.path.realpath(c)) for c in cands}))
        self.assertIsNone(linkmycom.run_status("/nonexistent/tailscale-binary"))

    def test_status_from_socket(self):
        import socket
        import tempfile
        import threading
        if not hasattr(socket, "AF_UNIX"):
            self.skipTest("AF_UNIX 없음")
        self.assertIsNone(linkmycom.status_from_socket("/nonexistent/tailscaled.socket"))
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "t.sock")
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(path)
            srv.listen(1)
            body = b'{"BackendState": "Running", "Peer": {}}'

            def serve():
                conn, _ = srv.accept()
                req = conn.recv(4096)
                assert req.startswith(b"GET /localapi/v0/status "), req
                conn.sendall(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n" + body)
                conn.close()

            t = threading.Thread(target=serve, daemon=True)
            t.start()
            st = linkmycom.status_from_socket(path)
            t.join(5)
            srv.close()
        self.assertEqual(st, {"BackendState": "Running", "Peer": {}})

    def test_write_self_keeps_content_and_mode(self):
        import os
        import stat
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "tssh"
            target.write_text("old", encoding="utf-8")
            os.chmod(target, 0o755)
            linkmycom.write_self(target, 'new\n__version__ = "9.9.9"\n')
            self.assertEqual(target.read_text(encoding="utf-8"), 'new\n__version__ = "9.9.9"\n')
            self.assertFalse((Path(d) / "linkmycom.new").exists())
            if os.name != "nt":
                self.assertTrue(target.stat().st_mode & stat.S_IXUSR, "실행 권한이 유지되어야 한다")

    def test_parse_keys_and_merge_authorized_keys(self):
        text = "# comment\nssh-ed25519 AAAA1 a@x\n\nssh-rsa BBBB b@y\nnot a key\nssh-ed25519 AAAA1 a@x\n"
        self.assertEqual(linkmycom.parse_keys(text), ["ssh-ed25519 AAAA1 a@x", "ssh-rsa BBBB b@y"])
        existing = "ssh-ed25519 OLD old@host\n"
        merged, count = linkmycom.merge_authorized_keys(existing, ["ssh-ed25519 AAAA1 a@x", "ssh-ed25519 OLD old@host"])
        self.assertEqual(count, 1)  # 블록 밖에 이미 있는 키는 블록에 넣지 않는다.
        self.assertTrue(merged.startswith(existing))
        self.assertIn(linkmycom.KEYS_BEGIN + "\nssh-ed25519 AAAA1 a@x\n" + linkmycom.KEYS_END, merged)
        merged2, count2 = linkmycom.merge_authorized_keys(merged, ["ssh-rsa BBBB b@y"])
        self.assertEqual(count2, 1)
        self.assertNotIn("AAAA1", merged2)
        self.assertEqual(merged2.count(linkmycom.KEYS_BEGIN), 1)
        self.assertIn("ssh-ed25519 OLD old@host", merged2)
        empty, c0 = linkmycom.merge_authorized_keys("", [])
        self.assertEqual((empty, c0), (linkmycom.KEYS_BEGIN + "\n" + linkmycom.KEYS_END + "\n", 0))

    def test_remote_pubkey_command_and_mobile_filter(self):
        self.assertEqual(linkmycom.remote_pubkey_command({"os": "linux"}), "cat ~/.ssh/id_ed25519.pub")
        self.assertIn("powershell", linkmycom.remote_pubkey_command({"os": "windows"}))
        status = {"Peer": {"x": {"HostName": "console", "DNSName": "tailscale-ssh-console-abc.example.ts.net.",
                                 "TailscaleIPs": ["100.9.9.9"], "OS": "js", "Online": True}}}
        self.assertEqual(linkmycom.load_peers(status), [])

    def test_keys_url_default(self):
        self.assertEqual(linkmycom.keys_url({"update_repo": "a/b"}),
                         "https://raw.githubusercontent.com/a/b/HEAD/tools/linkmycom/authorized_keys")
        self.assertEqual(linkmycom.keys_url({"update_repo": "a/b", "update_ref": "v1"}),
                         "https://raw.githubusercontent.com/a/b/v1/tools/linkmycom/authorized_keys")
        self.assertEqual(linkmycom.DEFAULT_REPO, "jekim14/linkmycom-cli")

    def test_migrate_config_drops_legacy_repo(self):
        legacy = next(iter(linkmycom.LEGACY_REPOS))
        cfg = {"update_repo": legacy, "keys_url": f"https://raw.githubusercontent.com/{legacy}/HEAD/x",
               "default_user": "idonl"}
        self.assertTrue(linkmycom.migrate_config(cfg))
        self.assertEqual(cfg, {"default_user": "idonl"})
        self.assertEqual(linkmycom.keys_url(cfg),
                         f"https://raw.githubusercontent.com/{linkmycom.DEFAULT_REPO}/HEAD/tools/linkmycom/authorized_keys")
        kept = {"update_repo": "someone/else"}
        self.assertFalse(linkmycom.migrate_config(kept))
        self.assertEqual(kept, {"update_repo": "someone/else"})
        self.assertEqual(linkmycom.keys_url({"keys_url": "https://x/y"}), "https://x/y")

    def test_repo_file_urls_prefer_api(self):
        urls = linkmycom.repo_file_urls("a/b", "HEAD", "tools/linkmycom/authorized_keys")
        self.assertEqual(urls[0][0], "https://api.github.com/repos/a/b/contents/tools/linkmycom/authorized_keys?ref=HEAD")
        self.assertEqual(urls[0][1], {"Accept": "application/vnd.github.raw"})
        self.assertEqual(urls[1][0], "https://raw.githubusercontent.com/a/b/HEAD/tools/linkmycom/authorized_keys")

    def test_fetch_repo_file_falls_back(self):
        calls = []
        original = linkmycom.http_get
        def fake(url, timeout=5.0, headers=None):
            calls.append(url)
            if "api.github.com" in url:
                raise OSError("rate limited")
            return b"ok"
        linkmycom.http_get = fake
        try:
            self.assertEqual(linkmycom.fetch_repo_file("a/b", "HEAD", "x"), b"ok")
        finally:
            linkmycom.http_get = original
        self.assertEqual(len(calls), 2)

    def test_display_remote_ps(self):
        ps = linkmycom.display_remote_ps("gather", 2)
        self.assertIn("-Action gather", ps)
        self.assertIn("-RestoreMinutes 5", ps)          # 하한 5분
        self.assertIn("-RunLevel Highest", ps)           # 관리자 창도 옮기기
        self.assertIn(linkmycom.REMOTE_DISPLAY_SCRIPT, ps)
        self.assertIn("-RestoreMinutes 1440", linkmycom.display_remote_ps("single", 99999))
        with self.assertRaises(ValueError):
            linkmycom.display_remote_ps("format-c", 10)
        import base64
        self.assertEqual(base64.b64decode(linkmycom.encode_ps("ab")).decode("utf-16-le"), "ab")

    def test_parse_minutes(self):
        self.assertEqual(linkmycom.parse_minutes(["pc", "single", "--minutes", "30"]), (["pc", "single"], 30))
        self.assertEqual(linkmycom.parse_minutes(["pc"]), (["pc"], 180))

    def test_screen_setting_is_merged(self):
        cfg = {"hosts": {"miniui-macmini": {"user": "jemac", "screen": "macmini"}}}
        mac = {"name": "miniui-macmini", "hostname": "x", "dns": "", "ip": "100.2.2.2", "os": "macOS", "online": True}
        self.assertEqual(linkmycom.host_settings(mac, cfg, [])["screen"], "macmini")

    def test_version_helpers(self):
        self.assertEqual(linkmycom.parse_version("v1.2.10"), (1, 2, 10))
        self.assertGreater(linkmycom.parse_version("0.2.0"), linkmycom.parse_version("0.1.9"))
        self.assertEqual(linkmycom.version_in_source('x\n__version__ = "3.4.5"\n'), "3.4.5")
        self.assertEqual(linkmycom.version_in_source("nothing"), "")

    def test_humanize_last_seen(self):
        now = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(linkmycom.humanize_last_seen("2026-10-11T23:30:00Z", now), "30분 전")
        self.assertEqual(linkmycom.humanize_last_seen("2026-10-01T00:00:00Z", now), "11일 전")
        self.assertEqual(linkmycom.humanize_last_seen("0001-01-01T00:00:00Z", now), "")
        self.assertEqual(linkmycom.humanize_last_seen("", now), "")


class LegacyMigrationTests(unittest.TestCase):
    """옛 이름 tssh 설치본이 새 코드를 받은 뒤 처음 실행될 때 linkmycom·lmc 를 옆에 만드는지 확인한다."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.src = (Path(linkmycom.__file__)).read_text(encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_windows_standalone(self):
        d = self.root / "tssh"
        d.mkdir()
        (d / "tssh.py").write_text(self.src, encoding="utf-8")
        (d / "tssh.cmd").write_text("@echo off", encoding="utf-8")
        made = linkmycom.migrate_legacy_install(d / "tssh.py")
        self.assertEqual({p.name for p in made}, {"linkmycom.py", "linkmycom.cmd", "lmc.cmd"})
        self.assertEqual((d / "linkmycom.py").read_text(encoding="utf-8"), self.src)
        self.assertIn(linkmycom.FORWARDER_MARK, (d / "tssh.py").read_text(encoding="utf-8"))
        self.assertIn("linkmycom.py", (d / "linkmycom.cmd").read_text(encoding="utf-8"))
        self.assertIn("linkmycom.cmd", (d / "lmc.cmd").read_text(encoding="utf-8"))
        # 넘김 파일이 된 뒤에는 다시 옮기지 않고, 업데이트는 새 이름 파일을 바꾼다.
        self.assertEqual(linkmycom.migrate_legacy_install(d / "tssh.py"), [])
        self.assertEqual(linkmycom.update_target(d / "tssh.py"), d / "linkmycom.py")

    def test_tower_folder_gets_bin_shims(self):
        tower = self.root / "DeskTools" / "tower"
        bin_dir = self.root / "DeskTools" / "bin"
        tower.mkdir(parents=True)
        bin_dir.mkdir()
        (tower / "tssh.py").write_text(self.src, encoding="utf-8")
        (tower / "tssh.ps1").write_text("# old", encoding="utf-8")
        (bin_dir / "tssh.cmd").write_text("@echo off", encoding="utf-8")
        made = {p.relative_to(self.root).as_posix() for p in linkmycom.migrate_legacy_install(tower / "tssh.py")}
        self.assertTrue({"DeskTools/tower/linkmycom.ps1", "DeskTools/bin/linkmycom.cmd", "DeskTools/bin/lmc.cmd"} <= made)
        self.assertIn(r"%~dp0..\tower\linkmycom.cmd", (bin_dir / "lmc.cmd").read_text(encoding="utf-8"))

    def test_tower_updated_by_package_gets_bin_shims(self):
        # 타워 업데이터로 새 패키지를 받은 PC: tssh.py 는 이미 넘김 파일이고 bin 에는 tssh.cmd 만 있다.
        tower = self.root / "DeskTools" / "tower"
        bin_dir = self.root / "DeskTools" / "bin"
        tower.mkdir(parents=True)
        bin_dir.mkdir()
        (tower / "linkmycom.py").write_text(self.src, encoding="utf-8")
        (tower / "linkmycom.cmd").write_text("@echo off", encoding="utf-8")
        (bin_dir / "tssh.cmd").write_text("@echo off", encoding="utf-8")
        made = {p.name for p in linkmycom.ensure_tower_bin_shims(tower / "linkmycom.py")}
        self.assertEqual(made, {"linkmycom.cmd", "lmc.cmd"})
        self.assertIn(r"%~dp0..\tower\linkmycom.cmd", (bin_dir / "linkmycom.cmd").read_text(encoding="utf-8"))
        self.assertEqual(linkmycom.ensure_tower_bin_shims(tower / "linkmycom.py"), [])
        self.assertEqual(linkmycom.ensure_tower_bin_shims(self.root / "x" / "linkmycom.py"), [])

    def test_shim_path_uses_env_vars_for_korean_user(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\김종은\AppData\Local",
                                          "USERPROFILE": r"C:\Users\김종은"}):
            py = r"C:\Users\김종은\AppData\Local\Programs\Python\Python312\python.exe"
            self.assertEqual(linkmycom.shim_path(py), r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe")
            self.assertEqual(linkmycom.shim_path(py, ps=True), r"$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")
            self.assertTrue(linkmycom.python_shim(py).isascii())
        self.assertEqual(linkmycom.shim_path(r"C:\Program Files\Python312\python.exe"), r"C:\Program Files\Python312\python.exe")

    def test_repair_broken_shims(self):
        d = self.root / "tssh"
        d.mkdir()
        (d / "linkmycom.py").write_text(self.src, encoding="utf-8")
        # 옛 설치기가 한글 사용자 이름을 ASCII 로 써서 '???' 가 된 파일과 옛 tssh.cmd.
        (d / "linkmycom.cmd").write_bytes(b'@echo off\r\n"C:\\Users\\???\\python.exe" "%~dp0linkmycom.py" %*\r\n')
        (d / "tssh.cmd").write_bytes(b'@echo off\r\n"C:\\Users\\???\\python.exe" "%~dp0tssh.py" %*\r\n')
        fixed = {p.name for p in linkmycom.repair_shims(d / "linkmycom.py")}
        self.assertEqual(fixed, {"linkmycom.cmd", "tssh.cmd"})
        self.assertNotIn(b"???", (d / "linkmycom.cmd").read_bytes())
        self.assertIn(b"linkmycom.cmd", (d / "tssh.cmd").read_bytes())
        self.assertEqual(linkmycom.repair_shims(d / "linkmycom.py"), [])  # 고친 뒤에는 그대로 둔다
        # 패키지의 linkmycom.cmd 는 PATH 의 python 을 찾으므로 손대지 않는다.
        (d / "linkmycom.cmd").write_bytes(b'@echo off\r\nwhere python >nul 2>nul\r\npython "%~dp0linkmycom.py" %*\r\n')
        self.assertEqual(linkmycom.repair_shims(d / "linkmycom.py"), [])

    def test_posix_bin(self):
        d = self.root / "bin"
        d.mkdir()
        (d / "tssh").write_text(self.src, encoding="utf-8")
        made = linkmycom.migrate_legacy_install(d / "tssh")
        self.assertEqual({p.name for p in made}, {"linkmycom", "lmc"})
        self.assertEqual((d / "linkmycom").read_text(encoding="utf-8"), self.src)
        self.assertIn(linkmycom.FORWARDER_MARK, (d / "tssh").read_text(encoding="utf-8"))
        self.assertEqual(linkmycom.update_target(d / "tssh"), d / "linkmycom")

    def test_new_name_and_source_checkout_untouched(self):
        d = self.root / "x"
        d.mkdir()
        (d / "linkmycom.py").write_text(self.src, encoding="utf-8")
        self.assertEqual(linkmycom.migrate_legacy_install(d / "linkmycom.py"), [])
        repo = self.root / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "tools").mkdir()
        (repo / "tools" / "tssh.py").write_text(self.src, encoding="utf-8")
        self.assertEqual(linkmycom.migrate_legacy_install(repo / "tools" / "tssh.py"), [])

    def test_legacy_notice_once_a_day(self):
        state = {}
        self.assertIn("lmc", linkmycom.legacy_name_notice("tssh", [], state))
        self.assertIsNone(linkmycom.legacy_name_notice("tssh", [], state))
        self.assertIn("lmc.cmd", linkmycom.legacy_name_notice("tssh", [Path("lmc.cmd")], state))

    def test_forwarder_runs_new_file(self):
        import subprocess
        d = self.root / "fw"
        d.mkdir()
        (d / "linkmycom.py").write_text(self.src, encoding="utf-8")
        (d / "tssh.py").write_text(linkmycom.forwarder_source("linkmycom.py"), encoding="utf-8")
        out = subprocess.run([sys.executable, str(d / "tssh.py"), "version"], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), f"linkmycom {linkmycom.__version__}")


if __name__ == "__main__":
    unittest.main()
