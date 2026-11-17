# linkmycom 0.5.0 의 clip(21120 규약)·자동 업데이트 적용·doctor 새 줄과 C1~C10(doctor --fix, maintain, hostkey, --json, 즐겨찾기·기록, forward --bg, exec --os/--ps, sessions close, fleet rollback)을 검사하는 단위 테스트.
from __future__ import annotations

import ast
import base64
import hashlib
import io
import json
import os
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import linkmycom  # noqa: E402

PEERS = [
    {"name": "pfl", "hostname": "pfl", "dns": "pfl.ts.net", "ip": "127.0.0.1", "os": "windows", "online": True,
     "last_seen": "", "ts_ssh": False, "tags": [], "cur_addr": "5.6.7.8:41641", "relay": "tok"},
    {"name": "mac", "hostname": "mac", "dns": "mac.ts.net", "ip": "100.1.1.2", "os": "macOS", "online": True,
     "last_seen": "", "ts_ssh": False, "tags": [], "cur_addr": "", "relay": ""},
    {"name": "phone", "hostname": "phone", "dns": "phone.ts.net", "ip": "100.1.1.3", "os": "iOS", "online": True,
     "last_seen": "", "ts_ssh": False, "tags": [], "cur_addr": "", "relay": ""},
    {"name": "off", "hostname": "off", "dns": "off.ts.net", "ip": "100.1.1.4", "os": "linux", "online": False,
     "last_seen": "2026-11-01T00:00:00Z", "ts_ssh": False, "tags": [], "cur_addr": "", "relay": ""},
    {"name": "zed", "hostname": "zed", "dns": "", "ip": "100.1.1.5", "os": "?", "online": True,
     "last_seen": "", "ts_ssh": False, "tags": [], "cur_addr": "", "relay": ""},
]


class TempHome(unittest.TestCase):
    """CONFIG_DIR·STATE_PATH·CONFIG_PATH·HOSTS_CACHE_PATH·SSH_DIR 를 임시 폴더로 돌린다."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        cfgdir = self.root / ".tssh"
        self.patches = [
            mock.patch.object(linkmycom, "CONFIG_DIR", cfgdir),
            mock.patch.object(linkmycom, "STATE_PATH", cfgdir / "state.json"),
            mock.patch.object(linkmycom, "CONFIG_PATH", cfgdir / "config.json"),
            mock.patch.object(linkmycom, "HOSTS_CACHE_PATH", cfgdir / "hosts.txt"),
            mock.patch.object(linkmycom, "SSH_DIR", self.root / ".ssh"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self._tmp.cleanup()

    def state(self) -> dict:
        return linkmycom.load_json(linkmycom.STATE_PATH)


# ---------------------------------------------------------------- 공통: 버전·도움말·문법.

class BasicsTests(unittest.TestCase):
    def test_version_and_commands(self):
        self.assertEqual(linkmycom.__version__, "0.5.0")
        for sub in ("clip", "maintain", "history", "hostkey", "sessions"):
            self.assertIn(sub, linkmycom.SUBCOMMANDS)
            self.assertIn(sub, linkmycom.COMMAND_HELP)
        self.assertIn("auto_update_apply", linkmycom.COMMAND_HELP["config"])
        self.assertIn("--fix", linkmycom.COMMAND_HELP["doctor"])
        self.assertIn("rollback", linkmycom.COMMAND_HELP["fleet"])
        for shell in linkmycom.COMPLETION_SHELLS:
            script = linkmycom.completion_script(shell)
            self.assertIn("clip", script)
            self.assertIn("--bg", script)

    def test_python39_syntax(self):
        src = (HERE / "linkmycom.py").read_text(encoding="utf-8")
        ast.parse(src, feature_version=(3, 9))
        ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_install_scripts_verify_signature(self):
        ps = (HERE / "install.ps1").read_bytes()
        self.assertTrue(ps.isascii())  # irm | iex 로 받을 때 Latin-1 로 읽힌다
        text = ps.decode("ascii")
        self.assertIn("releases/latest", text)
        self.assertIn("-RedirectStandardInput $File", text)  # 파이프가 아니라 파일 리디렉션
        self.assertIn(linkmycom.SIGNING_PUBKEY, text)
        self.assertIn("Get-FileHash", text)
        sh = (HERE / "install.sh").read_text(encoding="utf-8")
        self.assertIn('-s "$tmp/linkmycom.py.sig" < "$src"', sh)
        self.assertIn(linkmycom.SIGNING_PUBKEY, sh)
        self.assertIn("LINKMYCOM_UNVERIFIED", sh)


# ---------------------------------------------------------------- F1. lmc clip (가짜 21120 서버로 규약 확인).

class FakeClipServer:
    """socketserver 로 임의 포트에서 LMCCLIP 메시지를 받아 기록하고 정해진 응답을 돌려준다."""

    def __init__(self, reply: bytes = b"OK\n"):
        received = self.received = []

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                head = self.rfile.readline()
                parts = head.decode("ascii").split()
                size = int(parts[3])
                payload = self.rfile.read(size)
                received.append((parts, payload))
                self.wfile.write(reply)

        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


class ClipTests(TempHome):
    def test_parse_args(self):
        self.assertEqual(linkmycom.parse_clip_args(["pfl,mac", "--text", "hi"]), (["pfl", "mac"], "hi", []))
        self.assertEqual(linkmycom.parse_clip_args(["pfl", "--file", "a", "--file=b"]), (["pfl"], None, ["a", "b"]))
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                linkmycom.parse_clip_args(["--text", "x"])
            with self.assertRaises(SystemExit):
                linkmycom.parse_clip_args(["pfl", "--text", "x", "--file", "a"])

    def test_message_format(self):
        data = linkmycom.clip_message("text", "안녕".encode("utf-8"), "jekim-1")
        head, payload = data.split(b"\n", 1)
        parts = head.decode("ascii").split(" ")
        self.assertEqual(parts[:3], ["LMCCLIP", "1", "text"])
        self.assertEqual(int(parts[3]), len("안녕".encode("utf-8")))
        self.assertEqual(parts[4], hashlib.sha256(payload).hexdigest())
        self.assertEqual(parts[5], "jekim-1")
        self.assertEqual(len(parts), 6)
        with mock.patch.object(linkmycom.platform, "node", return_value="김 PC.local"):
            self.assertNotIn(" ", linkmycom.clip_sender_name())

    def test_send_ok_err_and_refused(self):
        with FakeClipServer() as srv:
            ok, msg = linkmycom.send_clip("127.0.0.1", linkmycom.clip_message("text", b"hello", "me"), port=srv.port)
        self.assertTrue(ok, msg)
        self.assertEqual(srv.received[0][1], b"hello")
        with FakeClipServer(b"ERR too large\n") as srv:
            ok, msg = linkmycom.send_clip("127.0.0.1", linkmycom.clip_message("text", b"x", "me"), port=srv.port)
        self.assertFalse(ok)
        self.assertEqual(msg, "too large")
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        free = s.getsockname()[1]
        s.close()
        ok, msg = linkmycom.send_clip("127.0.0.1", b"x", port=free, timeout=2)
        self.assertFalse(ok)
        self.assertIn(str(free), msg)

    def test_cmd_clip_text_end_to_end(self):
        with FakeClipServer() as srv, mock.patch.object(linkmycom, "CLIP_PORT", srv.port), \
                mock.patch.object(linkmycom, "pick_cached", return_value=(PEERS[0], PEERS)), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                redirect_stdout(io.StringIO()) as out:
            rc = linkmycom.cmd_clip({}, ["pfl", "--text", "붙여넣기"])
        self.assertEqual(rc, 0, out.getvalue())
        parts, payload = srv.received[0]
        self.assertEqual(parts[2], "text")
        self.assertEqual(payload.decode("utf-8"), "붙여넣기")
        self.assertIn("보냄", out.getvalue())

    def test_cmd_clip_files_uses_taildrop_then_names(self):
        f1 = self.root / "a.txt"
        f1.write_text("a", encoding="utf-8")
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with FakeClipServer() as srv, mock.patch.object(linkmycom, "CLIP_PORT", srv.port), \
                mock.patch.object(linkmycom, "pick_cached", return_value=(PEERS[0], PEERS)), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "tailscale_exe", return_value="tailscale"), \
                mock.patch.object(linkmycom.subprocess, "run", side_effect=fake_run), redirect_stdout(io.StringIO()):
            rc = linkmycom.cmd_clip({}, ["pfl", "--file", str(f1)])
        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][:3], ["tailscale", "file", "cp"])
        self.assertEqual(calls[0][-1], "127.0.0.1:")
        self.assertEqual(srv.received[0][0][2], "files")
        self.assertEqual(srv.received[0][1], b"a.txt")

    def test_text_limit_and_empty(self):
        with mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                linkmycom.cmd_clip({}, ["pfl", "--text", "x" * (linkmycom.CLIP_MAX_TEXT + 1)])
            with self.assertRaises(SystemExit):
                linkmycom.cmd_clip({}, ["pfl", "--text", ""])

    def test_linux_without_tools_explains(self):
        with mock.patch.object(linkmycom.platform, "system", return_value="Linux"), \
                mock.patch.object(linkmycom.shutil, "which", return_value=None), redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit):
                linkmycom.read_local_clipboard()
        self.assertIn("xclip", err.getvalue())


# ---------------------------------------------------------------- F3. 자동 업데이트 적용.

class AutoUpdateTests(TempHome):
    def test_apply_quietly_replaces_and_notifies(self):
        st, notice = {"update_available": "0.5.1"}, []
        with mock.patch.object(linkmycom, "fetch_release_source", return_value=(b"src", "0.5.1")), \
                mock.patch.object(linkmycom, "write_self") as ws:
            self.assertTrue(linkmycom.apply_update_quietly("r", {}, st, notice))
        ws.assert_called_once()
        self.assertEqual(ws.call_args[0][1], b"src")
        self.assertEqual(notice, ["linkmycom 0.5.1 으로 업데이트했습니다. 다음 실행부터 적용."])
        self.assertNotIn("update_available", st)
        self.assertEqual(st["last_auto_update"], "0.5.1")

    def test_apply_failure_is_recorded_quietly(self):
        st, notice = {}, []
        with mock.patch.object(linkmycom, "fetch_release_source", side_effect=RuntimeError("서명 확인 실패")), \
                mock.patch.object(linkmycom, "write_self") as ws:
            self.assertFalse(linkmycom.apply_update_quietly("r", {}, st, notice))
        ws.assert_not_called()
        self.assertIn("서명 확인 실패", st["update_error"])
        self.assertEqual(notice, [])

    def run_check(self, apply: bool):
        notice: list[str] = []
        rel = {"tag_name": "v0.5.9"}
        with mock.patch.object(linkmycom, "latest_release", return_value=rel), \
                mock.patch.object(linkmycom, "fetch_release_source", return_value=(b"src", "0.5.9")), \
                mock.patch.object(linkmycom, "write_self") as ws:
            t = linkmycom.background_update_check({"auto_update_check": True}, notice, apply=apply)
            t.join(5)
        return notice, ws

    def test_background_applies_when_allowed(self):
        notice, ws = self.run_check(True)
        ws.assert_called_once()
        self.assertIn("0.5.9 으로 업데이트했습니다", notice[0])
        self.assertEqual(self.state().get("last_auto_update"), "0.5.9")

    def test_background_only_checks_when_not_allowed(self):
        notice, ws = self.run_check(False)
        ws.assert_not_called()
        self.assertIn("'linkmycom update' 로 적용하세요", notice[0])
        self.assertEqual(self.state().get("update_available"), "0.5.9")

    def test_allowed_needs_config_and_tty(self):
        self.assertFalse(linkmycom.auto_apply_allowed({"auto_update_apply": False}))
        with mock.patch.object(sys, "stdin", io.StringIO()):
            self.assertFalse(linkmycom.auto_apply_allowed({}))  # 비대화형(파이프)

    def test_config_key(self):
        cfg = linkmycom.load_config()
        self.assertTrue(cfg["auto_update_apply"])
        with redirect_stdout(io.StringIO()):
            linkmycom.cmd_config(cfg, ["auto_update_apply=false"])
        self.assertFalse(linkmycom.load_json(linkmycom.CONFIG_PATH)["auto_update_apply"])


# ---------------------------------------------------------------- doctor 새 줄과 fleet '자동 업데이트' 열.

class DoctorRowsTests(unittest.TestCase):
    def test_script_has_new_rows(self):
        s = linkmycom.DOCTOR_PY
        self.assertTrue(s.isascii())
        compile(s, "doctor", "exec")
        for want in ("clip_port", "auto_update", "LinkMyCom-NativeUpdate", "LinkMyCom-TowerUpdate",
                     "com.linkmycom.native-update", "update-state.json", "lastResult", "21120"):
            self.assertIn(want, s)
        for name in ("clip_port", "auto_update"):
            self.assertIn(name, linkmycom.DOCTOR_LABELS)

    def test_summary(self):
        f = linkmycom.auto_update_summary
        self.assertEqual(f([]), "-")
        self.assertEqual(f([("auto_update", "OK", "tasks LinkMyCom-NativeUpdate; last ok 2026-11-18 04:30")]), "OK ok")
        self.assertEqual(f([("auto_update", "WARN", "missing LinkMyCom-NativeUpdate,LinkMyCom-TowerUpdate; no run recorded")]),
                         "WARN 없음 NativeUpdate,TowerUpdate")
        self.assertEqual(f([("auto_update", "INFO", "no updater job")]), "-")

    def test_fleet_table_column(self):
        fleet = [{"name": "me", "ip": "(이 PC)", "os": "windows", "peer": None, "error": "",
                  "rows": [("cli", "INFO", f"tower {linkmycom.__version__}"),
                           ("auto_update", "OK", "tasks LinkMyCom-NativeUpdate; last installed 2026-11-18 04:30")]}]
        with mock.patch.object(linkmycom, "fleet_rows", return_value=fleet), redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_fleet({}, ["status"])
        self.assertIn("자동 업데이트", out.getvalue())
        self.assertIn("OK installed", out.getvalue())


# ---------------------------------------------------------------- C1. doctor --fix.

BAD_ROWS = [("sshd", "FAIL", "Stopped"), ("firewall", "WARN", "x"), ("keys_task", "WARN", "missing"),
            ("keys_refresh", "WARN", "old"), ("tower_run", "WARN", "not running"), ("path_lmc", "WARN", "dup"),
            ("cli", "INFO", "")]


class DoctorFixTests(TempHome):
    def test_plan(self):
        keys = [k for k, _ in linkmycom.plan_fixes(BAD_ROWS, "Windows")]
        self.assertEqual(keys, ["keys_task", "keys_refresh", "server", "tower_run", "path_lmc"])
        self.assertEqual([k for k, _ in linkmycom.plan_fixes([("ssh_port", "FAIL", "")], "Darwin")], ["server"])
        self.assertEqual(linkmycom.plan_fixes([("sshd", "OK", "")], "Windows"), [])

    def test_dry_run_changes_nothing(self):
        names = ("schedule_keys_refresh", "refresh_keys", "setup_server_windows", "start_tower", "fix_path_lmc")
        mocks = {n: mock.patch.object(linkmycom, n).start() for n in names}
        try:
            with mock.patch.object(linkmycom.platform, "system", return_value="Windows"), \
                    redirect_stdout(io.StringIO()) as out:
                rc = linkmycom.cmd_doctor_fix({}, dry=True, rows=BAD_ROWS)
        finally:
            mock.patch.stopall()
        self.assertEqual(rc, 0)
        for m in mocks.values():
            m.assert_not_called()
        self.assertIn("바꾸지 않음", out.getvalue())
        self.assertIn("UAC", out.getvalue())

    def test_runs_each_fix_once(self):
        with mock.patch.object(linkmycom.platform, "system", return_value="Windows"), \
                mock.patch.object(linkmycom, "schedule_keys_refresh", return_value=True) as a, \
                mock.patch.object(linkmycom, "refresh_keys", return_value=4) as b, \
                mock.patch.object(linkmycom, "setup_server_windows", return_value=True) as s, \
                mock.patch.object(linkmycom, "start_tower", return_value=False) as t, \
                mock.patch.object(linkmycom, "fix_path_lmc", return_value=True) as p, redirect_stdout(io.StringIO()):
            rc = linkmycom.cmd_doctor_fix({}, rows=BAD_ROWS)
        for m in (a, b, s, t, p):
            m.assert_called_once()
        self.assertEqual(rc, 1)  # 타워 시작 실패

    def test_fix_path_lmc_asks_and_keeps_newest(self):
        a, b = self.root / "a" / "lmc.cmd", self.root / "b" / "lmc.cmd"
        for f in (a, b):
            f.parent.mkdir()
            f.write_text("x", encoding="utf-8")
        found = [(str(a), "A.py", "0.4.8"), (str(b), "B.py", "0.5.0")]
        with redirect_stdout(io.StringIO()):
            self.assertTrue(linkmycom.fix_path_lmc(found, ask=lambda q: "y"))
        self.assertFalse(a.exists())
        self.assertTrue(b.exists())
        b2 = self.root / "c" / "lmc.cmd"
        b2.parent.mkdir()
        b2.write_text("x", encoding="utf-8")
        self.assertFalse(linkmycom.fix_path_lmc([(str(b), "B.py", "0.5.0"), (str(b2), "C.py", "0.4.0")], ask=lambda q: "n"))
        self.assertTrue(b2.exists())


# ---------------------------------------------------------------- C2. maintain.

class MaintainTests(TempHome):
    def test_schedule_runs_maintain(self):
        self.assertEqual(linkmycom.refresh_command("py", "s")[2:], ["maintain", "--quiet"])
        self.assertIn("maintain --quiet", linkmycom.schedule_windows_ps("py", "s"))

    def test_records_and_notices(self):
        rows = [("sshd", "FAIL", "Stopped"), ("tower_run", "WARN", "x"), ("firewall", "OK", "")]
        with mock.patch.object(linkmycom, "refresh_keys", return_value=5), \
                mock.patch.object(linkmycom, "local_doctor_rows", return_value=rows), \
                mock.patch.object(linkmycom, "tower_start_script", return_value=Path("x")), \
                mock.patch.object(linkmycom, "start_tower", return_value=True) as st, \
                mock.patch.object(linkmycom, "setup_server_windows") as admin:
            rc = linkmycom.cmd_maintain({}, ["--quiet"])
        self.assertEqual(rc, 0)
        st.assert_called_once()
        admin.assert_not_called()  # 관리자 권한이 필요한 고침은 하지 않는다
        m = self.state()["maintain"]
        self.assertEqual(m["needs_admin"], ["sshd"])
        self.assertIn("tower_run", m["done"])
        self.assertIn("doctor --fix", linkmycom.maintain_notices()[0])

    def test_dry_run(self):
        with mock.patch.object(linkmycom, "refresh_keys") as rk, redirect_stdout(io.StringIO()):
            self.assertEqual(linkmycom.cmd_maintain({}, ["-n"]), 0)
        rk.assert_not_called()
        self.assertEqual(linkmycom.maintain_notices(), [])


# ---------------------------------------------------------------- C3. 호스트 키.

class HostKeyTests(TempHome):
    def test_batch_accept_new_only(self):
        self.assertIn("StrictHostKeyChecking=accept-new", linkmycom.BATCH_SSH_OPTS)
        cmd = linkmycom.build_ssh_cmd(PEERS[1], {}, {"ssh_options": {}}, [], ssh_path="ssh")
        self.assertNotIn("StrictHostKeyChecking=accept-new", " ".join(cmd))  # 대화형 접속에는 붙이지 않는다
        self.assertIn("hostkey reset", linkmycom.remote_rows_error([], "Host key verification failed.\r\n"))

    def test_reset_dry_run(self):
        with mock.patch.object(linkmycom, "pick_cached", return_value=(PEERS[1], PEERS)), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "find_keygen", return_value="ssh-keygen"), \
                mock.patch.object(linkmycom, "keyscan_bin", return_value="ssh-keyscan"), \
                mock.patch.object(linkmycom.subprocess, "run") as run, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_hostkey({"hosts": {}}, ["reset", "mac", "-n"]), 0)
        run.assert_not_called()
        text = out.getvalue()
        self.assertIn("-R 100.1.1.2", text)
        self.assertIn("-R mac.ts.net", text)
        self.assertIn("ssh-keyscan -T 5 100.1.1.2", text)
        self.assertEqual(linkmycom.known_hosts_names(PEERS[1], "2222")[0], "[100.1.1.2]:2222")


# ---------------------------------------------------------------- C4. 파이썬 없는 원격 Windows.

class NoPythonTests(unittest.TestCase):
    def test_powershell_fallback(self):
        ps = linkmycom.WINDOWS_NOPY_DOCTOR_PS
        self.assertTrue(ps.isascii())
        for want in ("LMCDOC|python|WARN", "LMCDOC|sshd|", "LMCDOC|firewall|", "LMCDOC|cli|", "LMCDOC|tower|",
                     "LMCDOC|native|", "LMCDOC|screen_svc|", "Python.Python.3.12"):
            self.assertIn(want, ps)
        win, _ = linkmycom.doctor_remote_command("windows", "AAAAkey")
        self.assertLess(len(win), 8000)
        decoded = base64.b64decode(win.split()[-1]).decode("utf-16-le")
        self.assertIn("LMCDOC|python|WARN", decoded)
        rows = [("python", "WARN", "python 3 not found; PowerShell-only checks"), ("cli", "INFO", "tower 0.4.8")]
        self.assertEqual(linkmycom.remote_rows_error(rows, ""), "")


# ---------------------------------------------------------------- C5. --json.

class JsonTests(TempHome):
    KEYS = {"name", "ip", "dns", "os", "online", "cur_addr", "relay", "fav", "last_seen"}

    def run_main(self, argv, peers=PEERS):
        with mock.patch.object(linkmycom, "migrate_legacy_install", return_value=[]), \
                mock.patch.object(linkmycom, "repair_shims", return_value=[]), \
                mock.patch.object(linkmycom, "ensure_tower_bin_shims", return_value=[]), \
                mock.patch.object(linkmycom, "fresh_peers", return_value=peers), \
                mock.patch.object(linkmycom, "cached_peers", return_value=(peers, True)), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                redirect_stdout(io.StringIO()) as out:
            rc = linkmycom.main(argv)
        return rc, out.getvalue()

    def test_list_json_fixed_shape(self):
        cfg = {"hosts": {"mac": {"fav": True}}}
        linkmycom.save_json(linkmycom.CONFIG_PATH, cfg)
        rc, out = self.run_main(["list", "--json"])
        data = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertEqual(len(data), len(PEERS))  # 모바일도 포함
        for item in data:
            self.assertEqual(set(item), self.KEYS)
        self.assertTrue(next(d for d in data if d["name"] == "mac")["fav"])
        self.assertEqual(data[0]["relay"], "tok")

    def test_resolve_json(self):
        rc, out = self.run_main(["resolve", "mac", "--json"])
        data = json.loads(out)
        self.assertEqual(data["name"], "mac")
        self.assertTrue(data["ssh"].endswith("@100.1.1.2"))
        self.assertTrue(self.KEYS <= set(data))

    def test_doctor_json_local(self):
        rows = [("tailscale", "OK", "x"), ("sshd", "FAIL", "Stopped")]
        with mock.patch.object(linkmycom, "local_doctor_rows", return_value=rows), \
                mock.patch.object(linkmycom, "doctor_keys_list_row", return_value=("keys_list", "OK", "k")), \
                redirect_stdout(io.StringIO()) as out:
            rc = linkmycom.cmd_doctor({}, ["--json"])
        data = json.loads(out.getvalue())
        self.assertEqual(rc, 1)
        self.assertEqual(set(data), {"name", "ip", "os", "rows", "error"})
        self.assertIn(["sshd", "FAIL", "Stopped"], data["rows"])


# ---------------------------------------------------------------- C6. 즐겨찾기·최근·기록.

class OrderAndHistoryTests(TempHome):
    def test_order(self):
        cfg = {"hosts": {"off": {"fav": True}}}
        names = [p["name"] for p in linkmycom.ordered_peers(PEERS, cfg, recent=["zed"])]
        self.assertEqual(names, ["off", "zed", "mac", "pfl"])  # 즐겨찾기 → 최근 → 온라인 → (모바일 숨김)
        self.assertIn("phone", [p["name"] for p in linkmycom.ordered_peers(PEERS, cfg, show_mobile=True)])
        rows = linkmycom.peer_rows([PEERS[2], PEERS[4]], cfg, [], None, [7, 9])
        self.assertEqual(rows[0][0], "7")
        self.assertEqual(rows[0][5], "SSH 없음")
        self.assertEqual(rows[1][3], "-")  # OS '?' 정리

    def test_list_hides_mobile(self):
        with mock.patch.object(linkmycom, "recent_hosts", return_value=[]), redirect_stdout(io.StringIO()) as out:
            linkmycom.show_list(PEERS, {"hosts": {}}, [])
        self.assertNotIn("phone", out.getvalue())
        self.assertIn("--all", out.getvalue())

    def test_set_fav(self):
        cfg = {"hosts": {}}
        with redirect_stdout(io.StringIO()):
            linkmycom.cmd_set(PEERS, cfg, [], ["mac", "fav=1", "forward=8080:80,9000:localhost:9000"])
        self.assertEqual(cfg["hosts"]["mac"], {"fav": True, "forward": "8080:80,9000:localhost:9000"})
        with redirect_stdout(io.StringIO()):
            linkmycom.cmd_set(PEERS, cfg, [], ["mac", "fav=0"])
        self.assertNotIn("fav", cfg["hosts"]["mac"])

    def test_history_and_recent(self):
        linkmycom.record_history("connect", ["pfl"])
        linkmycom.record_history("send", ["mac"], "1 files")
        linkmycom.record_history("screen", ["mac"])
        linkmycom.record_history("connect", ["pfl"])
        self.assertEqual(linkmycom.recent_hosts(5), ["pfl", "mac"])
        with redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_history(["mac", "--since", "7d"])
        text = out.getvalue()
        self.assertIn("send", text)
        self.assertNotIn("connect", text)
        old = {"time": "2020-01-01T00:00:00", "cmd": "exec", "names": ["mac"], "detail": "old"}
        with open(linkmycom.history_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(old) + "\n")
        with redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_history(["--since=1d"])
        self.assertNotIn("old", out.getvalue())


# ---------------------------------------------------------------- C7. forward --bg / list / stop / 저장 규칙.

class ForwardTests(TempHome):
    def test_saved_rule_dry_run(self):
        cfg = {"hosts": {"mac": {"forward": "8080:80"}}, "ssh_options": {}}
        with mock.patch.object(linkmycom, "pick_cached", return_value=(PEERS[1], PEERS)), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_forward(cfg, ["mac", "--bg", "-n"]), 0)
        text = out.getvalue()
        self.assertIn("-L 8080:127.0.0.1:80", text)
        self.assertIn("BatchMode=yes", text)  # 백그라운드는 묻지 않는다

    def test_bg_records_and_stop(self):
        class P:
            pid = 4242
            returncode = None

            def communicate(self, timeout=None):
                raise subprocess.TimeoutExpired("ssh", timeout)

        with mock.patch.object(linkmycom.subprocess, "Popen", return_value=P()), \
                mock.patch.object(linkmycom, "pid_alive", return_value=True), redirect_stdout(io.StringIO()):
            self.assertEqual(linkmycom.forward_start_bg(PEERS[1], ["8080:127.0.0.1:80"], ["ssh"]), 0)
            items = linkmycom.load_forwards()
            self.assertEqual(items[0]["pid"], 4242)
            with redirect_stdout(io.StringIO()) as out:
                linkmycom.forward_list()
            self.assertIn("4242", out.getvalue())
        with mock.patch.object(linkmycom, "pid_alive", side_effect=[True, False]), \
                mock.patch.object(linkmycom, "kill_pid", return_value=True) as k, redirect_stdout(io.StringIO()):
            self.assertEqual(linkmycom.forward_stop("1"), 0)
        k.assert_called_once_with(4242)
        with mock.patch.object(linkmycom, "pid_alive", return_value=True):
            self.assertEqual(linkmycom.load_forwards(), [])

    def test_dead_entries_pruned(self):
        linkmycom.save_json(linkmycom.forwards_path(), {"forwards": [{"pid": 1, "name": "x"}, {"pid": 2, "name": "y"}]})
        with mock.patch.object(linkmycom, "pid_alive", side_effect=lambda p: p == 2):
            self.assertEqual([f["pid"] for f in linkmycom.load_forwards()], [2])
        self.assertTrue(linkmycom.pid_alive(os.getpid()))


# ---------------------------------------------------------------- C8. exec --os / --ps.

class ExecFilterTests(unittest.TestCase):
    def test_options(self):
        rest, osf, ps = linkmycom.parse_exec_options(["all", "--os", "Mac", "--ps", "--", "echo", "--os"])
        self.assertEqual((rest, osf, ps), (["all", "--", "echo", "--os"], "macos", True))
        self.assertEqual(linkmycom.parse_exec_args(rest), ("all", ["echo", "--os"], None))
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                linkmycom.parse_exec_options(["all", "--os=bsd"])

    def test_filter_and_wrap(self):
        self.assertEqual([p["name"] for p in linkmycom.filter_by_os(PEERS, "windows")], ["pfl"])
        self.assertEqual([p["name"] for p in linkmycom.filter_by_os(PEERS, "macos")], ["mac"])
        wrapped = linkmycom.exec_remote_for(PEERS[0], ["Get-Date", "-Format", "o"], True)
        self.assertEqual(len(wrapped), 1)
        self.assertEqual(base64.b64decode(wrapped[0].split()[-1]).decode("utf-16-le"), "Get-Date -Format o")
        self.assertEqual(linkmycom.exec_remote_for(PEERS[1], ["uname"], True), ["uname"])


# ---------------------------------------------------------------- C9. sessions close.

class SessionTests(unittest.TestCase):
    def test_only_session_windows(self):
        procs = [
            (10, '"C:\\Program Files\\LinkMyCom\\linkmycom.exe" --connect 100.1.1.2'),
            (11, '"C:\\Program Files\\LinkMyCom\\linkmycom.exe" --tray'),
            (12, '"C:\\Program Files\\LinkMyCom\\linkmycom.exe"'),
            (13, "/Applications/LinkMyCom.app/Contents/MacOS/LinkMyCom --file-transfer 100.1.1.3"),
            (14, "C:\\Python\\python.exe linkmycom.py screen x --connect"),
            (15, '"C:\\Program Files\\LinkMyCom\\linkmycom.exe" --terminal 100.1.1.2'),
            (16, '"C:\\Program Files\\LinkMyCom\\linkmycom.exe" --service'),
        ]
        self.assertEqual(linkmycom.session_pids(procs, me=1), [10, 13, 15])

    def test_dry_run_does_not_kill(self):
        procs = [(10, "linkmycom.exe --connect 1.2.3.4")]
        with mock.patch.object(linkmycom, "list_processes", return_value=procs), \
                mock.patch.object(linkmycom, "kill_pid") as k, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_sessions(["close", "-n"]), 0)
        k.assert_not_called()
        self.assertIn("1개", out.getvalue())


# ---------------------------------------------------------------- C10. fleet update 의 .prev 와 rollback.

class RollbackTests(unittest.TestCase):
    def test_push_keeps_prev_and_rollback_restores(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "linkmycom.py"
            target.write_text('__version__ = "0.4.8"\n', encoding="utf-8")
            new = b'__version__ = "0.5.0"\n'
            push = linkmycom.fleet_push_script(new, "0.5.0", [str(target)])
            r = subprocess.run([sys.executable, "-c", push], capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(target.read_bytes(), new)
            self.assertIn("0.4.8", (Path(d) / "linkmycom.py.prev").read_text(encoding="utf-8"))
            back = linkmycom.fleet_rollback_script([str(target)])
            r = subprocess.run([sys.executable, "-c", back], capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("0.5.0->0.4.8", r.stdout)
            self.assertIn('"0.4.8"', target.read_text(encoding="utf-8"))
            self.assertFalse((Path(d) / "linkmycom.py.prev").exists())
            r = subprocess.run([sys.executable, "-c", back], capture_output=True, text=True, timeout=60)
            self.assertIn("no .prev backup", r.stdout)

    def test_rollback_dry_run_and_cli_only(self):
        with mock.patch.object(linkmycom, "resolve_targets", return_value=[PEERS[0]]), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "run_remote") as rr, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_fleet({}, ["rollback", "pfl", "cli", "-n"]), 0)
        rr.assert_not_called()
        self.assertIn(".prev", out.getvalue())
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                linkmycom.cmd_fleet({}, ["rollback", "pfl", "tower"])


if __name__ == "__main__":
    unittest.main()
