# linkmycom 0.7.0 의 C1~C10(Mac Tailscale 설치별 점검, Mac 권한 판정, Windows 예약 작업 점검·등록, fleet fix, 일회용 타워 업데이트와 --wait, disk·updater 줄, hide·unhide, forget, 서명 확인 환경 변수, status 요약)을 검사하는 단위 테스트.
from __future__ import annotations

import base64
import io
import json
import os
import re
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

INSTALLER = HERE.parent / "installer" / "Install-LinkMyCom.ps1"


def peer(name, ip, os_name="windows", online=True, hostname=None, last_seen=""):
    return {"name": name, "hostname": hostname or name, "dns": name + ".ts.net", "ip": ip, "os": os_name,
            "online": online, "last_seen": last_seen, "ts_ssh": False, "tags": [], "cur_addr": "", "relay": ""}


PFL = peer("pfl", "100.1.1.1")
MAC = peer("mac", "100.1.1.2", "macOS")


def ps_of(cmd: str) -> str:
    return base64.b64decode(cmd.split()[-1]).decode("utf-16-le")


def doctor_header() -> dict:
    """DOCTOR_PY 의 맨 앞(상수·순수 함수만 있는 부분)을 실행해 그 함수들을 꺼낸다."""
    head = linkmycom.DOCTOR_PY.split("PSP = TASKP = NETP = PSOUT = None")[0]
    ns: dict = {}
    exec(compile(head, "doctor-header", "exec"), ns)
    return ns


class TempHome(unittest.TestCase):
    """CONFIG_DIR·STATE_PATH·CONFIG_PATH·HOSTS_CACHE_PATH·SSH_DIR 를 임시 폴더로 돌린다(이 PC 의 ~/.tssh·~/.ssh 를 건드리지 않음)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cfgdir = self.root / ".tssh"
        self.patches = [
            mock.patch.object(linkmycom, "CONFIG_DIR", self.cfgdir),
            mock.patch.object(linkmycom, "STATE_PATH", self.cfgdir / "state.json"),
            mock.patch.object(linkmycom, "CONFIG_PATH", self.cfgdir / "config.json"),
            mock.patch.object(linkmycom, "HOSTS_CACHE_PATH", self.cfgdir / "hosts.txt"),
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
    def test_version_and_command_tables(self):
        self.assertEqual(linkmycom.__version__, "0.7.2")
        for sub in ("hide", "unhide", "forget"):
            self.assertIn(sub, linkmycom.SUBCOMMANDS)
            self.assertIn(sub, linkmycom.COMMAND_HELP)
            self.assertIn(f"linkmycom {sub}", linkmycom.__doc__)
        for word in ("--permissions", "--no-admin"):
            self.assertIn(word, linkmycom.COMMAND_HELP["doctor"])
        self.assertIn("fleet fix", linkmycom.COMMAND_HELP["fleet"])
        self.assertIn("--wait", linkmycom.COMMAND_HELP["fleet"])
        self.assertIn("fleet fix", linkmycom.__doc__)
        for shell in linkmycom.COMPLETION_SHELLS:
            text = linkmycom.completion_script(shell)
            for word in ("hide", "unhide", "forget", "--permissions", "--wait"):
                self.assertIn(word, text)
        # 도움말은 표준 출력으로 나간다. 그대로 두면 시험 결과의 마지막 줄 뒤에 찍혀 게이트의 판정을 흐린다.
        shown = io.StringIO()
        with redirect_stdout(shown):
            self.assertEqual(linkmycom.cmd_help(["forget"]), 0)
        self.assertIn("linkmycom forget", shown.getvalue())

    def test_doctor_script_stays_ascii_and_compiles(self):
        self.assertTrue(linkmycom.DOCTOR_PY.isascii())
        compile(linkmycom.DOCTOR_PY, "doctor", "exec")
        self.assertTrue(linkmycom.doctor_oneliner().isascii())


# ---------------------------------------------------------------- C1. Mac Tailscale 설치별 행.

APP_ST = {"BackendState": "Running", "Version": "1.82.0-t4a1b2c3d4", "Self": {
    "DNSName": "macmini.tail1234.ts.net.", "HostName": "미니의 Mac mini", "TailscaleIPs": ["100.110.204.16", "fd7a:115c::1"]}}
BREW_ST = {"BackendState": "Running", "Version": "1.80.2", "Self": {
    "DNSName": "miniui-macmini.tail1234.ts.net.", "TailscaleIPs": ["100.82.231.21"]}}


class MacTailscaleTests(unittest.TestCase):
    def test_both_logged_in_warns(self):
        ns = doctor_header()
        rows = ns["ts_install_rows"](APP_ST, BREW_ST)
        self.assertEqual([r[0] for r in rows], ["ts_app", "ts_brew", "ts_dup"])
        self.assertEqual(rows[0], ("ts_app", "OK", "Tailscale.app: macmini 100.110.204.16 1.82.0 (Running)"))
        self.assertEqual(rows[1], ("ts_brew", "OK", "Homebrew tailscaled: miniui-macmini 100.82.231.21 1.80.2 (Running)"))
        self.assertEqual(rows[2][1], "WARN")
        self.assertIn("macmini 100.110.204.16 / miniui-macmini 100.82.231.21", rows[2][2])
        self.assertIn("brew services stop tailscale", rows[2][2])

    def test_single_install_or_logged_out_does_not_warn(self):
        ns = doctor_header()
        rows = ns["ts_install_rows"](APP_ST, None)
        self.assertEqual([r[0] for r in rows], ["ts_app", "ts_brew"])
        self.assertEqual(rows[1][1], "INFO")
        self.assertIn("no daemon", rows[1][2])
        out = dict(BREW_ST, BackendState="NeedsLogin")
        rows = ns["ts_install_rows"](APP_ST, out)
        self.assertNotIn("ts_dup", [r[0] for r in rows])
        self.assertEqual(rows[1][1], "INFO")
        self.assertIn("(NeedsLogin)", rows[1][2])

    def test_labels_and_script_use_the_socket_flag(self):
        for key in ("ts_app", "ts_brew", "ts_dup", "permissions", "perm_screen", "perm_access", "perm_input"):
            self.assertIn(key, linkmycom.DOCTOR_LABELS)
        self.assertIn('"--socket=" + MAC_TS_SOCKET', linkmycom.DOCTOR_PY)
        self.assertIn('MAC_TS_SOCKET = "/var/run/tailscaled.socket"', linkmycom.DOCTOR_PY)
        self.assertIn("/Applications/Tailscale.app/Contents/MacOS/Tailscale", linkmycom.DOCTOR_PY)


# ---------------------------------------------------------------- C2. Mac 권한 판정.

# 2026-11-26 실측의 결과(ListenEvent 0, PostEvent 0, ScreenCapture 1)를 tccd 줄 모양(msgID·service·authValue 필드)으로 고정한 예시.
TCC_LINES = """\
2026-11-26 10:14:01.100 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_ATTRIBUTION: msgID=412.7, attribution={requesting={TCCDProcess: identifier=com.linkmycom.app, pid=5120, binary_path=/Applications/LinkMyCom.app/Contents/MacOS/LinkMyCom}}
2026-11-26 10:14:01.101 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_CTX: msgID=412.7, service=kTCCServiceListenEvent, preflight=yes, query=0
2026-11-26 10:14:01.102 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_RESULT: msgID=412.7, authValue=0, authReason=5, authVersion=1, error=(null)
2026-11-26 10:14:01.200 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_ATTRIBUTION: msgID=412.8, attribution={requesting={TCCDProcess: identifier=com.linkmycom.app, pid=5120}}
2026-11-26 10:14:01.201 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_CTX: msgID=412.8, service=kTCCServicePostEvent, preflight=yes, query=0
2026-11-26 10:14:01.202 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_RESULT: msgID=412.8, authValue=0, authReason=5, authVersion=1, error=(null)
2026-11-26 10:14:02.300 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_ATTRIBUTION: msgID=412.9, attribution={requesting={TCCDProcess: identifier=com.linkmycom.app, pid=5120}}
2026-11-26 10:14:02.301 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_CTX: msgID=412.9, service=kTCCServiceScreenCapture, preflight=no, query=1
2026-11-26 10:14:02.302 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_RESULT: msgID=412.9, authValue=1, authReason=0, authVersion=1, error=(null)
"""


def tcc(msg_id, service, auth):
    return (f"2026-11-26 10:15:00.000 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_CTX: msgID={msg_id}, service={service}, preflight=yes\n"
            f"2026-11-26 10:15:00.001 Df tccd[412:9f3] [com.apple.TCC:access] AUTHREQ_RESULT: msgID={msg_id}, authValue={auth}, authReason=5\n")


class PermissionTests(unittest.TestCase):
    def test_measured_example_means_none_granted(self):
        parsed = linkmycom.parse_tcc_log(TCC_LINES)
        self.assertEqual(parsed, {"perm_input": 0, "perm_access": 0, "perm_screen": 1})
        rows = linkmycom.permission_rows(parsed)
        self.assertEqual([(r[0], r[1]) for r in rows], [("perm_screen", "WARN"), ("perm_access", "WARN"), ("perm_input", "WARN")])
        self.assertIn("미결정(authValue=1)", rows[0][2])
        self.assertIn("화면 기록", rows[0][2])
        self.assertIn("거부됨(authValue=0)", rows[1][2])
        self.assertIn("입력 모니터링", rows[2][2])

    def test_granted_denied_limited_and_worst_of_merged_services(self):
        text = tcc("1.1", "kTCCServiceScreenCapture", 2) + tcc("1.2", "kTCCServiceAccessibility", 2) + \
            tcc("1.3", "kTCCServicePostEvent", 3) + tcc("1.4", "kTCCServiceListenEvent", 2)
        self.assertEqual(linkmycom.parse_tcc_log(text), {"perm_screen": 2, "perm_access": 3, "perm_input": 2})
        rows = {r[0]: r for r in linkmycom.permission_rows(linkmycom.parse_tcc_log(text))}
        self.assertEqual(rows["perm_screen"][1], "OK")
        self.assertEqual(rows["perm_access"][1], "WARN")  # 허용 + 제한 → 제한
        self.assertIn("제한됨", rows["perm_access"][2])
        allowed = linkmycom.parse_tcc_log(tcc("2.1", "kTCCServiceScreenCapture", 2) + tcc("2.2", "kTCCServiceAccessibility", 2)
                                          + tcc("2.3", "kTCCServicePostEvent", 2) + tcc("2.4", "kTCCServiceListenEvent", 2))
        self.assertEqual({r[1] for r in linkmycom.permission_rows(allowed)}, {"OK"})

    def test_asked_twice_last_answer_wins(self):
        text = tcc("3.1", "kTCCServiceScreenCapture", 0) + tcc("3.2", "kTCCServiceScreenCapture", 2)
        self.assertEqual(linkmycom.parse_tcc_log(text), {"perm_screen": 2})

    def test_nothing_captured_is_undecidable(self):
        self.assertEqual(linkmycom.parse_tcc_log(""), {})
        rows = linkmycom.permission_rows({})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:2], ("permissions", "WARN"))
        self.assertIn("판정 못 함", rows[0][2])
        partial = linkmycom.permission_rows({"perm_screen": 2})
        self.assertEqual(dict((r[0], r[1]) for r in partial), {"perm_screen": "OK", "perm_access": "INFO", "perm_input": "INFO"})
        self.assertIn("판정 못 함", partial[1][2])

    def test_script_output_markers(self):
        self.assertIn("설치돼 있지 않", linkmycom.permission_rows_from_output("LMCTCC|NOAPP\n")[0][2])
        nosudo = linkmycom.permission_rows_from_output("LMCTCC|NOSUDO\n")
        self.assertEqual(nosudo[0][:2], ("permissions", "WARN"))
        self.assertIn("실행하지 않았습니다", nosudo[0][2])
        self.assertEqual(linkmycom.permission_rows_from_output("oops\n")[0][1], "FAIL")
        ok = linkmycom.permission_rows_from_output("LMCTCC|BEGIN\n" + TCC_LINES + "LMCTCC|END\n")
        self.assertEqual(len(ok), 3)

    def test_script_only_stops_what_it_started_and_never_runs_without_sudo(self):
        s = linkmycom.MAC_PERM_SCRIPT
        self.assertTrue(s.isascii())
        self.assertLess(s.index("sudo -n true"), s.index("log stream"))  # sudo 가 안 되면 아무것도 띄우기 전에 끝낸다
        self.assertIn("LMCTCC|NOSUDO", s)
        self.assertIn("--style compact", s)
        self.assertIn('subsystem == "com.apple.TCC"', s)
        self.assertIn("open -g -a", s)
        self.assertIn("kill $STREAM", s)
        self.assertNotIn("pkill -f", s)  # 패턴으로 남의 프로세스를 죽이지 않는다
        self.assertNotIn("--server", s)  # 화면공유 서비스 프로세스는 건드리지 않는다
        if os.name != "nt" and shutil.which("bash"):
            r = subprocess.run(["bash", "-n"], input=s, text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_local_check_refuses_off_mac_and_remote_uses_quoted_bash(self):
        with mock.patch.object(linkmycom.platform, "system", return_value="Windows"), redirect_stderr(io.StringIO()):
            self.assertEqual(linkmycom.cmd_doctor_permissions({}, None), 1)
        calls = []

        def fake_remote(p, cfg, blocks, remote, stdin_text=None, timeout=120, ssh=None):
            calls.append(remote)
            return 0, "LMCTCC|BEGIN\n" + TCC_LINES + "LMCTCC|END\n", ""

        with mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "pick_cached", return_value=(MAC, [MAC])), \
                mock.patch.object(linkmycom, "run_remote", side_effect=fake_remote), \
                redirect_stdout(io.StringIO()) as out:
            rc = linkmycom.cmd_doctor_permissions({}, "mac", as_json=True)
        self.assertEqual(rc, 0)
        data = json.loads(out.getvalue())
        self.assertEqual([r[0] for r in data["rows"]], ["perm_screen", "perm_access", "perm_input"])
        self.assertTrue(calls[0][0].startswith("bash -c '"))
        with redirect_stderr(io.StringIO()), mock.patch.object(linkmycom, "pick_cached", return_value=(PFL, [PFL])), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]):
            self.assertEqual(linkmycom.cmd_doctor_permissions({}, "pfl"), 1)

    def test_doctor_dispatches_permissions_flag(self):
        with mock.patch.object(linkmycom, "cmd_doctor_permissions", return_value=0) as m:
            linkmycom.cmd_doctor({}, ["--permissions"])
            linkmycom.cmd_doctor({}, ["macmini", "--permissions", "--json"])
        self.assertEqual(m.call_args_list[0].args, ({}, None, False))
        self.assertEqual(m.call_args_list[1].args, ({}, "macmini", True))


# ---------------------------------------------------------------- C3. Windows 예약 작업.

class ScheduledTaskTests(unittest.TestCase):
    TOWER_DIR = r"C:\Users\x\AppData\Local\DeskTools\tower"

    @unittest.skipUnless(INSTALLER.is_file(), "설치기를 찾지 못함")
    def test_definitions_match_installer(self):
        inst = INSTALLER.read_text(encoding="utf-8")
        self.assertIn(linkmycom.TOWER_TASK_ARG_HEAD, inst)
        self.assertIn("'\" -NoBrowser'", inst)
        self.assertIn("'\" -Mirror -Auto'", inst)
        for kind, tail in (("tower", "-NoBrowser"), ("update", "-Mirror -Auto")):
            arg = linkmycom.tower_task_argument(kind, self.TOWER_DIR)
            spec = linkmycom.TOWER_TASK_SPECS[kind]
            self.assertEqual(arg, linkmycom.TOWER_TASK_ARG_HEAD + self.TOWER_DIR + "\\" + spec["script"] + '" ' + tail)
            self.assertIn("'" + spec["script"] + "'", inst)
            self.assertIn(f"'{spec['name']}'", inst)
        shared = [
            "-LogonType Interactive -RunLevel Limited",
            "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew",
            "(Join-Path $env:SystemRoot 'System32\\WindowsPowerShell\\v1.0\\powershell.exe')",
            "New-ScheduledTaskTrigger -AtLogOn -User $UserId",
            "-ExecutionTimeLimit ([TimeSpan]::Zero)",
            "-StartWhenAvailable",
            "-ExecutionTimeLimit ([TimeSpan]::FromMinutes(30))",
            "$deskLogon.Delay = 'PT15M'",
            "New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(9).AddMinutes(30))",
        ]
        mine = linkmycom.tower_task_ps("tower", self.TOWER_DIR) + linkmycom.tower_task_ps("update", self.TOWER_DIR)
        for piece in shared:
            self.assertIn(piece, inst, piece)
            self.assertIn(piece, mine, piece)

    def test_registration_script_shape(self):
        ps = linkmycom.tower_task_ps("tower", self.TOWER_DIR)
        self.assertIn("Register-ScheduledTask -TaskName 'LinkMyCom-Tower'", ps)
        self.assertIn("-RunLevel Limited", ps)
        self.assertNotIn("Highest", ps)  # 관리자 권한을 쓰지 않는다
        self.assertIn("LMC_TASK_OK", ps)
        up = linkmycom.tower_task_ps("update", self.TOWER_DIR)
        self.assertIn("Register-ScheduledTask -TaskName 'LinkMyCom-TowerUpdate'", up)
        self.assertIn("@($deskLogon, $deskDaily)", up)

    def test_plan_fixes_registers_only_missing_tower_tasks_on_windows(self):
        rows = [("task_tower", "WARN", "x"), ("task_tower_update", "WARN", "y"), ("task_native_update", "WARN", "z")]
        keys = [k for k, _ in linkmycom.plan_fixes(rows, "Windows")]
        self.assertEqual(keys, ["task_tower", "task_tower_update"])  # NativeUpdate(SYSTEM)는 고치지 않는다
        self.assertEqual(linkmycom.plan_fixes(rows, "Darwin"), [])
        ok = [("task_tower", "OK", "x"), ("task_tower_update", "INFO", "y")]
        self.assertEqual(linkmycom.plan_fixes(ok, "Windows"), [])
        self.assertIn("관리자 권한", linkmycom.fix_advice(rows)[0])
        self.assertEqual(linkmycom.fix_advice(ok), [])

    def test_run_fix_dispatch_and_no_admin(self):
        with mock.patch.object(linkmycom, "register_tower_task", return_value=True) as reg:
            self.assertTrue(linkmycom.run_fix("task_tower", {}))
            self.assertTrue(linkmycom.run_fix("task_tower_update", {}))
        self.assertEqual([c.args[0] for c in reg.call_args_list], ["tower", "update"])
        rows = [("sshd", "FAIL", "x"), ("keys_task", "WARN", "y"), ("path_lmc", "WARN", "z")]
        ran = []
        with mock.patch.object(linkmycom, "run_fix", side_effect=lambda k, cfg: ran.append(k) or True), \
                mock.patch.object(linkmycom, "platform") as plat, redirect_stdout(io.StringIO()):
            plat.system.return_value = "Windows"
            self.assertEqual(linkmycom.cmd_doctor_fix({}, rows=rows, no_admin=True), 0)
        self.assertEqual(ran, ["keys_task"])  # 서버 설정·중복 lmc 정리는 뺀다

    def test_doctor_script_reports_each_task(self):
        s = linkmycom.DOCTOR_PY
        for key in ("task_tower", "task_tower_update", "task_native_update"):
            self.assertIn(f'"{key}"', s)
            self.assertIn(key, linkmycom.DOCTOR_LABELS)
        self.assertIn('TOWER_TASK = "LinkMyCom-Tower"', s)


# ---------------------------------------------------------------- C6. disk·updater 줄.

class DiskUpdaterRowTests(unittest.TestCase):
    def test_helpers(self):
        ns = doctor_header()
        gb = 1024 ** 3
        self.assertEqual(ns["gb_text"](int(12.34 * gb)), "12.3 GB")
        self.assertEqual(ns["disk_row"]([("C:", int(12.34 * gb))]), ("OK", "C: 12.3 GB free"))
        self.assertEqual(ns["disk_row"]([("C:", 12 * gb), ("D:", int(1.5 * gb))]), ("WARN", "C: 12.0 GB free, D: 1.5 GB free (low)"))
        self.assertEqual(ns["disk_row"]([("/", 2 * gb)])[0], "OK")  # 2 GB 는 아직 경고가 아니다
        self.assertEqual(ns["etime_minutes"]("05:10"), 5)
        self.assertEqual(ns["etime_minutes"]("12:34"), 12)
        self.assertEqual(ns["etime_minutes"]("02:03:04"), 123)
        self.assertEqual(ns["etime_minutes"]("1-02:03:04"), 1440 + 123)
        self.assertEqual(ns["updater_row"]([]), ("OK", "idle"))
        self.assertEqual(ns["updater_row"]([("2952", 372), ("10", 3)]), ("WARN", "stuck 372 min (pid 2952)"))
        self.assertEqual(ns["updater_row"]([("7", 30)]), ("OK", "running 30 min (pid 7)"))  # 30분 '넘게' 돌 때만 stuck
        self.assertEqual(ns["updater_row"]([("7", 31)])[0], "WARN")

    def test_updater_query_cannot_match_itself(self):
        ns = doctor_header()
        query = ns["PS_UPDATERS"]
        m = re.search(r"-match '(-File\\s\+\\S\*Update-\(LinkMyCom\|Native\)\\\.ps1)'", query)
        self.assertTrue(m, query)
        pattern = re.compile(m.group(1).replace("\\\\", "\\"))
        self.assertIsNone(pattern.search(query))  # 조회 자신의 명령줄은 걸리지 않는다
        self.assertTrue(pattern.search(r'powershell.exe -NoProfile -File "C:\x\tower\Update-LinkMyCom.ps1" -Mirror -Auto'))
        self.assertTrue(pattern.search(r"powershell -File C:\ProgramData\LinkMyCom\Update-Native.ps1"))

    def test_script_runs_with_one_powershell_launch(self):
        self.assertEqual(linkmycom.DOCTOR_PY.count('"powershell"'), 1)

    def test_fleet_status_surfaces_disk_and_updater(self):
        rows = [("cli", "INFO", "tower 0.7.0"), ("disk", "WARN", "C: 1.0 GB free (low)"), ("updater", "WARN", "stuck 372 min (pid 2952)")]
        results = [{"name": "pfl", "ip": "100.1.1.1", "os": "windows", "peer": PFL, "rows": rows, "error": ""}]
        with mock.patch.object(linkmycom, "fleet_rows", return_value=results), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value={"cli": "0.7.0"}), \
                redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_fleet({}, ["status", "--json"])
            data = json.loads(out.getvalue())
        self.assertIn(["disk", "WARN", "C: 1.0 GB free (low)"], data[0]["rows"])
        self.assertEqual(data[0]["disk"], {"status": "WARN", "detail": "C: 1.0 GB free (low)"})
        self.assertEqual(data[0]["updater"]["detail"], "stuck 372 min (pid 2952)")
        with mock.patch.object(linkmycom, "fleet_rows", return_value=results), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value={"cli": "0.7.0"}), \
                redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_fleet({}, ["status"])
        self.assertIn("디스크: C: 1.0 GB free (low)", out.getvalue())
        self.assertIn("업데이터: stuck 372 min (pid 2952)", out.getvalue())

    def test_doctor_json_carries_disk_and_updater_keys(self):
        rows = [("disk", "OK", "C: 12.3 GB free"), ("updater", "OK", "idle")]
        with redirect_stdout(io.StringIO()) as out:
            linkmycom.print_doctor_json({"name": "x", "ip": "1", "os": "windows", "rows": rows, "error": ""})
        data = json.loads(out.getvalue())
        self.assertEqual(data["disk"]["status"], "OK")
        self.assertEqual(data["updater"]["detail"], "idle")


# ---------------------------------------------------------------- C4. fleet fix.

class FleetFixTests(TempHome):
    def test_command_shapes(self):
        win = ps_of(linkmycom.fleet_fix_command("windows", "tower"))
        self.assertIn("doctor --fix --no-admin 2>&1", win)
        self.assertIn(r"%LOCALAPPDATA%\DeskTools\tower\linkmycom.py", win)
        self.assertIn("LMCFIX|rc|", win)
        self.assertIn("-n 2>&1", ps_of(linkmycom.fleet_fix_command("windows", "linkmycom", dry=True)))
        unix = linkmycom.fleet_fix_command("macOS", "bin", dry=True)
        self.assertIn("doctor --fix --no-admin -n", unix)
        self.assertIn("LMCFIX|rc|$?", unix)

    def test_parse_and_summary(self):
        done = ("linkmycom doctor --fix\n  1. [키 갱신 예약] 일일 유지 작업 다시 예약\n  2. [타워 실행] 타워 시작\n"
                "OK  일일 유지 작업 다시 예약\n실패 타워 시작\n다시 점검: linkmycom doctor\nLMCFIX|rc|1\n")
        info = linkmycom.parse_fix_output(done)
        self.assertEqual(info["done"], ["일일 유지 작업 다시 예약"])
        self.assertEqual(info["failed"], ["타워 시작"])
        self.assertEqual(len(info["plan"]), 2)
        self.assertEqual(info["rc"], 1)
        self.assertEqual(linkmycom.fleet_fix_summary(info, False)[0], "실패")
        nothing = linkmycom.parse_fix_output("고칠 항목이 없습니다(자동으로 고치는 항목 기준).\nLMCFIX|rc|0\n")
        self.assertEqual(linkmycom.fleet_fix_summary(nothing, False), ("OK", "고칠 항목 없음"))
        dry = linkmycom.parse_fix_output("  1. [타워 실행] 타워 시작\nLMCFIX|rc|0\n")
        self.assertEqual(linkmycom.fleet_fix_summary(dry, True), ("OK", "할 일 타워 시작"))
        self.assertEqual(linkmycom.fleet_fix_summary(linkmycom.parse_fix_output("LMCFIX|nocli\n"), False)[0], "건너뜀")
        self.assertEqual(linkmycom.fleet_fix_summary(linkmycom.parse_fix_output("garbage\n"), False)[0], "실패")

    def run_fix_cmd(self, args, outputs):
        results = [
            {"name": "local", "ip": "(이 PC)", "os": "windows", "peer": None, "rows": [], "error": ""},
            {"name": "pfl", "ip": "100.1.1.1", "os": "windows", "peer": PFL, "error": "",
             "rows": [("cli", "INFO", "tower 0.7.0, linkmycom 0.6.0")]},
            {"name": "old", "ip": "100.1.1.5", "os": "windows", "peer": peer("old", "100.1.1.5"), "error": "",
             "rows": [("cli", "INFO", "tower 0.6.0")]},
            {"name": "mac", "ip": "100.1.1.2", "os": "macOS", "peer": MAC, "error": "",
             "rows": [("cli", "INFO", "bin 0.7.0")]},
        ]
        sent = []

        def fake_remote(p, cfg, blocks, remote, stdin_text=None, timeout=120, ssh=None):
            sent.append((p["name"], remote[0]))
            return outputs[p["name"]]

        with mock.patch.object(linkmycom, "fleet_rows", return_value=results), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "resolve_targets", return_value=[PFL]), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), \
                mock.patch.object(linkmycom, "run_remote", side_effect=fake_remote), \
                redirect_stdout(io.StringIO()) as out:
            rc = linkmycom.cmd_fleet({}, ["fix"] + args)
        return rc, out.getvalue(), sent

    def test_fixes_new_enough_pcs_and_skips_old_ones(self):
        rc, text, sent = self.run_fix_cmd([], {
            "pfl": (0, "OK  타워 시작\nLMCFIX|rc|0\n", ""),
            "mac": (0, "고칠 항목이 없습니다(자동으로 고치는 항목 기준).\nLMCFIX|rc|0\n", "")})
        self.assertEqual(rc, 0)
        self.assertEqual([n for n, _ in sent], ["pfl", "mac"])  # 이 PC 와 낡은 PC 는 보내지 않는다
        self.assertIn("고침 타워 시작", text)
        self.assertIn("고칠 항목 없음", text)
        self.assertRegex(text, r"old\s+건너뜀\s+CLI 0\.7\.0 이상이 필요합니다\(현재 0\.6\.0\)")
        self.assertTrue(ps_of(sent[0][1]).count("doctor --fix --no-admin") >= 1)
        self.assertIn(r"%LOCALAPPDATA%\DeskTools\tower\linkmycom.py", ps_of(sent[0][1]))  # 0.7.0 인 설치본을 고른다

    def test_one_target_dry_run_and_failure_exit_code(self):
        rc, text, sent = self.run_fix_cmd(["pfl", "-n"], {"pfl": (0, "  1. [타워 실행] 타워 시작\nLMCFIX|rc|0\n", "")})
        self.assertEqual((rc, [n for n, _ in sent]), (0, ["pfl"]))
        self.assertIn("할 일 타워 시작", text)
        self.assertIn("-n 2>&1", ps_of(sent[0][1]))
        rc, text, _ = self.run_fix_cmd(["pfl"], {"pfl": (255, "", "Connection refused")})
        self.assertEqual(rc, 1)
        self.assertIn("실패", text)


# ---------------------------------------------------------------- C5. fleet update tower.

class TowerUpdateTests(unittest.TestCase):
    def test_missing_task_uses_one_shot_interactive_task_not_the_session(self):
        ps = ps_of(linkmycom.component_update_command("tower", "windows"))
        self.assertIn("schtasks /Run /TN $t", ps)  # 작업이 있으면 지금처럼 그 작업을 시작
        for word in ("Register-ScheduledTask", "Start-ScheduledTask", "Unregister-ScheduledTask", "-LogonType Interactive",
                     "quser", "LMCUPD|nosession|", linkmycom.TOWER_UPDATE_ONCE_TASK, "-Mirror -Auto"):
            self.assertIn(word, ps)
        self.assertLess(ps.index("Start-ScheduledTask"), ps.index("Unregister-ScheduledTask"))  # 시작한 뒤 지운다
        self.assertNotIn("& powershell", ps)  # 세션 안에서 업데이터를 직접 돌리던 가지는 없앴다
        self.assertNotIn("LMCUPD|ran|", ps)
        native = ps_of(linkmycom.component_update_command("native", "windows"))
        self.assertNotIn("Register-ScheduledTask", native)
        self.assertIn("LMCUPD|missing|", native)
        mac = linkmycom.component_update_command("native", "macOS")
        self.assertIn("Update-Native-Mac.sh", mac)

    def test_result_messages(self):
        ok, msg = linkmycom.component_update_result("tower", 0, "LMCUPD|started|LinkMyCom-TowerUpdate-Once\n", "")
        self.assertTrue(ok)
        ok, msg = linkmycom.component_update_result("tower", 0, "LMCUPD|nosession|jekim\n", "")
        self.assertFalse(ok)
        self.assertIn("로그온한 사용자(jekim)가 없어", msg)

    def test_parse_wait(self):
        self.assertEqual(linkmycom.parse_wait(["tower", "--apply"]), (["tower", "--apply"], None))
        self.assertEqual(linkmycom.parse_wait(["tower", "--apply", "--wait"]), (["tower", "--apply"], 120.0))
        self.assertEqual(linkmycom.parse_wait(["--wait", "30", "tower", "pfl"]), (["tower", "pfl"], 30.0))
        self.assertEqual(linkmycom.parse_wait(["tower", "--wait=45"]), (["tower"], 45.0))
        self.assertEqual(linkmycom.parse_wait(["--wait", "tower"]), (["tower"], 120.0))  # 숫자가 아니면 이름으로 둔다

    def test_state_line_and_verdict(self):
        line = 'LMCSTATE|{ "lastResult": "ok", "checked": "2026-11-26T09:30:12Z", "available": "0.6.0" }\n'
        st = linkmycom.parse_state_line("noise\n" + line)
        self.assertEqual(st, {"result": "ok", "checked": "2026-11-26T09:30:12Z", "available": "0.6.0"})
        self.assertEqual(linkmycom.parse_state_line("LMCSTATE|\n"), {"result": "", "checked": "", "available": ""})
        self.assertIsNone(linkmycom.parse_state_line("ssh: connection refused\n"))
        self.assertEqual(linkmycom.parse_state_line("LMCSTATE|{bad\n")["result"], "unreadable")
        # 0.7.1: Windows 상태 파일(BOM 없는 UTF-8, 한글 message)을 UTF-8 로 읽고 판정에 쓰는 필드만 ASCII 로 보낸다.
        for what in ("tower", "native"):
            ps = ps_of(linkmycom.update_state_read_command(what, "windows"))
            self.assertIn("-Encoding UTF8", ps)
            self.assertIn("ConvertTo-Json -Compress", ps)
            self.assertNotIn("message", ps)
        before = {"result": "ok", "checked": "2026-11-25T09:30:00Z", "available": ""}
        self.assertIsNone(linkmycom.update_wait_verdict(before, dict(before)))  # 아직 이번 실행이 기록되지 않음
        self.assertIsNone(linkmycom.update_wait_verdict(before, {"result": "installing", "checked": "2026-11-26T09:30:12Z"}))
        done = linkmycom.update_wait_verdict(before, {"result": "ok", "checked": "2026-11-26T09:30:12Z"})
        self.assertEqual(done, (True, "업데이트 완료 (2026-11-26 09:30)"))
        self.assertEqual(linkmycom.update_wait_verdict(before, {"result": "error", "checked": "2026-11-26T09:30:12Z"})[0], False)
        self.assertEqual(linkmycom.update_wait_verdict({}, {"result": "none", "checked": "x"})[1], "새 판 없음 (x)")
        self.assertIn("미룸", linkmycom.update_wait_verdict(before, {"result": "deferred", "checked": "y"})[1])

    def test_wait_loop_polls_until_done_or_timeout(self):
        before = {"result": "ok", "checked": "old", "available": ""}
        states = iter([None, dict(before), {"result": "installing", "checked": "new"}, {"result": "ok", "checked": "new"}])
        sleeps = []
        clock = {"t": 0.0}

        def fake_sleep(s):
            sleeps.append(s)
            clock["t"] += s

        ok, text = linkmycom.wait_update_result(lambda: next(states), before, 120, interval=5, sleep=fake_sleep,
                                                clock=lambda: clock["t"])
        self.assertTrue(ok)
        self.assertEqual(sleeps, [5, 5, 5])
        clock["t"] = 0.0
        sleeps.clear()
        ok, text = linkmycom.wait_update_result(lambda: dict(before), before, 12, interval=5, sleep=fake_sleep,
                                                clock=lambda: clock["t"])
        self.assertFalse(ok)
        self.assertIn("12초 안에 결과가 기록되지 않았습니다(마지막 상태: ok)", text)
        self.assertLessEqual(sum(sleeps), 12)

    def test_fleet_update_tower_wait_reports_per_pc_result(self):
        results = [{"name": "pfl", "ip": "100.1.1.1", "os": "windows", "peer": PFL, "error": "",
                    "rows": [("tower", "INFO", "0.5.0")]}]
        reads = iter([
            'LMCSTATE|{"lastResult": "ok", "checked": "2026-11-25T09:30:00Z"}\n',   # 시작 전
            'LMCSTATE|{"lastResult": "ok", "checked": "2026-11-26T09:31:00Z"}\n',   # 시작 뒤
        ])
        sent = []

        def fake_remote(p, cfg, blocks, remote, stdin_text=None, timeout=120, ssh=None):
            ps = ps_of(remote[0])
            sent.append("state" if "update-state.json" in ps else "start")
            if "update-state.json" in ps:
                return 0, next(reads), ""
            return 0, "LMCUPD|started|LinkMyCom-TowerUpdate-Once (one-shot task, removed after start)\n", ""

        with tempfile.TemporaryDirectory() as d, mock.patch.object(linkmycom, "CONFIG_DIR", Path(d)), \
                mock.patch.object(linkmycom, "fleet_rows", return_value=results), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value={"tower": "0.6.0"}), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "ssh_bin", return_value="ssh"), \
                mock.patch.object(linkmycom, "run_remote", side_effect=fake_remote), \
                redirect_stdout(io.StringIO()) as out:
            rc = linkmycom.cmd_fleet({}, ["update", "tower", "--apply", "--wait", "30"])
        self.assertEqual(rc, 0)
        self.assertEqual(sent, ["state", "start", "state"])
        self.assertIn("결과: 업데이트 완료 (2026-11-26 09:31)", out.getvalue())

    def test_wait_without_apply_does_nothing_remote(self):
        results = [{"name": "pfl", "ip": "100.1.1.1", "os": "windows", "peer": PFL, "error": "",
                    "rows": [("tower", "INFO", "0.5.0")]}]
        with mock.patch.object(linkmycom, "fleet_rows", return_value=results), \
                mock.patch.object(linkmycom, "fetch_latest_components", return_value={"tower": "0.6.0"}), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "run_remote") as remote, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_fleet({}, ["update", "--wait", "tower"]), 0)
        remote.assert_not_called()
        self.assertIn("--apply", out.getvalue())


# ---------------------------------------------------------------- C7. 숨기기·오래 꺼진 장비.

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def iso(days):
    return (NOW - timedelta(days=days)).isoformat().replace("+00:00", "Z")


def real_iso(days):
    """지금 기준 days 일 전(낡음 판정이 실제 시계를 쓰므로)."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")


class HideTests(TempHome):
    OLD = peer("oldbox", "100.1.1.9", online=False, last_seen=real_iso(40))
    RECENT = peer("recent", "100.1.1.8", online=False, last_seen=real_iso(3))
    NEVER = peer("never", "100.1.1.7", online=False, last_seen="0001-01-01T00:00:00Z")
    HID = peer("hid", "100.1.1.6")

    def test_stale_and_hidden_predicates(self):
        self.assertTrue(linkmycom.is_stale(self.OLD))
        self.assertFalse(linkmycom.is_stale(self.RECENT))
        self.assertFalse(linkmycom.is_stale(self.NEVER))  # 마지막 시각을 모르면 낡았다고 보지 않는다
        self.assertFalse(linkmycom.is_stale(dict(self.OLD, online=True)))
        edge = peer("edge", "100.1.1.5", online=False, last_seen=iso(31))
        self.assertTrue(linkmycom.is_stale(edge, NOW))
        self.assertFalse(linkmycom.is_stale(dict(edge, last_seen=iso(29)), NOW))
        self.assertEqual(linkmycom.hidden_names({"hidden": ["a", 3, "b"]}), ["a", "b"])
        self.assertEqual(linkmycom.hidden_names({"hidden": "x"}), [])
        self.assertTrue(linkmycom.is_hidden(self.HID, {"hidden": ["HID"]}))
        self.assertFalse(linkmycom.is_hidden(PFL, {"hidden": ["HID"]}))

    def test_default_list_tucks_away_hidden_and_old_but_all_shows_them(self):
        cfg = {"hosts": {}, "hidden": ["hid"]}
        peers = [PFL, self.HID, self.RECENT, self.NEVER, self.OLD, MAC]
        names = [p["name"] for p in linkmycom.ordered_peers(peers, cfg, recent=[], show_hidden=False)]
        self.assertEqual(sorted(names), ["mac", "never", "pfl", "recent"])  # 숨김(hid)과 40일 꺼진(oldbox)만 빠진다
        self.assertNotIn("hid", names)
        self.assertNotIn("oldbox", names)
        full = [p["name"] for p in linkmycom.ordered_peers(peers, cfg, recent=[])]
        self.assertIn("hid", full)  # show_hidden 기본값은 True: 기존 호출은 그대로
        self.assertIn("oldbox", full)

    def test_show_list_messages(self):
        stale = self.OLD
        cfg = {"hosts": {}, "hidden": ["hid"]}
        with redirect_stdout(io.StringIO()) as out:
            linkmycom.show_list([PFL, self.HID, stale], cfg, [])
        text = out.getvalue()
        self.assertIn("pfl", text)
        self.assertNotIn("oldbox", text)
        self.assertNotRegex(text, r"\bhid\b\s+windows")
        self.assertIn("2대는 빼고 보임(--all 로 표시", text)
        with redirect_stdout(io.StringIO()) as out:
            linkmycom.show_list([PFL, self.HID, stale], cfg, [], show_all=True)
        self.assertIn("oldbox", out.getvalue())
        self.assertIn("hid", out.getvalue())
        with redirect_stdout(io.StringIO()) as out:
            linkmycom.show_list([PFL, self.HID], cfg, [], as_json=True)
        self.assertEqual([p["name"] for p in json.loads(out.getvalue())], ["pfl", "hid"])  # --json 형식·내용은 그대로

    def test_all_targets_skip_hidden_but_named_targets_do_not(self):
        cfg = {"hosts": {}, "hidden": ["pfl"]}
        self.assertEqual([p["name"] for p in linkmycom.ssh_capable([PFL, MAC], cfg)], ["mac"])
        self.assertEqual([p["name"] for p in linkmycom.ssh_capable([PFL, MAC])], ["pfl", "mac"])
        with mock.patch.object(linkmycom, "cached_peers", return_value=([PFL, MAC], True)):
            self.assertEqual([p["name"] for p in linkmycom.resolve_targets(cfg, [], "all")], ["mac"])
            with mock.patch.object(linkmycom, "pick_cached", return_value=(PFL, [PFL, MAC])):
                self.assertEqual([p["name"] for p in linkmycom.resolve_targets(cfg, [], "pfl")], ["pfl"])

    def test_hide_and_unhide_edit_config_hidden(self):
        cfg = linkmycom.load_config()
        with mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                mock.patch.object(linkmycom, "pick_cached", return_value=(MAC, [PFL, MAC])), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_hide(cfg, ["mac"]), 0)
            self.assertEqual(linkmycom.cmd_hide(cfg, ["mac"]), 0)  # 두 번째는 이미 숨겨짐
        self.assertIn("이미 숨겨져", out.getvalue())
        self.assertEqual(json.loads(linkmycom.CONFIG_PATH.read_text(encoding="utf-8"))["hidden"], ["mac"])
        self.assertEqual(linkmycom.hidden_names(linkmycom.load_config()), ["mac"])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(linkmycom.cmd_unhide(linkmycom.load_config(), ["MA"]), 0)  # 숨긴 목록에서 이름을 찾는다
        self.assertNotIn("hidden", json.loads(linkmycom.CONFIG_PATH.read_text(encoding="utf-8")))
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            linkmycom.cmd_unhide(linkmycom.load_config(), ["mac"])
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            linkmycom.cmd_hide({}, [])


# ---------------------------------------------------------------- C8. forget.

class ForgetTests(TempHome):
    KNOWN = ("100.9.9.9 ssh-ed25519 AAAAold1\n"
             "gone ssh-ed25519 AAAAold1\n"
             "gone.ts.net,100.9.9.9 ssh-ed25519 AAAAold2\n"
             "[100.9.9.9]:2222 ssh-ed25519 AAAAold3\n"
             "other,GONE ssh-rsa AAAAmixed\n"
             "|1|salt|hash ssh-ed25519 AAAAhashed\n"
             "# gone is only a comment\n"
             "100.1.1.1 ssh-ed25519 AAAAkeep\n")

    def setup_state(self):
        (self.root / ".ssh").mkdir(parents=True)
        self.kh = self.root / ".ssh" / "known_hosts"
        self.kh.write_text(self.KNOWN, encoding="utf-8")
        linkmycom.save_json(linkmycom.CONFIG_PATH, {"hosts": {"gone": {"user": "x"}, "pfl": {"user": "y"}}, "hidden": ["gone"]})
        linkmycom.save_json(linkmycom.macs_path(), {"self": {"mac": "aa"}, "hosts": {"gone": {"mac": "bb"}, "pfl": {"mac": "cc"}}})
        self.gone = peer("gone", "100.9.9.9", online=False, last_seen=real_iso(60))
        linkmycom.write_peers_cache([self.gone, PFL], now=1000.0)

    def forget(self, args):
        cfg = linkmycom.load_config()
        with mock.patch.object(linkmycom, "cached_peers", return_value=([PFL, MAC], True)), \
                mock.patch.object(linkmycom, "ssh_config_blocks", return_value=[]), \
                redirect_stdout(io.StringIO()) as out:
            rc = linkmycom.cmd_forget(cfg, args)
        return rc, out.getvalue()

    def test_removes_every_trace_and_backs_up_known_hosts(self):
        self.setup_state()
        rc, text = self.forget(["gone"])
        self.assertEqual(rc, 0)
        self.assertIn("지웠습니다", text)
        self.assertEqual(self.kh.read_text(encoding="utf-8"),
                         "other ssh-rsa AAAAmixed\n|1|salt|hash ssh-ed25519 AAAAhashed\n# gone is only a comment\n100.1.1.1 ssh-ed25519 AAAAkeep\n")
        self.assertEqual((self.root / ".ssh" / "known_hosts.old").read_text(encoding="utf-8"), self.KNOWN)
        cfg = json.loads(linkmycom.CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(list(cfg["hosts"]), ["pfl"])
        self.assertNotIn("hidden", cfg)
        self.assertEqual(list(linkmycom.load_json(linkmycom.macs_path())["hosts"]), ["pfl"])
        self.assertEqual([p["name"] for p in linkmycom.read_peers_cache()[0]], ["pfl"])
        self.assertEqual(linkmycom.read_peers_cache()[1], 1000.0)
        self.assertEqual((self.cfgdir / "hosts.txt").read_text(encoding="utf-8"), "pfl\n")
        rc, text = self.forget(["gone"])
        self.assertIn("로컬 흔적이 없습니다", text)

    def test_dry_run_changes_nothing(self):
        self.setup_state()
        before = {p: p.read_bytes() for p in (self.kh, linkmycom.CONFIG_PATH, linkmycom.macs_path(), linkmycom.peers_cache_path())}
        rc, text = self.forget(["gone", "-n"])
        self.assertEqual(rc, 0)
        self.assertIn("지울 것(-n: 바꾸지 않음)", text)
        self.assertIn("known_hosts 5줄", text)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertFalse((self.root / ".ssh" / "known_hosts.old").exists())

    def test_refuses_online_node(self):
        self.setup_state()
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            self.forget(["pfl"])
        self.assertEqual(self.kh.read_text(encoding="utf-8"), self.KNOWN)
        self.assertIn("pfl", json.loads(linkmycom.CONFIG_PATH.read_text(encoding="utf-8"))["hosts"])

    def test_unknown_node_uses_typed_name_only(self):
        self.setup_state()
        rc, text = self.forget(["other"])  # 피어 목록·캐시에 없는 이름
        self.assertEqual(rc, 0)
        self.assertIn("known_hosts 1줄", text)
        self.assertIn("피어 목록에 없는 이름", text)
        self.assertIn("gone ssh-ed25519 AAAAold1", self.kh.read_text(encoding="utf-8"))

    def test_known_hosts_matching_rules(self):
        self.assertTrue(linkmycom.known_hosts_matches("[100.9.9.9]:2222", ["100.9.9.9"]))
        self.assertTrue(linkmycom.known_hosts_matches("a,GONE", ["gone"]))
        self.assertFalse(linkmycom.known_hosts_matches("gone2", ["gone"]))
        self.assertFalse(linkmycom.known_hosts_matches("|1|salt|hash", ["gone"]))


# ---------------------------------------------------------------- C9. 서명 확인 환경 변수.

FD_STATE = "c28fc6f98a2c44abbbd89d6a3037d0d9_POSIX_FD_STATE"


class FdStateTests(unittest.TestCase):
    def test_env_helper_masks_only_the_fd_state_variable(self):
        with mock.patch.dict(os.environ, {FD_STATE: "x", "OTHER_POSIX_FD_STATE": "1", "KEEP_ME": "yes"}):
            env = linkmycom.env_without_fd_state()
        self.assertNotIn(FD_STATE, env)
        self.assertNotIn("OTHER_POSIX_FD_STATE", env)
        self.assertEqual(env["KEEP_ME"], "yes")

    def test_verify_passes_the_cleaned_env_to_ssh_keygen(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen["env"] = kw.get("env")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        with mock.patch.object(linkmycom, "find_keygen", return_value="ssh-keygen"), \
                mock.patch.dict(os.environ, {FD_STATE: "x"}), \
                mock.patch.object(linkmycom.subprocess, "run", side_effect=fake_run):
            ok, _ = linkmycom.verify_signature(b"data", b"-----BEGIN SSH SIGNATURE-----\nx\n", "ns", "ssh-ed25519 AAAA")
        self.assertTrue(ok)
        self.assertNotIn(FD_STATE, seen["env"])

    @unittest.skipUnless(os.name == "nt" and linkmycom.find_keygen(), "Windows OpenSSH 의 ssh-keygen 이 필요함")
    def test_real_verification_survives_the_variable_on_windows(self):
        keygen = linkmycom.find_keygen()
        with tempfile.TemporaryDirectory() as d:
            key = Path(d) / "k"
            data = Path(d) / "payload"
            data.write_bytes(b"signed payload\n")
            subprocess.run([keygen, "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True, stdin=subprocess.DEVNULL,
                           capture_output=True, env=linkmycom.env_without_fd_state())
            subprocess.run([keygen, "-Y", "sign", "-f", str(key), "-n", "linkmycom-keys", str(data)], check=True,
                           stdin=subprocess.DEVNULL, capture_output=True, env=linkmycom.env_without_fd_state())
            sig = Path(str(data) + ".sig").read_bytes()
            pub = " ".join(key.with_suffix(".pub").read_text(encoding="ascii").split()[:2])
            with mock.patch.dict(os.environ, {FD_STATE: "x"}):
                ok, why = linkmycom.verify_signature(data.read_bytes(), sig, "linkmycom-keys", pub)
                bad, _ = linkmycom.verify_signature(b"tampered\n", sig, "linkmycom-keys", pub)
        self.assertTrue(ok, why)
        self.assertFalse(bad)


# ---------------------------------------------------------------- C10. status.

class StatusSummaryTests(TempHome):
    def test_next_commands(self):
        self.assertEqual(linkmycom.status_next(None, None, []), [])
        nxt = linkmycom.status_next({"status": "WARN", "detail": "C: 1.0 GB free (low)"},
                                    {"status": "WARN", "detail": "stuck 372 min (pid 2952)"},
                                    ["LinkMyCom-Tower", "LinkMyCom-NativeUpdate"])
        text = " | ".join(nxt)
        self.assertIn("linkmycom doctor --fix", text)
        self.assertIn("설치기를 관리자 권한으로", text)
        self.assertIn("Stop-Process -Id 2952", text)
        self.assertIn("디스크 여유", text)
        only_native = linkmycom.status_next(None, None, ["LinkMyCom-NativeUpdate"])
        self.assertNotIn("doctor --fix", " ".join(only_native))

    def rows(self):
        return [("disk", "WARN", "C: 1.0 GB free (low)"), ("updater", "WARN", "stuck 372 min (pid 2952)"),
                ("task_tower", "WARN", "missing"), ("task_tower_update", "OK", "x"), ("task_native_update", "WARN", "missing")]

    def test_status_data_and_text_include_health_lines(self):
        cfg = {"hosts": {}, "hidden": ["a", "b"]}
        with mock.patch.object(linkmycom, "received_log_path", return_value=None), \
                mock.patch.object(linkmycom, "update_state_paths", return_value={}), \
                mock.patch.object(linkmycom, "local_component_versions", return_value={"cli": "0.7.0", "tower": "", "native": ""}):
            data = linkmycom.status_data(cfg, {}, [PFL], self.rows())
            with mock.patch.object(linkmycom, "fetch_latest_components", return_value={}), \
                    mock.patch.object(linkmycom, "cached_peers", return_value=([PFL], True)), \
                    mock.patch.object(linkmycom, "local_doctor_rows", return_value=self.rows()), \
                    redirect_stdout(io.StringIO()) as out:
                self.assertEqual(linkmycom.cmd_status(cfg, []), 0)
            with mock.patch.object(linkmycom, "fetch_latest_components", return_value={}), \
                    mock.patch.object(linkmycom, "cached_peers", return_value=([PFL], True)), \
                    mock.patch.object(linkmycom, "local_doctor_rows", return_value=self.rows()), \
                    redirect_stdout(io.StringIO()) as jout:
                linkmycom.cmd_status(cfg, ["--json"])
        self.assertEqual(data["disk"]["status"], "WARN")
        self.assertEqual(data["tasks_missing"], ["LinkMyCom-Tower", "LinkMyCom-NativeUpdate"])
        self.assertEqual(data["hidden"], 2)
        text = out.getvalue()
        for piece in ("디스크", "C: 1.0 GB free (low)", "업데이터", "stuck 372 min (pid 2952)", "없음: LinkMyCom-Tower, LinkMyCom-NativeUpdate",
                      "숨긴 장비", "2대", "다음: linkmycom doctor --fix"):
            self.assertIn(piece, text)
        parsed = json.loads(jout.getvalue())
        for key in ("disk", "updater", "tasks_missing", "hidden", "next"):
            self.assertIn(key, parsed)

    def test_status_still_works_when_the_check_script_fails(self):
        with mock.patch.object(linkmycom, "fetch_latest_components", return_value={}), \
                mock.patch.object(linkmycom, "cached_peers", return_value=([], True)), \
                mock.patch.object(linkmycom, "received_log_path", return_value=None), \
                mock.patch.object(linkmycom, "local_doctor_rows", side_effect=SystemExit(1)), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_status({}, ["--json"]), 0)
        data = json.loads(out.getvalue())
        self.assertIsNone(data["disk"])
        self.assertEqual(data["next"], [])

# ---------------------------------------------------------------- 0.7.1: 원격 실행기의 표준 입력 읽기와 Mac 의 최신 판.

class StdinLauncherTests(unittest.TestCase):
    def test_reader_has_a_time_limit_and_distinct_variables(self):
        lines = "\n".join(linkmycom.windows_stdin_read_lines("$code"))
        self.assertIn(linkmycom.STDIN_TIMEOUT_MARK, lines)
        self.assertIn(".Wait(%d)" % (linkmycom.STDIN_WAIT_SECONDS * 1000), lines)
        self.assertIn("[Environment]::Exit(3)", lines)
        self.assertIn("OpenStandardInput", lines)   # [Console]::In 의 비동기 읽기는 동기라 시간 제한이 듣지 않는다
        self.assertNotIn("[Console]::In.", lines)
        # PowerShell 변수는 대소문자를 가리지 않는다. 줄($l)과 목록이 같은 이름이면 코드가 사라진다(0.7.1 개발 중 실기에서 잡음).
        names = set(re.findall(r"\$([A-Za-z]\w*)", lines)) - {"null", "code"}
        self.assertEqual(len(names), len({n.lower() for n in names}), names)

    def test_windows_launchers_fit_the_cmd_exe_limit(self):
        blob = "A" * 68   # ed25519 공개키의 base64 길이
        for versions in (False, True):
            cmd, stdin_text = linkmycom.doctor_remote_command("windows", blob, versions_only=versions)
            self.assertLessEqual(len(cmd), 8191, "cmd.exe 명령줄 한도를 넘었습니다")
            self.assertTrue(stdin_text.endswith(linkmycom.DOCTOR_STDIN_END + "\n"))
            self.assertIn(linkmycom.STDIN_TIMEOUT_MARK, ps_of(cmd))

    def test_run_remote_retries_once_when_the_script_did_not_arrive(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(kwargs.get("input"))
            out = linkmycom.STDIN_TIMEOUT_MARK + "\n" if len(calls) == 1 else "LMCDOC|cli|INFO|tower 0.7.1\n"
            return subprocess.CompletedProcess(cmd, 0, out, "")

        with mock.patch.object(linkmycom, "remote_ssh_cmd", return_value=["ssh", "x"]), \
                mock.patch.object(linkmycom.subprocess, "run", side_effect=fake_run):
            rc, out, err = linkmycom.run_remote(PFL, {}, [], ["cmd"], "code\n")
        self.assertEqual((rc, len(calls)), (0, 2))
        self.assertIn("LMCDOC|cli", out)

        calls.clear()
        with mock.patch.object(linkmycom, "remote_ssh_cmd", return_value=["ssh", "x"]), \
                mock.patch.object(linkmycom.subprocess, "run",
                                  side_effect=lambda cmd, **k: (calls.append(1), subprocess.CompletedProcess(
                                      cmd, 3, linkmycom.STDIN_TIMEOUT_MARK + "\n", ""))[1]):
            rc, out, err = linkmycom.run_remote(PFL, {}, [], ["cmd"], "code\n")
        self.assertEqual((rc, len(calls)), (124, 2))
        self.assertIn("받지 못했습니다", err)


    def test_timeout_reaps_stuck_launchers_on_windows_only(self):
        sig = linkmycom.encode_ps("$py = $null\n")[:32]
        cmd, _ = linkmycom.doctor_remote_command("windows", versions_only=True)
        self.assertIn(sig, cmd)                                   # 실행기 명령줄에 그 앞머리가 실제로 있다
        reap = linkmycom.stuck_launcher_reap_command()
        self.assertNotIn(sig, reap)                               # 치우는 명령 자신은 대상이 아니다
        script = ps_of(reap)
        self.assertIn(sig, script)
        self.assertIn("SessionId -eq 0", script)
        self.assertIn("TotalSeconds -gt 100", script)
        seen = []

        def fake_run(cmd, **kwargs):
            seen.append(kwargs.get("input"))
            if kwargs.get("input") is not None:
                raise subprocess.TimeoutExpired(cmd, 120)
            return subprocess.CompletedProcess(cmd, 0, "LMCREAP|11\nLMCREAP|12\n", "")

        with mock.patch.object(linkmycom, "remote_ssh_cmd", return_value=["ssh", "x"]), \
                mock.patch.object(linkmycom.subprocess, "run", side_effect=fake_run):
            rc, _, err = linkmycom.run_remote(PFL, {}, [], ["cmd"], "code\n")
            self.assertEqual((rc, seen), (124, ["code\n", None]))  # 시간 초과 뒤 정리 명령을 한 번 보냈다
            seen.clear()
            rc, _, _ = linkmycom.run_remote(MAC, {}, [], ["cmd"], "code\n")
            self.assertEqual((rc, seen), (124, ["code\n"]))        # Mac 에는 보내지 않는다
            self.assertEqual(linkmycom.reap_stuck_launchers(PFL, {}, []), 2)

class MacLatestTests(unittest.TestCase):
    RELS = [
        {"tag_name": "native-v0.8.0", "assets": [{"name": "linkmycom-native-0.8.0-windows-x64.zip"}]},
        {"tag_name": "native-v0.6.0", "assets": [{"name": "linkmycom-native-0.6.0-windows-x64.zip"},
                                                {"name": "linkmycom-native-0.6.0-macos-arm64.zip"},
                                                {"name": "linkmycom-native-0.6.0-macos-arm64.zip.sig"}]},
        {"tag_name": "native-v0.9.0", "prerelease": True, "assets": [{"name": "linkmycom-native-0.9.0-macos-arm64.zip"}]},
        {"tag_name": "v0.7.1"}, {"tag_name": "tower-v0.6.0"},
    ]

    def test_mac_only_counts_releases_with_a_mac_package(self):
        latest = linkmycom.latest_components(self.RELS)
        self.assertEqual(latest["native"], "0.8.0")
        self.assertEqual(latest["native_macos"], "0.6.0")
        self.assertEqual(linkmycom.latest_for(latest, "native", "macOS"), "0.6.0")
        self.assertEqual(linkmycom.latest_for(latest, "native", "windows"), "0.8.0")
        self.assertEqual(linkmycom.latest_for(latest, "cli", "macOS"), "0.7.1")
        self.assertEqual(linkmycom.latest_for({"native": "0.8.0"}, "native", "macos"), "")
        self.assertEqual(linkmycom.outdated_components({"cli": "0.7.1", "tower": "", "native": "0.6.0"}, latest, "macOS"), [])
        self.assertEqual(linkmycom.outdated_components({"cli": "0.7.1", "tower": "", "native": "0.7.0"}, latest, "windows"),
                         ["native"])


# ---------------------------------------------------------------- 0.7.2: 백신(V3)이 막던 원격 점검 명령.

class AntivirusFriendlyLauncherTests(unittest.TestCase):
    def test_doctor_launcher_has_no_socket_client(self):
        # 인코딩된 PowerShell 명령줄에 소켓 클라이언트가 들어 있으면 V3 가 역방향 셸로 보고 프로세스 생성을 막는다
        # (Execution/MDP.Powershell.M2514, jekimlabtop 2026-11-27 실기: TcpClient 줄을 빼자 경고 없이 실행됨).
        for versions in (False, True):
            cmd, _ = linkmycom.doctor_remote_command("windows", "A" * 68, versions_only=versions)
            script = ps_of(cmd)
            for bad in ("Net.Sockets", "TcpClient", "DownloadString", "Invoke-Expression"):
                self.assertNotIn(bad.lower(), script.lower(), bad)
            self.assertIn("Get-NetTCPConnection -LocalPort 21118 -State Listen", script)
            self.assertIn("LMCDOC|screen_svc|", script)

    def test_refused_exec_is_reported_as_blocked(self):
        err = "exec request failed on channel 0\n"
        self.assertIn("명령 실행을 거부", linkmycom.remote_rows_error([], err))
        self.assertIn("Connection timed out", linkmycom.remote_rows_error([], "ssh: connect to host x port 22: Connection timed out"))


if __name__ == "__main__":
    unittest.main()
