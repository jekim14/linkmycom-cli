#!/usr/bin/env python3
# Tailscale 피어 목록에서 골라 SSH로 접속하는 명령줄 도구.
"""tssh - Tailscale SSH 접속기.

사용법:
  tssh                          피어 목록을 보여 주고 골라서 접속
  tssh <이름> [ssh 인자...]      이름(일부만 입력해도 됨)으로 바로 접속
  tssh <사용자>@<이름>           사용자 이름을 지정해 접속
  tssh -u <사용자> -p <포트> <이름>   한 번만 쓰는 사용자·포트 지정
  tssh --dns <이름>              IP 대신 MagicDNS 이름으로 접속
  tssh -n <이름>                 실행할 ssh 명령만 출력 (dry-run)
  tssh last                      최근 접속한 호스트에 다시 접속

  tssh list                      피어 목록만 출력
  tssh set <이름> user=.. port=.. key=.. alias=.. args=..   호스트별 접속 설정 저장
  tssh unset <이름>              저장한 호스트 설정 삭제
  tssh resolve <이름>            user@주소 형태로 출력 (scp 등에 활용)
  tssh export                    ~/.ssh/config 에 tssh 관리 블록 기록
  tssh config [키=값 ...]        전역 설정 보기/변경 (default_user, use_magicdns, update_repo, auto_update_check)
  tssh update [--check]          새 버전 확인/적용
  tssh version                   버전 출력

  tssh setup [--no-server] [--no-keys]   이 컴퓨터를 SSH 서버로 켜고(Tailscale 대역만 허용) 공개키를 교환
  tssh keys [show|refresh]       내 공개키 보기 / 저장소의 공개키 목록을 받아 authorized_keys 갱신
  tssh keys publish [--collect]  (관리 PC) 각 컴퓨터의 공개키를 모아 저장소에 게시
"""

from __future__ import annotations

import difflib
import getpass
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

__version__ = "0.2.3"

# tssh 는 DeskTools 저장소(jekim14/desktools, 비공개)의 tools/tssh 에서 개발하고, 공개 거울 저장소 jekim14/tssh 의
# 같은 경로로 배포한다. 업데이트·공개키 목록·설치 스크립트는 인증 없이 받을 수 있는 거울에서 가져온다.
DEFAULT_REPO = "jekim14/tssh"
# 설정 파일에 남아 있어도 raw 주소로 받을 수 없는 저장소 이름. 읽을 때 지워 기본 저장소를 쓰게 한다.
LEGACY_REPOS = {"jekim14/desktools"}
DEFAULT_UPDATE_REF = "HEAD"
DEFAULT_UPDATE_PATH = "tools/tssh/tssh.py"
DEFAULT_KEYS_PATH = "tools/tssh/authorized_keys"
CONFIG_DIR = Path.home() / ".tssh"
CONFIG_PATH = CONFIG_DIR / "config.json"
STATE_PATH = CONFIG_DIR / "state.json"
SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"
MANAGED_BEGIN = "# >>> tssh managed (tssh export 가 생성, 직접 고치지 마세요) >>>"
MANAGED_END = "# <<< tssh managed <<<"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,253}$")
SUBCOMMANDS = {"list", "ls", "set", "unset", "resolve", "export", "config", "update", "version", "help", "last",
               "setup", "keys"}
SSH_DIR = Path.home() / ".ssh"
LOCAL_KEY = SSH_DIR / "id_ed25519"
AUTHORIZED_KEYS = SSH_DIR / "authorized_keys"
KEYS_BEGIN = "# >>> tssh keys (tssh setup 이 관리, 직접 고치지 마세요) >>>"
KEYS_END = "# <<< tssh keys <<<"
KEY_PREFIXES = ("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-", "sk-ssh-ed25519@", "sk-ecdsa-sha2-")
MOBILE_OS = {"iOS", "android", "js"}

# ---------------------------------------------------------------- 출력 보조.

_COLOR = None


def color_enabled() -> bool:
    global _COLOR
    if _COLOR is None:
        _COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
        if _COLOR and os.name == "nt":
            try:
                import ctypes

                k32 = ctypes.windll.kernel32
                h = k32.GetStdHandle(-11)
                mode = ctypes.c_uint32()
                if k32.GetConsoleMode(h, ctypes.byref(mode)):
                    k32.SetConsoleMode(h, mode.value | 0x0004)
            except Exception:
                pass
    return _COLOR


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if color_enabled() else text


def warn(msg: str) -> None:
    print(c("경고: ", "33") + msg, file=sys.stderr)


def die(msg: str, code: int = 1):
    print(c("오류: ", "31") + msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- 설정 파일.


def load_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        warn(f"{path} 를 읽지 못했습니다 ({e}). 빈 설정으로 진행합니다.")
        return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def migrate_config(cfg: dict) -> bool:
    """옛 버전이 남긴 설정을 현재 기본값으로 옮긴다. 바뀐 것이 있으면 True."""
    changed = False
    if cfg.get("update_repo") in LEGACY_REPOS:
        cfg.pop("update_repo", None)
        cfg.pop("keys_url", None)
        changed = True
    return changed


def load_config() -> dict:
    cfg = load_json(CONFIG_PATH)
    if migrate_config(cfg):
        try:
            save_json(CONFIG_PATH, cfg)
        except OSError:
            pass
    cfg.setdefault("hosts", {})
    cfg.setdefault("use_magicdns", False)
    cfg.setdefault("auto_update_check", True)
    cfg.setdefault("ssh_options", {"ServerAliveInterval": "60"})
    return cfg


# ---------------------------------------------------------------- Tailscale.


TAILSCALE_KNOWN_PATHS = (
    r"C:\Program Files\Tailscale\tailscale.exe",
    "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    "/usr/local/bin/tailscale",
    "/opt/homebrew/bin/tailscale",
    "/usr/bin/tailscale",
)


def tailscale_candidates() -> list[str]:
    """tailscale CLI 후보를 중복 없이 모은다. 환경 변수 TSSH_TAILSCALE 이 있으면 그것만 쓴다."""
    forced = os.environ.get("TSSH_TAILSCALE")
    if forced:
        return [forced]
    cands: list[str] = []
    found = shutil.which("tailscale")
    if found:
        cands.append(found)
    for cand in TAILSCALE_KNOWN_PATHS:
        if os.path.exists(cand):
            cands.append(cand)
    seen: set[str] = set()
    unique = []
    for cnd in cands:
        key = os.path.normcase(os.path.realpath(cnd))
        if key not in seen:
            seen.add(key)
            unique.append(cnd)
    return unique


def run_status(exe: str) -> dict | None:
    try:
        proc = subprocess.run(
            [exe, "status", "--json"], capture_output=True, text=True, encoding="utf-8", timeout=20
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    try:
        status = json.loads(proc.stdout)
    except ValueError:
        return None
    return status if isinstance(status, dict) else None


TAILSCALED_SOCKETS = (
    "/var/run/tailscaled.socket",
    "/var/run/tailscale/tailscaled.sock",
)


def status_from_socket(path: str, timeout: float = 5.0) -> dict | None:
    """tailscaled 유닉스 소켓의 LocalAPI(/localapi/v0/status) 를 직접 읽는다. 실패하면 None."""
    import socket

    if not hasattr(socket, "AF_UNIX") or not os.path.exists(path):
        return None
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(path)
        s.sendall(b"GET /localapi/v0/status HTTP/1.0\r\nHost: local-tailscaled.sock\r\n\r\n")
        chunks = []
        while True:
            data = s.recv(65536)
            if not data:
                break
            chunks.append(data)
        s.close()
    except OSError:
        return None
    raw = b"".join(chunks)
    head, _, body = raw.partition(b"\r\n\r\n")
    first = head.split(b"\r\n", 1)[0]
    if not first.startswith(b"HTTP/1.") or b" 200" not in first:
        return None
    try:
        status = json.loads(body.decode("utf-8"))
    except ValueError:
        return None
    return status if isinstance(status, dict) else None


def tailscale_status() -> dict:
    """여러 tailscale CLI 와 데몬 소켓 중 실제로 연결된(Running) 것을 고른다.

    macOS 처럼 Homebrew tailscaled 와 Tailscale.app 이 함께 있으면 CLI 가 로그인 안 된 쪽에 붙을 수 있다.
    그런 경우 유닉스 소켓의 LocalAPI 를 직접 읽어 연결된 데몬의 상태를 얻는다.
    """
    cands = tailscale_candidates()
    sockets = [] if os.name == "nt" else [p for p in TAILSCALED_SOCKETS if os.path.exists(p)]
    if not cands and not sockets:
        die("tailscale 명령을 찾지 못했습니다. Tailscale이 설치되어 있는지 확인하세요.")
    fallback: dict | None = None
    tried: list[str] = []
    for exe in cands:
        tried.append(exe)
        status = run_status(exe)
        if status is None:
            continue
        if status.get("BackendState") == "Running":
            return status
        if fallback is None:
            fallback = status
    for path in sockets:
        tried.append(path)
        status = status_from_socket(path)
        if status is None:
            continue
        if status.get("BackendState") == "Running":
            return status
        if fallback is None:
            fallback = status
    if fallback is None:
        die("tailscale status 를 실행하지 못했습니다. Tailscale 서비스가 실행 중인지 확인하세요. "
            f"(시도한 경로: {', '.join(tried)})")
    warn(f"Tailscale 상태가 '{fallback.get('BackendState')}' 입니다. 로그인/연결 상태를 확인하세요.")
    return fallback


def load_peers(status: dict) -> list[dict]:
    """status JSON 에서 피어 목록을 뽑아 온라인 우선, 이름순으로 정렬한다."""
    peers = []
    for raw in (status.get("Peer") or {}).values():
        ips = raw.get("TailscaleIPs") or []
        ip4 = next((i for i in ips if "." in i), ips[0] if ips else "")
        dns = (raw.get("DNSName") or "").rstrip(".")
        hostname = raw.get("HostName") or ""
        name = dns.split(".")[0] if dns else hostname
        if not name or not NAME_RE.match(name):
            continue
        if raw.get("OS") == "js":  # Tailscale 웹 SSH 콘솔 같은 임시 노드는 숨긴다.
            continue
        peers.append(
            {
                "name": name,
                "hostname": hostname,
                "dns": dns,
                "ip": ip4,
                "os": raw.get("OS") or "?",
                "online": bool(raw.get("Online")),
                "last_seen": raw.get("LastSeen") or "",
                "ts_ssh": bool(raw.get("sshHostKeys")),
                "tags": raw.get("Tags") or [],
            }
        )
    peers.sort(key=lambda p: (not p["online"], p["name"].lower()))
    return peers


def humanize_last_seen(value: str, now: datetime | None = None) -> str:
    if not value or value.startswith("0001-"):
        return ""
    try:
        seen = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    now = now or datetime.now(timezone.utc)
    secs = int((now - seen).total_seconds())
    if secs < 60:
        return "방금 전"
    if secs < 3600:
        return f"{secs // 60}분 전"
    if secs < 86400:
        return f"{secs // 3600}시간 전"
    return f"{secs // 86400}일 전"


# ---------------------------------------------------------------- ssh config 읽기.


def parse_ssh_config(text: str) -> list[dict]:
    """~/.ssh/config 의 Host 블록을 [{'host': alias, 'hostname': ..., 'user': ..., ...}] 로 반환한다."""
    blocks: list[dict] = []
    current: dict | None = None
    in_managed = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == MANAGED_BEGIN:
            in_managed = True
            continue
        if stripped == MANAGED_END:
            in_managed = False
            continue
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^(\S+)\s*[=\s]\s*(.*)$", stripped)
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2).strip()
        if key == "host":
            current = {"host": val, "managed": in_managed}
            blocks.append(current)
        elif key == "match":
            current = None
        elif current is not None:
            current.setdefault(key, val)
    return blocks


def ssh_config_blocks() -> list[dict]:
    try:
        text = SSH_CONFIG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as e:
        warn(f"{SSH_CONFIG_PATH} 를 읽지 못했습니다 ({e}).")
        return []
    return parse_ssh_config(text)


def match_ssh_config(peer: dict, blocks: list[dict]) -> dict | None:
    """기존 ssh config 중 이 피어의 주소를 가리키는(관리 블록이 아닌) 항목을 찾는다."""
    targets = {peer["ip"].lower(), peer["dns"].lower(), peer["name"].lower()}
    targets.discard("")
    for b in blocks:
        if b.get("managed") or "*" in b["host"] or "?" in b["host"]:
            continue
        hostname = (b.get("hostname") or b["host"]).lower()
        if hostname in targets:
            return b
    return None


# ---------------------------------------------------------------- 이름 해석.


def host_settings(peer: dict, cfg: dict, blocks: list[dict]) -> dict:
    """저장값 > 기존 ssh config > 전역 기본값 순으로 합친 접속 설정."""
    merged: dict = {}
    sc = match_ssh_config(peer, blocks)
    if sc:
        merged["from_ssh_config"] = sc["host"]
        if sc.get("user"):
            merged["user"] = sc["user"]
        if sc.get("port"):
            merged["port"] = sc["port"]
        if sc.get("identityfile"):
            merged["key"] = sc["identityfile"]
    saved = cfg.get("hosts", {}).get(peer["name"]) or {}
    for k in ("user", "port", "key", "args", "alias"):
        if saved.get(k) not in (None, "", []):
            merged[k] = saved[k]
    if not merged.get("user") and cfg.get("default_user"):
        merged["user"] = cfg["default_user"]
    return merged


def aliases_of(peer: dict, cfg: dict, blocks: list[dict]) -> list[str]:
    names = []
    saved = cfg.get("hosts", {}).get(peer["name"]) or {}
    alias = saved.get("alias")
    if isinstance(alias, str):
        names += [a for a in alias.split(",") if a]
    elif isinstance(alias, list):
        names += alias
    sc = match_ssh_config(peer, blocks)
    if sc:
        names.append(sc["host"])
    return [n.lower() for n in names]


def resolve(peers: list[dict], query: str, cfg: dict | None = None, blocks: list[dict] | None = None) -> list[dict]:
    """이름 조각으로 피어를 찾는다. 정확 일치 → 별칭 → 접두 → 부분 → 유사 이름 순."""
    cfg = cfg or {"hosts": {}}
    blocks = blocks or []
    q = query.strip().lower()
    if not q:
        return []
    exact = [p for p in peers if q in (p["name"].lower(), p["hostname"].lower(), p["ip"], p["dns"].lower())]
    if exact:
        return exact[:1]
    alias = [p for p in peers if q in aliases_of(p, cfg, blocks)]
    if alias:
        return alias[:1]
    prefix = [p for p in peers if p["name"].lower().startswith(q) or p["hostname"].lower().startswith(q)]
    if prefix:
        return prefix
    sub = [p for p in peers if q in p["name"].lower() or q in p["hostname"].lower() or q in p["ip"]]
    if sub:
        return sub
    by_name = {p["name"].lower(): p for p in peers}
    return [by_name[n] for n in difflib.get_close_matches(q, list(by_name), n=5, cutoff=0.6)]


# ---------------------------------------------------------------- ssh 명령 조립.


def ssh_bin() -> str:
    found = shutil.which("ssh")
    if not found and os.name == "nt":
        cand = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "OpenSSH", "ssh.exe")
        if os.path.exists(cand):
            found = cand
    if not found:
        die("ssh 명령을 찾지 못했습니다. OpenSSH 클라이언트를 설치하세요.")
    return found


# 값을 하나 더 받는 OpenSSH 옵션 글자. 그 밖의 한 글자 옵션은 값 없는 플래그로 본다.
SSH_OPTS_WITH_VALUE = set("bcDEeFIiJLlmOopQRSWwBP")


def split_ssh_args(args: list[str]) -> tuple[list[str], list[str]]:
    """ssh 인자를 (호스트 앞에 둘 옵션, 호스트 뒤에 둘 원격 명령) 으로 나눈다."""
    options: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return options, list(args[i + 1:])
        if not a.startswith("-") or a == "-":
            return options, list(args[i:])
        options.append(a)
        # "-p" 처럼 글자 하나만 있고 값이 붙지 않았으면 다음 인자가 값이다.
        if len(a) == 2 and a[1] in SSH_OPTS_WITH_VALUE and i + 1 < len(args):
            options.append(args[i + 1])
            i += 1
        i += 1
    return options, []


def build_ssh_cmd(
    peer: dict,
    settings: dict,
    cfg: dict,
    extra: list[str] | None = None,
    user: str | None = None,
    port: str | None = None,
    use_dns: bool | None = None,
    ssh_path: str = "ssh",
) -> list[str]:
    use_dns = cfg.get("use_magicdns", False) if use_dns is None else use_dns
    target = peer["dns"] if use_dns and peer["dns"] else peer["ip"]
    if not target:
        die(f"{peer['name']} 의 주소를 알 수 없습니다.")
    login = user or settings.get("user") or getpass.getuser()
    cmd = [ssh_path]
    for k, v in (cfg.get("ssh_options") or {}).items():
        cmd += ["-o", f"{k}={v}"]
    port = port or settings.get("port")
    if port:
        cmd += ["-p", str(port)]
    if settings.get("key"):
        cmd += ["-i", os.path.expanduser(str(settings["key"]))]
    args = settings.get("args") or []
    if isinstance(args, str):
        args = args.split()
    cmd += list(args)
    options, remote = split_ssh_args(list(extra or []))
    cmd += options
    cmd.append(f"{login}@{target}")
    cmd += remote
    return cmd


def quote_cmd(cmd: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(cmd)
    import shlex

    return shlex.join(cmd)


def connect(peer: dict, cfg: dict, blocks: list[dict], extra: list[str], user: str | None, port: str | None,
            use_dns: bool | None, dry_run: bool) -> int:
    settings = host_settings(peer, cfg, blocks)
    cmd = build_ssh_cmd(peer, settings, cfg, extra, user, port, use_dns, ssh_bin())
    if dry_run:
        print(quote_cmd(cmd))
        return 0
    if not peer["online"]:
        warn(f"{peer['name']} 은(는) 현재 오프라인으로 표시됩니다. 그래도 시도합니다.")
    src = f" (설정 출처: ~/.ssh/config 'Host {settings['from_ssh_config']}')" if settings.get("from_ssh_config") else ""
    remote = split_ssh_args(list(extra))[1]
    target = cmd[len(cmd) - len(remote) - 1]
    print(c(f"→ {target}", "36") + f"  [{peer['os']}]" + src)
    state = load_json(STATE_PATH)
    state["last_host"] = peer["name"]
    state["last_connect"] = datetime.now(timezone.utc).isoformat()
    save_json(STATE_PATH, state)
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130


# ---------------------------------------------------------------- 목록과 선택기.

HEADER = ["#", " ", "이름", "OS", "Tailscale IP", "접속"]


def peer_rows(peers: list[dict], cfg: dict, blocks: list[dict], last: str | None) -> list[list[str]]:
    rows = []
    for i, p in enumerate(peers, 1):
        st = host_settings(p, cfg, blocks)
        user = st.get("user") or getpass.getuser()
        info = f"{user}@" + (f":{st['port']}" if st.get("port") else "")
        if not p["online"]:
            ls = humanize_last_seen(p["last_seen"])
            info += f"  (마지막 {ls})" if ls else ""
        mark = "*" if p["name"] == last else " "
        status = c("●", "32") if p["online"] else c("○", "90")
        rows.append([str(i), status, mark + p["name"], p["os"], p["ip"], info])
    return rows


def _visible_len(s: str) -> int:
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def print_table(rows: list[list[str]], header: list[str]) -> None:
    widths = [max(_visible_len(r[i]) for r in [header] + rows) for i in range(len(header))]
    for r in [header] + rows:
        line = "  ".join(cell + " " * (widths[i] - _visible_len(cell)) for i, cell in enumerate(r))
        print(line.rstrip())


def show_list(peers: list[dict], cfg: dict, blocks: list[dict]) -> None:
    last = load_json(STATE_PATH).get("last_host")
    if not peers:
        print("표시할 피어가 없습니다.")
        return
    print_table(peer_rows(peers, cfg, blocks, last), HEADER)


def pick_interactive(peers: list[dict], cfg: dict, blocks: list[dict], notice: list[str]) -> dict | None:
    """번호나 이름 조각을 입력받아 피어 하나를 고른다. None 이면 종료."""
    last = load_json(STATE_PATH).get("last_host")
    shown = peers
    while True:
        print()
        online = sum(1 for p in peers if p["online"])
        print(c(f"Tailscale SSH 접속기 v{__version__}", "1") + f"   온라인 {online}/{len(peers)}")
        if notice:
            print(c(notice[0], "33"))
        print_table(peer_rows(shown, cfg, blocks, last), HEADER)
        hint = f"  (Enter = * {last})" if last and any(p["name"] == last for p in peers) else ""
        try:
            raw = input(c("접속할 번호 또는 이름", "1") + f"{hint}  [r 새로고침, q 종료]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if raw.lower() in ("q", "quit", "exit"):
            return None
        if raw.lower() == "r":
            return {"__refresh__": True}
        if raw == "":
            if last:
                found = [p for p in peers if p["name"] == last]
                if found:
                    return found[0]
            shown = peers
            continue
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(shown):
                return shown[idx - 1]
            print(c(f"1~{len(shown)} 사이 번호를 입력하세요.", "31"))
            continue
        found = resolve(peers, raw, cfg, blocks)
        if len(found) == 1:
            return found[0]
        if not found:
            print(c(f"'{raw}' 에 맞는 피어가 없습니다.", "31"))
            shown = peers
        else:
            print(c(f"'{raw}' 에 맞는 피어가 {len(found)}개입니다. 번호로 고르세요.", "33"))
            shown = found


def ask_user_if_missing(peer: dict, cfg: dict, blocks: list[dict]) -> None:
    """처음 접속하는 호스트면 사용자 이름을 묻고 저장한다."""
    st = host_settings(peer, cfg, blocks)
    if st.get("user") or peer["name"] in cfg.get("hosts", {}):
        return
    default = getpass.getuser()
    try:
        ans = input(f"{peer['name']} 의 SSH 사용자 이름 [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        ans = ""
    cfg["hosts"][peer["name"]] = {"user": ans or default}
    save_json(CONFIG_PATH, cfg)
    print(f"저장했습니다. 바꾸려면: tssh set {peer['name']} user=<이름>")


# ---------------------------------------------------------------- export.


def managed_block(peers: list[dict], cfg: dict, blocks: list[dict]) -> str:
    existing = {b["host"].lower() for b in blocks if not b.get("managed")}
    lines = [MANAGED_BEGIN]
    for p in peers:
        if p["name"].lower() in existing:
            warn(f"'{p['name']}' 은(는) 이미 ~/.ssh/config 에 있어 건너뜁니다.")
            continue
        st = host_settings(p, cfg, blocks)
        target = p["dns"] if cfg.get("use_magicdns") and p["dns"] else p["ip"]
        if not target:
            continue
        lines.append(f"Host {p['name']}")
        lines.append(f"    HostName {target}")
        if st.get("user"):
            lines.append(f"    User {st['user']}")
        if st.get("port"):
            lines.append(f"    Port {st['port']}")
        if st.get("key"):
            lines.append(f"    IdentityFile {st['key']}")
        for k, v in (cfg.get("ssh_options") or {}).items():
            lines.append(f"    {k} {v}")
    lines.append(MANAGED_END)
    return "\n".join(lines) + "\n"


def replace_managed_block(text: str, block: str, begin: str = MANAGED_BEGIN, end: str = MANAGED_END) -> str:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.S)
    if pattern.search(text):
        return pattern.sub(lambda _: block, text, count=1)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + ("\n" if text else "") + block


def cmd_export(peers: list[dict], cfg: dict, blocks: list[dict]) -> None:
    block = managed_block(peers, cfg, blocks)
    try:
        old = SSH_CONFIG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        old = ""
    new = replace_managed_block(old, block)
    if new == old:
        print("~/.ssh/config 가 이미 최신입니다.")
        return
    SSH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if old:
        backup = SSH_CONFIG_PATH.with_name("config.bak-tssh")
        backup.write_text(old, encoding="utf-8")
        print(f"백업: {backup}")
    SSH_CONFIG_PATH.write_text(new, encoding="utf-8")
    count = block.count("\nHost ")
    print(f"~/.ssh/config 에 {count}개 호스트를 기록했습니다. 이제 'ssh <이름>' 으로도 접속됩니다.")


# ---------------------------------------------------------------- update.


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums) or (0,)


def http_get(url: str, timeout: float = 5.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": f"tssh/{__version__}", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_latest(repo: str, timeout: float = 5.0, ref: str = DEFAULT_UPDATE_REF,
                 path: str = DEFAULT_UPDATE_PATH) -> tuple[str, str]:
    """(참조 이름, tssh.py 원문) 을 돌려준다. DeskTools 저장소 기본 브랜치의 파일을 그대로 받는다. 실패하면 예외."""
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"
    src = http_get(url, timeout).decode("utf-8")
    if not version_in_source(src):
        raise RuntimeError(f"받은 파일에 버전이 없습니다: {url}")
    return ref, src


def version_in_source(src: str) -> str:
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M)
    return m.group(1) if m else ""


def write_self(target: Path, src: str) -> None:
    """새 소스를 임시 파일에 쓰고 원본의 실행 권한을 그대로 옮긴 뒤 원자적으로 교체한다."""
    tmp = target.with_name(target.name + ".new")
    tmp.write_text(src, encoding="utf-8")
    try:
        shutil.copymode(target, tmp)
    except OSError:
        pass
    os.replace(tmp, target)


def cmd_update(cfg: dict, check_only: bool) -> int:
    repo = cfg.get("update_repo") or DEFAULT_REPO
    ref = cfg.get("update_ref") or DEFAULT_UPDATE_REF
    print(f"저장소 {repo} ({ref}) 에서 최신 tssh 를 확인합니다...")
    try:
        tag, src = fetch_latest(repo, timeout=15, ref=ref)
    except Exception as e:  # noqa: BLE001
        die(f"최신 파일을 가져오지 못했습니다: {e}\n다른 저장소를 쓴다면 'tssh config update_repo=<owner/repo>' 로 지정하세요.")
    remote = version_in_source(src)
    if not remote:
        die("받은 파일에서 버전을 찾지 못했습니다.")
    if parse_version(remote) <= parse_version(__version__):
        print(f"이미 최신입니다 (설치 {__version__}, 릴리스 {remote}).")
        return 0
    print(f"새 버전 {remote} (태그 {tag}) 이(가) 있습니다. 현재 {__version__}.")
    if check_only:
        print("적용하려면: tssh update")
        return 0
    target = Path(__file__).resolve()
    write_self(target, src)
    state = load_json(STATE_PATH)
    state["last_update_check"] = datetime.now(timezone.utc).isoformat()
    state.pop("update_available", None)
    save_json(STATE_PATH, state)
    print(f"{target} 를 {remote} 으로 교체했습니다.")
    return 0


def background_update_check(cfg: dict, notice: list[str]) -> threading.Thread | None:
    """하루 한 번 새 버전을 조용히 확인해 notice 에 한 줄 넣는다."""
    if not cfg.get("auto_update_check", True):
        return None
    state = load_json(STATE_PATH)
    last = state.get("last_update_check", "")
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() if last else 1e9
    except ValueError:
        age = 1e9
    if age < 86400:
        if state.get("update_available"):
            notice.append(f"새 버전 {state['update_available']} 이(가) 있습니다. 'tssh update' 로 적용하세요.")
        return None

    def work() -> None:
        st = load_json(STATE_PATH)
        st["last_update_check"] = datetime.now(timezone.utc).isoformat()
        if st.get("setup_done"):
            try:
                refresh_keys(cfg, quiet=True)
            except Exception:  # noqa: BLE001
                pass
        try:
            tag, src = fetch_latest(cfg.get("update_repo") or DEFAULT_REPO, timeout=4,
                                    ref=cfg.get("update_ref") or DEFAULT_UPDATE_REF)
            remote = version_in_source(src)
            if remote and parse_version(remote) > parse_version(__version__):
                st["update_available"] = remote
                notice.append(f"새 버전 {remote} 이(가) 있습니다. 'tssh update' 로 적용하세요.")
            else:
                st.pop("update_available", None)
        except Exception:  # noqa: BLE001
            pass
        try:
            save_json(STATE_PATH, st)
        except OSError:
            pass

    t = threading.Thread(target=work, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------- 키 교환과 SSH 서버 설정 (tssh setup / keys).


def keys_url(cfg: dict) -> str:
    repo = cfg.get("update_repo") or DEFAULT_REPO
    ref = cfg.get("update_ref") or DEFAULT_UPDATE_REF
    return cfg.get("keys_url") or f"https://raw.githubusercontent.com/{repo}/{ref}/{DEFAULT_KEYS_PATH}"


def parse_keys(text: str) -> list[str]:
    """공개키처럼 보이는 줄만 순서대로, 중복 없이 돌려준다."""
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(KEY_PREFIXES) and len(s.split()) >= 2 and s not in out:
            out.append(s)
    return out


def strip_block(text: str, begin: str, end: str) -> str:
    return re.sub(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", "", text, count=1, flags=re.S)


def keygen_bin() -> str:
    found = shutil.which("ssh-keygen")
    if not found and os.name == "nt":
        cand = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "OpenSSH", "ssh-keygen.exe")
        if os.path.exists(cand):
            found = cand
    if not found:
        die("ssh-keygen 을 찾지 못했습니다. OpenSSH 클라이언트를 설치하세요.")
    return found


def ensure_local_key() -> str:
    """~/.ssh/id_ed25519 가 없으면 만들고 공개키 한 줄을 돌려준다."""
    pub = LOCAL_KEY.with_suffix(".pub")
    if not LOCAL_KEY.exists():
        SSH_DIR.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(SSH_DIR, 0o700)
        comment = f"tssh@{platform.node().split('.')[0]}"
        subprocess.run(
            [keygen_bin(), "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(LOCAL_KEY)],
            check=True, stdin=subprocess.DEVNULL,
        )
        print(f"새 SSH 키를 만들었습니다: {LOCAL_KEY}")
    return pub.read_text(encoding="utf-8").strip()


def merge_authorized_keys(existing: str, keys: list[str]) -> tuple[str, int]:
    """관리 블록에 keys 를 넣은 새 authorized_keys 내용과, 블록에 들어간 키 수를 돌려준다."""
    outside = set(parse_keys(strip_block(existing, KEYS_BEGIN, KEYS_END)))
    managed = [k for k in keys if k not in outside]
    block = "\n".join([KEYS_BEGIN, *managed, KEYS_END]) + "\n"
    return replace_managed_block(existing, block, KEYS_BEGIN, KEYS_END), len(managed)


def install_authorized_keys(keys: list[str]) -> int:
    try:
        existing = AUTHORIZED_KEYS.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""
    new_text, count = merge_authorized_keys(existing, keys)
    if new_text != existing:
        SSH_DIR.mkdir(parents=True, exist_ok=True)
        AUTHORIZED_KEYS.write_text(new_text, encoding="utf-8")
        if os.name != "nt":
            os.chmod(SSH_DIR, 0o700)
            os.chmod(AUTHORIZED_KEYS, 0o600)
    return count


def fetch_remote_keys(cfg: dict, timeout: float = 10.0) -> list[str]:
    return parse_keys(http_get(keys_url(cfg), timeout).decode("utf-8", "replace"))


def refresh_keys(cfg: dict, quiet: bool = False) -> int:
    """저장소의 공개키 목록을 받아 authorized_keys 관리 블록을 갱신한다. 실패하면 -1."""
    try:
        keys = fetch_remote_keys(cfg)
    except Exception as e:  # noqa: BLE001
        if not quiet:
            warn(f"공개키 목록을 받지 못했습니다 ({keys_url(cfg)}): {e}")
        return -1
    local = ensure_local_key() if LOCAL_KEY.exists() else ""
    keys = [k for k in keys if k != local]
    count = install_authorized_keys(keys)
    if not quiet:
        print(f"authorized_keys 관리 블록에 공개키 {count}개를 등록했습니다 ({AUTHORIZED_KEYS}).")
    return count


def port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_windows_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# 관리자 PowerShell 에서 실행되는 Windows SSH 서버 설정. ASCII 만 쓴다.
WINDOWS_SERVER_SETUP_PS1 = r"""
$ErrorActionPreference = 'Stop'
$log = $args[0]
Start-Transcript -Path $log -Force | Out-Null
try {
  if (-not (Get-Service sshd -ErrorAction SilentlyContinue)) {
    $installed = $false
    try {
      $cap = Get-WindowsCapability -Online -Name 'OpenSSH.Server*' | Select-Object -First 1
      if ($cap -and $cap.State -ne 'Installed') { Write-Host "Installing $($cap.Name) ..."; Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
      $installed = [bool](Get-Service sshd -ErrorAction SilentlyContinue)
    } catch { Write-Host "Windows optional feature install failed: $($_.Exception.Message)" }
    if (-not $installed) {
      Write-Host 'Falling back to the signed Win32-OpenSSH MSI from github.com/PowerShell/Win32-OpenSSH.'
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      $rel = Invoke-RestMethod -UseBasicParsing -Uri 'https://api.github.com/repos/PowerShell/Win32-OpenSSH/releases/latest' -Headers @{ 'User-Agent' = 'tssh' }
      $asset = $rel.assets | Where-Object { $_.name -match '^OpenSSH-Win64-v.*\.msi$' } | Select-Object -First 1
      if (-not $asset) { throw 'Win32-OpenSSH MSI asset not found in the latest release.' }
      $msi = Join-Path $env:TEMP $asset.name
      Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $msi
      $sig = Get-AuthenticodeSignature -LiteralPath $msi
      if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw "MSI signature check failed: $($sig.Status) $($sig.SignerCertificate.Subject)" }
      Write-Host "Installing $($asset.name) ..."
      $p = Start-Process msiexec.exe -ArgumentList @('/i', ('"' + $msi + '"'), '/qn', '/norestart', 'ADDLOCAL=Server') -Wait -PassThru
      if ($p.ExitCode -notin @(0,3010)) { throw "MSI install failed: exit code $($p.ExitCode)" }
      if (-not (Get-Service sshd -ErrorAction SilentlyContinue)) { throw 'sshd service is missing after the MSI install.' }
    }
  }
  Set-Service sshd -StartupType Automatic
  $conf = Join-Path $env:ProgramData 'ssh\sshd_config'
  if (-not (Test-Path $conf)) { Start-Service sshd; Start-Sleep -Seconds 2 }
  if (Test-Path $conf) {
    $lines = Get-Content $conf
    $out = foreach ($l in $lines) {
      if ($l -match '^\s*Match\s+Group\s+administrators' -or $l -match '^\s*AuthorizedKeysFile\s+__PROGRAMDATA__') { "#tssh# $l" } else { $l }
    }
    Set-Content -Path $conf -Value $out -Encoding ASCII
  }
  New-Item -Path 'HKLM:\SOFTWARE\OpenSSH' -Force | Out-Null
  $pwsh = (Get-Command powershell.exe).Source
  Set-ItemProperty -Path 'HKLM:\SOFTWARE\OpenSSH' -Name DefaultShell -Value $pwsh
  Get-NetFirewallRule -DisplayName 'OpenSSH*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  Get-NetFirewallRule -Name 'tssh-OpenSSH' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  New-NetFirewallRule -Name 'tssh-OpenSSH' -DisplayName 'OpenSSH Server (Tailscale only, tssh)' -Direction Inbound -Protocol TCP -LocalPort 22 -RemoteAddress @('100.64.0.0/10','fd7a:115c:a1e0::/48') -Action Allow | Out-Null
  Restart-Service sshd
  Write-Host 'TSSH_SETUP_OK'
} catch {
  Write-Host "TSSH_SETUP_FAIL: $($_.Exception.Message)"
} finally {
  Stop-Transcript | Out-Null
}
"""


def setup_server_windows() -> bool:
    log = Path(tempfile.gettempdir()) / "tssh-setup.log"
    script = Path(tempfile.gettempdir()) / "tssh-setup.ps1"
    script.write_text(WINDOWS_SERVER_SETUP_PS1, encoding="ascii")
    if log.exists():
        log.unlink()
    if is_windows_admin():
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(log)])
    else:
        print("관리자 권한 확인 창(UAC)이 뜨면 '예'를 누르세요. OpenSSH 서버 설치·방화벽 설정에 필요합니다.")
        arg = f"-NoProfile -ExecutionPolicy Bypass -File \"{script}\" \"{log}\""
        subprocess.run([
            "powershell", "-NoProfile", "-Command",
            f"Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList '{arg}'",
        ])
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    ok = "TSSH_SETUP_OK" in text
    if not ok:
        tail = "\n".join(line for line in text.splitlines() if "TSSH_SETUP_FAIL" in line or "Install" in line)
        warn("Windows SSH 서버 설정이 끝나지 않았습니다. " + (tail or "UAC 창을 취소했거나 로그가 없습니다.") +
             f"\n로그: {log}")
    return ok


def setup_server_macos() -> bool:
    if port_open("127.0.0.1", 22):
        print("macOS 원격 로그인(SSH)이 이미 켜져 있습니다.")
        return True
    if not sys.stdin.isatty():
        warn("원격 로그인이 꺼져 있습니다. 시스템 설정 → 일반 → 공유 → 원격 로그인을 켜거나 "
             "터미널에서 'sudo systemsetup -setremotelogin on' 을 실행하세요.")
        return False
    print("원격 로그인을 켭니다. 관리자 비밀번호를 물을 수 있습니다.")
    r = subprocess.run(["sudo", "systemsetup", "-setremotelogin", "on"])
    return r.returncode == 0 and port_open("127.0.0.1", 22, 3.0)


def setup_server_linux() -> bool:
    exe = tailscale_candidates()
    if exe:
        print("Tailscale SSH 를 켭니다 (tailscale set --ssh). 관리자 비밀번호를 물을 수 있습니다.")
        cmd = [exe[0], "set", "--ssh"]
        if os.geteuid() != 0:  # type: ignore[attr-defined]
            if not shutil.which("sudo"):
                warn("sudo 가 없어 Tailscale SSH 를 켜지 못했습니다. root 로 'tailscale set --ssh' 를 실행하세요.")
                return False
            cmd = ["sudo"] + (["-n"] if not sys.stdin.isatty() else []) + cmd
        r = subprocess.run(cmd)
        if r.returncode == 0:
            print("Tailscale SSH 가 켜졌습니다. 접근 권한은 Tailscale 관리 콘솔의 SSH 정책을 따릅니다.")
            return True
        warn("Tailscale SSH 를 켜지 못했습니다. 아래 OpenSSH 서버 설치로 넘어갑니다.")
    if port_open("127.0.0.1", 22):
        print("OpenSSH 서버가 이미 실행 중입니다.")
        return True
    if not sys.stdin.isatty():
        warn("OpenSSH 서버가 없습니다. 'sudo apt install openssh-server' 또는 'sudo dnf install openssh-server' 를 실행하세요.")
        return False
    if shutil.which("apt-get"):
        cmds = [["sudo", "apt-get", "install", "-y", "openssh-server"], ["sudo", "systemctl", "enable", "--now", "ssh"]]
    elif shutil.which("dnf"):
        cmds = [["sudo", "dnf", "install", "-y", "openssh-server"], ["sudo", "systemctl", "enable", "--now", "sshd"]]
    else:
        warn("패키지 관리자를 몰라 OpenSSH 서버를 설치하지 못했습니다.")
        return False
    for cmd in cmds:
        if subprocess.run(cmd).returncode != 0:
            warn(f"실패: {' '.join(cmd)}")
            return False
    return port_open("127.0.0.1", 22, 3.0)


def cmd_setup(cfg: dict, args: list[str]) -> int:
    """이 컴퓨터를 tailnet 안에서 SSH 로 들어올 수 있게 만들고 공개키를 교환한다."""
    no_server = "--no-server" in args
    no_keys = "--no-keys" in args
    print(c("tssh setup: 이 컴퓨터를 SSH 로 묶습니다.", "1"))
    pub = ensure_local_key()
    print(f"이 컴퓨터의 공개키: {pub[:40]}...")
    if not no_keys:
        refresh_keys(cfg)
    ok = True
    if not no_server:
        system = platform.system()
        if system == "Windows":
            ok = setup_server_windows()
        elif system == "Darwin":
            ok = setup_server_macos()
        elif system == "Linux":
            ok = setup_server_linux()
        else:
            warn(f"{system} 에서는 SSH 서버 자동 설정을 지원하지 않습니다.")
            ok = False
    state = load_json(STATE_PATH)
    state["setup_done"] = datetime.now(timezone.utc).isoformat()
    state["server_ok"] = ok
    save_json(STATE_PATH, state)
    if ok:
        print(c("완료. 이제 다른 기기에서 'tssh <이 컴퓨터 이름>' 으로 들어올 수 있습니다.", "32"))
        print("이 컴퓨터의 공개키를 저장소 목록에 올리려면 관리 PC 에서 'tssh keys publish --collect' 를 실행하세요.")
    return 0 if ok else 1


def remote_pubkey_command(peer: dict) -> str:
    if peer["os"] == "windows":
        return 'powershell -NoProfile -Command "Get-Content $env:USERPROFILE\\.ssh\\id_ed25519.pub"'
    return "cat ~/.ssh/id_ed25519.pub"


def collect_keys(peers: list[dict], cfg: dict, blocks: list[dict]) -> list[tuple[str, str]]:
    """SSH 로 들어갈 수 있는 컴퓨터마다 공개키를 가져온다."""
    found: list[tuple[str, str]] = []
    ssh = ssh_bin()
    for p in peers:
        if not p["online"] or p["os"] in MOBILE_OS or not p["ip"]:
            continue
        if not port_open(p["ip"], 22):
            print(f"  {p['name']}: SSH 포트 닫힘, 건너뜀")
            continue
        settings = host_settings(p, cfg, blocks)
        extra = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new"]
        cmd = build_ssh_cmd(p, settings, cfg, extra, ssh_path=ssh)
        cmd.append(remote_pubkey_command(p))
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        except subprocess.TimeoutExpired:
            print(f"  {p['name']}: 응답 없음")
            continue
        keys = parse_keys(r.stdout)
        if r.returncode != 0 or not keys:
            reason = (r.stderr or "").strip().splitlines()[-1:] or ["공개키 없음 (tssh setup 미실행)"]
            print(f"  {p['name']}: 실패 - {reason[0]}")
            continue
        found.append((p["name"], keys[0]))
        print(f"  {p['name']}: {keys[0][:40]}...")
    return found


def repo_dir(cfg: dict) -> Path:
    """DeskTools 저장소 복제본의 루트. 설정값, 이 파일의 위치(tools/tssh/tssh.py) 순으로 찾는다."""
    d = cfg.get("repo_dir")
    if d and (Path(d) / ".git").exists():
        return Path(d)
    here = Path(__file__).resolve()
    for cand in (here.parent, here.parents[2] if len(here.parents) > 2 else here.parent):
        if (cand / ".git").exists():
            return cand
    die("저장소 복제본 위치를 모릅니다. 'tssh config repo_dir=<desktools 클론 경로>' 로 지정하세요.")


def keys_file(cfg: dict) -> Path:
    """저장소 안의 공개키 목록 파일 경로."""
    rd = repo_dir(cfg)
    nested = rd / DEFAULT_KEYS_PATH
    return nested if nested.parent.is_dir() else rd / "authorized_keys"


def cmd_keys(peers_loader, cfg: dict, args: list[str]) -> int:
    sub = args[0] if args else "show"
    if sub == "show":
        print(ensure_local_key())
        return 0
    if sub == "refresh":
        return 0 if refresh_keys(cfg) >= 0 else 1
    if sub in ("collect", "publish"):
        rd = repo_dir(cfg)
        target = keys_file(cfg)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        entries: dict[str, str] = {}
        for line in existing.splitlines():
            s = line.strip()
            if s.startswith(KEY_PREFIXES):
                entries[s] = s
        local = ensure_local_key()
        entries[local] = local
        if sub == "collect" or "--collect" in args:
            peers, blocks = peers_loader()
            print("각 컴퓨터에서 공개키를 모읍니다...")
            for name, key in collect_keys(peers, cfg, blocks):
                entries[key] = key
        header = "# tssh 가 관리하는 tailnet 공개키 목록. 각 기기의 'tssh setup' / 'tssh keys refresh' 가 이 파일을 받아 authorized_keys 에 넣는다.\n"
        text = header + "\n".join(entries) + "\n"
        changed = text != existing
        target.write_text(text, encoding="utf-8")
        print(f"{target}: 공개키 {len(entries)}개")
        if sub == "publish":
            if not changed:
                print("바뀐 내용이 없습니다.")
                return 0
            rel = str(target.relative_to(rd)).replace("\\", "/")
            cmds = [["git", "add", rel],
                    ["git", "commit", "-q", "-m", "keys: tailnet 공개키 목록 갱신"],
                    ["git", "push", "-q"]]
            for cmd in cmds:
                r = subprocess.run(cmd, cwd=rd)
                if r.returncode != 0:
                    die(f"실패: {' '.join(cmd)}")
            print(f"게시했습니다. 각 기기는 하루 안에 자동으로 받거나 'tssh keys refresh' 로 바로 받습니다.\n{keys_url(cfg)}")
        return 0
    die("사용법: tssh keys [show|refresh|collect|publish [--collect]]")


# ---------------------------------------------------------------- 하위 명령.


def parse_kv(items: list[str]) -> dict:
    out = {}
    for it in items:
        if "=" not in it:
            die(f"'{it}' 은(는) 키=값 형식이어야 합니다.")
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def cmd_set(peers: list[dict], cfg: dict, blocks: list[dict], args: list[str]) -> None:
    if len(args) < 2:
        die("사용법: tssh set <이름> user=.. port=.. key=.. alias=.. args=\"-A -X\"")
    found = resolve(peers, args[0], cfg, blocks)
    if len(found) != 1:
        die(f"'{args[0]}' 에 맞는 피어가 {len(found)}개입니다. 정확한 이름을 쓰세요.")
    name = found[0]["name"]
    kv = parse_kv(args[1:])
    allowed = {"user", "port", "key", "alias", "args"}
    bad = set(kv) - allowed
    if bad:
        die(f"알 수 없는 키: {', '.join(sorted(bad))}. 가능한 키: {', '.join(sorted(allowed))}")
    entry = cfg["hosts"].get(name, {})
    for k, v in kv.items():
        if v == "":
            entry.pop(k, None)
        elif k == "args":
            entry[k] = v.split()
        else:
            entry[k] = v
    cfg["hosts"][name] = entry
    save_json(CONFIG_PATH, cfg)
    print(f"{name}: {json.dumps(entry, ensure_ascii=False)}")


def cmd_unset(peers: list[dict], cfg: dict, blocks: list[dict], args: list[str]) -> None:
    if not args:
        die("사용법: tssh unset <이름>")
    name = args[0]
    found = resolve(peers, name, cfg, blocks)
    if len(found) == 1:
        name = found[0]["name"]
    if cfg["hosts"].pop(name, None) is None:
        die(f"'{name}' 에 저장된 설정이 없습니다.")
    save_json(CONFIG_PATH, cfg)
    print(f"{name} 설정을 지웠습니다.")


def cmd_config(cfg: dict, args: list[str]) -> None:
    if not args:
        print(f"설정 파일: {CONFIG_PATH}")
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return
    kv = parse_kv(args)
    bools = {"use_magicdns", "auto_update_check"}
    for k, v in kv.items():
        if k in bools:
            cfg[k] = v.lower() in ("1", "true", "yes", "on", "y")
        elif k in ("default_user", "update_repo", "update_ref", "repo_dir", "keys_url"):
            if v:
                cfg[k] = v
            else:
                cfg.pop(k, None)
        elif k.startswith("ssh_options."):
            opt = k.split(".", 1)[1]
            if v:
                cfg.setdefault("ssh_options", {})[opt] = v
            else:
                cfg.get("ssh_options", {}).pop(opt, None)
        else:
            die(f"알 수 없는 설정 키: {k} (가능: default_user, use_magicdns, update_repo, update_ref, auto_update_check, "
                "repo_dir, keys_url, ssh_options.<옵션>)")
    save_json(CONFIG_PATH, cfg)
    print(json.dumps(cfg, ensure_ascii=False, indent=2))


def pick_one_or_die(peers: list[dict], cfg: dict, blocks: list[dict], query: str) -> dict:
    found = resolve(peers, query, cfg, blocks)
    if len(found) == 1:
        return found[0]
    if not found:
        die(f"'{query}' 에 맞는 피어가 없습니다. 'tssh list' 로 이름을 확인하세요.")
    if not sys.stdin.isatty():
        return found[0]
    print(c(f"'{query}' 에 맞는 피어가 {len(found)}개입니다.", "33"))
    chosen = pick_interactive(found, cfg, blocks, [])
    if not chosen or chosen.get("__refresh__"):
        sys.exit(1)
    return chosen


def parse_connect_args(argv: list[str]) -> dict:
    """tssh 자체 옵션(호스트 이름 앞)과 호스트, 그 뒤 ssh 인자를 나눈다."""
    opts: dict = {"user": None, "port": None, "use_dns": None, "dry_run": False, "host": None, "extra": []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if opts["host"] is not None:
            opts["extra"].append(a)
        elif a in ("-u", "--user") and i + 1 < len(argv):
            opts["user"] = argv[i + 1]
            i += 1
        elif a in ("-p", "--port") and i + 1 < len(argv):
            opts["port"] = argv[i + 1]
            i += 1
        elif a == "--dns":
            opts["use_dns"] = True
        elif a == "--ip":
            opts["use_dns"] = False
        elif a in ("-n", "--dry-run"):
            opts["dry_run"] = True
        elif a in ("-h", "--help"):
            opts["host"] = "help"
        elif a.startswith("-"):
            die(f"알 수 없는 옵션 {a}. ssh 옵션은 호스트 이름 뒤에 쓰세요. 예: tssh pfl -L 8080:localhost:80")
        else:
            opts["host"] = a
        i += 1
    if opts["host"] and "@" in opts["host"]:
        u, h = opts["host"].rsplit("@", 1)
        opts["user"] = opts["user"] or u
        opts["host"] = h
    return opts


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Windows 에서 파이프·Git Bash 로 출력할 때 cp949 로 한글이 깨지지 않도록 UTF-8 로 고정한다.
    if not os.environ.get("PYTHONIOENCODING"):
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            except Exception:
                pass
    cfg = load_config()
    sub = argv[0] if argv and argv[0] in SUBCOMMANDS else None

    if sub == "version":
        print(f"tssh {__version__}")
        return 0
    if sub == "help" or (argv and argv[0] in ("-h", "--help")):
        print(__doc__)
        return 0
    if sub == "update":
        return cmd_update(cfg, check_only="--check" in argv[1:])
    if sub == "config":
        cmd_config(cfg, argv[1:])
        return 0
    if sub == "setup":
        return cmd_setup(cfg, argv[1:])
    if sub == "keys":
        return cmd_keys(lambda: (load_peers(tailscale_status()), ssh_config_blocks()), cfg, argv[1:])

    status = tailscale_status()
    peers = load_peers(status)
    blocks = ssh_config_blocks()

    if sub in ("list", "ls"):
        show_list(peers, cfg, blocks)
        return 0
    if sub == "set":
        cmd_set(peers, cfg, blocks, argv[1:])
        return 0
    if sub == "unset":
        cmd_unset(peers, cfg, blocks, argv[1:])
        return 0
    if sub == "export":
        cmd_export(peers, cfg, blocks)
        return 0
    if sub == "resolve":
        if len(argv) < 2:
            die("사용법: tssh resolve <이름>")
        peer = pick_one_or_die(peers, cfg, blocks, argv[1])
        st = host_settings(peer, cfg, blocks)
        target = peer["dns"] if cfg.get("use_magicdns") and peer["dns"] else peer["ip"]
        print(f"{st.get('user') or getpass.getuser()}@{target}")
        return 0
    if sub == "last":
        last = load_json(STATE_PATH).get("last_host")
        if not last:
            die("최근 접속 기록이 없습니다.")
        argv = [last] + argv[1:]

    opts = parse_connect_args(argv)
    if opts["host"] == "help":
        print(__doc__)
        return 0

    if opts["host"]:
        peer = pick_one_or_die(peers, cfg, blocks, opts["host"])
        return connect(peer, cfg, blocks, opts["extra"], opts["user"], opts["port"], opts["use_dns"], opts["dry_run"])

    if not sys.stdin.isatty():
        die("대화형 선택은 터미널에서만 됩니다. 'tssh <이름>' 으로 호스트를 지정하세요.")
    notice: list[str] = []
    background_update_check(cfg, notice)
    while True:
        chosen = pick_interactive(peers, cfg, blocks, notice)
        if chosen is None:
            return 0
        if chosen.get("__refresh__"):
            peers = load_peers(tailscale_status())
            blocks = ssh_config_blocks()
            continue
        ask_user_if_missing(chosen, cfg, blocks)
        return connect(chosen, cfg, blocks, opts["extra"], opts["user"], opts["port"], opts["use_dns"], opts["dry_run"])


if __name__ == "__main__":
    sys.exit(main())
