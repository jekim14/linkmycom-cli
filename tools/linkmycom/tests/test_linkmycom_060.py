# linkmycom 0.6.0 의 실행 시 자동 업데이트(1시간 주기·update --all)와 C2~C10(open, cp, wake, profiles, audit, fleet 최신 판정·원격 업데이터, doctor 21118·중복 노드, 옛 이름 정리, status)을 검사하는 단위 테스트.
from __future__ import annotations

import ast
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import linkmycom  # noqa: E402


def peer(name, ip, os_name="windows", online=True, hostname=None, relay="", cur_addr=""):
    return {"name": name, "hostname": hostname or name, "dns": name + ".ts.net", "ip": ip, "os": os_name,
            "online": online, "last_seen": "", "ts_ssh": False, "tags": [], "cur_addr": cur_addr, "relay": relay}


PFL = peer("pfl", "100.1.1.1", "windows", cur_addr="1.2.3.4:41641", relay="tok")
MAC = peer("mac", "100.1.1.2", "macOS", relay="tok")
OFF = peer("box", "100.1.1.4", "windows", online=False)
PHONE = peer("phone", "100.1.1.3", "iOS")
# 실제 집의 Mac: Homebrew tailscaled(miniui-macmini, 22 만) 와 Tailscale.app(macmini, 호스트 이름 '미니의 Mac mini', 21118).
MINIUI = peer("miniui-macmini", "100.82.231.21", "macOS", hostname="miniui-Macmini")
MACMINI = peer("macmini", "100.110.204.16", "macOS", hostname="미니의 Mac mini")
JEKIM1 = peer("jekim-1", "100.108.229.83", "windows", hostname="jekim")
HERMES = peer("officehermes", "100.112.209.77", "windows")
PEERS = [PFL, MAC, OFF, PHONE]


def ps_of(cmd: str) -> str:
    return base64.b64decode(cmd.split()[-1]).decode("utf-16-le")


class TempHome(unittest.TestCase):
    """CONFIG_DIR·STATE_PATH·CONFIG_PATH·HOSTS_CACHE_PATH·SSH_DIR 를 임시 폴더로 돌린다(이 PC 의 설정을 건드리지 않음)."""

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


# ---------------------------------------------------------------- 공통.

class BasicsTests(unittest.TestCase):
    def test_version_commands_help_completion(self):
        self.assertEqual(linkmycom.__version__, "0.6.0")
        for sub in ("open", "cp", "wake", "profiles", "audit", "status"):
            self.assertIn(sub, linkmycom.SUBCOMMANDS)
            self.assertIn(sub, linkmycom.COMMAND_HELP)
            self.assertIn(f"linkmycom {sub}", linkmycom.__doc__)
        self.assertIn("--all", linkmycom.COMMAND_HELP["update"])
        self.assertIn("--apply", linkmycom.COMMAND_HELP["fleet"])
        self.assertIn("screen=", linkmycom.COMMAND_HELP["doctor"])
        for shell in linkmycom.COMPLETION_SHELLS:
            script = linkmycom.completion_script(shell)
            for word in ("wake", "--via", "--apply", "windows-terminal", "audit"):
                self.assertIn(word, script)

    def test_python39_syntax_and_ascii_doctor(self):
        ast.parse((HERE / "linkmycom.py").read_text(encoding="utf-8"), feature_version=(3, 9))
        ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))
        self.assertTrue(linkmycom.DOCTOR_PY.isascii())
        compile(linkmycom.DOCTOR_PY, "doctor", "exec")
        self.assertIn('out("lan"', linkmycom.DOCTOR_PY)
        self.assertIn("LMCDOC|lan|", linkmycom.WINDOWS_NOPY_DOCTOR_PS)
        self.assertTrue(linkmycom.WINDOWS_NOPY_DOCTOR_PS.isascii())


# ---------------------------------------------------------------- 0절·C1. 자동 업데이트 1시간 주기와 update --all.

class AutoUpdateIntervalTests(TempHome):
    def set_state(self, **kw):
        linkmycom.save_json(linkmycom.STATE_PATH, kw)

    def ago(self, seconds):
        return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()

    def test_interactive_checks_hourly_noninteractive_daily(self):
        self.set_state(last_update_check=self.ago(2 * 3600))
        with mock.patch.object(linkmycom, "latest_release", side_effect=RuntimeError("offline")):
            t = linkmycom.background_update_check({}, [], apply=True)
            self.assertIsNotNone(t)
            t.join(5)
        self.set_state(last_update_check=self.ago(2 * 3600))
        self.assertIsNone(linkmycom.background_update_check({}, [], apply=False))
        self.set_state(last_update_check=self.ago(30 * 60))
        self.assertIsNone(linkmycom.background_update_check({}, [], apply=True))

    def test_keys_refresh_stays_daily(self):
        self.set_state(last_update_check=self.ago(7200), setup_done=True, last_keys_refresh=self.ago(3600))
        with mock.patch.object(linkmycom, "latest_release", side_effect=RuntimeError("offline")), \
                mock.patch.object(linkmycom, "refresh_keys") as rk:
            linkmycom.background_update_check({}, [], apply=True).join(5)
        rk.assert_not_called()
        self.set_state(last_update_check=self.ago(7200), setup_done=True, last_keys_refresh=self.ago(90000))
        with mock.patch.object(linkmycom, "latest_release", side_effect=RuntimeError("offline")), \
                mock.patch.object(linkmycom, "refresh_keys") as rk:
            linkmycom.background_update_check({}, [], apply=True).join(5)
        rk.assert_called_once()

    def test_seconds_since(self):
        self.assertGreater(linkmycom.seconds_since(""), 1e8)
        self.assertGreater(linkmycom.seconds_since("garbage"), 1e8)
        self.assertAlmostEqual(linkmycom.seconds_since(self.ago(100)), 100, delta=5)


class ComponentTests(unittest.TestCase):
    RELS = [{"tag_name": "native-v0.7.0"}, {"tag_name": "native-v0.6.1"}, {"tag_name": "tower-v0.5.0"},
            {"tag_name": "tower-v0.5.1", "draft": True}, {"tag_name": "v0.6.0"}, {"tag_name": "v0.5.10"},
            {"tag_name": "v0.7.0", "prerelease": True}, {"tag_name": "junk"}]

    def test_latest_components_by_prefix(self):
        self.assertEqual(linkmycom.latest_components(self.RELS), {"cli": "0.6.0", "tower": "0.5.0", "native": "0.7.0"})
        with mock.patch.object(linkmycom, "http_get", return_value=json.dumps(self.RELS).encode()) as hg:
            self.assertEqual(linkmycom.fetch_latest_components({})["native"], "0.7.0")
        self.assertIn("releases?per_page=100", hg.call_args[0][0])  # /releases/latest 를 쓰지 않는다

    def test_update_all_dry_and_apply(self):
        have = {"cli": "0.6.0", "tower": "0.4.4", "native": ""}
        latest = {"cli": "0.6.0", "tower": "0.5.0", "native": "0.7.0"}
        with mock.patch.object(linkmycom, "local_component_versions", return_value=have), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value=latest), \
                mock.patch.object(linkmycom, "run_local_component_update", side_effect=AssertionError("-n")), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_update_all({}, dry=True), 0)
        text = out.getvalue()
        self.assertIn("CLI 0.6.0", text)
        self.assertIn("타워 0.4.4 → 0.5.0", text)
        self.assertIn("화면공유 앱: 설치되지 않음", text)
        with mock.patch.object(linkmycom, "local_component_versions", return_value=have), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value=latest), \
                mock.patch.object(linkmycom, "run_local_component_update", return_value=(True, "done")) as run, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(linkmycom.cmd_update_all({}), 0)
        self.assertEqual([c[0][0] for c in run.call_args_list], ["tower"])
        with mock.patch.object(linkmycom, "local_component_versions", return_value=have), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value=latest), \
                mock.patch.object(linkmycom, "run_local_component_update", return_value=(False, "no")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(linkmycom.cmd_update_all({}), 1)

    def test_update_all_check_only_offline(self):
        with mock.patch.object(linkmycom, "local_component_versions", return_value={"cli": "0.6.0", "tower": "", "native": ""}), \
                mock.patch.object(linkmycom, "fetch_latest_components", side_effect=OSError("offline")), \
                mock.patch.object(linkmycom, "run_local_component_update", side_effect=AssertionError("check")), \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            self.assertEqual(linkmycom.cmd_update_all({}, check_only=True), 0)
        self.assertIn("확인 필요", out.getvalue())

    @unittest.skipUnless(os.name == "nt", "Windows 예약 작업 경로")
    def test_native_task_refused_hint(self):
        refused = subprocess.CompletedProcess([], 1, "", "ERROR: Access is denied.")
        with mock.patch.object(linkmycom.subprocess, "run", return_value=refused), \
                mock.patch.object(linkmycom, "native_task_exists", return_value=True):
            ok, msg = linkmycom.run_local_component_update("native", {})
        self.assertFalse(ok)
        self.assertIn("schtasks /run /tn LinkMyCom-NativeUpdate", msg)
        with mock.patch.object(linkmycom.subprocess, "run", return_value=refused), \
                mock.patch.object(linkmycom, "native_task_exists", return_value=False):
            self.assertIn("설치기를 다시", linkmycom.run_local_component_update("native", {})[1])
        started = subprocess.CompletedProcess([], 0, "SUCCESS", "")
        with mock.patch.object(linkmycom.subprocess, "run", return_value=started) as run:
            self.assertTrue(linkmycom.run_local_component_update("native", {})[0])
        self.assertEqual(run.call_args[0][0], ["schtasks", "/Run", "/TN", "LinkMyCom-NativeUpdate"])

    def test_local_versions_and_state_files(self):
        with tempfile.TemporaryDirectory() as d:
            tower = Path(d, "DeskTools", "tower")
            tower.mkdir(parents=True)
            (tower / "release.json").write_text('\ufeff{"version": "0.5.0"}', encoding="utf-8")
            Path(d, "LinkMyCom").mkdir()
            Path(d, "LinkMyCom", "LINKMYCOM_VERSION").write_text("0.7.0\n", encoding="utf-8")
            st = Path(d, "state.json")
            st.write_text(json.dumps({"lastResult": "installing", "checked": "2026-11-21T03:00:00Z", "available": "0.7.1"}),
                          encoding="utf-8")
            if os.name == "nt":
                with mock.patch.dict(os.environ, {"LOCALAPPDATA": d, "ProgramFiles": d}):
                    self.assertEqual(linkmycom.local_component_versions(),
                                     {"cli": linkmycom.__version__, "tower": "0.5.0", "native": "0.7.0"})
            self.assertEqual(linkmycom.read_update_state(str(st)),
                             {"result": "installing", "checked": "2026-11-21 03:00", "available": "0.7.1"})
            self.assertEqual(linkmycom.read_update_state(str(Path(d, "none.json")))["result"], "")


# ---------------------------------------------------------------- C2. open, C3. cp.

class OpenCopyTests(unittest.TestCase):
    def test_share_open_cmd(self):
        self.assertEqual(linkmycom.share_open_cmd(PFL, "home/docs", "Windows"), ["explorer.exe", r"\\100.1.1.1\home\docs"])
        self.assertEqual(linkmycom.share_open_cmd(PFL, "", "Windows"), ["explorer.exe", r"\\100.1.1.1"])
        self.assertEqual(linkmycom.share_open_cmd(MAC, "/공유 폴더/a", "Darwin"),
                         ["open", "smb://100.1.1.2/%EA%B3%B5%EC%9C%A0%20%ED%8F%B4%EB%8D%94/a"])
        self.assertEqual(linkmycom.share_open_cmd(MAC, "x", "Linux")[0], "xdg-open")

    def test_open_dry_run(self):
        with mock.patch.object(linkmycom, "pick_cached", return_value=(PFL, PEERS)), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom.subprocess, "Popen", side_effect=AssertionError("-n")), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_open({}, ["pfl", "home", "-n"]), 0)
        self.assertIn("100.1.1.1", out.getvalue())

    def test_split_remote_spec(self):
        self.assertEqual(linkmycom.split_remote_spec("pfl:/tmp/a"), (None, "pfl", "/tmp/a"))
        self.assertEqual(linkmycom.split_remote_spec("root@pfl:"), ("root", "pfl", ""))
        self.assertIsNone(linkmycom.split_remote_spec(r"C:\Users\x\a.txt"))
        self.assertIsNone(linkmycom.split_remote_spec("C:/x"))
        self.assertIsNone(linkmycom.split_remote_spec("plain.txt"))

    def run_cp(self, args, target):
        cfg = {"hosts": {"pfl": {"user": "win", "port": "2222"}, "mac": {"user": "jemac"}}}
        with mock.patch.object(linkmycom, "pick_cached", return_value=(target, PEERS)), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "ssh_bin", return_value=os.path.join("X", "ssh")), \
                mock.patch.object(linkmycom.subprocess, "call", side_effect=AssertionError("-n")), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_cp(cfg, args), 0)
        return out.getvalue()

    def test_cp_upload_windows_uses_legacy_protocol(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            local = f.name
        try:
            text = self.run_cp(["-n", "-r", local, "pfl:Desktop/"], PFL)
        finally:
            os.remove(local)
        self.assertIn("-O", text.split())
        self.assertIn("-r", text.split())
        self.assertIn("-P 2222", text)
        self.assertTrue(text.strip().endswith("win@100.1.1.1:Desktop/"))

    def test_cp_download_mac_without_O(self):
        text = self.run_cp(["mac:/tmp/a.txt", "mac:b.txt", ".", "-n"], MAC)
        self.assertNotIn(" -O ", text)
        self.assertIn("jemac@100.1.1.2:/tmp/a.txt", text)
        self.assertIn("jemac@100.1.1.2:b.txt", text)

    def test_cp_needs_exactly_one_remote_side(self):
        for args in (["a.txt", "b.txt"], ["pfl:a", "mac:b"], ["pfl:a"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                linkmycom.cmd_cp({"hosts": {}}, args)


# ---------------------------------------------------------------- C4. wake.

class WakeTests(TempHome):
    def test_packet_and_lan(self):
        p = linkmycom.magic_packet("AA-bb-cc-dd-ee-ff")
        self.assertEqual(len(p), 102)
        self.assertEqual(p[:6], b"\xff" * 6)
        self.assertEqual(p[6:12], bytes.fromhex("aabbccddeeff"))
        with self.assertRaises(ValueError):
            linkmycom.magic_packet("aa:bb")
        a = {"ip": "192.168.0.10", "prefix": 24}
        self.assertEqual(linkmycom.lan_broadcast(a), "192.168.0.255")
        self.assertTrue(linkmycom.same_lan(a, {"ip": "192.168.0.99", "prefix": 24}))
        self.assertFalse(linkmycom.same_lan(a, {"ip": "192.168.1.99", "prefix": 24}))

    def test_remember_lans_from_doctor_rows(self):
        local = [("tailscale", "OK", "jekimlabtop 100.9.9.9"), ("lan", "INFO", "mac=aa:bb:cc:dd:ee:01 ip=10.0.0.5/24")]
        remote = [("lan", "INFO", "mac=aa:bb:cc:dd:ee:02 ip=192.168.0.20/24")]
        # Tailscale SSH 세션의 Mac 은 ifconfig 가 02:00:00:00:00:00 으로 가린다(miniui-macmini 실측). 기억하지 않는다.
        masked = [("lan", "INFO", "mac=02:00:00:00:00:00 ip=192.168.0.99/24")]
        linkmycom.remember_lans([(None, local), ("pfl", remote), ("mac", [("cli", "INFO", "x")]), ("miniui", masked)])
        self.assertIn("networksetup", linkmycom.DOCTOR_PY)
        data = linkmycom.load_json(linkmycom.macs_path())
        self.assertEqual(data["self"]["mac"], "aa:bb:cc:dd:ee:01")
        self.assertEqual(data["hosts"]["jekimlabtop"]["ip"], "10.0.0.5")
        self.assertEqual(data["hosts"]["pfl"]["prefix"], 24)
        self.assertNotIn("mac", data["hosts"])
        self.assertNotIn("miniui", data["hosts"])

    def test_remote_commands(self):
        p = linkmycom.magic_packet("aa:bb:cc:dd:ee:ff")
        ps = ps_of(linkmycom.wake_remote_command("windows", p, "192.168.0.255"))
        self.assertIn(p.hex(), ps)
        self.assertIn("'192.168.0.255', '255.255.255.255'", ps)
        self.assertIn("LMCWAKE|sent|", ps)
        sh = linkmycom.wake_remote_command("macOS", p, "192.168.0.255")
        self.assertTrue(sh.startswith('python3 -c "'))
        code = sh.split('"')[1]
        compile(code, "wake", "exec")
        self.assertNotIn("$", code)

    def prepare(self):
        target = dict(PFL, online=False)
        linkmycom.save_json(linkmycom.macs_path(), {
            "self": {"mac": "aa:bb:cc:dd:ee:01", "ip": "10.0.0.5", "prefix": 24},
            "hosts": {"pfl": {"mac": "aa:bb:cc:dd:ee:02", "ip": "192.168.0.20", "prefix": 24},
                      "mac": {"mac": "aa:bb:cc:dd:ee:03", "ip": "192.168.0.30", "prefix": 24}}})
        return target

    def test_wake_picks_same_lan_peer_and_sends_via_ssh(self):
        target = self.prepare()
        sent = []

        def fake_remote(p, cfg, blocks, remote, stdin_text=None, timeout=None, ssh=None):
            sent.append((p["name"], remote[0]))
            return 0, "LMCWAKE|sent|2\n", ""

        with mock.patch.object(linkmycom, "pick_cached", return_value=(target, [target, MAC, PHONE])), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "send_magic", side_effect=AssertionError("다른 LAN 에서 직접 보내면 안 됨")), \
                mock.patch.object(linkmycom, "run_remote", side_effect=fake_remote), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_wake({"hosts": {}}, ["pfl", "-n"]), 0)
            self.assertIn("← mac", out.getvalue())
            self.assertEqual(sent, [])
            self.assertEqual(linkmycom.cmd_wake({"hosts": {}}, ["pfl"]), 0)
        self.assertEqual(sent[0][0], "mac")
        self.assertIn("python3 -c", sent[0][1])

    def test_wake_local_when_same_lan_and_missing_record(self):
        target = self.prepare()
        data = linkmycom.load_json(linkmycom.macs_path())
        data["self"] = {"mac": "aa:bb:cc:dd:ee:01", "ip": "192.168.0.5", "prefix": 24}
        linkmycom.save_json(linkmycom.macs_path(), data)
        with mock.patch.object(linkmycom, "pick_cached", return_value=(target, [target, MAC])), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "send_magic", return_value=2) as sm, \
                mock.patch.object(linkmycom, "run_remote", side_effect=AssertionError("같은 LAN 이면 SSH 불필요")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(linkmycom.cmd_wake({"hosts": {}}, ["pfl"]), 0)
        self.assertEqual(sm.call_args[0][1], "192.168.0.255")
        with mock.patch.object(linkmycom, "pick_cached", return_value=(OFF, [OFF])), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            linkmycom.cmd_wake({"hosts": {}}, ["box"])
        self.assertIn("doctor", err.getvalue())


# ---------------------------------------------------------------- C5. profiles.

class ProfileTests(TempHome):
    def test_fragments_and_dynamic_profiles(self):
        wt = linkmycom.wt_fragment([PFL, MAC, PHONE], ["cmd.exe", "/c", "lmc"])
        names = [p["name"] for p in wt["profiles"]]
        self.assertEqual(names, ["LinkMyCom · mac", "LinkMyCom · pfl"])  # 모바일 제외, 이름순
        self.assertEqual(wt["profiles"][1]["commandline"], "cmd.exe /c lmc pfl")
        self.assertRegex(wt["profiles"][0]["guid"], r"^\{[0-9a-f-]{36}\}$")
        self.assertEqual(wt["linkmycomManaged"], linkmycom.PROFILE_MARK)
        it = linkmycom.iterm_profiles([MAC], ["/usr/local/bin/lmc"])
        self.assertEqual(it["Profiles"][0]["Command"], "/usr/local/bin/lmc mac")
        self.assertEqual(it["Profiles"][0]["Guid"], linkmycom.profile_guid("mac"))  # 다시 만들어도 같은 GUID

    def test_only_managed_files_are_rewritten(self):
        path = self.root / "frag" / "linkmycom.json"
        linkmycom.write_managed_profile(path, {"linkmycomManaged": linkmycom.PROFILE_MARK, "profiles": []})
        linkmycom.write_managed_profile(path, {"linkmycomManaged": linkmycom.PROFILE_MARK, "profiles": [1]})
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["profiles"], [1])
        path.write_text('{"profiles": ["mine"]}', encoding="utf-8")
        with self.assertRaises(RuntimeError):
            linkmycom.write_managed_profile(path, {"linkmycomManaged": linkmycom.PROFILE_MARK, "profiles": []})
        self.assertIn("mine", path.read_text(encoding="utf-8"))

    def test_cmd_profiles_dry_run(self):
        with mock.patch.object(linkmycom, "cached_peers", return_value=([PFL, MAC], True)), \
                mock.patch.object(linkmycom, "profile_path", return_value=self.root / "x.json"), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_profiles({}, ["iterm", "-n"]), 0)
        self.assertIn("프로필 2개", out.getvalue())
        self.assertFalse((self.root / "x.json").exists())
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            linkmycom.cmd_profiles({}, ["konsole"])


# ---------------------------------------------------------------- C6. audit.

ED_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGWKhtP9dXCC5mljTV/5DOf42NzaQ7EUHRAo9B+bX0+s tssh@miniui-Macmini"


class AuditTests(TempHome):
    def test_parse_three_log_styles(self):
        fp = linkmycom.key_fingerprint(ED_KEY)[0]
        text = "\n".join([
            f"2026-11-20T01:02:03Z sshd: Accepted publickey for idonl from 100.1.1.2 port 50000 ssh2: ED25519 {fp}",
            f"2026-11-20 10:00:00.123456+0900 localhost sshd-session[123]: Accepted publickey for jemac from 100.1.1.1 port 1 ssh2: ED25519 {fp}",
            "2026-11-20T10:00:00+0900 pfl sshd[9]: Accepted password for root from 100.1.1.9 port 22 ssh2",
            "2026-11-20T10:00:00Z sshd: banner exchange: Connection from 127.0.0.1",
            "LMCAUDERR|access denied",
        ])
        events, errors = linkmycom.parse_audit(text, "pc")
        self.assertEqual(errors, ["access denied"])
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["time"], datetime(2026, 11, 20, 1, 2, 3, tzinfo=timezone.utc))
        self.assertEqual(events[1]["time"], datetime(2026, 11, 20, 1, 0, 0, tzinfo=timezone.utc))
        self.assertEqual((events[1]["user"], events[1]["from"], events[1]["fp"]), ("jemac", "100.1.1.1", fp))
        self.assertEqual((events[2]["method"], events[2]["fp"]), ("password", ""))

    def test_fingerprint_matches_ssh_keygen(self):
        fp, comment = linkmycom.key_fingerprint(ED_KEY)
        self.assertEqual(comment, "tssh@miniui-Macmini")
        self.assertTrue(fp.startswith("SHA256:") and not fp.endswith("="))
        keygen = linkmycom.find_keygen()
        if not keygen:
            self.skipTest("ssh-keygen 없음")
        f = self.root / "k.pub"
        f.write_text(ED_KEY + "\n", encoding="ascii")
        out = subprocess.run([keygen, "-lf", str(f)], capture_output=True, text=True, timeout=30).stdout
        self.assertIn(fp, out)
        self.assertEqual(linkmycom.key_fingerprint("not a key"), ("", ""))

    def test_commands(self):
        ps = ps_of(linkmycom.audit_remote_command("windows", 3600))
        self.assertIn("OpenSSH/Operational", ps)
        self.assertIn("AddSeconds(-3600)", ps)
        self.assertIn("NoMatchingEventsFound", ps)
        sh = linkmycom.audit_remote_command("macOS", 7 * 86400)
        self.assertIn("--last 10080m", sh)
        self.assertIn("--since=-604800s", sh)

    def test_cmd_audit_resolves_keys_and_names(self):
        (self.root / ".ssh").mkdir()
        (self.root / ".ssh" / "authorized_keys").write_text(ED_KEY + "\n", encoding="utf-8")
        fp = linkmycom.key_fingerprint(ED_KEY)[0]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{now} sshd: Accepted publickey for idonl from 100.1.1.2 port 5 ssh2: ED25519 {fp}\n"
        old = f"2020-01-01T00:00:00Z sshd: Accepted publickey for idonl from 100.1.1.2 port 5 ssh2: ED25519 {fp}\n"
        with mock.patch.object(linkmycom, "cached_peers", return_value=(PEERS, True)), \
                mock.patch.object(linkmycom, "resolve_targets", return_value=[PFL]), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), \
                mock.patch.object(linkmycom, "skip_without_ssh", return_value=None), \
                mock.patch.object(linkmycom, "fetch_remote_keys", side_effect=RuntimeError("offline")), \
                mock.patch.object(linkmycom, "tailscale_status", return_value={"Self": {"TailscaleIPs": ["100.9.9.9"]}}), \
                mock.patch.object(linkmycom, "run_remote", return_value=(0, line + old, "")), \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            self.assertEqual(linkmycom.cmd_audit({}, ["pfl", "--json"]), 0)
        data = json.loads(out.getvalue())
        self.assertEqual(len(data["events"]), 1)  # 7일보다 오래된 줄은 뺀다
        ev = data["events"][0]
        self.assertEqual((ev["pc"], ev["key"], ev["from_name"]), ("pfl", "tssh@miniui-Macmini", "mac"))


# ---------------------------------------------------------------- C7. fleet 최신 판정·원격 업데이터.

class FleetComponentTests(unittest.TestCase):
    LATEST = {"cli": "0.6.0", "tower": "0.5.0", "native": "0.7.0"}

    def rows(self):
        v = linkmycom.__version__
        return [
            {"name": "me", "ip": "(이 PC)", "os": "windows", "peer": None, "error": "",
             "rows": [("cli", "INFO", f"tower {v}"), ("tower", "INFO", "0.5.0"), ("native", "INFO", "0.6.1")]},
            {"name": "pfl", "ip": "100.1.1.1", "os": "windows", "peer": PFL, "error": "",
             "rows": [("cli", "INFO", f"tower {v}"), ("tower", "INFO", "0.4.4"), ("native", "INFO", "0.7.0")]},
            {"name": "mac", "ip": "100.1.1.2", "os": "macOS", "peer": MAC, "error": "",
             "rows": [("cli", "INFO", f"bin {v}"), ("native", "INFO", "0.6.0")]},
            {"name": "box", "ip": "100.1.1.4", "os": "windows", "peer": OFF, "error": "", "rows": [], "skipped": "SSH 포트 닫힘"},
        ]

    def test_versions_and_cells(self):
        r = self.rows()[1]["rows"] + [("path_lmc", "OK", r"lmc -> ~\AppData\Local\linkmycom\linkmycom.py (0.5.2)")]
        self.assertEqual(linkmycom.row_versions(r), {"cli": "0.5.2", "tower": "0.4.4", "native": "0.7.0"})
        self.assertEqual(linkmycom.row_versions([("native", "INFO", "not installed")])["native"], "")
        self.assertEqual(linkmycom.outdated_components(linkmycom.row_versions(r), self.LATEST), ["cli", "tower"])
        self.assertEqual(linkmycom.version_cell("0.4.4", "0.5.0"), "0.4.4 → 0.5.0")
        self.assertEqual(linkmycom.version_cell("0.5.0", "0.5.0"), "0.5.0 최신")
        self.assertEqual(linkmycom.version_cell("0.5.0", ""), "0.5.0")

    def test_status_shows_latest_and_json_keeps_list(self):
        with mock.patch.object(linkmycom, "fleet_rows", return_value=self.rows()), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value=self.LATEST), \
                redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_fleet({}, ["status"])
        text = out.getvalue()
        self.assertIn("0.4.4 → 0.5.0", text)
        self.assertIn("0.7.0 최신", text)
        self.assertIn("거울 최신: CLI 0.6.0, 타워 0.5.0, 화면공유 앱 0.7.0", text)
        with mock.patch.object(linkmycom, "fleet_rows", return_value=self.rows()), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value=self.LATEST), \
                redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_fleet({}, ["status", "--json"])
        data = json.loads(out.getvalue())
        self.assertIsInstance(data, list)  # 타워가 읽는 형식 유지
        self.assertEqual(data[1]["outdated"], ["tower"])
        self.assertEqual(data[2]["outdated"], ["native"])

    def run_update(self, args, remote_out="LMCUPD|started|LinkMyCom-NativeUpdate\n"):
        calls = []

        def fake_remote(p, cfg, blocks, remote, stdin_text=None, timeout=None, ssh=None):
            calls.append((p["name"], remote[0]))
            return 0, remote_out, ""

        with mock.patch.object(linkmycom, "fleet_rows", return_value=self.rows()), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value=self.LATEST), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), \
                mock.patch.object(linkmycom, "record_history"), \
                mock.patch.object(linkmycom, "run_remote", side_effect=fake_remote), \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            rc = linkmycom.cmd_fleet({}, ["update"] + args)
        return rc, out.getvalue(), calls

    def test_native_plan_without_apply(self):
        rc, text, calls = self.run_update(["native"])
        self.assertEqual((rc, calls), (0, []))
        self.assertIn("mac: 화면공유 앱 0.6.0 → 0.7.0", text)
        self.assertNotIn("pfl:", text)  # 이미 최신
        self.assertIn("이 PC 의 화면공유 앱 0.6.1 도 낡았습니다", text)
        self.assertIn("--apply", text)

    def test_apply_runs_updater_and_reports_refusal(self):
        rc, text, calls = self.run_update(["tower", "--apply"])
        self.assertEqual(rc, 0)
        self.assertEqual([c[0] for c in calls], ["pfl"])
        self.assertIn("LinkMyCom-TowerUpdate", ps_of(calls[0][1]))
        rc, text, calls = self.run_update(["native", "--apply"], "LMCUPD|denied|ERROR: Access is denied.\n")
        self.assertEqual(rc, 1)
        self.assertIn("schtasks /run /tn LinkMyCom-NativeUpdate", text)
        self.assertTrue(calls[0][1].startswith('f="$HOME/Library/Application Support/LinkMyCom/Update-Native-Mac.sh"'))

    def test_two_tailscale_nodes_of_one_mac_update_once(self):
        rows = self.rows()[:1] + [
            {"name": n["name"], "ip": n["ip"], "os": "macOS", "peer": n, "error": "", "rows": [("native", "INFO", "0.6.0")]}
            for n in (MACMINI, MINIUI)]
        with mock.patch.object(self, "rows", return_value=rows):
            rc, text, calls = self.run_update(["native", "--apply"])
        self.assertEqual([c[0] for c in calls], ["macmini"])
        self.assertIn("miniui-macmini: macmini 와 같은 장비로 보여 건너뜁니다", text)

    def test_named_target_runs_even_when_current(self):
        with mock.patch.object(linkmycom, "resolve_targets", return_value=[PFL]):
            rc, text, calls = self.run_update(["native", "pfl", "--apply"])
        self.assertEqual([c[0] for c in calls], ["pfl"])

    def test_remote_commands(self):
        ps = ps_of(linkmycom.component_update_command("native", "windows"))
        self.assertIn("$t = 'LinkMyCom-NativeUpdate'", ps)
        self.assertIn("schtasks /Run /TN $t", ps)
        self.assertNotIn("Update-LinkMyCom.ps1", ps)
        tower = ps_of(linkmycom.component_update_command("tower", "windows"))
        self.assertIn(r"DeskTools\tower\Update-LinkMyCom.ps1", tower)
        self.assertIn("-Mirror -Auto", tower)
        self.assertEqual(linkmycom.component_update_result("native", 0, "LMCUPD|missing|x\n", "")[0], False)
        self.assertTrue(linkmycom.component_update_result("tower", 0, "LMCUPD|ran|ok\n", "")[0])


# ---------------------------------------------------------------- C8. doctor 21118·중복 노드.

class DuplicateNodeTests(unittest.TestCase):
    def test_related_nodes_catches_two_tailscales_on_one_mac(self):
        peers = [MINIUI, MACMINI, JEKIM1, HERMES, PFL, MAC, PHONE]
        self.assertEqual([p["name"] for p in linkmycom.related_nodes(MINIUI, peers)], ["macmini"])
        self.assertEqual([p["name"] for p in linkmycom.related_nodes(MACMINI, peers)], ["miniui-macmini"])
        self.assertEqual(linkmycom.related_nodes(JEKIM1, peers), [])
        self.assertEqual(linkmycom.related_nodes(PFL, peers), [])
        self.assertEqual(linkmycom.node_key("미니의 Mac mini"), "macmini")

    def reach(self, target, keys, cfg=None):
        open_ips = {MACMINI["ip"]}
        with mock.patch.object(linkmycom, "port_open", side_effect=lambda ip, port, timeout=1.5: ip in open_ips), \
                mock.patch.object(linkmycom, "host_key_blobs", side_effect=lambda ip: keys.get(ip)):
            return linkmycom.reach_rows(target, [MINIUI, MACMINI, PFL], cfg or {"hosts": {}}, [])

    def test_warns_and_suggests_screen_setting(self):
        same = {MINIUI["ip"]: {"K1"}, MACMINI["ip"]: {"K1"}}
        rows = self.reach(MINIUI, same)
        self.assertEqual(rows[0][:2], ("screen_reach", "WARN"))
        dup = [r for r in rows if r[0] == "dup_node"]
        self.assertEqual(dup[0][1], "WARN")
        self.assertIn("linkmycom set miniui-macmini screen=macmini", dup[0][2])
        self.assertIn("호스트 키가 같은", dup[0][2])
        rows = self.reach(MINIUI, same, {"hosts": {"miniui-macmini": {"screen": "macmini"}}})
        self.assertEqual([r[1] for r in rows if r[0] == "dup_node"], ["INFO"])
        rows = self.reach(MACMINI, same)
        self.assertEqual(rows[0][:2], ("screen_reach", "OK"))
        self.assertEqual([r[1] for r in rows if r[0] == "dup_node"], ["INFO"])

    def test_different_host_keys_mean_different_machines(self):
        rows = self.reach(MINIUI, {MINIUI["ip"]: {"K1"}, MACMINI["ip"]: {"K2"}})
        self.assertEqual([r for r in rows if r[0] == "dup_node"], [])
        rows = self.reach(MINIUI, {})  # ssh-keyscan 없음: 이름·OS 로만 판단
        self.assertIn("이름·OS", [r for r in rows if r[0] == "dup_node"][0][2])

    def test_doctor_host_adds_rows_and_remembers_lan(self):
        out_text = "LMCDOC|sshd|OK|Running\nLMCDOC|lan|INFO|mac=aa:bb:cc:dd:ee:ff ip=192.168.0.9/24\n"
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(linkmycom, "CONFIG_DIR", Path(d)), \
                mock.patch.object(linkmycom, "pick_cached", return_value=(MINIUI, [MINIUI, MACMINI])), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "local_key_blob", return_value=""), \
                mock.patch.object(linkmycom, "run_remote", return_value=(0, out_text, "")), \
                mock.patch.object(linkmycom, "reach_rows", return_value=[("screen_reach", "WARN", "x")]), \
                redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_doctor({"hosts": {}}, ["miniui-macmini", "--json"])
            macs = linkmycom.load_json(Path(d) / "macs.json")
        data = json.loads(out.getvalue())
        self.assertIn(["screen_reach", "WARN", "x"], data["rows"])
        self.assertEqual(macs["hosts"]["miniui-macmini"]["mac"], "aa:bb:cc:dd:ee:ff")


# ---------------------------------------------------------------- C9. 옛 이름 정리.

class CleanupTests(unittest.TestCase):
    def test_paths_and_messages(self):
        for p in linkmycom.FLEET_INSTALL_PATHS["windows"].values():
            self.assertNotIn("\\\\", p)
        self.assertEqual(linkmycom.path_folder(r"C:\Users\x\AppData\Local\DeskTools\\tower\\linkmycom.py"), "tower")
        self.assertEqual(linkmycom.path_folder("/Users/x/.local/bin/linkmycom"), "bin")
        src = (HERE / "linkmycom.py").read_text(encoding="utf-8")
        self.assertNotIn("DeskTools 또는 RustDesk", src)
        self.assertNotIn("def fleet_update_command", src)
        for word in ("keys_signer", "repo_dir", "ssh_options", "keys collect"):
            self.assertIn(word, linkmycom.__doc__)


# ---------------------------------------------------------------- C10. status.

class StatusTests(TempHome):
    def test_status_data_and_json(self):
        now = datetime.now(timezone.utc)
        recv = self.root / "received.json"
        recv.write_text(json.dumps({"schema": 1, "items": [
            {"name": "a", "size": 1, "at": now.isoformat()},
            {"name": "b", "size": 1, "at": (now - timedelta(hours=2)).isoformat()},
            {"name": "c", "size": 1, "at": (now - timedelta(days=3)).isoformat()}]}), encoding="utf-8")
        native_state = self.root / "native.json"
        native_state.write_text(json.dumps({"lastResult": "installing", "available": "0.7.0", "checked": "2026-11-21T01:00:00Z"}),
                                encoding="utf-8")
        linkmycom.save_json(linkmycom.STATE_PATH, {"last_update_check": now.isoformat(), "update_available": "0.6.1"})
        linkmycom.save_json(linkmycom.forwards_path(), {"forwards": [{"pid": os.getpid(), "name": "pfl", "specs": ["8080:127.0.0.1:80"]},
                                                                      {"pid": 0, "name": "dead", "specs": []}]})
        with mock.patch.object(linkmycom, "received_log_path", return_value=recv), \
                mock.patch.object(linkmycom, "update_state_paths", return_value={"native": str(native_state)}), \
                mock.patch.object(linkmycom, "local_component_versions",
                                  return_value={"cli": "0.6.0", "tower": "", "native": "0.6.1"}):
            data = linkmycom.status_data({}, {"native": "0.7.0"}, [PFL, MAC, OFF, PHONE])
            with mock.patch.object(linkmycom, "fetch_latest_components", return_value={"native": "0.7.0"}), \
                    mock.patch.object(linkmycom, "cached_peers", return_value=([PFL, MAC, OFF, PHONE], True)), \
                    redirect_stdout(io.StringIO()) as out:
                self.assertEqual(linkmycom.cmd_status({}, []), 0)
        self.assertEqual(data["received"], {"total": 3, "last24h": 2})
        self.assertEqual(data["devices"], {"online": 2, "total": 3, "relayed": ["mac"]})
        self.assertEqual([f["name"] for f in data["forwards"]], ["pfl"])
        self.assertEqual(data["auto_update"]["native"]["result"], "installing")
        self.assertIn("새 판 0.6.1", data["auto_update"]["cli"])
        text = out.getvalue()
        self.assertIn("0.6.1 → 0.7.0", text)
        self.assertIn("새 버전 0.7.0 설치 중", text)
        self.assertIn("켜짐 2 / 3", text)
        self.assertIn("24시간 안 2개", text)

    def test_status_json_offline(self):
        with mock.patch.object(linkmycom, "fetch_latest_components", side_effect=OSError("offline")), \
                mock.patch.object(linkmycom, "cached_peers", side_effect=SystemExit(1)), \
                mock.patch.object(linkmycom, "received_log_path", return_value=None), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_status({}, ["--json"]), 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["latest"], {})
        self.assertEqual(data["devices"]["online"], 0)
        self.assertEqual(data["versions"]["cli"], linkmycom.__version__)


if __name__ == "__main__":
    unittest.main()
