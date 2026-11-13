# linkmycom 0.4.4 의 키 목록 보호·서명 검증·update·keys publish·doctor·예약·자동 완성을 검사하는 단위 테스트.
from __future__ import annotations

import base64
import hashlib
import io
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import linkmycom  # noqa: E402

KEYGEN = linkmycom.find_keygen()
K1, K2, K3, K4 = (f"ssh-ed25519 AAAAkey{i} host{i}" for i in range(1, 5))


def make_signer(d: Path, name: str = "signer") -> tuple[Path, str]:
    """임시 ed25519 서명키를 만들고 (비밀키 경로, 공개키 한 줄) 을 돌려준다."""
    key = d / name
    subprocess.run([KEYGEN, "-q", "-t", "ed25519", "-N", "", "-C", "test", "-f", str(key)], check=True,
                   stdin=subprocess.DEVNULL)
    return key, key.with_name(name + ".pub").read_text(encoding="utf-8").strip()


def sign(key: Path, data: bytes, namespace: str = "linkmycom-keys") -> bytes:
    r = subprocess.run([KEYGEN, "-Y", "sign", "-f", str(key), "-n", namespace], input=data, capture_output=True,
                       check=True)
    return r.stdout


class TempHome(unittest.TestCase):
    """SSH_DIR·AUTHORIZED_KEYS·LOCAL_KEY·STATE_PATH·CONFIG_PATH 를 임시 폴더로 돌려 실제 홈을 건드리지 않는다."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        ssh = self.root / ".ssh"
        cfgdir = self.root / ".tssh"
        self.patches = [
            mock.patch.object(linkmycom, "SSH_DIR", ssh),
            mock.patch.object(linkmycom, "AUTHORIZED_KEYS", ssh / "authorized_keys"),
            mock.patch.object(linkmycom, "LOCAL_KEY", ssh / "id_ed25519"),
            mock.patch.object(linkmycom, "SIGNING_KEY", ssh / "linkmycom-signing"),
            mock.patch.object(linkmycom, "CONFIG_DIR", cfgdir),
            mock.patch.object(linkmycom, "STATE_PATH", cfgdir / "state.json"),
            mock.patch.object(linkmycom, "CONFIG_PATH", cfgdir / "config.json"),
            mock.patch.object(linkmycom, "HOSTS_CACHE_PATH", cfgdir / "hosts.txt"),
        ]
        for p in self.patches:
            p.start()
        self.ak = ssh / "authorized_keys"

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self._tmp.cleanup()

    def write_block(self, keys):
        self.ak.parent.mkdir(parents=True, exist_ok=True)
        self.ak.write_bytes(("ssh-ed25519 OUTSIDE me@x\n" + linkmycom.KEYS_BEGIN + "\n" + "".join(k + "\n" for k in keys)
                             + linkmycom.KEYS_END + "\n").encode("utf-8"))


# ---------------------------------------------------------------- 1·2. 키 목록이 비거나 크게 줄면 적용하지 않고, 원자적으로 쓴다.

class KeysGuardTests(TempHome):
    def test_shrink_reason(self):
        self.assertIsNone(linkmycom.keys_shrink_reason(0, 3, 3))      # 처음 등록
        self.assertIsNone(linkmycom.keys_shrink_reason(4, 3, 3))      # 조금 줄어듦
        self.assertIn("하나도", linkmycom.keys_shrink_reason(4, 0, 0))
        self.assertIn("절반", linkmycom.keys_shrink_reason(4, 2, 2))
        self.assertIn("절반", linkmycom.keys_shrink_reason(2, 1, 1))
        self.assertIn("하나도", linkmycom.keys_shrink_reason(0, 0, 0))

    def test_install_refuses_empty_and_halving(self):
        self.write_block([K1, K2, K3, K4])
        before = self.ak.read_bytes()
        with self.assertRaises(linkmycom.KeysRefused):
            linkmycom.install_authorized_keys([], received=0)
        with self.assertRaises(linkmycom.KeysRefused):
            linkmycom.install_authorized_keys([], received=0, force=True)   # 빈 목록은 force 로도 안 됨
        with self.assertRaises(linkmycom.KeysRefused):
            linkmycom.install_authorized_keys([], force=True)
        with self.assertRaises(linkmycom.KeysRefused):
            linkmycom.install_authorized_keys([K1, K2])
        self.assertEqual(self.ak.read_bytes(), before)
        self.assertEqual(linkmycom.install_authorized_keys([K1, K2, K3]), 3)
        self.assertEqual(linkmycom.managed_keys_in(self.ak.read_text(encoding="utf-8")), [K1, K2, K3])
        self.assertEqual(linkmycom.install_authorized_keys([K1], force=True), 1)
        self.assertIn("ssh-ed25519 OUTSIDE me@x", self.ak.read_text(encoding="utf-8"))

    def test_first_install_and_atomic_write(self):
        self.assertEqual(linkmycom.install_authorized_keys([K1]), 1)
        self.assertEqual(linkmycom.managed_keys_in(self.ak.read_text(encoding="utf-8")), [K1])
        self.assertEqual(sorted(p.name for p in self.ak.parent.iterdir()), ["authorized_keys"])  # 임시 파일이 남지 않음
        if os.name != "nt":
            self.assertEqual(self.ak.stat().st_mode & 0o777, 0o600)
        # 기존 파일의 CRLF 줄은 그대로 둔다.
        self.ak.write_bytes(b"ssh-rsa CRLF a@b\r\n")
        linkmycom.install_authorized_keys([K2])
        self.assertTrue(self.ak.read_bytes().startswith(b"ssh-rsa CRLF a@b\r\n"))

    def test_refresh_keys_refuses_html_page(self):
        self.write_block([K1, K2])
        before = self.ak.read_bytes()
        with mock.patch.object(linkmycom, "fetch_remote_keys", return_value=[]), redirect_stderr(io.StringIO()) as err:
            self.assertEqual(linkmycom.refresh_keys({}), -1)
        self.assertIn("하나도", err.getvalue())
        self.assertEqual(self.ak.read_bytes(), before)
        self.assertIn("last_keys_error", linkmycom.load_json(linkmycom.STATE_PATH))
        with mock.patch.object(linkmycom, "fetch_remote_keys", return_value=[K1, K2, K3]), redirect_stdout(io.StringIO()):
            self.assertEqual(linkmycom.refresh_keys({}), 3)
        state = linkmycom.load_json(linkmycom.STATE_PATH)
        self.assertIn("last_keys_refresh", state)
        self.assertNotIn("last_keys_error", state)

    def test_refresh_force_allows_halving(self):
        self.write_block([K1, K2, K3, K4])
        with mock.patch.object(linkmycom, "fetch_remote_keys", return_value=[K1]):
            self.assertEqual(linkmycom.refresh_keys({}, quiet=True), -1)
            self.assertEqual(linkmycom.refresh_keys({}, quiet=True, force=True), 1)


# ---------------------------------------------------------------- 3·4. 서명 검증(실제 ssh-keygen).

@unittest.skipUnless(KEYGEN, "ssh-keygen 없음")
class SignatureTests(TempHome):
    def setUp(self):
        super().setUp()
        self.key, self.pub = make_signer(self.root)
        self.signer = mock.patch.object(linkmycom, "SIGNING_PUBKEY", self.pub)
        self.signer.start()

    def tearDown(self):
        self.signer.stop()
        super().tearDown()

    def test_verify_signature(self):
        data = b"# list\n" + K1.encode() + b"\n"
        sig = sign(self.key, data)
        self.assertEqual(linkmycom.verify_signature(data, sig, "linkmycom-keys"), (True, ""))
        ok, reason = linkmycom.verify_signature(data + b"x", sig, "linkmycom-keys")
        self.assertFalse(ok)
        self.assertIn("서명", reason)
        self.assertFalse(linkmycom.verify_signature(data, sig, "other-namespace")[0])
        self.assertFalse(linkmycom.verify_signature(data, b"<html>404</html>", "linkmycom-keys")[0])
        # 내장 공개키가 아닌 키로 서명하면 거부한다.
        other, _ = make_signer(self.root, "other")
        self.assertFalse(linkmycom.verify_signature(data, sign(other, data), "linkmycom-keys")[0])
        # CRLF 로 바뀐 바이트는 서명이 맞지 않는다(받은 바이트 그대로 검증해야 하는 이유).
        self.assertFalse(linkmycom.verify_signature(data.replace(b"\n", b"\r\n"), sig, "linkmycom-keys")[0])

    def serve(self, files: dict):
        def fake(url, timeout=5.0, headers=None):
            if url not in files:
                raise OSError(f"404 {url}")
            return files[url]
        return mock.patch.object(linkmycom, "http_get", side_effect=fake)

    def test_fetch_remote_keys_needs_matching_signature(self):
        data = ("# list\n" + K1 + "\n" + K2 + "\n").encode()
        api, raw = (u for u, _ in linkmycom.repo_file_urls(linkmycom.DEFAULT_REPO, "HEAD", linkmycom.DEFAULT_KEYS_PATH))
        self.assertEqual(linkmycom.sig_url_for(api), api.replace("authorized_keys?", "authorized_keys.sig?"))
        good = sign(self.key, data)
        with self.serve({api: data, linkmycom.sig_url_for(api): good}):
            self.assertEqual(linkmycom.fetch_remote_keys({}), [K1, K2])
        # API 가 옛 목록(서명 불일치)이고 raw 가 맞으면 raw 를 쓴다.
        with self.serve({api: data + b"x", linkmycom.sig_url_for(api): good, raw: data, linkmycom.sig_url_for(raw): good}):
            self.assertEqual(linkmycom.fetch_remote_keys({}), [K1, K2])
        with self.serve({api: data, raw: data}):  # 서명 파일 없음
            with self.assertRaises(RuntimeError) as cm:
                linkmycom.fetch_remote_keys({})
            self.assertIn("서명 파일", str(cm.exception))
        evil = ("# list\nssh-ed25519 AAAAevil x@y\n").encode()
        with self.serve({api: evil, linkmycom.sig_url_for(api): good, raw: evil, linkmycom.sig_url_for(raw): good}):
            with self.assertRaises(RuntimeError):
                linkmycom.fetch_remote_keys({})

    def test_custom_keys_url_uses_keys_signer(self):
        other, other_pub = make_signer(self.root, "own")
        data = (K3 + "\n").encode()
        url = "https://example.org/my/authorized_keys"
        with self.serve({url: data, url + ".sig": sign(other, data)}):
            with self.assertRaises(RuntimeError):
                linkmycom.fetch_remote_keys({"keys_url": url})
            self.assertEqual(linkmycom.fetch_remote_keys({"keys_url": url, "keys_signer": other_pub}), [K3])

    def release_files(self, src: bytes, sig: bytes | None, sha: str | None = None, tag: str = "v9.9.9"):
        base = "https://github.com/jekim14/linkmycom-cli/releases/download/" + tag + "/"
        assets = [{"name": "linkmycom.py", "browser_download_url": base + "linkmycom.py"}]
        files = {base + "linkmycom.py": src}
        if sig is not None:
            assets.append({"name": "linkmycom.py.sig", "browser_download_url": base + "linkmycom.py.sig"})
            files[base + "linkmycom.py.sig"] = sig
        if sha is not None:
            assets.append({"name": "linkmycom.py.sha256", "browser_download_url": base + "linkmycom.py.sha256"})
            files[base + "linkmycom.py.sha256"] = sha.encode()
        return {"tag_name": tag, "assets": assets}, files

    def test_check_release_source(self):
        src = b'# x\n__version__ = "9.9.9"\nprint(1)\n'
        sig = sign(self.key, src)
        self.assertEqual(linkmycom.check_release_source(src, sig), "9.9.9")
        sha = hashlib.sha256(src).hexdigest() + "  linkmycom.py\n"
        self.assertEqual(linkmycom.check_release_source(src, sig, sha), "9.9.9")
        for bad_src, bad_sig, bad_sha, word in (
            (src, None, None, "서명 파일"),
            (src + b"#", sig, None, "서명"),
            (src, sig, "0" * 64, "SHA256"),
        ):
            with self.assertRaises(RuntimeError) as cm:
                linkmycom.check_release_source(bad_src, bad_sig, bad_sha)
            self.assertIn(word, str(cm.exception))
        broken = b'__version__ = "9.9.9"\ndef (:\n'
        with self.assertRaises(RuntimeError) as cm:
            linkmycom.check_release_source(broken, sign(self.key, broken))
        self.assertIn("문법", str(cm.exception))
        nover = b"print(1)\n"
        with self.assertRaises(RuntimeError):
            linkmycom.check_release_source(nover, sign(self.key, nover))

    def run_update(self, rel, files, target: Path, check_only=False):
        with mock.patch.object(linkmycom, "latest_release", return_value=rel), self.serve(files), \
                mock.patch.object(linkmycom, "update_target", return_value=target), \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            try:
                code = linkmycom.cmd_update({}, check_only)
            except SystemExit as e:
                code = e.code
        return code, out.getvalue() + err.getvalue()

    def test_cmd_update_replaces_only_verified_bytes(self):
        target = self.root / "linkmycom.py"
        target.write_bytes(b"old\n")
        src = b'# new\r\n__version__ = "9.9.9"\r\n'  # 받은 바이트(CRLF 포함)를 그대로 써야 한다
        rel, files = self.release_files(src, sign(self.key, src), hashlib.sha256(src).hexdigest() + "  linkmycom.py")
        code, _ = self.run_update(rel, files, target, check_only=True)
        self.assertEqual((code, target.read_bytes()), (0, b"old\n"))
        code, out = self.run_update(rel, files, target)
        self.assertEqual(code, 0, out)
        self.assertEqual(target.read_bytes(), src)

    def test_cmd_update_refuses_bad_or_missing_signature(self):
        target = self.root / "linkmycom.py"
        target.write_bytes(b"old\n")
        src = b'__version__ = "9.9.9"\n'
        for sig in (None, sign(self.key, b"something else"), sign(make_signer(self.root, "x")[0], src)):
            rel, files = self.release_files(src, sig)
            code, out = self.run_update(rel, files, target)
            self.assertEqual(code, 1, out)
            self.assertEqual(target.read_bytes(), b"old\n")

    def test_cmd_update_already_latest_needs_no_signature(self):
        target = self.root / "linkmycom.py"
        target.write_bytes(b"old\n")
        rel, files = self.release_files(b"x", None, tag="v" + linkmycom.__version__)
        code, out = self.run_update(rel, files, target)
        self.assertEqual(code, 0)
        self.assertIn("이미 최신", out)


# ---------------------------------------------------------------- 10. keys publish 는 거울 클론에서만, 서명해 커밋한다.

@unittest.skipUnless(KEYGEN and shutil.which("git"), "ssh-keygen 또는 git 없음")
class PublishTests(TempHome):
    def setUp(self):
        super().setUp()
        ssh = self.root / ".ssh"
        ssh.mkdir()
        self.key, self.pub = make_signer(ssh, "linkmycom-signing")
        make_signer(ssh, "id_ed25519")
        self.signer = mock.patch.object(linkmycom, "SIGNING_PUBKEY", self.pub)
        self.signer.start()
        self.bare = self.root / "bare.git"
        self.repo = self.root / "mirror"
        self.git("init", "-q", "--bare", str(self.bare), cwd=self.root)
        self.git("init", "-q", str(self.repo), cwd=self.root)
        for k, v in (("user.name", "t"), ("user.email", "t@example.org"), ("core.autocrlf", "true")):
            self.git("config", k, v)
        (self.repo / "tools" / "linkmycom").mkdir(parents=True)
        (self.repo / "README.md").write_text("x\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-q", "-m", "init")
        # origin 은 거울 주소처럼 보이게 하고, 실제 푸시는 로컬 bare 저장소로 보낸다.
        self.git("remote", "add", "origin", "https://github.com/jekim14/linkmycom-cli.git")
        self.git("config", "remote.origin.pushurl", str(self.bare))
        self.git("push", "-q", "-u", "origin", "HEAD")
        self.cfg = {"repo_dir": str(self.repo), "hosts": {}}

    def tearDown(self):
        self.signer.stop()
        super().tearDown()

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.repo, check=True, capture_output=True).stdout

    def publish(self, cfg=None):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            try:
                code = linkmycom.cmd_keys(lambda: ([], []), cfg or self.cfg, ["publish"])
            except SystemExit as e:
                code = e.code
        return code, out.getvalue() + err.getvalue()

    def test_mirror_origin_rule(self):
        for url in ("https://github.com/jekim14/linkmycom-cli.git", "git@github.com:jekim14/linkmycom-cli.git",
                    "https://github.com/jekim14/linkmycom-cli", "https://github.com/jekim14/tssh.git"):
            self.assertTrue(linkmycom.is_mirror_origin(url), url)
        for url in ("https://github.com/jekim14/linkmycom.git", "https://github.com/evil/linkmycom-cli.git",
                    "https://github.com/jekim14/linkmycom-cli-fork.git", ""):
            self.assertFalse(linkmycom.is_mirror_origin(url), url)

    def test_refuses_non_mirror_and_missing_signing_key(self):
        self.git("remote", "set-url", "origin", "https://github.com/jekim14/linkmycom.git")
        code, out = self.publish()
        self.assertEqual(code, 1)
        self.assertIn("거울", out)
        self.assertFalse((self.repo / "tools" / "linkmycom" / "authorized_keys").exists())
        self.git("remote", "set-url", "origin", "https://github.com/jekim14/linkmycom-cli.git")
        with mock.patch.object(linkmycom, "SIGNING_KEY", self.root / "nope"):
            code, out = self.publish()
        self.assertEqual(code, 1)
        self.assertIn("서명키", out)

    def test_publish_signs_commits_and_pushes(self):
        code, out = self.publish()
        self.assertEqual(code, 0, out)
        rel = "tools/linkmycom/authorized_keys"
        data = subprocess.run(["git", "--git-dir", str(self.bare), "show", f"HEAD:{rel}"], capture_output=True).stdout
        sig = subprocess.run(["git", "--git-dir", str(self.bare), "show", f"HEAD:{rel}.sig"], capture_output=True).stdout
        self.assertNotIn(b"\r\n", data)
        self.assertEqual(linkmycom.verify_signature(data, sig, "linkmycom-keys"), (True, ""))
        self.assertEqual(len(linkmycom.parse_keys(data.decode())), 1)
        # 바뀐 것이 없으면 다시 커밋하지 않는다.
        head = self.git("rev-parse", "HEAD")
        code, out = self.publish()
        self.assertEqual(code, 0)
        self.assertIn("바뀐 내용이 없습니다", out)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        # 목록은 그대로인데 서명이 없으면(첫 서명 게시) 서명을 만들어 올린다.
        (self.repo / f"{rel}.sig").unlink()
        self.git("rm", "-q", "--cached", f"{rel}.sig")
        self.git("commit", "-q", "-m", "drop sig")
        code, out = self.publish()
        self.assertEqual(code, 0, out)
        self.assertTrue((self.repo / f"{rel}.sig").exists())
        # 새로 체크아웃해 작업 폴더가 CRLF 가 돼도(core.autocrlf=true) 바뀐 것이 없으면 커밋 없이 끝난다.
        head = self.git("rev-parse", "HEAD")
        (self.repo / rel).unlink()
        (self.repo / f"{rel}.sig").unlink()
        self.git("checkout", "--", ".")
        code, out = self.publish()
        self.assertEqual(code, 0, out)
        self.assertIn("바뀐 내용이 없습니다", out)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)


# ---------------------------------------------------------------- 5·6. 비대화형 모호한 이름, args 나누기.

class ResolveAndArgsTests(unittest.TestCase):
    PEERS = [{"name": n, "hostname": n, "dns": f"{n}.ts.net", "ip": ip, "os": "linux", "online": True}
             for n, ip in (("pfl", "100.3.3.3"), ("pfl-server", "100.4.4.4"))]

    def test_non_interactive_ambiguous_exits_1(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False), redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit) as cm:
                linkmycom.pick_one_or_die(self.PEERS, {"hosts": {}}, [], "pf")
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("pfl, pfl-server", err.getvalue())
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            self.assertEqual(linkmycom.pick_one_or_die(self.PEERS, {"hosts": {}}, [], "pfl")["name"], "pfl")

    def test_split_args(self):
        self.assertEqual(linkmycom.split_args("-A -o \"ProxyJump a b\""), ["-A", "-o", "ProxyJump a b"])
        self.assertEqual(linkmycom.split_args("-o 'SetEnv X=1 2'"), ["-o", "SetEnv X=1 2"])
        self.assertEqual(linkmycom.split_args("-A #notcomment"), ["-A", "#notcomment"])
        with self.assertRaises(ValueError):
            linkmycom.split_args("-o \"open")
        if os.name == "nt":
            self.assertEqual(linkmycom.split_args(r"-i C:\Users\x\key"), ["-i", r"C:\Users\x\key"])
            self.assertEqual(linkmycom.split_args(r'-i "C:\Users\a b\key"'), ["-i", r"C:\Users\a b\key"])

    def test_build_ssh_cmd_splits_string_args(self):
        cmd = linkmycom.build_ssh_cmd(self.PEERS[0], {"user": "u", "args": "-o \"ProxyCommand nc %h 22\" -A"},
                                      {"ssh_options": {}}, ssh_path="ssh")
        self.assertEqual(cmd, ["ssh", "-o", "ProxyCommand nc %h 22", "-A", "u@100.3.3.3"])

    def test_cmd_set_args_quoted(self):
        cfg = {"hosts": {}}
        with mock.patch.object(linkmycom, "save_json"), redirect_stdout(io.StringIO()):
            linkmycom.cmd_set(self.PEERS, cfg, [], ["pfl", "args=-o \"ProxyJump j k\" -A"])
        self.assertEqual(cfg["hosts"]["pfl"]["args"], ["-o", "ProxyJump j k", "-A"])


# ---------------------------------------------------------------- 7·8·9·11·12.

class ScriptBuilderTests(unittest.TestCase):
    def test_firewall_rule_created_before_old_removed(self):
        ps = linkmycom.WINDOWS_SERVER_SETUP_PS1
        self.assertTrue(ps.isascii())
        self.assertIn("InterfaceDescription -like 'Tailscale*'", ps)
        self.assertIn("$fw.InterfaceAlias = $tsIf.Name", ps)
        new = ps.index("New-NetFirewallRule -Name 'tssh-OpenSSH-next'")
        drop = ps.index("Get-NetFirewallRule -DisplayName 'OpenSSH*'")
        self.assertLess(new, drop)
        self.assertIn("Where-Object { $_.Name -ne 'tssh-OpenSSH-next' } | Remove-NetFirewallRule", ps)
        self.assertLess(drop, ps.index("Rename-NetFirewallRule -Name 'tssh-OpenSSH-next' -NewName 'tssh-OpenSSH'"))
        self.assertIn("existing tssh-OpenSSH rule is left unchanged", ps)
        self.assertNotIn("Remove-NetFirewallRule\n  New-NetFirewallRule", ps)

    def test_doctor_script(self):
        self.assertTrue(linkmycom.DOCTOR_PY.isascii())
        compile(linkmycom.DOCTOR_PY, "doctor", "exec")
        rows = linkmycom.parse_doctor_lines("noise\nLMCDOC|tailscale|OK|a b\r\nLMCDOC|firewall|WARN|x|y\nLMCDOC|bad\n")
        self.assertEqual(rows, [("tailscale", "OK", "a b"), ("firewall", "WARN", "x|y")])
        win, stdin_text = linkmycom.doctor_remote_command("windows", "AAAAkey")
        ps = base64.b64decode(win.split()[-1]).decode("utf-16-le")
        self.assertIn("WindowsApps", ps)
        self.assertTrue(ps.rstrip().endswith("AAAAkey"))
        self.assertLess(len(win), 8000)  # 원격 기본 셸이 cmd.exe 여도(명령줄 8191자) 들어가야 한다
        # 0.4.6 부터 표준 입력 끝에 종료 표시 줄이 붙는다(Windows OpenSSH 가 EOF 를 안 넘길 때 멈추지 않게).
        self.assertTrue(stdin_text.rstrip().endswith(linkmycom.DOCTOR_STDIN_END))
        self.assertEqual(stdin_text.rstrip().removesuffix(linkmycom.DOCTOR_STDIN_END).strip(), linkmycom.doctor_oneliner())
        posix, none = linkmycom.doctor_remote_command("linux", "AAAAkey")
        self.assertIsNone(none)
        self.assertTrue(posix.startswith("python3 -c "))
        self.assertIn("LMCDOC|python|FAIL", posix)

    @unittest.skipIf(os.name == "nt" and not os.environ.get("LINKMYCOM_SLOW_TESTS"),
                     "Windows 에서는 PowerShell 을 여러 번 띄워 30초쯤 걸린다(LINKMYCOM_SLOW_TESTS=1 로 실행)")
    def test_doctor_script_runs(self):
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "HOME": d, "USERPROFILE": d}
            # 홈을 바꾸면 PowerShell 이 모듈 캐시를 현재 폴더에 만들 수 있어 cwd 도 임시 폴더로 둔다.
            r = subprocess.run([sys.executable, "-c", linkmycom.doctor_oneliner(), "AAAAnokey"], capture_output=True,
                               text=True, encoding="utf-8", timeout=150, env=env, cwd=d)
        names = [n for n, _, _ in linkmycom.parse_doctor_lines(r.stdout)]
        self.assertEqual(r.returncode, 0, r.stderr)
        for want in ("tailscale", "ssh_port", "firewall", "authorized_keys", "cli", "native", "keys_refresh"):
            self.assertIn(want, names)
        rows = dict((n, s) for n, s, _ in linkmycom.parse_doctor_lines(r.stdout))
        self.assertEqual(rows["authorized_keys"], "FAIL")  # 빈 홈에는 authorized_keys 가 없다
        self.assertEqual(rows["keys_refresh"], "WARN")

    def test_schedule_builders(self):
        ps = linkmycom.schedule_windows_ps(r"C:\Users\김\py thon\pythonw.exe", r"C:\Users\김\it's\linkmycom.py")
        self.assertIn("-TaskName 'LinkMyCom-KeysRefresh'", ps)
        self.assertIn("it''s", ps)
        self.assertIn("keys refresh --quiet", ps)
        self.assertNotIn("RunLevel", ps)
        self.assertIn("New-ScheduledTaskAction", ps)
        plist = plistlib.loads(linkmycom.launchd_plist("/usr/bin/python3", "/Users/a b/.local/bin/linkmycom", "/tmp/l"))
        self.assertEqual(plist["Label"], linkmycom.LAUNCHD_LABEL)
        self.assertEqual(plist["ProgramArguments"], ["/usr/bin/python3", "/Users/a b/.local/bin/linkmycom",
                                                     "keys", "refresh", "--quiet"])
        self.assertEqual(plist["StartCalendarInterval"], {"Hour": 9, "Minute": 0})
        service, timer = linkmycom.systemd_units("/usr/bin/python3", "/home/a b/.local/bin/linkmycom")
        self.assertIn('ExecStart=/usr/bin/python3 "/home/a b/.local/bin/linkmycom" keys refresh --quiet', service)
        self.assertIn("OnCalendar=daily", timer)
        self.assertIn("Persistent=true", timer)

    def test_cmd_shim_skips_store_stub(self):
        shim = Path(linkmycom.__file__).with_name("linkmycom.cmd")
        raw = shim.read_bytes()
        self.assertTrue(raw.isascii())
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        self.assertIn(b"WindowsApps", raw)
        self.assertIn(b'"%~dp0linkmycom.py" %*', raw)
        self.assertFalse(linkmycom.broken_exe_path(shim))  # repair_shims 가 덮어쓰지 않아야 한다

    def test_completion_and_help(self):
        for shell in linkmycom.COMPLETION_SHELLS:
            text = linkmycom.completion_script(shell)
            self.assertIn("hosts.txt", text)
            self.assertIn("doctor", text)
            self.assertIn("lmc", text)
        if shutil.which("bash") and os.name != "nt":  # Windows 의 PATH bash 는 WSL 일 수 있어 건너뛴다.
            r = subprocess.run(["bash", "-n"], input=linkmycom.completion_script("bash").encode("utf-8"),
                               capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(linkmycom.cmd_help(["keys"]), 0)
        self.assertIn("--force", out.getvalue())
        with redirect_stdout(io.StringIO()) as out:
            linkmycom.cmd_help(["ls"])
        self.assertIn("linkmycom list", out.getvalue())
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            linkmycom.cmd_help(["nope"])
        self.assertTrue(set(linkmycom.SUBCOMMANDS) - {"ls"} <= set(linkmycom.COMMAND_HELP) | {"ls"})

    def test_hosts_cache(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(linkmycom, "CONFIG_DIR", Path(d) / "c"), \
                    mock.patch.object(linkmycom, "HOSTS_CACHE_PATH", Path(d) / "c" / "hosts.txt"):
                linkmycom.write_hosts_cache([{"name": "pfl"}, {"name": "mac"}])
                self.assertEqual((Path(d) / "c" / "hosts.txt").read_text(encoding="utf-8"), "pfl\nmac\n")


if __name__ == "__main__":
    unittest.main()
