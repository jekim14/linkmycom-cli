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
"""

from __future__ import annotations

import difflib
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

__version__ = "0.1.2"

DEFAULT_REPO = "jekim14/tssh"
CONFIG_DIR = Path.home() / ".tssh"
CONFIG_PATH = CONFIG_DIR / "config.json"
STATE_PATH = CONFIG_DIR / "state.json"
SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"
MANAGED_BEGIN = "# >>> tssh managed (tssh export 가 생성, 직접 고치지 마세요) >>>"
MANAGED_END = "# <<< tssh managed <<<"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,253}$")
SUBCOMMANDS = {"list", "ls", "set", "unset", "resolve", "export", "config", "update", "version", "help", "last"}

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


def load_config() -> dict:
    cfg = load_json(CONFIG_PATH)
    cfg.setdefault("hosts", {})
    cfg.setdefault("use_magicdns", False)
    cfg.setdefault("auto_update_check", True)
    cfg.setdefault("update_repo", DEFAULT_REPO)
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


def replace_managed_block(text: str, block: str) -> str:
    pattern = re.compile(re.escape(MANAGED_BEGIN) + r".*?" + re.escape(MANAGED_END) + r"\n?", re.S)
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


def fetch_latest(repo: str, timeout: float = 5.0) -> tuple[str, str]:
    """(최신 태그, tssh.py 원문) 을 돌려준다. 실패하면 예외."""
    data = json.loads(http_get(f"https://api.github.com/repos/{repo}/releases/latest", timeout))
    tag = data.get("tag_name") or ""
    if not tag:
        raise RuntimeError("릴리스 태그를 찾지 못했습니다.")
    src = http_get(f"https://raw.githubusercontent.com/{repo}/{tag}/tssh.py", timeout).decode("utf-8")
    return tag, src


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
    print(f"저장소 {repo} 에서 최신 릴리스를 확인합니다...")
    try:
        tag, src = fetch_latest(repo, timeout=15)
    except Exception as e:  # noqa: BLE001
        die(f"릴리스를 가져오지 못했습니다: {e}\n저장소가 아직 없다면 'tssh config update_repo=<owner/repo>' 로 지정하세요.")
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
        try:
            tag, src = fetch_latest(cfg.get("update_repo") or DEFAULT_REPO, timeout=4)
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
        elif k in ("default_user", "update_repo"):
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
            die(f"알 수 없는 설정 키: {k} (가능: default_user, use_magicdns, update_repo, auto_update_check, ssh_options.<옵션>)")
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
