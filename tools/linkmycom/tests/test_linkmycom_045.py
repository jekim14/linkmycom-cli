# linkmycom 0.4.5 의 lmc 심 단축·늦은 임포트·피어 캐시·doctor 병렬화와 새 명령(exec·fleet·send·inbox·forward·screen 모드)을 검사하는 단위 테스트.
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import linkmycom  # noqa: E402

PEERS = [
    {"name": "pfl", "hostname": "pfl", "dns": "pfl.ts.net", "ip": "100.1.1.1", "os": "windows", "online": True,
     "last_seen": "", "ts_ssh": False, "tags": [], "cur_addr": "", "relay": ""},
    {"name": "mac", "hostname": "mac", "dns": "mac.ts.net", "ip": "100.1.1.2", "os": "macOS", "online": True,
     "last_seen": "", "ts_ssh": False, "tags": [], "cur_addr": "1.2.3.4:41641", "relay": ""},
    {"name": "phone", "hostname": "phone", "dns": "phone.ts.net", "ip": "100.1.1.3", "os": "iOS", "online": True,
     "last_seen": "", "ts_ssh": False, "tags": [], "cur_addr": "", "relay": ""},
    {"name": "off", "hostname": "off", "dns": "off.ts.net", "ip": "100.1.1.4", "os": "linux", "online": False,
     "last_seen": "", "ts_ssh": False, "tags": [], "cur_addr": "", "relay": ""},
]
STATUS = {"BackendState": "Running", "Peer": {
    "a": {"HostName": "pfl", "DNSName": "pfl.ts.net.", "TailscaleIPs": ["100.1.1.1"], "OS": "windows", "Online": True,
          "CurAddr": "5.6.7.8:41641", "Relay": "tok"},
}}


class TempHome(unittest.TestCase):
    """CONFIG_DIR·STATE_PATH·HOSTS_CACHE_PATH 를 임시 폴더로 돌린다."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        cfgdir = self.root / ".tssh"
        self.patches = [
            mock.patch.object(linkmycom, "CONFIG_DIR", cfgdir),
            mock.patch.object(linkmycom, "STATE_PATH", cfgdir / "state.json"),
            mock.patch.object(linkmycom, "CONFIG_PATH", cfgdir / "config.json"),
            mock.patch.object(linkmycom, "HOSTS_CACHE_PATH", cfgdir / "hosts.txt"),
        ]
        for p in self.patches:
            p.start()
        self.cfgdir = cfgdir

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self._tmp.cleanup()


# ---------------------------------------------------------------- C1. bin\lmc.cmd 가 파이썬을 바로 부른다.

class ShimTests(TempHome):
    def make_tower(self):
        tower = self.root / "DeskTools" / "tower"
        bin_dir = self.root / "DeskTools" / "bin"
        tower.mkdir(parents=True)
        bin_dir.mkdir()
        for name in ("linkmycom.py", "linkmycom.cmd", "tssh.cmd"):
            (tower / name).write_text("x", encoding="utf-8")
        (bin_dir / "tssh.cmd").write_text("@echo off", encoding="utf-8")
        return tower, bin_dir

    def test_direct_python_with_fallback(self):
        tower, bin_dir = self.make_tower()
        py = self.root / "Python312" / "python.exe"
        py.parent.mkdir()
        py.write_bytes(b"")
        made = {p.name for p in linkmycom.ensure_tower_bin_shims(tower / "linkmycom.py", str(py))}
        self.assertEqual(made, {"linkmycom.cmd", "lmc.cmd", "tssh.cmd"})
        body = (bin_dir / "lmc.cmd").read_bytes().decode("ascii")
        self.assertIn(f'if not exist "{py}" goto lmc_find', body)
        self.assertIn(f'"{py}" "%~dp0..\\tower\\linkmycom.py" %*', body)
        self.assertIn(r'call "%~dp0..\tower\linkmycom.cmd" %*', body)  # 파이썬이 사라졌을 때
        self.assertNotIn("linkmycom.cmd\" %*\r\n:lmc_find", body)
        self.assertEqual(body.count("\n"), body.count("\r\n"))
        # tssh 는 LINKMYCOM_INVOKED_AS 를 넣는 tower\tssh.cmd 를 그대로 거친다.
        self.assertIn(rb"%~dp0..\tower\tssh.cmd", (bin_dir / "tssh.cmd").read_bytes())
        self.assertEqual(linkmycom.ensure_tower_bin_shims(tower / "linkmycom.py", str(py)), [])

    def test_shim_python_rules(self):
        d = self.root / "py"
        d.mkdir()
        (d / "python.exe").write_bytes(b"")
        (d / "pythonw.exe").write_bytes(b"")
        self.assertEqual(linkmycom.shim_python(str(d / "pythonw.exe")), str(d / "python.exe"))
        self.assertIsNone(linkmycom.shim_python(str(self.root / "WindowsApps" / "python.exe")))
        self.assertIsNone(linkmycom.shim_python(str(self.root / "gone" / "python.exe")))
        self.assertIsNone(linkmycom.shim_python(None))

    def test_korean_user_path_uses_env_var(self):
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\김종은\AppData\Local"}):
            body = linkmycom.tower_bin_body("tower", r"C:\Users\김종은\AppData\Local\Programs\Python\Python312\python.exe")
        self.assertTrue(body.isascii())
        self.assertIn(r'"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"', body)

    def test_remembered_python_is_recorded_once(self):
        py = linkmycom.shim_python(sys.executable)
        if not py:
            self.skipTest("이 파이썬은 심에 쓸 수 없음")
        self.assertEqual(linkmycom.remembered_python(), py)
        self.assertEqual(json.loads(linkmycom.STATE_PATH.read_text(encoding="utf-8"))["python"], py)
        linkmycom.STATE_PATH.write_text(json.dumps({"python": str(self.root / "gone.exe")}), encoding="utf-8")
        self.assertEqual(linkmycom.remembered_python(), py)  # 기록된 파이썬이 사라졌으면 다시 기록

    def test_install_ps1_lmc_is_direct(self):
        text = (HERE / "install.ps1").read_text(encoding="ascii")
        self.assertIn('Write-Shim (Join-Path $dest "lmc.cmd") $cmdShim', text)


# ---------------------------------------------------------------- C2. 늦은 임포트.

class LazyImportTests(unittest.TestCase):
    def test_heavy_modules_not_imported_at_startup(self):
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import linkmycom; "
                "print(','.join(m for m in ('urllib.request', 'difflib') if m in sys.modules))")
        r = subprocess.run([sys.executable, "-c", code, str(HERE)], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "")


# ---------------------------------------------------------------- C3. peers.json 캐시.

class PeersCacheTests(TempHome):
    def test_hit_skips_tailscale(self):
        linkmycom.write_peers_cache(PEERS, now=1000.0)
        self.assertEqual((self.cfgdir / "hosts.txt").read_text(encoding="utf-8"), "pfl\nmac\nphone\noff\n")
        with mock.patch.object(linkmycom, "tailscale_status", side_effect=AssertionError("불리면 안 됨")):
            peers, cached = linkmycom.cached_peers(now=1030.0)
        self.assertTrue(cached)
        self.assertEqual([p["name"] for p in peers], ["pfl", "mac", "phone", "off"])
        self.assertEqual(peers[1]["cur_addr"], "1.2.3.4:41641")

    def test_expired_queries_and_rewrites(self):
        linkmycom.write_peers_cache(PEERS, now=1000.0)
        with mock.patch.object(linkmycom, "tailscale_status", return_value=STATUS) as ts:
            peers, cached = linkmycom.cached_peers(now=1046.0)
        ts.assert_called_once_with(soft=True)
        self.assertFalse(cached)
        self.assertEqual([p["name"] for p in peers], ["pfl"])
        self.assertEqual(peers[0]["cur_addr"], "5.6.7.8:41641")
        self.assertEqual(linkmycom.read_peers_cache()[1], 1046.0)

    def test_offline_uses_stale_cache_with_warning(self):
        linkmycom.write_peers_cache(PEERS, now=1000.0)
        err = io.StringIO()
        with mock.patch.object(linkmycom, "tailscale_status", side_effect=linkmycom.TailscaleUnavailable("tailscale 없음")), \
                redirect_stderr(err):
            peers, cached = linkmycom.cached_peers(now=5000.0)
        self.assertTrue(cached)
        self.assertEqual(len(peers), 4)
        self.assertIn("4000초 전", err.getvalue())

    def test_no_cache_and_offline_dies_as_before(self):
        def status(soft=False):
            if soft:
                raise linkmycom.TailscaleUnavailable("x")
            raise SystemExit(1)

        with mock.patch.object(linkmycom, "tailscale_status", side_effect=status), self.assertRaises(SystemExit):
            linkmycom.cached_peers(now=1.0)

    def test_soft_status_raises_instead_of_die(self):
        with mock.patch.object(linkmycom, "tailscale_candidates", return_value=[]), \
                mock.patch.object(linkmycom, "TAILSCALED_SOCKETS", ()), \
                self.assertRaises(linkmycom.TailscaleUnavailable):
            linkmycom.tailscale_status(soft=True)

    def test_broken_cache_is_ignored(self):
        self.cfgdir.mkdir(parents=True)
        (self.cfgdir / "peers.json").write_text("{not json", encoding="utf-8")
        self.assertIsNone(linkmycom.read_peers_cache())
        (self.cfgdir / "peers.json").write_text(json.dumps({"time": 1, "peers": [{"name": "x"}]}), encoding="utf-8")
        self.assertIsNone(linkmycom.read_peers_cache())

    def test_pick_cached_refreshes_unknown_name(self):
        linkmycom.write_peers_cache(PEERS[:1], now=time.time())
        with mock.patch.object(linkmycom, "fresh_peers", return_value=PEERS) as fresh:
            peer, _ = linkmycom.pick_cached({"hosts": {}}, [], "mac")
        fresh.assert_called_once()
        self.assertEqual(peer["name"], "mac")


# ---------------------------------------------------------------- C4·C6. doctor 스크립트.

class DoctorScriptTests(unittest.TestCase):
    def test_script_shape(self):
        s = linkmycom.DOCTOR_PY
        self.assertTrue(s.isascii())
        compile(s, "doctor", "exec")
        self.assertEqual(s.count('"powershell"'), 1)  # PowerShell 은 한 번만 띄운다
        self.assertIn('TASK = "%s"' % linkmycom.SCHEDULE_TASK_NAME, s)
        self.assertIn('LAUNCHD = "%s"' % linkmycom.LAUNCHD_LABEL, s)
        self.assertIn('UNIT = "%s"' % linkmycom.SYSTEMD_UNIT, s)
        self.assertNotIn("capture_output", s)  # 원격 파이썬 3.6 호환
        self.assertNotIn('"FAIL" if', s.split("path_lmc")[1].split("tower_ver")[0])  # 새 점검은 FAIL 을 내지 않는다
        for name in ("path_lmc", "tower_run", "screen_svc", "keys_task"):
            self.assertIn(name, linkmycom.DOCTOR_LABELS)

    def test_versions_only_runs_fast(self):
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "HOME": d, "USERPROFILE": d}
            t = time.time()
            r = subprocess.run([sys.executable, "-c", linkmycom.doctor_oneliner(), "--versions"], capture_output=True,
                               text=True, encoding="utf-8", timeout=60, env=env, cwd=d)
            took = time.time() - t
        names = [n for n, _, _ in linkmycom.parse_doctor_lines(r.stdout)]
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(names, ["cli", "path_lmc", "tower", "native"] if os.name == "nt" else ["cli", "path_lmc", "native"])
        self.assertLess(took, 20)

    def test_remote_command_versions_flag(self):
        win, _ = linkmycom.doctor_remote_command("windows", "AAAAkey", versions_only=True)
        ps = base64.b64decode(win.split()[-1]).decode("utf-16-le")
        self.assertTrue(ps.rstrip().endswith("AAAAkey --versions"))
        posix, _ = linkmycom.doctor_remote_command("linux", versions_only=True)
        self.assertIn('" --versions ||', posix)

    def test_local_doctor_overlaps_key_list(self):
        # 키 목록 받기와 점검 스크립트가 함께 돌면 전체 시간은 둘의 합보다 짧다.
        def slow_rows(versions_only=False):
            time.sleep(1.0)
            return [("tailscale", "OK", ""), ("cli", "INFO", "tower 0.4.5")]

        def slow_keys(cfg):
            time.sleep(1.0)
            return "keys_list", "OK", "x"

        out = io.StringIO()
        with mock.patch.object(linkmycom, "local_doctor_rows", side_effect=slow_rows), \
                mock.patch.object(linkmycom, "doctor_keys_list_row", side_effect=slow_keys), redirect_stdout(out):
            t = time.time()
            rc = linkmycom.cmd_doctor({}, [])
            took = time.time() - t
        self.assertEqual(rc, 0)
        self.assertLess(took, 1.8)  # 직렬이면 2초
        text = out.getvalue()
        self.assertLess(text.index("게시된 키 목록"), text.index("CLI 버전"))


# ---------------------------------------------------------------- C5. doctor --all.

class DoctorAllTests(unittest.TestCase):
    def test_one_failure_keeps_other_rows(self):
        def fake_remote(peer, cfg, blocks, remote, stdin_text=None, timeout=None, ssh=None):
            if peer["name"] == "mac":
                return 255, "", "ssh: connect to host 100.1.1.2 port 22: Connection timed out"
            return 0, "LMCDOC|sshd|OK|Running\nLMCDOC|firewall|OK|x\nLMCDOC|my_key|OK|y\nLMCDOC|cli|INFO|tower 0.4.5\n" \
                      "LMCDOC|native|INFO|0.5.2\nLMCDOC|screen_svc|OK|z\n", ""

        local = [("tailscale", "OK", ""), ("ssh_port", "FAIL", "closed"), ("cli", "INFO", "linkmycom 0.4.5")]
        with mock.patch.object(linkmycom, "cached_peers", return_value=(PEERS, True)), \
                mock.patch.object(linkmycom, "run_remote", side_effect=fake_remote), \
                mock.patch.object(linkmycom, "local_doctor_rows", return_value=local), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "port_open", return_value=True), \
                mock.patch.object(linkmycom, "local_key_blob", return_value="AAAA"):
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                rc = linkmycom.cmd_doctor_all({"hosts": {}}, as_json=True)
            data = json.loads(out.getvalue())
            out2 = io.StringIO()
            with redirect_stdout(out2), redirect_stderr(io.StringIO()):
                linkmycom.cmd_doctor_all({"hosts": {}})
        self.assertEqual(rc, 1)
        self.assertEqual([r["name"] for r in data[1:]], ["pfl", "mac"])  # 모바일·오프라인은 빼고 순서 유지
        self.assertIn("Connection timed out", data[2]["error"])
        self.assertEqual(data[1]["error"], "")
        table = out2.getvalue()
        self.assertIn("0.5.2 OK", table)
        self.assertIn("tower 0.4.5", table)
        self.assertIn("SSH 실패", table)

    def test_host_without_sshd_is_skipped_not_failed(self):
        """exec all 과 같은 규칙: Tailscale SSH 도 없고 22 가 닫힌 PC 는 '건너뜀' 행이고 종료 코드에 들지 않는다."""
        local = [("tailscale", "OK", ""), ("cli", "INFO", "linkmycom 0.4.5")]
        calls = []

        def fake_remote(peer, *a, **k):
            calls.append(peer["name"])
            return 0, "LMCDOC|sshd|OK|Running\nLMCDOC|cli|INFO|tower 0.4.5\n", ""

        with mock.patch.object(linkmycom, "cached_peers", return_value=(PEERS, True)), \
                mock.patch.object(linkmycom, "run_remote", side_effect=fake_remote), \
                mock.patch.object(linkmycom, "local_doctor_rows", return_value=local), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "port_open", side_effect=lambda ip, port, timeout=1.5: ip != "100.1.1.2"), \
                mock.patch.object(linkmycom, "local_key_blob", return_value="AAAA"):
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                rc = linkmycom.cmd_doctor_all({"hosts": {}}, as_json=True)
            data = json.loads(out.getvalue())
            out2 = io.StringIO()
            with redirect_stdout(out2), redirect_stderr(io.StringIO()):
                rc2 = linkmycom.cmd_fleet({"hosts": {}}, ["status"])
        self.assertEqual(rc, 0)
        self.assertEqual(rc2, 0)
        self.assertEqual(data[2]["skipped"], "SSH 포트 닫힘")
        self.assertEqual(data[2]["error"], "")
        self.assertNotIn("mac", calls)
        self.assertIn("건너뜀", out2.getvalue())

    def test_summary(self):
        s = linkmycom.doctor_summary([("ssh_port", "OK", ""), ("firewall", "SKIP", ""), ("authorized_keys", "OK", ""),
                                      ("cli", "INFO", "bin 0.4.4"), ("native", "INFO", "not installed"),
                                      ("keys_task", "WARN", "")])
        self.assertEqual((s["sshd"], s["firewall"], s["keys"], s["cli"], s["screen"]), ("OK", "SKIP", "OK", "bin 0.4.4", "-"))
        self.assertEqual(s["result"], "WARN keys_task")
        self.assertEqual(linkmycom.remote_rows_error([("python", "FAIL", "x")], ""), "원격에 파이썬 3 이 없어 점검하지 못함")


# ---------------------------------------------------------------- C7. send / inbox.

class SendInboxTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(linkmycom.parse_send_args(["a.txt", "b c.txt", "--to", "pfl,mac"]),
                         (["a.txt", "b c.txt"], ["pfl", "mac"]))
        self.assertEqual(linkmycom.parse_send_args(["--to=pfl", "a"]), (["a"], ["pfl"]))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            linkmycom.parse_send_args(["a.txt"])

    def test_one_cp_per_target_and_failure_marked(self):
        with tempfile.TemporaryDirectory() as d:
            f1, f2 = Path(d) / "a.txt", Path(d) / "b.txt"
            f1.write_text("a")
            f2.write_text("b")
            calls = []

            def fake_run(cmd, **kw):
                calls.append(cmd)
                rc = 1 if cmd[-1] == "100.1.1.2:" else 0
                return subprocess.CompletedProcess(cmd, rc, "", "no route" if rc else "")

            peers = {"pfl": PEERS[0], "mac": PEERS[1]}
            out = io.StringIO()
            with mock.patch.object(linkmycom, "pick_cached", side_effect=lambda cfg, b, n: (peers[n], PEERS)), \
                    mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                    mock.patch.object(linkmycom, "tailscale_exe", return_value="tailscale"), \
                    mock.patch.object(linkmycom.subprocess, "run", side_effect=fake_run), redirect_stdout(out):
                rc = linkmycom.cmd_send({}, [str(f1), str(f2), "--to", "pfl,mac,pfl"])
        self.assertEqual(rc, 1)
        self.assertEqual(sorted(c[-1] for c in calls), ["100.1.1.1:", "100.1.1.2:"])
        for c in calls:
            self.assertEqual(c[:3], ["tailscale", "file", "cp"])
            self.assertEqual(c[3:5], [str(f1), str(f2)])
        self.assertIn("실패(1) no route", out.getvalue())

    def test_inbox(self):
        with mock.patch.object(linkmycom.platform, "system", return_value="Darwin"), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_inbox([]), 0)
        self.assertIn("Downloads", out.getvalue())
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(linkmycom.platform, "system", return_value="Windows"), \
                mock.patch.object(linkmycom, "tailscale_exe", return_value="tailscale"), \
                mock.patch.object(linkmycom.subprocess, "call", return_value=0) as call, redirect_stdout(io.StringIO()):
            self.assertEqual(linkmycom.cmd_inbox([d, "--wait"]), 0)
        call.assert_called_once_with(["tailscale", "file", "get", "--conflict=rename", "--wait", d])


# ---------------------------------------------------------------- C8. exec.

class ExecTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(linkmycom.parse_exec_args(["all", "--", "lmc", "version"]), ("all", ["lmc", "version"], None))
        self.assertEqual(linkmycom.parse_exec_args(["pfl", "--timeout", "5", "--", "-x"]), ("pfl", ["-x"], 5.0))
        self.assertEqual(linkmycom.parse_exec_args(["pfl", "hostname"]), ("pfl", ["hostname"], None))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            linkmycom.parse_exec_args(["pfl", "--"])

    def test_prefix_and_exit_codes(self):
        def fake_cmd(peer, cfg, blocks, remote, ssh=None):
            code = 0 if peer["name"] == "pfl" else 3
            return [sys.executable, "-c", f"print('one'); print({remote[0]!r}); raise SystemExit({code})"]

        out = io.StringIO()
        err = io.StringIO()
        with mock.patch.object(linkmycom, "resolve_targets", return_value=PEERS[:2]), \
                mock.patch.object(linkmycom, "remote_ssh_cmd", side_effect=fake_cmd), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                redirect_stdout(out), redirect_stderr(err):
            rc = linkmycom.cmd_exec({}, ["pfl,mac", "--", "hostname"])
        self.assertEqual(rc, 1)
        lines = out.getvalue().splitlines()
        self.assertIn("[pfl] one", lines)
        self.assertIn("[mac] hostname", lines)
        self.assertEqual(len(lines), 4)
        self.assertIn("실패: mac(3)", err.getvalue())

    def test_all_targets(self):
        self.assertEqual([p["name"] for p in linkmycom.ssh_capable(PEERS)], ["pfl", "mac"])


# ---------------------------------------------------------------- C9. fleet.

class FleetTests(unittest.TestCase):
    def test_versions_and_update_command(self):
        self.assertEqual(linkmycom.cli_versions([("cli", "INFO", "linkmycom 0.4.1, tower 0.4.4")]),
                         {"linkmycom": "0.4.1", "tower": "0.4.4"})
        win = linkmycom.fleet_update_command("windows", ["linkmycom", "tower"])
        ps = base64.b64decode(win.split()[-1]).decode("utf-16-le")
        self.assertIn(r'& "$env:LOCALAPPDATA\linkmycom\linkmycom.cmd" update', ps)
        self.assertIn(r'& "$env:LOCALAPPDATA\DeskTools\tower\linkmycom.cmd" update', ps)
        self.assertLess(len(win), 8000)
        self.assertTrue(ps.startswith("lmc update"))  # PATH 의 lmc 가 부르는 설치본 먼저
        mac = linkmycom.fleet_update_command("macOS", ["bin"], path_stale=False)
        self.assertIn('/.local/bin/linkmycom', mac)
        self.assertNotIn("lmc update;", mac)
        only = base64.b64decode(linkmycom.fleet_update_command("windows", ["tower"], path_stale=False).split()[-1])
        self.assertNotIn("lmc update", only.decode("utf-16-le"))

    def test_path_install_older_than_listed_ones(self):
        # jekim-1 처럼 PATH 의 lmc 가 %LOCALAPPDATA%\tssh 의 옛 설치본을 부르면 고정 위치가 최신이어도 낡음으로 본다.
        v = linkmycom.__version__
        rows = [("cli", "INFO", f"tower {v}"),
                ("path_lmc", "WARN", f"lmc -> ~\\AppData\\Local\\tssh\\linkmycom.py (0.4.3); also on PATH: x ({v})")]
        self.assertEqual(linkmycom.path_lmc_version(rows), ("~\\AppData\\Local\\tssh\\linkmycom.py", "0.4.3"))
        self.assertEqual(linkmycom.stale_installs(rows), (True, []))
        fleet = [{"name": "me", "ip": "", "os": "windows", "peer": None, "error": "", "rows": [("cli", "INFO", f"tower {v}")]},
                 {"name": "jekim-1", "ip": "100.1.1.1", "os": "windows", "peer": PEERS[0], "error": "", "rows": rows}]
        with mock.patch.object(linkmycom, "fleet_rows", return_value=fleet), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_fleet({}, ["update", "-n"]), 0)
        self.assertIn("jekim-1: lmc(PATH)", out.getvalue())
        with mock.patch.object(linkmycom, "fleet_rows", return_value=fleet), redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_fleet({}, ["status"])
        self.assertIn("CLI 낡음: lmc 0.4.3", out.getvalue())

    def test_update_only_stale_and_dry_run(self):
        rows = [
            {"name": "me", "ip": "(이 PC)", "os": "windows", "peer": None, "error": "",
             "rows": [("cli", "INFO", f"tower {linkmycom.__version__}")]},
            {"name": "pfl", "ip": "100.1.1.1", "os": "windows", "peer": PEERS[0], "error": "",
             "rows": [("cli", "INFO", "linkmycom 0.4.1, tower 9.9.9")]},
            {"name": "mac", "ip": "100.1.1.2", "os": "macOS", "peer": PEERS[1], "error": "",
             "rows": [("cli", "INFO", f"bin {linkmycom.__version__}")]},
        ]
        with mock.patch.object(linkmycom, "fleet_rows", return_value=rows), \
                mock.patch.object(linkmycom, "run_remote", side_effect=AssertionError("-n 은 원격 실행 금지")), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_fleet({}, ["update", "-n"]), 0)
        self.assertIn("pfl: linkmycom 설치본", out.getvalue())
        self.assertNotIn("mac:", out.getvalue())
        sent = []
        stdin_seen = []

        def fake_remote(p, cfg, blocks, remote, stdin_text=None, timeout=None, ssh=None):
            sent.append(p["name"])
            stdin_seen.append(stdin_text)
            return 0, "LMCPUSH|C:\\x\\tower\\linkmycom.py|0.4.1->%s\n" % linkmycom.__version__, ""

        # 0.4.7 부터 관리 PC 가 릴리스를 받아 서명 확인한 뒤 원격에 밀어 넣는다(원격이 스스로 받지 않는다).
        with mock.patch.object(linkmycom, "fleet_rows", return_value=rows), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), \
                mock.patch.object(linkmycom, "latest_release", return_value={"tag_name": "v" + linkmycom.__version__}), \
                mock.patch.object(linkmycom, "fetch_release_source", return_value=(b"__version__ = 'x'\n", linkmycom.__version__)), \
                mock.patch.object(linkmycom, "remote_scp_cmd", return_value=[sys.executable, "-c", "pass"]), \
                mock.patch.object(linkmycom, "run_remote", side_effect=fake_remote), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_fleet({}, ["update", "cli"]), 0)
        self.assertEqual(sent, ["pfl"])
        self.assertIn("LMCPUSH", stdin_seen[0])
        self.assertTrue(stdin_seen[0].rstrip().endswith(linkmycom.DOCTOR_STDIN_END))  # Windows 는 종료 표시 줄
        self.assertIn("tower: 0.4.1->", out.getvalue())
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_fleet({}, ["update", "native"]), 0)
        self.assertIn("Deploy-NativeHost.ps1", out.getvalue())


# ---------------------------------------------------------------- C10. screen 모드·forward.

class ScreenForwardTests(unittest.TestCase):
    def test_parse_screen(self):
        self.assertEqual(linkmycom.parse_screen_args(["pfl"]), (["pfl"], False, "--connect", None))
        self.assertEqual(linkmycom.parse_screen_args(["pfl", "--files", "--gather"]), (["pfl"], True, "--file-transfer", None))
        self.assertEqual(linkmycom.parse_screen_args(["--forward", "8080:80", "pfl"]), (["pfl"], False, "--port-forward", "8080:80"))
        self.assertEqual(linkmycom.parse_screen_args(["pfl", "--terminal"])[2], "--terminal")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            linkmycom.parse_screen_args(["pfl", "--files", "--terminal"])

    def test_screen_launches_viewer_before_gather_finishes(self):
        events = []

        def slow_gather(peers, cfg, blocks, args):
            time.sleep(0.5)
            events.append("gather-done")

        def popen(cmd, **kw):
            events.append(("viewer", cmd[1], cmd[2]))
            return mock.Mock()

        with mock.patch.object(linkmycom, "cmd_display", side_effect=slow_gather), \
                mock.patch.object(linkmycom, "screen_app_exe", return_value="app.exe"), \
                mock.patch.object(linkmycom.subprocess, "Popen", side_effect=popen), redirect_stdout(io.StringIO()):
            rc = linkmycom.cmd_screen(PEERS, {"hosts": {}}, [], ["pfl", "--gather", "--terminal"])
        self.assertEqual(rc, 0)
        self.assertEqual(events, [("viewer", "--terminal", "100.1.1.1"), "gather-done"])  # 뷰어 먼저, 모으기는 기다려 끝냄

    def test_forward_spec_and_command(self):
        self.assertEqual(linkmycom.parse_forward_spec("8080:80"), "8080:127.0.0.1:80")
        self.assertEqual(linkmycom.parse_forward_spec("5432:db.local:5432"), "5432:db.local:5432")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            linkmycom.parse_forward_spec("x:80")
        with mock.patch.object(linkmycom, "pick_cached", return_value=(PEERS[0], PEERS)), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_forward({"hosts": {}}, ["pfl", "8080:80", "-n"]), 0)
        line = out.getvalue()
        self.assertIn("-N", line)
        self.assertIn("-L 8080:127.0.0.1:80", line)
        self.assertIn("ExitOnForwardFailure=yes", line)


# ---------------------------------------------------------------- 도움말·자동 완성.

class HelpCompletionTests(unittest.TestCase):
    def test_new_commands_documented_and_completed(self):
        for cmd in ("send", "inbox", "exec", "fleet", "forward"):
            self.assertIn(cmd, linkmycom.SUBCOMMANDS)
            self.assertIn(cmd, linkmycom.COMMAND_HELP)
            self.assertIn(f"linkmycom {cmd}", linkmycom.__doc__)
        for shell in linkmycom.COMPLETION_SHELLS:
            text = linkmycom.completion_script(shell)
            for word in ("--all", "--files", "--terminal", "--forward", "fleet", "--to"):
                self.assertIn(word, text)
        ps = linkmycom.completion_script("powershell")
        self.assertIn("'screen' { $words = @('--gather'", ps)
        self.assertIn("{ @('set', 'unset', 'resolve', 'display') -contains $_ }", ps)  # 옵션 있는 명령은 일반 호스트 줄에서 빠져 덮어쓰지 않는다


if __name__ == "__main__":
    unittest.main()
