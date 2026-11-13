#!/usr/bin/env python3
# Tailscale 피어 목록에서 골라 SSH로 접속하는 명령줄 도구.
"""linkmycom - Tailscale SSH 접속기. 줄여서 lmc 로도 부르며, 옛 이름 tssh 도 이 명령으로 넘어온다.

사용법:
  linkmycom                          피어 목록을 보여 주고 골라서 접속
  linkmycom <이름> [ssh 인자...]      이름(일부만 입력해도 됨)으로 바로 접속
  linkmycom <사용자>@<이름>           사용자 이름을 지정해 접속
  linkmycom -u <사용자> -p <포트> <이름>   한 번만 쓰는 사용자·포트 지정
  linkmycom --dns <이름>              IP 대신 MagicDNS 이름으로 접속
  linkmycom -n <이름>                 실행할 ssh 명령만 출력 (dry-run)
  linkmycom last                      최근 접속한 호스트에 다시 접속

  linkmycom list                      피어 목록만 출력
  linkmycom set <이름> user=.. port=.. key=.. alias=.. args=..   호스트별 접속 설정 저장
  linkmycom unset <이름>              저장한 호스트 설정 삭제
  linkmycom resolve <이름>            user@주소 형태로 출력 (scp 등에 활용)
  linkmycom export                    ~/.ssh/config 에 linkmycom 관리 블록 기록
  linkmycom config [키=값 ...]        전역 설정 보기/변경 (default_user, use_magicdns, update_repo, auto_update_check)
  linkmycom update [--check]          거울의 최신 릴리스를 서명 확인 뒤 적용(--check: 확인만)
  linkmycom version                   버전 출력
  linkmycom help [명령]               도움말(명령을 주면 그 명령만)
  linkmycom completion powershell|bash|zsh   셸 자동 완성 스크립트 출력(호스트 이름은 list 캐시)
  linkmycom doctor [이름] [--all [--json]]   이 PC(또는 그 PC, --all: 온라인 PC 전부 병렬)의 Tailscale·sshd·방화벽·
                                 authorized_keys·버전·키 갱신 예약·화면공유 서비스 점검표
  linkmycom exec <이름|a,b|all> -- <명령...>   여러 PC 에 같은 명령을 병렬 실행([이름] 접두어, 하나라도 실패면 1)
  linkmycom fleet status | update [cli] [-n]   각 PC 의 CLI·타워·화면공유 버전 표 / 낡은 PC 만 원격 CLI 업데이트
  linkmycom send <파일...> --to <이름,...>     Taildrop 으로 파일 보내기(대상 병렬)
  linkmycom inbox [폴더] [--wait]     Taildrop 으로 받은 파일을 폴더(기본 Downloads)로 옮기기
  linkmycom forward <이름> <로컬:원격>    ssh -N -L 로 포트 잇기

  linkmycom setup [--no-server] [--no-keys] [--no-schedule]
                                 이 컴퓨터를 SSH 서버로 켜고(Tailscale 대역만 허용) 공개키를 교환하고
                                 하루 한 번 'keys refresh' 를 예약
  linkmycom keys [show|refresh [--force]]   내 공개키 보기 / 서명된 공개키 목록을 받아 authorized_keys 갱신
  linkmycom keys publish [--collect]  (관리 PC) 각 컴퓨터의 공개키를 모아 서명해 거울 저장소에 게시

  linkmycom screen <이름> [--gather] [--files|--terminal|--forward [로컬:원격]]
                                 LinkMyCom 화면공유 앱으로 그 PC 화면 보기(또는 파일 전송·터미널·포트 전달) 창을 연다
                                 (--gather: 그 PC 의 창을 주 모니터로 모으기를 함께 보냄)
                                 linkmycom set <이름> screen=<다른 이름> 으로 화면용 접속 대상을 따로 지정
  linkmycom display <이름|self> [list|gather|single|extend] [--minutes N]
                                 여러 모니터 PC 정리: 모니터 목록, 모든 창을 주 모니터로 모으기,
                                 주 모니터만 쓰기(N분 뒤 자동 복원, 기본 180), 원래대로 복원
  linkmycom password                  화면공유 영구 비밀번호를 내 모든 PC 에 한 번에 설정(직접 입력)
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# difflib·tempfile·threading·urllib.request·concurrent.futures 는 쓰는 함수 안에서 늦게 임포트한다(시작 시간 절약).

__version__ = "0.4.7"

# linkmycom(옛 tssh)은 LinkMyCom 저장소(jekim14/linkmycom, 비공개)의 tools/linkmycom 에서 개발하고, 공개 거울 저장소
# jekim14/linkmycom-cli(옛 jekim14/tssh)의 같은 경로로 배포한다. 거울은 옛 설치본을 위해 tools/tssh/ 에도 같은 파일을 둔다. 업데이트·공개키 목록·설치 스크립트는 인증 없이 받을 수 있는 거울에서 가져온다.
DEFAULT_REPO = "jekim14/linkmycom-cli"
# 설정 파일에 남아 있어도 raw 주소로 받을 수 없는 저장소 이름. 읽을 때 지워 기본 저장소를 쓰게 한다.
LEGACY_REPOS = {"jekim14/desktools", "jekim14/linkmycom", "jekim14/tssh"}
DEFAULT_UPDATE_REF = "HEAD"
DEFAULT_KEYS_PATH = "tools/linkmycom/authorized_keys"
# 공개키 목록과 CLI 릴리스 자산의 서명. 관리 PC(jekimlabtop)의 ~/.ssh/linkmycom-signing 으로 'ssh-keygen -Y sign' 한다.
# 받는 쪽은 아래 공개키 하나만 믿는다(allowed_signers 한 줄: "<SIGNER_IDENTITY> <SIGNING_PUBKEY>").
SIGNING_PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGWKhtP9dXCC5mljTV/5DOf42NzaQ7EUHRAo9B+bX0+s"
SIGNER_IDENTITY = "linkmycom"
KEYS_SIG_NAMESPACE = "linkmycom-keys"
CLI_SIG_NAMESPACE = "linkmycom-keys"
SIG_SUFFIX = ".sig"
# 거울 릴리스 자산 이름. linkmycom.py.sha256 은 "<16진 해시>  linkmycom.py" 한 줄(있으면 대조, 없어도 서명이 맞으면 진행).
CLI_ASSET = "linkmycom.py"
CLI_SIG_ASSET = CLI_ASSET + SIG_SUFFIX
CLI_SHA_ASSET = CLI_ASSET + ".sha256"
# keys publish 는 origin 이 이 거울일 때만 한다(Publish-Cli.ps1 과 같은 규칙).
MIRROR_ORIGIN_RE = re.compile(r"github\.com[/:]jekim14/(linkmycom-cli|tssh)(\.git)?/?$")
CONFIG_DIR = Path.home() / ".tssh"
CONFIG_PATH = CONFIG_DIR / "config.json"
STATE_PATH = CONFIG_DIR / "state.json"
SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"
MANAGED_BEGIN = "# >>> tssh managed (tssh export 가 생성, 직접 고치지 마세요) >>>"
MANAGED_END = "# <<< tssh managed <<<"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,253}$")
SUBCOMMANDS = {"list", "ls", "set", "unset", "resolve", "export", "config", "update", "version", "help", "last",
               "setup", "keys", "display", "screen", "password", "doctor", "completion",
               "send", "inbox", "exec", "fleet", "forward"}
HOSTS_CACHE_PATH = CONFIG_DIR / "hosts.txt"
SSH_DIR = Path.home() / ".ssh"
LOCAL_KEY = SSH_DIR / "id_ed25519"
SIGNING_KEY = SSH_DIR / "linkmycom-signing"
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


class TailscaleUnavailable(RuntimeError):
    """tailscale 상태를 전혀 얻지 못했다(soft 모드에서 die 대신 올린다)."""


def tailscale_status(soft: bool = False) -> dict:
    """여러 tailscale CLI 와 데몬 소켓 중 실제로 연결된(Running) 것을 고른다.

    macOS 처럼 Homebrew tailscaled 와 Tailscale.app 이 함께 있으면 CLI 가 로그인 안 된 쪽에 붙을 수 있다.
    그런 경우 유닉스 소켓의 LocalAPI 를 직접 읽어 연결된 데몬의 상태를 얻는다.
    soft 면 상태를 얻지 못했을 때 die 대신 TailscaleUnavailable 을 올린다(캐시로 물러설 때).
    """
    def fail(msg: str):
        if soft:
            raise TailscaleUnavailable(msg)
        die(msg)

    cands = tailscale_candidates()
    sockets = [] if os.name == "nt" else [p for p in TAILSCALED_SOCKETS if os.path.exists(p)]
    if not cands and not sockets:
        fail("tailscale 명령을 찾지 못했습니다. Tailscale이 설치되어 있는지 확인하세요.")
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
        fail("tailscale status 를 실행하지 못했습니다. Tailscale 서비스가 실행 중인지 확인하세요. "
             f"(시도한 경로: {', '.join(tried)})")
    if soft:
        raise TailscaleUnavailable(f"Tailscale 상태가 '{fallback.get('BackendState')}' 입니다")
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
                "cur_addr": raw.get("CurAddr") or "",
                "relay": raw.get("Relay") or "",
            }
        )
    peers.sort(key=lambda p: (not p["online"], p["name"].lower()))
    return peers


# 피어 목록 캐시. 'tailscale status' 가 명령마다 130ms 쯤 걸려 resolve·screen·접속은 45초 안의 캐시를 먼저 쓴다.
PEERS_CACHE_TTL = 45.0


def peers_cache_path() -> Path:
    """캐시 경로. 테스트가 CONFIG_DIR·HOSTS_CACHE_PATH 를 바꿔도 따라가도록 부를 때마다 계산한다."""
    return HOSTS_CACHE_PATH.with_name("peers.json")


def write_peers_cache(peers: list[dict], now: float | None = None) -> None:
    """peers.json(이름·IP·OS·online·CurAddr 등)과 자동 완성용 hosts.txt 를 쓴다. 실패해도 조용히 넘어간다."""
    data = {"time": time.time() if now is None else now, "version": __version__, "peers": peers}
    try:
        HOSTS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        replace_text(peers_cache_path(), json.dumps(data, ensure_ascii=False))
    except (OSError, TypeError, ValueError):
        pass
    write_hosts_cache(peers)


def read_peers_cache() -> tuple[list[dict], float] | None:
    """(피어 목록, 저장 시각). 없거나 깨졌으면 None."""
    try:
        with open(peers_cache_path(), encoding="utf-8") as f:
            data = json.load(f)
        peers = data["peers"]
        stamp = float(data["time"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(peers, list) or not all(isinstance(p, dict) and p.get("name") and "ip" in p for p in peers):
        return None
    for p in peers:  # 옛 캐시에 없던 키는 기본값으로 채운다.
        for k, v in (("hostname", ""), ("dns", ""), ("os", "?"), ("online", False), ("last_seen", ""),
                     ("ts_ssh", False), ("tags", []), ("cur_addr", ""), ("relay", "")):
            p.setdefault(k, v)
    return peers, stamp


def fresh_peers() -> list[dict]:
    """tailscale 에서 바로 읽고 캐시를 갱신한다. 상태가 Running 일 때만 캐시를 덮는다."""
    status = tailscale_status()
    peers = load_peers(status)
    if status.get("BackendState") == "Running" and peers:
        write_peers_cache(peers)
    else:
        write_hosts_cache(peers)
    return peers


def cached_peers(max_age: float = PEERS_CACHE_TTL, now: float | None = None) -> tuple[list[dict], bool]:
    """(피어 목록, 캐시에서 왔는지). 캐시가 max_age 초 안이면 그대로 쓰고, 아니면 tailscale 을 부른다.

    tailscale 을 부르지 못하면 만료된 캐시라도 경고와 함께 쓴다. 캐시도 없으면 예전처럼 die.
    """
    now = time.time() if now is None else now
    cache = read_peers_cache()
    if cache and 0 <= now - cache[1] < max_age:
        return cache[0], True
    try:
        status = tailscale_status(soft=True)
    except TailscaleUnavailable as e:
        if cache:
            warn(f"{e}. {int(now - cache[1])}초 전에 저장한 피어 목록을 씁니다(online 표시가 낡았을 수 있음).")
            return cache[0], True
        return fresh_peers(), False
    peers = load_peers(status)
    if peers:
        write_peers_cache(peers, now)
    return peers, False


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
    for k in ("user", "port", "key", "args", "alias", "screen"):
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
    import difflib

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


def split_args(text: str) -> list[str]:
    """'args=' 값을 셸처럼 나눈다. 따옴표로 묶은 공백은 한 인자로 둔다.

    Windows 에서는 역슬래시를 이스케이프로 보지 않는다(C:\\Users\\x\\key 같은 경로를 그대로 둔다).
    따옴표가 짝이 맞지 않으면 ValueError.
    """
    import shlex

    lex = shlex.shlex(text, posix=True)
    lex.whitespace_split = True
    lex.commenters = ""
    if os.name == "nt":
        lex.escape = ""
    return list(lex)


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
        try:
            args = split_args(args)
        except ValueError:
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
    print(f"저장했습니다. 바꾸려면: linkmycom set {peer['name']} user=<이름>")


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


def http_get(url: str, timeout: float = 5.0, headers: dict | None = None) -> bytes:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": f"linkmycom/{__version__}", "Accept": "*/*", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def repo_file_urls(repo: str, ref: str, path: str) -> list[tuple[str, dict]]:
    """저장소 파일을 받을 주소 목록. raw.githubusercontent 는 몇 분간 옛 내용을 주므로 캐시 없는 API 를 먼저 쓴다."""
    return [
        (f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}", {"Accept": "application/vnd.github.raw"}),
        (f"https://raw.githubusercontent.com/{repo}/{ref}/{path}", {}),
    ]


def fetch_repo_file(repo: str, ref: str, path: str, timeout: float = 5.0) -> bytes:
    """API → raw 순서로 시도해 처음 성공한 내용을 돌려준다. 모두 실패하면 마지막 예외를 다시 올린다."""
    last: Exception | None = None
    for url, headers in repo_file_urls(repo, ref, path):
        try:
            return http_get(url, timeout, headers)
        except Exception as e:  # noqa: BLE001
            last = e
    raise last if last else RuntimeError("받을 주소가 없습니다.")


def find_keygen() -> str | None:
    found = shutil.which("ssh-keygen")
    if not found and os.name == "nt":
        cand = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "OpenSSH", "ssh-keygen.exe")
        if os.path.exists(cand):
            found = cand
    return found


def verify_signature(data: bytes, sig: bytes, namespace: str, signer: str | None = None) -> tuple[bool, str]:
    """data 가 signer(기본 SIGNING_PUBKEY) 의 namespace 서명인지 'ssh-keygen -Y verify' 로 확인한다.

    die() 를 부르지 않는다(백그라운드 스레드에서도 쓴다). (성공 여부, 실패 사유) 를 돌려준다.
    받은 바이트 그대로 검증해야 하므로 data 는 디코드하지 않은 원본이어야 한다.
    """
    exe = find_keygen()
    if not exe:
        return False, "ssh-keygen 을 찾지 못했습니다(OpenSSH 클라이언트 필요)"
    if not sig or b"BEGIN SSH SIGNATURE" not in sig:
        return False, "서명 파일이 비었거나 형식이 아닙니다"
    import tempfile

    signer = (signer or SIGNING_PUBKEY).strip()
    with tempfile.TemporaryDirectory(prefix="linkmycom-verify-") as d:
        allowed = Path(d) / "allowed_signers"
        sig_path = Path(d) / "data.sig"
        allowed.write_bytes(f"{SIGNER_IDENTITY} {signer}\n".encode("ascii", "replace"))
        sig_path.write_bytes(sig)
        data_path = Path(d) / "data"
        data_path.write_bytes(data)
        # 파이프(input=)로 주면 Windows OpenSSH 세션 안의 ssh-keygen 이 끝까지 읽지 못해 30초를 다 쓴다
        # (officehermes, 2026-11-13: 파이프 20초 초과, 파일 리디렉션 78ms). 그래서 파일을 표준 입력으로 준다.
        try:
            with open(data_path, "rb") as fin:
                r = subprocess.run([exe, "-Y", "verify", "-f", str(allowed), "-I", SIGNER_IDENTITY, "-n", namespace,
                                    "-s", str(sig_path)], stdin=fin, capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, f"ssh-keygen 을 실행하지 못했습니다: {e}"
    if r.returncode == 0:
        return True, ""
    msg = (r.stderr + r.stdout).decode("utf-8", "replace").strip()
    low = msg.lower()
    if "unknown option" in low or "illegal option" in low or "usage:" in low:
        return False, "이 ssh-keygen 은 서명 검증(-Y verify)을 지원하지 않습니다(OpenSSH 8.1 이상 필요)"
    return False, "서명이 맞지 않습니다" + (f" ({msg.splitlines()[-1]})" if msg else "")


def latest_release(repo: str, timeout: float = 10.0) -> dict:
    """거울 저장소의 최신 GitHub 릴리스(비인증 API). 실패하면 예외."""
    data = http_get(f"https://api.github.com/repos/{repo}/releases/latest", timeout,
                    {"Accept": "application/vnd.github+json"})
    rel = json.loads(data.decode("utf-8"))
    if not isinstance(rel, dict) or not rel.get("tag_name"):
        raise RuntimeError(f"{repo} 의 최신 릴리스 정보를 읽지 못했습니다.")
    return rel


def release_asset_url(rel: dict, name: str) -> str | None:
    for asset in rel.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name") == name:
            return asset.get("browser_download_url")
    return None


def check_release_source(src: bytes, sig: bytes | None, sha_text: str | None = None,
                         signer: str | None = None) -> str:
    """받은 linkmycom.py 를 서명 → sha256 → 문법 → 버전 순으로 확인하고 버전을 돌려준다. 하나라도 어긋나면 RuntimeError."""
    import hashlib

    if not sig:
        raise RuntimeError(f"릴리스에 서명 파일 {CLI_SIG_ASSET} 이 없어 교체하지 않습니다.")
    ok, reason = verify_signature(src, sig, CLI_SIG_NAMESPACE, signer)
    if not ok:
        raise RuntimeError(f"{CLI_ASSET} 서명 확인 실패: {reason}. 교체하지 않습니다.")
    if sha_text:
        expected = (sha_text.strip().split() or [""])[0].lower()
        actual = hashlib.sha256(src).hexdigest()
        if expected != actual:
            raise RuntimeError(f"{CLI_ASSET} SHA256 이 {CLI_SHA_ASSET} 과 다릅니다. 교체하지 않습니다.")
    try:
        compile(src, CLI_ASSET, "exec")
    except (SyntaxError, ValueError) as e:
        raise RuntimeError(f"받은 {CLI_ASSET} 의 문법이 맞지 않습니다: {e}") from e
    version = version_in_source(src.decode("utf-8", "replace"))
    if not version:
        raise RuntimeError(f"받은 {CLI_ASSET} 에 버전이 없습니다.")
    return version


def fetch_release_source(repo: str, rel: dict, timeout: float = 30.0) -> tuple[bytes, str]:
    """릴리스 자산 linkmycom.py·.sig·.sha256 을 받아 확인한 (원본 바이트, 버전) 을 돌려준다."""
    py_url = release_asset_url(rel, CLI_ASSET)
    if not py_url:
        raise RuntimeError(f"{repo} 릴리스 {rel.get('tag_name')} 에 {CLI_ASSET} 자산이 없습니다.")
    src = http_get(py_url, timeout)
    sig_url = release_asset_url(rel, CLI_SIG_ASSET)
    sig = http_get(sig_url, timeout) if sig_url else None
    sha_url = release_asset_url(rel, CLI_SHA_ASSET)
    sha_text = http_get(sha_url, timeout).decode("utf-8", "replace") if sha_url else None
    return src, check_release_source(src, sig, sha_text)


def version_in_source(src: str) -> str:
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M)
    return m.group(1) if m else ""


def write_self(target: Path, src: str | bytes) -> None:
    """새 소스를 임시 파일에 쓰고 원본의 실행 권한을 그대로 옮긴 뒤 원자적으로 교체한다. 받은 바이트를 그대로 쓴다."""
    tmp = target.with_name(target.name + ".new")
    tmp.write_bytes(src if isinstance(src, bytes) else src.encode("utf-8"))
    try:
        shutil.copymode(target, tmp)
    except OSError:
        pass
    os.replace(tmp, target)


def update_target(here: Path) -> Path:
    """업데이트로 바꿀 파일. 옛 이름 파일이 넘김 파일이 됐으면 옆의 새 이름 파일을 바꾼다."""
    if here.name in LEGACY_NAMES:
        new = here.with_name("linkmycom.py" if here.suffix == ".py" else "linkmycom")
        if new.exists():
            return new
    return here


def cmd_update(cfg: dict, check_only: bool) -> int:
    repo = cfg.get("update_repo") or DEFAULT_REPO
    print(f"저장소 {repo} 의 최신 릴리스를 확인합니다...")
    try:
        rel = latest_release(repo, timeout=15)
    except Exception as e:  # noqa: BLE001
        die(f"최신 릴리스를 가져오지 못했습니다: {e}\n다른 저장소를 쓴다면 'linkmycom config update_repo=<owner/repo>' 로 지정하세요.")
    tag = rel["tag_name"]
    if parse_version(tag) <= parse_version(__version__):
        print(f"이미 최신입니다 (설치 {__version__}, 릴리스 {tag}).")
        return 0
    print(f"새 릴리스 {tag} 이(가) 있습니다. 현재 {__version__}.")
    if check_only:
        print("적용하려면: linkmycom update")
        return 0
    try:
        src, remote = fetch_release_source(repo, rel)
    except Exception as e:  # noqa: BLE001
        die(f"{e}")
    if parse_version(remote) <= parse_version(__version__):
        print(f"이미 최신입니다 (설치 {__version__}, 받은 파일 {remote}).")
        return 0
    print(f"서명 확인 완료({SIGNER_IDENTITY}, {CLI_SIG_NAMESPACE}).")
    target = update_target(Path(__file__).resolve())
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
            notice.append(f"새 버전 {state['update_available']} 이(가) 있습니다. 'linkmycom update' 로 적용하세요.")
        return None

    def work() -> None:
        if state.get("setup_done"):
            try:
                refresh_keys(cfg, quiet=True)  # 상태 파일에 갱신 기록을 남기므로 아래에서 다시 읽는다.
            except Exception:  # noqa: BLE001
                pass
        st = load_json(STATE_PATH)
        st["last_update_check"] = datetime.now(timezone.utc).isoformat()
        try:
            remote = latest_release(cfg.get("update_repo") or DEFAULT_REPO, timeout=4)["tag_name"].lstrip("v")
            if remote and parse_version(remote) > parse_version(__version__):
                st["update_available"] = remote
                notice.append(f"새 버전 {remote} 이(가) 있습니다. 'linkmycom update' 로 적용하세요.")
            else:
                st.pop("update_available", None)
        except Exception:  # noqa: BLE001
            pass
        try:
            save_json(STATE_PATH, st)
        except OSError:
            pass

    import threading

    t = threading.Thread(target=work, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------- 키 교환과 SSH 서버 설정 (linkmycom setup / keys).


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
    found = find_keygen()
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


def managed_keys_in(text: str) -> list[str]:
    """authorized_keys 내용에서 linkmycom 관리 블록 안의 키만 돌려준다."""
    m = re.search(re.escape(KEYS_BEGIN) + r"(.*?)" + re.escape(KEYS_END), text, re.S)
    return parse_keys(m.group(1)) if m else []


def keys_shrink_reason(old_count: int, received: int, new_count: int) -> str | None:
    """받은 목록을 적용하면 안 되는 이유. 괜찮으면 None.

    HTML 오류 페이지나 잘린 파일을 받아 키가 한꺼번에 지워지는 사고를 막는다. 빈 목록은 항상 거부하고,
    관리 블록의 키가 절반 이하로 줄면 거부한다(처음 등록할 때처럼 기존 블록이 비었으면 통과).
    """
    if received == 0:
        return "받은 목록에 공개키가 하나도 없습니다"
    if old_count > 0 and new_count * 2 <= old_count:
        return f"관리 블록의 공개키가 {old_count}개에서 {new_count}개로 절반 이하로 줄어듭니다"
    return None


class KeysRefused(RuntimeError):
    """받은 공개키 목록이 비었거나 크게 줄어 적용하지 않았다."""


def install_authorized_keys(keys: list[str], received: int | None = None, force: bool = False) -> int:
    """관리 블록에 keys 를 넣는다. 임시 파일에 쓴 뒤 교체한다. 목록이 비었거나 절반 이하로 줄면 KeysRefused."""
    try:
        existing = AUTHORIZED_KEYS.read_bytes().decode("utf-8")
    except FileNotFoundError:
        existing = ""
    new_text, count = merge_authorized_keys(existing, keys)
    received = len(keys) if received is None else received
    reason = keys_shrink_reason(len(managed_keys_in(existing)), received, count)
    if reason and (received == 0 or not force):
        raise KeysRefused(reason)
    if new_text != existing:
        SSH_DIR.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(SSH_DIR, 0o700)
        replace_keeping_acl(AUTHORIZED_KEYS, new_text)
    return count


def replace_keeping_acl(path: Path, text: str) -> None:
    """원자적으로 교체한다. Windows 는 ReplaceFileW 로 기존 파일의 ACL·소유자를 그대로 둔다.

    os.replace 는 새 파일의 ACL 을 폴더에서 물려받아, Add-SshUser 가 상속을 끊고 지정한 권한이 사라진다.
    """
    if os.name != "nt" or not path.exists():
        replace_text(path, text, 0o600 if os.name != "nt" else None)
        return
    import ctypes

    tmp = path.with_name(path.name + ".new")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not k32.ReplaceFileW(str(path), str(tmp), None, 0, None, None):
        os.replace(tmp, path)  # ReplaceFileW 를 못 쓰면(다른 볼륨 등) 원자적 교체만이라도 한다.


def keys_sources(cfg: dict) -> list[tuple[str, dict]]:
    """공개키 목록을 받을 주소 목록. 서명은 각 주소 뒤에 .sig 를 붙여 같은 곳에서 받는다."""
    if cfg.get("keys_url"):
        return [(cfg["keys_url"], {})]
    return repo_file_urls(cfg.get("update_repo") or DEFAULT_REPO, cfg.get("update_ref") or DEFAULT_UPDATE_REF,
                          DEFAULT_KEYS_PATH)


def sig_url_for(url: str) -> str:
    """목록 주소에 대응하는 서명 주소. API 주소의 ?ref= 앞에 .sig 를 넣는다."""
    base, sep, query = url.partition("?")
    return base + SIG_SUFFIX + sep + query


def fetch_remote_keys(cfg: dict, timeout: float = 10.0) -> list[str]:
    """서명이 맞는 공개키 목록을 받는다. 목록과 서명은 같은 주소에서 받고(API·raw 캐시가 섞이지 않게), 받은 바이트 그대로 검증한다.

    keys_url 로 다른 목록을 쓰면 그 주소 뒤 .sig 를 받아 keys_signer(없으면 내장 공개키)로 검증한다. 모두 실패하면 예외.
    """
    errors: list[str] = []
    for url, headers in keys_sources(cfg):
        try:
            data = http_get(url, timeout, headers)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{url}: {e}")
            continue
        try:
            sig = http_get(sig_url_for(url), timeout, headers)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{sig_url_for(url)}: 서명 파일을 받지 못함({e})")
            continue
        ok, reason = verify_signature(data, sig, KEYS_SIG_NAMESPACE, cfg.get("keys_signer"))
        if ok:
            return parse_keys(data.decode("utf-8", "replace"))
        errors.append(f"{url}: {reason}")
    raise RuntimeError("서명이 확인된 공개키 목록을 받지 못했습니다. " + " / ".join(errors))


def refresh_keys(cfg: dict, quiet: bool = False, force: bool = False) -> int:
    """서명된 공개키 목록을 받아 authorized_keys 관리 블록을 갱신한다. 실패하거나 거부하면 -1.

    force 는 '절반 이하로 줄어듦' 만 넘긴다(키를 일부러 많이 뺐을 때). 빈 목록은 force 로도 적용하지 않는다.
    """
    state = load_json(STATE_PATH)
    try:
        received = fetch_remote_keys(cfg)
        local = ensure_local_key() if LOCAL_KEY.exists() else ""
        keys = [k for k in received if k != local]
        count = install_authorized_keys(keys, received=len(received), force=force)
    except KeysRefused as e:
        state["last_keys_error"] = f"{datetime.now(timezone.utc).isoformat()} {e}"
        _save_state_quietly(state)
        if not quiet:
            warn(f"authorized_keys 를 바꾸지 않았습니다: {e}. 목록이 맞다면 'linkmycom keys refresh --force'.")
        return -1
    except Exception as e:  # noqa: BLE001
        state["last_keys_error"] = f"{datetime.now(timezone.utc).isoformat()} {e}"
        _save_state_quietly(state)
        if not quiet:
            warn(f"공개키 목록을 적용하지 못했습니다 ({keys_url(cfg)}): {e}")
        return -1
    state["last_keys_refresh"] = datetime.now(timezone.utc).isoformat()
    state["last_keys_count"] = count
    state.pop("last_keys_error", None)
    _save_state_quietly(state)
    if not quiet:
        print(f"서명 확인 후 authorized_keys 관리 블록에 공개키 {count}개를 등록했습니다 ({AUTHORIZED_KEYS}).")
    return count


def _save_state_quietly(state: dict) -> None:
    try:
        save_json(STATE_PATH, state)
    except OSError:
        pass


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
      $rel = Invoke-RestMethod -UseBasicParsing -Uri 'https://api.github.com/repos/PowerShell/Win32-OpenSSH/releases/latest' -Headers @{ 'User-Agent' = 'linkmycom' }
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
  # 100.64.0.0/10 overlaps carrier-grade NAT, so also bind the rule to the Tailscale interface when it exists.
  # Create the new rule first, then drop the old ones, so SSH is never left without an allow rule.
  $fw = @{ Direction = 'Inbound'; Protocol = 'TCP'; LocalPort = 22; RemoteAddress = @('100.64.0.0/10','fd7a:115c:a1e0::/48'); Action = 'Allow' }
  $tsIf = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.InterfaceDescription -like 'Tailscale*' } | Select-Object -First 1
  $old = Get-NetFirewallRule -Name 'tssh-OpenSSH' -ErrorAction SilentlyContinue
  Get-NetFirewallRule -Name 'tssh-OpenSSH-next' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  if ($tsIf -or -not $old) {
    if ($tsIf) { $fw.InterfaceAlias = $tsIf.Name; Write-Host "SSH rule bound to interface '$($tsIf.Name)'." }
    else { Write-Host 'Tailscale interface not found; the SSH rule allows Tailscale addresses on any interface.' }
    New-NetFirewallRule -Name 'tssh-OpenSSH-next' -DisplayName 'OpenSSH Server (Tailscale only, tssh)' @fw | Out-Null
    Get-NetFirewallRule -DisplayName 'OpenSSH*' -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'tssh-OpenSSH-next' } | Remove-NetFirewallRule
    Rename-NetFirewallRule -Name 'tssh-OpenSSH-next' -NewName 'tssh-OpenSSH'
  } else {
    Write-Host 'Tailscale interface not found; the existing tssh-OpenSSH rule is left unchanged.'
    Get-NetFirewallRule -DisplayName 'OpenSSH*' -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne 'tssh-OpenSSH' } | Remove-NetFirewallRule
  }
  Restart-Service sshd
  Write-Host 'TSSH_SETUP_OK'
} catch {
  Write-Host "TSSH_SETUP_FAIL: $($_.Exception.Message)"
} finally {
  Stop-Transcript | Out-Null
}
"""


def setup_server_windows() -> bool:
    import tempfile

    log = Path(tempfile.gettempdir()) / "linkmycom-setup.log"
    script = Path(tempfile.gettempdir()) / "linkmycom-setup.ps1"
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


# 하루 한 번 'linkmycom keys refresh --quiet' 예약. 이름은 고정이라 setup 을 다시 해도 하나만 남는다.
SCHEDULE_TASK_NAME = "LinkMyCom-KeysRefresh"
LAUNCHD_LABEL = "com.linkmycom.keys-refresh"
SYSTEMD_UNIT = "linkmycom-keys"


def refresh_command(python: str, script: str) -> list[str]:
    return [python, script, "keys", "refresh", "--quiet"]


def ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def schedule_windows_ps(python: str, script: str) -> str:
    """현재 사용자로 매일 도는 예약 작업을 등록하는 PowerShell(display 의 예약 작업과 같은 cmdlet). 관리자 권한은 쓰지 않는다.

    한글 경로가 깨지지 않도록 파일로 쓰지 않고 -EncodedCommand(UTF-16) 로 넘긴다.
    """
    arg = subprocess.list2cmdline(refresh_command(python, script)[1:])
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"$act = New-ScheduledTaskAction -Execute {ps_quote(python)} -Argument {ps_quote(arg)}",
        "$trg = New-ScheduledTaskTrigger -Daily -At '09:00' -RandomDelay (New-TimeSpan -Minutes 60)",
        "$set = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-ExecutionTimeLimit (New-TimeSpan -Minutes 10)",
        f"Register-ScheduledTask -TaskName {ps_quote(SCHEDULE_TASK_NAME)} -Action $act -Trigger $trg -Settings $set "
        "-Description 'linkmycom keys refresh (daily)' -Force | Out-Null",
        "'LMC_SCHEDULE_OK'",
    ]) + "\n"


def launchd_plist(python: str, script: str, log: str) -> bytes:
    import plistlib

    return plistlib.dumps({
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": refresh_command(python, script),
        "StartCalendarInterval": {"Hour": 9, "Minute": 0},
        "RunAtLoad": False,
        "StandardOutPath": log,
        "StandardErrorPath": log,
    })


def systemd_units(python: str, script: str) -> tuple[str, str]:
    """(서비스, 타이머) 내용. systemd 의 ExecStart 는 공백 있는 인자를 큰따옴표로 묶는다."""
    exec_start = " ".join('"' + a.replace('"', '\\"') + '"' if (" " in a or '"' in a) else a
                          for a in refresh_command(python, script))
    service = ("[Unit]\nDescription=linkmycom keys refresh\n\n"
               f"[Service]\nType=oneshot\nExecStart={exec_start}\n")
    timer = ("[Unit]\nDescription=linkmycom keys refresh (daily)\n\n"
             "[Timer]\nOnCalendar=daily\nRandomizedDelaySec=1h\nPersistent=true\n\n"
             "[Install]\nWantedBy=timers.target\n")
    return service, timer


def schedule_python() -> str:
    """예약 실행에 쓸 파이썬. Windows 는 창이 뜨지 않게 옆의 pythonw.exe 를 쓴다."""
    exe = sys.executable
    if os.name == "nt":
        w = Path(exe).with_name("pythonw.exe")
        if w.exists():
            return str(w)
    return exe


def schedule_keys_refresh() -> bool:
    """하루 한 번 'keys refresh' 를 예약한다(Windows 예약 작업, macOS launchd, Linux systemd 사용자 타이머)."""
    python = schedule_python()
    script = str(update_target(Path(__file__).resolve()))
    system = platform.system()
    try:
        if system == "Windows":
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand",
                                encode_ps(schedule_windows_ps(python, script))],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            ok = "LMC_SCHEDULE_OK" in r.stdout
            if not ok:
                warn("키 자동 갱신 예약 작업을 만들지 못했습니다: " + (r.stderr.strip().splitlines() or ["?"])[-1])
            return ok
        if system == "Darwin":
            agents = Path.home() / "Library" / "LaunchAgents"
            agents.mkdir(parents=True, exist_ok=True)
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            plist = agents / f"{LAUNCHD_LABEL}.plist"
            plist.write_bytes(launchd_plist(python, script, str(CONFIG_DIR / "keys-refresh.log")))
            subprocess.run(["launchctl", "unload", str(plist)], capture_output=True, timeout=30)
            return subprocess.run(["launchctl", "load", "-w", str(plist)], capture_output=True, timeout=30).returncode == 0
        if system == "Linux":
            if not shutil.which("systemctl"):
                warn("systemctl 이 없어 키 자동 갱신을 예약하지 못했습니다. cron 에 'linkmycom keys refresh --quiet' 를 넣으세요.")
                return False
            unit_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user"
            unit_dir.mkdir(parents=True, exist_ok=True)
            service, timer = systemd_units(python, script)
            (unit_dir / f"{SYSTEMD_UNIT}.service").write_text(service, encoding="utf-8")
            (unit_dir / f"{SYSTEMD_UNIT}.timer").write_text(timer, encoding="utf-8")
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=30)
            return subprocess.run(["systemctl", "--user", "enable", "--now", f"{SYSTEMD_UNIT}.timer"],
                                  capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired) as e:
        warn(f"키 자동 갱신을 예약하지 못했습니다: {e}")
        return False
    return False


def cmd_setup(cfg: dict, args: list[str]) -> int:
    """이 컴퓨터를 tailnet 안에서 SSH 로 들어올 수 있게 만들고 공개키를 교환한다."""
    no_server = "--no-server" in args
    no_keys = "--no-keys" in args
    print(c("linkmycom setup: 이 컴퓨터를 SSH 로 묶습니다.", "1"))
    pub = ensure_local_key()
    print(f"이 컴퓨터의 공개키: {pub[:40]}...")
    if not no_keys:
        refresh_keys(cfg)
        if "--no-schedule" not in args:
            if schedule_keys_refresh():
                print("하루 한 번 공개키 목록을 자동으로 받도록 예약했습니다(keys refresh).")
            else:
                warn("키 자동 갱신 예약을 건너뜁니다. 대화형 실행 때 하루 한 번 확인은 그대로 합니다.")
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
        print(c("완료. 이제 다른 기기에서 'linkmycom <이 컴퓨터 이름>' 으로 들어올 수 있습니다.", "32"))
        print("이 컴퓨터의 공개키를 저장소 목록에 올리려면 관리 PC 에서 'linkmycom keys publish --collect' 를 실행하세요.")
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
            reason = (r.stderr or "").strip().splitlines()[-1:] or ["공개키 없음 (linkmycom setup 미실행)"]
            print(f"  {p['name']}: 실패 - {reason[0]}")
            continue
        found.append((p["name"], keys[0]))
        print(f"  {p['name']}: {keys[0][:40]}...")
    return found


def repo_dir(cfg: dict) -> Path:
    """LinkMyCom 저장소 복제본의 루트. 설정값, 이 파일의 위치(tools/linkmycom/linkmycom.py) 순으로 찾는다."""
    d = cfg.get("repo_dir")
    if d and (Path(d) / ".git").exists():
        return Path(d)
    here = Path(__file__).resolve()
    for cand in (here.parent, here.parents[2] if len(here.parents) > 2 else here.parent):
        if (cand / ".git").exists():
            return cand
    die("저장소 복제본 위치를 모릅니다. 'linkmycom config repo_dir=<linkmycom 클론 경로>' 로 지정하세요.")


def keys_file(cfg: dict) -> Path:
    """저장소 안의 공개키 목록 파일 경로."""
    rd = repo_dir(cfg)
    nested = rd / DEFAULT_KEYS_PATH
    return nested if nested.parent.is_dir() else rd / "authorized_keys"


def git_origin(rd: Path) -> str:
    try:
        r = subprocess.run(["git", "-C", str(rd), "remote", "get-url", "origin"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def is_mirror_origin(url: str) -> bool:
    return bool(MIRROR_ORIGIN_RE.search(url.strip()))


def sign_bytes(data: bytes, key: Path, namespace: str) -> bytes:
    """'ssh-keygen -Y sign' 으로 data 의 서명(armored)을 만든다. 실패하면 die."""
    try:
        r = subprocess.run([keygen_bin(), "-Y", "sign", "-f", str(key), "-n", namespace], input=data,
                           capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        die(f"서명하지 못했습니다: {e}")
    if r.returncode != 0 or b"BEGIN SSH SIGNATURE" not in r.stdout:
        die("서명하지 못했습니다: " + r.stderr.decode("utf-8", "replace").strip())
    return r.stdout


def git_show_bytes(rd: Path, rev_path: str) -> bytes:
    r = subprocess.run(["git", "-C", str(rd), "show", rev_path], capture_output=True, timeout=30)
    if r.returncode != 0:
        die(f"git show {rev_path} 실패: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout


def cmd_keys(peers_loader, cfg: dict, args: list[str]) -> int:
    sub = args[0] if args else "show"
    if sub == "show":
        print(ensure_local_key())
        return 0
    if sub == "refresh":
        return 0 if refresh_keys(cfg, quiet="--quiet" in args, force="--force" in args) >= 0 else 1
    if sub in ("collect", "publish"):
        rd = repo_dir(cfg)
        origin = git_origin(rd)
        if not is_mirror_origin(origin):
            die(f"{rd} 의 origin 이 거울 저장소 jekim14/linkmycom-cli 가 아닙니다: {origin or '(없음)'}\n"
                "'linkmycom config repo_dir=<linkmycom-cli 클론 경로>' 로 거울 클론을 지정하세요.")
        if sub == "publish" and not SIGNING_KEY.exists():
            die(f"서명키 {SIGNING_KEY} 가 없습니다. 공개키 목록은 관리 PC 의 서명키로만 게시합니다.")
        target = keys_file(cfg)
        existing = target.read_bytes().decode("utf-8") if target.exists() else ""
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
        header = "# linkmycom 가 관리하는 tailnet 공개키 목록. 각 기기의 'linkmycom setup' / 'linkmycom keys refresh' 가 이 파일을 받아 authorized_keys 에 넣는다.\n"
        text = header + "\n".join(entries) + "\n"
        data = text.encode("utf-8")  # 서명한 바이트와 게시되는 바이트가 같도록 LF 그대로 쓴다.
        target.write_bytes(data)
        print(f"{target}: 공개키 {len(entries)}개")
        if sub == "publish":
            sig_path = target.with_name(target.name + SIG_SUFFIX)
            old_sig = sig_path.read_bytes() if sig_path.exists() else b""
            sig_ok = bool(old_sig) and verify_signature(data, old_sig, KEYS_SIG_NAMESPACE)[0]
            if text == existing and sig_ok:
                print("바뀐 내용이 없습니다(서명도 맞음).")
                return 0
            sig = sign_bytes(data, SIGNING_KEY, KEYS_SIG_NAMESPACE)
            ok, reason = verify_signature(data, sig, KEYS_SIG_NAMESPACE)
            if not ok:
                die(f"새 서명이 내장 공개키로 확인되지 않습니다({reason}). {SIGNING_KEY} 가 맞는 서명키인지 확인하세요.")
            sig_path.write_bytes(sig)
            rel = str(target.relative_to(rd)).replace("\\", "/")
            rel_sig = rel + SIG_SUFFIX
            if subprocess.run(["git", "-c", "core.autocrlf=false", "add", rel, rel_sig], cwd=rd).returncode != 0:
                die(f"실패: git add {rel} {rel_sig}")
            # core.autocrlf 로 작업 폴더만 CRLF 였던 경우 등, 다시 쓰고 서명해도 커밋할 바이트가 같으면 끝낸다
            # (ed25519 서명은 같은 내용이면 같은 바이트다).
            if subprocess.run(["git", "diff", "--cached", "--quiet", "--", rel, rel_sig], cwd=rd).returncode == 0:
                print("바뀐 내용이 없습니다(커밋된 목록·서명과 같음).")
                return 0
            cmd = ["git", "-c", "core.autocrlf=false", "commit", "-q", "-m", "keys: tailnet 공개키 목록 갱신(서명)"]
            if subprocess.run(cmd, cwd=rd).returncode != 0:
                die(f"실패: {' '.join(cmd)}")
            # 커밋된 바이트로 다시 확인한다. 줄바꿈 변환 등으로 어긋나면 올리지 않는다.
            ok, reason = verify_signature(git_show_bytes(rd, f"HEAD:{rel}"), git_show_bytes(rd, f"HEAD:{rel_sig}"),
                                          KEYS_SIG_NAMESPACE)
            if not ok:
                die(f"커밋된 목록의 서명이 맞지 않아 푸시하지 않습니다({reason}). 'git -C {rd} reset HEAD~1' 로 되돌리고 확인하세요.")
            if subprocess.run(["git", "push", "-q"], cwd=rd).returncode != 0:
                die("실패: git push")
            print(f"서명해 게시했습니다. 각 기기는 하루 안에 자동으로 받거나 'linkmycom keys refresh' 로 바로 받습니다.\n{keys_url(cfg)}")
        return 0
    die("사용법: linkmycom keys [show|refresh [--force]|collect|publish [--collect]]")


# ---------------------------------------------------------------- 화면 보기와 여러 모니터 도우미 (screen / display / password).

DISPLAY_ACTIONS = ("list", "gather", "single", "extend")
# 화면공유 앱의 도우미 스크립트. 새 이름을 먼저 보고, 아직 옛 DeskTools 로 설치된 PC 면 옛 경로를 쓴다.
REMOTE_DISPLAY_SCRIPT = r"C:\Program Files\LinkMyCom\LinkMyCom-Display.ps1"
LEGACY_DISPLAY_SCRIPT = r"C:\Program Files\DeskTools\DeskTools-Display.ps1"


def display_remote_ps(action: str, minutes: int) -> str:
    """원격 Windows 의 로그인 사용자 데스크톱에서 LinkMyCom-Display.ps1 을 실행하고 결과를 출력하는 PowerShell."""
    if action not in DISPLAY_ACTIONS:
        raise ValueError(action)
    minutes = max(5, min(int(minutes), 24 * 60))
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$script = '{REMOTE_DISPLAY_SCRIPT}'",
        f"if (-not (Test-Path $script)) {{ $script = '{LEGACY_DISPLAY_SCRIPT}' }}",
        "if (-not (Test-Path $script)) { 'LinkMyCom-Display.ps1 is not installed on this PC (run Install-NativeHost).'; exit 2 }",
        "$user = (Get-CimInstance Win32_ComputerSystem).UserName",
        "if (-not $user) { 'Nobody is signed in on this PC.'; exit 3 }",
        "$dir = Join-Path $env:ProgramData 'LinkMyCom'; New-Item -ItemType Directory -Force -Path $dir | Out-Null",
        "$out = Join-Path $dir ('display-' + [guid]::NewGuid().ToString('N') + '.txt')",
        f"$arg = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \"' + $script + '\" -Action {action} "
        f"-RestoreMinutes {minutes} -Out \"' + $out + '\"'",
        "$act = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg",
        "$pr = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest",
        "$name = 'LinkMyCom-Display-' + [guid]::NewGuid().ToString('N').Substring(0, 8)",
        "Register-ScheduledTask -TaskName $name -Action $act -Principal $pr -Force | Out-Null",
        "Start-ScheduledTask -TaskName $name",
        "$deadline = (Get-Date).AddSeconds(60)",
        "while ((Get-Date) -lt $deadline -and -not (Test-Path $out)) { Start-Sleep -Milliseconds 500 }",
        "Unregister-ScheduledTask -TaskName $name -Confirm:$false",
        "if (Test-Path $out) { Get-Content $out -Encoding UTF8; Remove-Item $out } else { 'No result within 60 s.'; exit 4 }",
    ]
    return "\n".join(lines) + "\n"


def encode_ps(script: str) -> str:
    import base64

    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def find_local_file(*candidates) -> str | None:
    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    return None


def portable_exe(local: str, root: str, exe: str) -> str | None:
    """휴대용 설치(%LOCALAPPDATA%\\<root>)의 활성 버전 실행 파일. 기록이 없거나 깨졌으면 None."""
    cur = os.path.join(local, root, "current.json")
    if not local or not os.path.exists(cur):
        return None
    try:
        with open(cur, encoding="utf-8") as f:
            ver = json.load(f).get("version", "")
        return os.path.join(local, root, "versions", ver, exe)
    except (OSError, ValueError):
        return None


def screen_app_exe() -> str | None:
    """화면공유 앱 실행 파일. LinkMyCom 을 먼저, 아직 바꾸지 않은 PC 의 DeskTools·RustDesk 를 그다음에 찾는다."""
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    local = os.environ.get("LOCALAPPDATA", "")
    return find_local_file(os.path.join(pf, "LinkMyCom", "linkmycom.exe"),
                           portable_exe(local, "LinkMyComNative", "linkmycom.exe"),
                           os.path.join(pf, "DeskTools", "desktools.exe"),
                           portable_exe(local, "DeskToolsNative", "desktools.exe"),
                           os.path.join(pf, "RustDesk", "rustdesk.exe"),
                           "/Applications/LinkMyCom.app/Contents/MacOS/LinkMyCom",
                           "/Applications/RustDesk.app/Contents/MacOS/RustDesk")


def parse_minutes(args: list[str], default: int = 180) -> tuple[list[str], int]:
    rest, minutes, i = [], default, 0
    while i < len(args):
        if args[i] in ("--minutes", "-m") and i + 1 < len(args):
            try:
                minutes = int(args[i + 1])
            except ValueError:
                die(f"--minutes 에는 숫자를 쓰세요: {args[i + 1]}")
            i += 2
            continue
        rest.append(args[i])
        i += 1
    return rest, minutes


def cmd_display(peers: list[dict], cfg: dict, blocks: list[dict], args: list[str]) -> int:
    args, minutes = parse_minutes(args)
    if not args:
        die("사용법: linkmycom display <이름|self> [list|gather|single|extend] [--minutes N]")
    action = args[1] if len(args) > 1 else "list"
    if action not in DISPLAY_ACTIONS:
        die(f"알 수 없는 동작 {action}. 가능: {', '.join(DISPLAY_ACTIONS)}")
    if args[0] in ("self", "local", "."):
        if os.name != "nt":
            die("display 는 Windows PC 에서만 씁니다.")
        script = find_local_file(REMOTE_DISPLAY_SCRIPT, str(Path(__file__).with_name("LinkMyCom-Display.ps1")),
                                 LEGACY_DISPLAY_SCRIPT)
        if not script:
            die("LinkMyCom-Display.ps1 을 찾지 못했습니다.")
        return subprocess.call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
                                "-Action", action, "-RestoreMinutes", str(minutes)])
    peer = pick_one_or_die(peers, cfg, blocks, args[0])
    if peer["os"] != "windows":
        die(f"{peer['name']} 은(는) Windows 가 아닙니다. display 는 Windows PC 에서만 씁니다.")
    settings = host_settings(peer, cfg, blocks)
    cmd = build_ssh_cmd(peer, settings, cfg, ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"], ssh_path=ssh_bin())
    cmd.append("powershell -NoProfile -EncodedCommand " + encode_ps(display_remote_ps(action, minutes)))
    print(c(f"→ {peer['name']} display {action}", "36"))
    return subprocess.call(cmd)


# lmc screen 의 세션 종류 → 화면공유 앱 명령줄 스위치(딥링크 linkmycom://connect|file-transfer|terminal|port-forward 와 같은 동작).
SCREEN_MODES = {"--files": "--file-transfer", "--terminal": "--terminal", "--forward": "--port-forward"}
SCREEN_USAGE = "사용법: linkmycom screen <이름> [--gather] [--files | --terminal | --forward [로컬:원격]]"


def parse_screen_args(args: list[str]) -> tuple[list[str], bool, str, str | None]:
    """(나머지 인자, gather, 앱 스위치, --forward 에 준 '로컬:원격') 을 돌려준다."""
    rest: list[str] = []
    gather, switch, spec = False, "--connect", None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--gather":
            gather = True
        elif a in SCREEN_MODES:
            if switch != "--connect" and switch != SCREEN_MODES[a]:
                die("--files·--terminal·--forward 는 하나만 쓰세요.")
            switch = SCREEN_MODES[a]
            if a == "--forward" and i + 1 < len(args) and re.match(r"^\d+:", args[i + 1]):
                spec = args[i + 1]
                i += 1
        else:
            rest.append(a)
        i += 1
    return rest, gather, switch, spec


def cmd_screen(peers: list[dict], cfg: dict, blocks: list[dict], args: list[str]) -> int:
    args, gather, switch, spec = parse_screen_args(args)
    if not args:
        die(SCREEN_USAGE)
    peer = pick_one_or_die(peers, cfg, blocks, args[0])
    gather_thread = None
    if gather and peer["os"] == "windows":
        # 모으기(최대 60초)를 기다리지 않고 뷰어를 먼저 띄운다. 스레드는 끝까지 기다려 원격 예약 작업이 남지 않게 한다.
        import threading

        gather_thread = threading.Thread(target=lambda: _gather_quietly(peers, cfg, blocks, peer["name"]))
        gather_thread.start()
    # 한 컴퓨터에 Tailscale 이 두 개 떠 있는 경우처럼 화면 접속만 다른 노드로 해야 할 때 screen= 설정을 따른다.
    alt = host_settings(peer, cfg, blocks).get("screen")
    if alt:
        found = resolve(peers, alt, cfg, blocks)
        if len(found) == 1:
            peer = found[0]
        else:
            warn(f"screen={alt} 에 맞는 피어가 {len(found)}개라 {peer['name']} 으로 접속합니다.")
    exe = screen_app_exe()
    if not exe:
        die("화면공유 앱(DeskTools 또는 RustDesk) 실행 파일을 찾지 못했습니다. LinkMyCom 설치기를 먼저 실행하세요.")
    if not peer["online"]:
        warn(f"{peer['name']} 은(는) 오프라인으로 표시됩니다.")
    kind = {"--connect": "화면 보기", "--file-transfer": "파일 전송", "--terminal": "터미널",
            "--port-forward": "포트 전달"}[switch]
    print(c(f"→ {kind} {peer['name']} ({peer['ip']})", "36") + f"  {exe}")
    if spec:
        # 앱의 포트 전달 창은 명령줄로 규칙을 받지 않는다. 창에서 직접 넣거나 SSH 로 바로 잇는 lmc forward 를 안내한다.
        lp, _, rp = spec.partition(":")
        print(f"  포트 전달 창에서 로컬 {lp} → 원격 {rp} 를 추가하세요. SSH 로 바로 이으려면: linkmycom forward {peer['name']} {spec}")
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([exe, switch, peer["ip"]], **kwargs)
    if gather_thread is not None:
        gather_thread.join()
    return 0


def _gather_quietly(peers: list[dict], cfg: dict, blocks: list[dict], name: str) -> None:
    """screen --gather 의 백그라운드 모으기. die(SystemExit) 가 나도 뷰어 쪽을 흔들지 않는다."""
    try:
        cmd_display(peers, cfg, blocks, [name, "gather"])
    except SystemExit:
        pass
    except Exception as e:  # noqa: BLE001
        warn(f"창 모으기를 하지 못했습니다: {e}")


def cmd_password() -> int:
    if os.name != "nt":
        die("password 는 Windows PC 에서 실행하세요(Mac 도 함께 설정합니다).")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    script = find_local_file(os.path.join(pf, "LinkMyCom", "Set-LinkMyComPassword.ps1"),
                             str(Path(__file__).with_name("Set-LinkMyComPassword.ps1")),
                             os.path.join(pf, "DeskTools", "Set-DeskToolsPassword.ps1"))
    if not script:
        die("Set-LinkMyComPassword.ps1 을 찾지 못했습니다.")
    return subprocess.call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script])


# ---------------------------------------------------------------- 점검 (doctor).

# 이 PC 와 원격 PC 에서 똑같이 실행하는 점검 스크립트. 원격에는 압축·base64 로 명령줄에 실어 보낸다.
# 원격 셸·코드 페이지에 흔들리지 않게 ASCII 만 쓰고, 결과는 "LMCDOC|이름|상태|내용" 줄로 낸다(표는 부른 쪽에서 그린다).
# 인자: 확인할 내 공개키의 base64 부분(없으면 그 항목을 건너뜀), '--versions'(버전 줄만, fleet status 용).
# 파이썬 3.6 이상에서 돈다. Windows 는 PowerShell 점검(sshd·방화벽·키 권한·화면공유 서비스·타워)을 한 번에 묶어
# 맨 먼저 띄워 두고, 그동안 tailscale·포트·파일 점검을 한 뒤 결과를 모아 정해진 순서로 낸다.
DOCTOR_PY = r'''
import json, os, re, shutil, socket, subprocess, sys, time
ARGS = sys.argv[1:]
ONLY_VERSIONS = "--versions" in ARGS
KEY = ([a for a in ARGS if not a.startswith("--")] + [""])[0]
WIN = os.name == "nt"
MAC = sys.platform == "darwin"
HOME = os.path.expanduser("~")
PFX = ("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-", "sk-ssh-ed25519@", "sk-ecdsa-sha2-")
LAD = os.environ.get("LOCALAPPDATA", "")
AK = os.path.join(HOME, ".ssh", "authorized_keys")
TASK = "LinkMyCom-KeysRefresh"
LAUNCHD = "com.linkmycom.keys-refresh"
UNIT = "linkmycom-keys"
PIPE = subprocess.PIPE

def out(name, status, detail=""):
    d = " ".join(str(detail).replace("|", "/").split())[:200]
    print("LMCDOC|%s|%s|%s" % (name, status, d.encode("ascii", "backslashreplace").decode("ascii")))
    sys.stdout.flush()

def start(cmd):
    try:
        return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=PIPE, stderr=PIPE)
    except Exception:
        return None

def finish(p, timeout=60):
    if p is None:
        return -1, ""
    try:
        o, _ = p.communicate(timeout=timeout)
    except Exception as e:
        try:
            p.kill()
        except Exception:
            pass
        return -1, str(e)
    return p.returncode, o.decode("utf-8", "replace").strip()

def run(cmd, timeout=25):
    return finish(start(cmd), timeout)

def read(path):
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except (OSError, TypeError):
        return None

def ver_in(path):
    m = re.search(r'(?m)^__version__\s*=\s*"([^"]+)"', read(path) or "")
    return m.group(1) if m else ""

def short(path):
    return ("~" + path[len(HOME):]) if HOME and path.lower().startswith(HOME.lower()) else path

PSP = TASKP = NETP = None
if WIN and not ONLY_VERSIONS:
    q = AK.replace("'", "''")
    PSP = start(["powershell", "-NoProfile", "-NonInteractive", "-Command", "\n".join([
        "$ErrorActionPreference = 'SilentlyContinue'",
        "'SSHD;' + (Get-Service sshd).Status",
        "$r = Get-NetFirewallRule -Name 'tssh-OpenSSH','tssh-OpenSSH-next' | Select-Object -First 1",
        "if (-not $r) { 'FW;NONE' } else { 'FW;RULE;' + $r.Name + ';' + $r.Enabled + ';' + "
        "(@(($r | Get-NetFirewallInterfaceFilter).InterfaceAlias) -join ',') + ';' + "
        "(@(($r | Get-NetFirewallAddressFilter).RemoteAddress) -join ',') }",
        "if (Test-Path -LiteralPath '%s') { $bad = @('S-1-1-0','S-1-5-32-545','S-1-5-11'); $w = @(); "
        "foreach ($a in (Get-Acl -LiteralPath '%s').Access) { try { $sid = $a.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { continue }; "
        "if ($a.AccessControlType -eq 'Allow' -and $bad -contains $sid -and $a.FileSystemRights.ToString() -match 'Write|Modify|FullControl') { $w += $sid } }; "
        "if ($w.Count) { 'ACL;BAD;' + ($w -join ',') } else { 'ACL;OK' } } else { 'ACL;MISSING' }" % (q, q),
        "$v = Get-Service LinkMyCom; if (-not $v) { $v = Get-Service DeskTools }",
        "if ($v) { 'SVC;' + $v.Name + ';' + $v.Status } else { 'SVC;' }",
        "'TOWER;' + [bool](Get-Process ime-probe)",
    ])])
    TASKP = start(["schtasks", "/Query", "/TN", TASK])
    NETP = start(["netstat", "-an", "-p", "TCP"])

if not ONLY_VERSIONS:
    st = {}
    cands = [shutil.which("tailscale") or "", r"C:\Program Files\Tailscale\tailscale.exe",
             "/Applications/Tailscale.app/Contents/MacOS/Tailscale", "/usr/local/bin/tailscale",
             "/opt/homebrew/bin/tailscale", "/usr/bin/tailscale"]
    for exe in [c for c in cands if c and os.path.exists(c)]:
        rc, o = run([exe, "status", "--json"])
        try:
            st = json.loads(o) if rc == 0 else {}
        except ValueError:
            st = {}
        if st.get("BackendState") == "Running":
            break
    me = st.get("Self") or {}
    if st.get("BackendState") == "Running":
        out("tailscale", "OK", "%s %s" % ((me.get("DNSName") or "").split(".")[0], " ".join((me.get("TailscaleIPs") or [])[:1])))
    else:
        out("tailscale", "FAIL", st.get("BackendState") or "tailscale not found or not running")

    try:
        socket.create_connection(("127.0.0.1", 22), 0.5).close()
        out("ssh_port", "OK", "127.0.0.1:22 open")
    except OSError:
        if me.get("sshHostKeys"):
            out("ssh_port", "OK", "Tailscale SSH")
        else:
            out("ssh_port", "FAIL", "nothing listens on port 22")

    PS = {}
    if WIN:
        for line in finish(PSP, 90)[1].splitlines():
            k, _, v = line.strip().partition(";")
            PS.setdefault(k, v)
        o = PS.get("SSHD", "")
        out("sshd", "OK" if o == "Running" else "FAIL", o or "sshd service missing")
        o = PS.get("FW", "")
        p = o.split(";")
        if p[0] != "RULE" or len(p) < 5:
            out("firewall", "FAIL", "rule tssh-OpenSSH missing" if o in ("NONE", "") else o)
        elif p[2] != "True":
            out("firewall", "FAIL", "%s disabled" % p[1])
        elif p[3] in ("", "Any"):
            out("firewall", "WARN", "%s not bound to the Tailscale interface (%s)" % (p[1], p[4]))
        else:
            out("firewall", "OK", "%s on %s (%s)" % (p[1], p[3], p[4]))
    else:
        out("firewall", "SKIP", "not Windows")

    text = read(AK)
    if text is None:
        out("authorized_keys", "FAIL", "missing")
    else:
        keys = [l.strip() for l in text.splitlines() if l.strip().startswith(PFX)]
        m = re.search(r"# >>> tssh keys.*?\n(.*?)# <<< tssh keys", text, re.S)
        managed = len([l for l in (m.group(1) if m else "").splitlines() if l.strip().startswith(PFX)])
        note = ""
        if WIN and re.search(r"(?mi)^\s*Match\s+Group\s+administrators", read(os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "ssh", "sshd_config")) or ""):
            note = "; sshd_config still sends administrators to administrators_authorized_keys"
        out("authorized_keys", "WARN" if note or not keys else "OK", "%d keys, %d in the linkmycom block%s" % (len(keys), managed, note))
        if WIN:
            o = PS.get("ACL", "")
            out("ak_acl", "OK" if o == "OK" else "FAIL", "no broad write access" if o == "OK" else (o or "ACL check gave no result"))
        else:
            bad = [p for p in (AK, os.path.dirname(AK)) if os.stat(p).st_mode & 0o022 or os.stat(p).st_uid != os.getuid()]
            out("ak_acl", "FAIL" if bad else "OK", ("group/other writable or not owned: " + ", ".join(bad)) if bad else "owner only")
        if KEY:
            found = any(KEY in l.split() for l in keys)
            out("my_key", "OK" if found else "FAIL", "my key is registered" if found else "my key is not in authorized_keys")

clis = ([os.path.join(LAD, "linkmycom", "linkmycom.py"), os.path.join(LAD, "DeskTools", "tower", "linkmycom.py")] if WIN
        else [os.path.join(HOME, ".local", "bin", "linkmycom"), "/usr/local/bin/linkmycom"])
vers = ["%s %s" % (os.path.basename(os.path.dirname(p)), ver_in(p)) for p in clis if ver_in(p)]
out("cli", "INFO" if vers else "WARN", ", ".join(vers) or "linkmycom not found in the usual places")

if True:  # also in --versions mode: fleet needs the install that 'lmc' on PATH really runs
    found = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, "lmc.cmd" if WIN else "lmc") if d else ""
        if not p or not os.path.isfile(p):
            continue
        if WIN:
            srcs = [os.path.join(d, "linkmycom.py"), os.path.join(d, "..", "tower", "linkmycom.py"),
                    os.path.join(d, "..", "linkmycom", "linkmycom.py")]
        else:
            srcs = [os.path.realpath(p)]
        src = next((os.path.normpath(s) for s in srcs if ver_in(s)), "")
        if src and all(os.path.normcase(src) != os.path.normcase(f[1]) for f in found):
            found.append((p, src, ver_in(src)))
    if not found:
        out("path_lmc", "WARN", "lmc is not on PATH")
    else:
        first = "%s (%s)" % (short(found[0][1]), found[0][2])
        if len(found) == 1:
            out("path_lmc", "OK", "lmc -> " + first)
        else:
            out("path_lmc", "WARN", "lmc -> %s; also on PATH: %s" % (first, ", ".join("%s (%s)" % (short(f[1]), f[2]) for f in found[1:])))

tower_ver = ""
if WIN:
    try:
        tower_ver = json.loads(read(os.path.join(LAD, "DeskTools", "tower", "release.json")) or "{}").get("version") or ""
        out("tower", "INFO", tower_ver or "not installed")
    except ValueError:
        out("tower", "WARN", "release.json unreadable")
    if not ONLY_VERSIONS:
        if not tower_ver:
            out("tower_run", "SKIP", "tower not installed")
        elif PS.get("TOWER") == "True":
            out("tower_run", "OK", "ime-probe running")
        else:
            out("tower_run", "WARN", "tower is not running (Start-ControlTower.ps1)")
nv = ""
if WIN:
    nv = (read(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "LinkMyCom", "LINKMYCOM_VERSION")) or "").strip()
    if not nv:
        try:
            nv = json.loads(read(os.path.join(LAD, "LinkMyComNative", "current.json")) or "{}").get("version") or ""
        except ValueError:
            nv = ""
elif MAC:
    try:
        import plistlib
        with open("/Applications/LinkMyCom.app/Contents/Info.plist", "rb") as f:
            nv = plistlib.load(f).get("CFBundleShortVersionString") or ""
    except Exception:
        nv = ""
out("native", "INFO", nv or "not installed")

if not ONLY_VERSIONS:
    if WIN:
        svc = PS.get("SVC", "").split(";")
        net = finish(NETP, 30)[1]
        # netstat misses the [::] dual-stack listener on some PCs (jekimlabtop), so try a real connect first.
        try:
            socket.create_connection(("127.0.0.1", 21118), 1.0).close()
            listen = True
        except OSError:
            listen = bool(re.search(r"(?m)^\s*TCP\s+\S+:21118\s+\S+\s+LISTEN", net))
        if len(svc) < 2 or not svc[0]:
            out("screen_svc", "INFO" if not nv else "WARN", "service not installed" + ("" if listen else ", 21118 not listening"))
        elif svc[1] == "Running" and listen:
            out("screen_svc", "OK", "%s Running, 21118 listening" % svc[0])
        else:
            out("screen_svc", "WARN", "%s %s, 21118 %s" % (svc[0], svc[1], "listening" if listen else "not listening"))
    elif MAC:
        rc, o = run(["lsof", "-nP", "-iTCP:21118", "-sTCP:LISTEN"], 15)
        procs = sorted(set(l.split()[0] for l in o.splitlines()[1:] if l.split()))
        if procs:
            out("screen_svc", "OK", "21118 listening (%s)" % ",".join(procs))
        else:
            out("screen_svc", "WARN" if nv else "INFO", "21118 not listening" if nv else "not installed")
    else:
        out("screen_svc", "SKIP", "no screen-sharing host on this OS")

    try:
        state = json.loads(read(os.path.join(HOME, ".tssh", "state.json")) or "{}")
    except ValueError:
        state = {}
    last = state.get("last_keys_refresh") or ""
    err = state.get("last_keys_error") or ""
    if not last:
        out("keys_refresh", "WARN", ("never; last error: " + err) if err else "no record (setup not run, or before 0.4.4)")
    else:
        try:
            import datetime
            age = time.time() - datetime.datetime.strptime(last[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()
        except ValueError:
            age = 0
        stale = age > 3 * 86400 or (err and err[:19] > last[:19])
        out("keys_refresh", "WARN" if stale else "OK", last[:16].replace("T", " ") + " UTC" + ("; later error: " + err if err and err[:19] > last[:19] else ""))

    if WIN:
        rc, o = finish(TASKP, 30)
        out("keys_task", "OK" if rc == 0 else "WARN", ("scheduled task " + TASK) if rc == 0 else (TASK + " task missing (run 'lmc setup')"))
    elif MAC:
        plist = os.path.join(HOME, "Library", "LaunchAgents", LAUNCHD + ".plist")
        rc, o = run(["launchctl", "list", LAUNCHD], 15)
        if os.path.exists(plist) and rc == 0:
            out("keys_task", "OK", "launchd " + LAUNCHD)
        else:
            out("keys_task", "WARN", "launchd %s %s (run 'lmc setup')" % (LAUNCHD, "not loaded" if os.path.exists(plist) else "missing"))
    elif shutil.which("systemctl"):
        rc, o = run(["systemctl", "--user", "is-enabled", UNIT + ".timer"], 15)
        out("keys_task", "OK" if rc == 0 else "WARN", ("systemd timer %s.timer %s" % (UNIT, o or "")) if rc == 0 else ("systemd timer %s.timer not enabled (run 'lmc setup')" % UNIT))
    else:
        out("keys_task", "WARN", "no systemctl; schedule 'linkmycom keys refresh --quiet' with cron")
'''

DOCTOR_LABELS = {
    "python": "파이썬", "tailscale": "Tailscale", "ssh_port": "SSH 22 포트", "sshd": "sshd 서비스",
    "firewall": "방화벽 규칙", "authorized_keys": "authorized_keys", "ak_acl": "authorized_keys 권한",
    "my_key": "내 공개키 등록", "keys_list": "게시된 키 목록", "cli": "CLI 버전", "tower": "타워 버전",
    "native": "화면공유 앱 버전", "keys_refresh": "마지막 키 갱신",
    "path_lmc": "PATH 의 lmc", "tower_run": "타워 실행", "screen_svc": "화면공유 서비스·21118",
    "keys_task": "키 갱신 예약",
}
DOCTOR_COLORS = {"OK": "32", "FAIL": "31", "WARN": "33", "INFO": "36", "SKIP": "90"}


def doctor_oneliner() -> str:
    """DOCTOR_PY 를 zlib·base64 로 줄여 'python -c' 한 줄로 실행하는 코드."""
    import base64
    import zlib

    packed = base64.b64encode(zlib.compress(DOCTOR_PY.encode("ascii"), 9)).decode("ascii")
    return f"import base64,zlib;exec(zlib.decompress(base64.b64decode('{packed}')))"


DOCTOR_STDIN_END = "__LMCDOC_END__"


def doctor_remote_command(os_name: str, key_blob: str = "", versions_only: bool = False) -> tuple[str, str | None]:
    """원격 PC 에서 같은 점검 스크립트를 돌리는 (명령 한 줄, ssh 표준 입력으로 보낼 내용).

    Windows 는 sshd 기본 셸이 cmd.exe 일 수 있어 명령줄을 8191자 안으로 줄여야 하므로, 짧은 PowerShell 이
    Store 파이썬 스텁을 건너뛴 파이썬을 찾고 점검 코드는 표준 입력으로 받는다. 그 밖은 코드를 명령줄에 싣는다.
    versions_only 면 버전 줄(cli·tower·native)만 낸다(fleet status).
    """
    code = doctor_oneliner()
    tail = (f" {key_blob}" if key_blob else "") + (" --versions" if versions_only else "")
    if os_name == "windows":
        lines = [
            "$py = $null",
            "foreach ($n in @('python','python3','py')) { $c = Get-Command $n -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1; if ($c) { $py = $c.Source; break } }",
            "if (-not $py) { 'LMCDOC|python|FAIL|python 3 not found'; exit 0 }",
            # Windows OpenSSH sometimes never delivers the stdin EOF to a nested PowerShell, so ReadToEnd() hung
            # for the full timeout and left orphaned wrappers (officehermes, 2026-11-13). Read up to a sentinel line.
            "$lines = New-Object System.Collections.Generic.List[string]",
            "while ($null -ne ($l = [Console]::In.ReadLine())) { if ($l -eq '" + DOCTOR_STDIN_END + "') { break }; $lines.Add($l) }",
            "$code = ($lines -join \"`n\").Trim()",
            "& $py -c $code" + tail,
        ]
        return ("powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps("\n".join(lines) + "\n"),
                code + "\n" + DOCTOR_STDIN_END + "\n")
    return (f"python3 -c \"{code}\"{tail} || python -c \"{code}\"{tail} || "
            "echo 'LMCDOC|python|FAIL|python 3 not found'"), None


def parse_doctor_lines(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        parts = line.strip().split("|", 3)
        if len(parts) == 4 and parts[0] == "LMCDOC":
            rows.append((parts[1], parts[2], parts[3]))
    return rows


def local_key_blob() -> str:
    """내 공개키의 base64 부분. 키가 없으면 빈 문자열."""
    try:
        parts = LOCAL_KEY.with_suffix(".pub").read_text(encoding="utf-8").split()
    except OSError:
        return ""
    return parts[1] if len(parts) >= 2 else ""


def doctor_keys_list_row(cfg: dict) -> tuple[str, str, str]:
    """게시된 공개키 목록을 받아 서명을 확인하고 내 키가 들어 있는지 본다."""
    try:
        keys = fetch_remote_keys(cfg)
    except Exception as e:  # noqa: BLE001
        return "keys_list", "FAIL", str(e)
    blob = local_key_blob()
    mine = bool(blob) and any(blob in k.split() for k in keys)
    if not blob:
        return "keys_list", "WARN", f"서명 확인, 키 {len(keys)}개. 이 PC 에 공개키가 없음('linkmycom setup')"
    if not mine:
        return "keys_list", "WARN", f"서명 확인, 키 {len(keys)}개. 이 PC 의 키가 없음(관리 PC 에서 'keys publish --collect')"
    return "keys_list", "OK", f"서명 확인, 키 {len(keys)}개, 이 PC 의 키 포함"


def print_doctor(title: str, rows: list[tuple[str, str, str]]) -> int:
    print(c(title, "1"))
    table = [[DOCTOR_LABELS.get(n, n), c(s, DOCTOR_COLORS.get(s, "0")), d] for n, s, d in rows]
    print_table(table, ["점검", "결과", "내용"])
    failed = [r for r in rows if r[1] == "FAIL"]
    return 1 if failed else 0


def local_doctor_rows(versions_only: bool = False) -> list[tuple[str, str, str]]:
    """이 PC 에서 점검 스크립트를 돌린 결과 줄. 실행하지 못하면 die(주 스레드에서만 부른다)."""
    cmd = [sys.executable, "-c", doctor_oneliner()] + (["--versions"] if versions_only else [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        die(f"점검 스크립트를 실행하지 못했습니다: {e}")
    return parse_doctor_lines(r.stdout)


def cmd_doctor(cfg: dict, args: list[str]) -> int:
    """이 PC(또는 이름을 준 PC)의 SSH 연결 조건을 점검해 OK/FAIL 표로 보인다. FAIL 이 있으면 종료 코드 1."""
    if "--all" in args:
        return cmd_doctor_all(cfg, as_json="--json" in args)
    host = next((a for a in args if not a.startswith("-")), None)
    if not host:
        # 게시된 키 목록 받기(네트워크)와 점검 스크립트(PowerShell 등)를 함께 돌린다.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as pool:
            keys_row = pool.submit(doctor_keys_list_row, cfg)
            rows = local_doctor_rows()
            row = keys_row.result()
        idx = next((i for i, x in enumerate(rows) if x[0] == "cli"), len(rows))
        rows.insert(idx, row)
        return print_doctor(f"linkmycom doctor · 이 PC ({platform.node()}) · CLI {__version__}", rows)
    blocks = ssh_config_blocks()
    peer, _ = pick_cached(cfg, blocks, host)
    remote, stdin_text = doctor_remote_command(peer["os"], local_key_blob())
    print(c(f"→ {peer['name']} 에 점검 스크립트를 보냅니다...", "36"))
    rc, out, err = run_remote(peer, cfg, blocks, [remote], stdin_text, timeout=180)
    rows = parse_doctor_lines(out)
    if not rows:
        reason = ((err or "").strip().splitlines() or ["출력 없음"])[-1]
        print_doctor(f"linkmycom doctor · {peer['name']}", [("ssh_port", "FAIL", f"SSH 로 들어가지 못했습니다: {reason}")])
        return 1
    return print_doctor(f"linkmycom doctor · {peer['name']} ({peer['ip']})", rows)


# ---------------------------------------------------------------- 여러 PC 에 한꺼번에 (exec / doctor --all / fleet).

BATCH_SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
REMOTE_WORKERS = 5


def pick_cached(cfg: dict, blocks: list[dict], query: str) -> tuple[dict, list[dict]]:
    """캐시(45초)로 이름을 풀고, 캐시에서 하나로 정해지지 않으면 tailscale 을 다시 읽어 푼다."""
    peers, from_cache = cached_peers()
    if from_cache and len(resolve(peers, query, cfg, blocks)) != 1:
        peers = fresh_peers()
    return pick_one_or_die(peers, cfg, blocks, query), peers


def ssh_capable(peers: list[dict]) -> list[dict]:
    """'all' 대상: 온라인이고 모바일이 아니며 주소가 있는 PC."""
    return [p for p in peers if p.get("online") and p.get("os") not in MOBILE_OS and p.get("ip")]


def resolve_targets(cfg: dict, blocks: list[dict], spec: str) -> list[dict]:
    """'all' 또는 쉼표로 나눈 이름들을 피어 목록으로. 이름이 모호하면 pick_one_or_die 규칙(비대화형이면 종료 1)."""
    if spec.lower() in ("all", "@all"):
        peers, _ = cached_peers()
        return ssh_capable(peers)
    out: list[dict] = []
    for name in [s.strip() for s in spec.split(",") if s.strip()]:
        peer, _ = pick_cached(cfg, blocks, name)
        if all(p["name"] != peer["name"] for p in out):
            out.append(peer)
    return out


def remote_ssh_cmd(peer: dict, cfg: dict, blocks: list[dict], remote: list[str], ssh: str | None = None) -> list[str]:
    """BatchMode ssh 명령. remote 는 호스트 뒤에 그대로 붙인다(split_ssh_args 를 거치지 않음)."""
    cmd = build_ssh_cmd(peer, host_settings(peer, cfg, blocks), cfg, BATCH_SSH_OPTS, ssh_path=ssh or ssh_bin())
    return cmd + list(remote)


def run_remote(peer: dict, cfg: dict, blocks: list[dict], remote: list[str], stdin_text: str | None = None,
               timeout: float | None = 120, ssh: str | None = None) -> tuple[int, str, str]:
    """원격 명령을 돌려 (종료 코드, stdout, stderr). 예외·die 없이 실패도 값으로 돌려준다(작업 스레드에서 쓴다)."""
    try:
        cmd = remote_ssh_cmd(peer, cfg, blocks, remote, ssh)
    except SystemExit:
        return 255, "", "주소를 알 수 없음"
    kwargs: dict = {"input": stdin_text} if stdin_text is not None else {"stdin": subprocess.DEVNULL}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           **kwargs)
    except subprocess.TimeoutExpired:
        return 124, "", f"{int(timeout or 0)}초 안에 끝나지 않음"
    except OSError as e:
        return 255, "", str(e)
    return r.returncode, r.stdout or "", r.stderr or ""


def parallel_map(func, items: list, workers: int = REMOTE_WORKERS) -> list:
    """items 마다 func 를 스레드 풀에서 돌려 같은 순서로 결과를 돌려준다. 한 항목의 예외는 그 자리의 예외 객체가 된다."""
    from concurrent.futures import ThreadPoolExecutor

    def safe(item):
        try:
            return func(item)
        except BaseException as e:  # noqa: BLE001 - 다른 PC 의 결과를 잃지 않는다
            return e

    if not items:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(items)))) as pool:
        return list(pool.map(safe, items))


def last_line(text: str, default: str = "") -> str:
    return ((text or "").strip().splitlines() or [default])[-1]


def skip_without_ssh(peer: dict) -> dict | None:
    """exec all 과 같은 규칙: Tailscale SSH 도 없고 22 포트도 닫힌 PC 는 실패가 아니라 '건너뜀' 행."""
    if peer.get("ts_ssh") or port_open(peer["ip"], 22, 2.0):
        return None
    return {"name": peer["name"], "ip": peer["ip"], "os": peer["os"], "peer": peer, "rows": [], "error": "",
            "skipped": "SSH 포트 닫힘"}


def remote_rows_error(rows: list[tuple[str, str, str]], err: str) -> str:
    """원격 점검 결과가 쓸모없을 때의 사유. 쓸 수 있으면 빈 문자열."""
    if not rows:
        return f"SSH 실패: {last_line(err, '출력 없음')}"
    if rows[0][0] == "python" and rows[0][1] == "FAIL":
        return "원격에 파이썬 3 이 없어 점검하지 못함"
    return ""


def parse_exec_args(args: list[str]) -> tuple[str, list[str], float | None]:
    """'<대상> [--timeout N] [--] <명령...>' 을 (대상, 원격 명령, 시간 제한) 으로."""
    if not args:
        die("사용법: linkmycom exec <이름|이름,이름|all> [--timeout 초] -- <명령...>")
    target, rest, timeout = args[0], list(args[1:]), None
    while rest and rest[0] == "--timeout" and len(rest) > 1:
        try:
            timeout = float(rest[1])
        except ValueError:
            die(f"--timeout 에는 숫자를 쓰세요: {rest[1]}")
        rest = rest[2:]
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not rest:
        die("실행할 명령이 없습니다. 예: linkmycom exec all -- hostname")
    return target, rest, timeout


def cmd_exec(cfg: dict, args: list[str]) -> int:
    """여러 PC 에 같은 명령을 BatchMode SSH 로 병렬 실행하고 '[이름] ' 을 붙여 줄 단위로 출력한다. 하나라도 실패면 1."""
    import queue
    import threading

    target, remote, timeout = parse_exec_args(args)
    blocks = ssh_config_blocks()
    peers = resolve_targets(cfg, blocks, target)
    if not peers:
        die("명령을 보낼 온라인 PC 가 없습니다.")
    is_all = target.lower() in ("all", "@all")
    ssh = ssh_bin()
    lines: "queue.Queue[tuple[str, str] | None]" = queue.Queue()
    results: dict[str, int] = {}
    sem = threading.Semaphore(8)

    def work(peer: dict) -> None:
        name = peer["name"]
        with sem:
            try:
                if is_all and not peer.get("ts_ssh") and not port_open(peer["ip"], 22, 2.0):
                    lines.put((name, "(SSH 포트 닫힘, 건너뜀)"))
                    results[name] = -1
                    return
                cmd = remote_ssh_cmd(peer, cfg, blocks, remote, ssh)
                proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace")
                timer = None
                if timeout:
                    timer = threading.Timer(timeout, proc.kill)
                    timer.start()
                assert proc.stdout is not None
                for line in proc.stdout:
                    lines.put((name, line.rstrip("\r\n")))
                rc = proc.wait()
                if timer:
                    timer.cancel()
                results[name] = rc
            except BaseException as e:  # noqa: BLE001
                lines.put((name, f"(실행 실패: {e})"))
                results[name] = 255
            finally:
                lines.put(None)

    for p in peers:
        threading.Thread(target=work, args=(p,), daemon=True).start()
    done = 0
    width = max(len(p["name"]) for p in peers)
    try:
        while done < len(peers):
            item = lines.get()
            if item is None:
                done += 1
                continue
            name, line = item
            print(c(f"[{name}]".ljust(width + 2), "36") + " " + line, flush=True)
    except KeyboardInterrupt:
        return 130
    failed = sorted(n for n, rc in results.items() if rc not in (0, -1))
    skipped = sorted(n for n, rc in results.items() if rc == -1)
    ok = len(peers) - len(failed) - len(skipped)
    summary = f"성공 {ok}/{len(peers)}" + (f", 실패: {', '.join(f'{n}({results[n]})' for n in failed)}" if failed else "") + \
        (f", 건너뜀: {', '.join(skipped)}" if skipped else "")
    print(c(summary, "31" if failed else "32"), file=sys.stderr)
    return 1 if failed else 0


def doctor_summary(rows: list[tuple[str, str, str]]) -> dict:
    """doctor 결과 줄을 한 PC 의 요약 칸(CLI·sshd·방화벽·키·화면공유·결과)으로."""
    d = {n: (s, det) for n, s, det in rows}

    def st(name: str) -> str:
        return d.get(name, ("-", ""))[0]

    cli = ", ".join(f"{a} {b}" for a, b in re.findall(r"(\S+) (\d+(?:\.\d+)+)", d.get("cli", ("", ""))[1])) or "-"
    native = d.get("native", ("", "-"))[1]
    screen = (native if native != "not installed" else "-") + (f" {st('screen_svc')}" if "screen_svc" in d else "")
    fails = [n for n, s, _ in rows if s == "FAIL"]
    warns = [n for n, s, _ in rows if s == "WARN"]
    return {
        "cli": cli,
        "sshd": st("sshd") if "sshd" in d else st("ssh_port"),
        "firewall": st("firewall"),
        "keys": st("my_key") if "my_key" in d else st("authorized_keys"),
        "screen": screen.strip() or "-",
        "result": ("FAIL " + ",".join(fails)) if fails else ("WARN " + ",".join(warns)) if warns else "OK",
    }


def cmd_doctor_all(cfg: dict, as_json: bool = False) -> int:
    """온라인 PC 전부(와 이 PC)를 병렬로 점검해 한 표로. 꺼졌거나 SSH 가 안 되는 PC 도 행으로 남긴다."""
    blocks = ssh_config_blocks()
    peers, _ = cached_peers()
    targets = ssh_capable(peers)
    blob = local_key_blob()
    ssh = ssh_bin()
    if not as_json:
        print(c(f"linkmycom doctor --all · 이 PC 와 온라인 {len(targets)}대를 점검합니다...", "36"), file=sys.stderr)

    def check(peer: dict) -> dict:
        skipped = skip_without_ssh(peer)
        if skipped:
            return skipped
        remote, stdin_text = doctor_remote_command(peer["os"], blob)
        rc, out, err = run_remote(peer, cfg, blocks, [remote], stdin_text, timeout=180, ssh=ssh)
        rows = parse_doctor_lines(out)
        return {"name": peer["name"], "ip": peer["ip"], "os": peer["os"], "rows": rows,
                "error": remote_rows_error(rows, err)}

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        remote_f = pool.submit(parallel_map, check, targets, REMOTE_WORKERS)
        local = {"name": platform.node().split(".")[0], "ip": "(이 PC)", "os": platform.system().lower(),
                 "rows": local_doctor_rows(), "error": ""}
        results = [local] + [r if isinstance(r, dict) else
                             {"name": t["name"], "ip": t["ip"], "os": t["os"], "rows": [], "error": f"오류: {r}"}
                             for t, r in zip(targets, remote_f.result())]
    if as_json:
        print(json.dumps([dict(r, rows=[list(x) for x in r["rows"]]) for r in results], ensure_ascii=False, indent=2))
    else:
        table = []
        for r in results:
            if r.get("skipped"):
                table.append([r["name"], "-", "-", "-", "-", "-", c(f"건너뜀 ({r['skipped']})", "90")])
                continue
            if r["error"]:
                table.append([r["name"], "-", "-", "-", "-", "-", c(r["error"], "31")])
                continue
            s = doctor_summary(r["rows"])
            color = "31" if s["result"].startswith("FAIL") else "33" if s["result"].startswith("WARN") else "32"
            table.append([r["name"], s["cli"], s["sshd"], s["firewall"], s["keys"], s["screen"], c(s["result"], color)])
        print_table(table, ["PC", "CLI", "sshd", "방화벽", "키", "화면공유", "결과"])
    bad = [r for r in results if r["error"] or any(s == "FAIL" for _, s, _ in r["rows"])]
    return 1 if bad else 0


# ---------------------------------------------------------------- fleet: 각 PC 의 버전 표와 원격 CLI 업데이트.

def cli_versions(rows: list[tuple[str, str, str]]) -> dict[str, str]:
    """doctor 의 cli 줄('linkmycom 0.4.4, tower 0.4.4')을 {설치 위치: 버전} 으로."""
    detail = next((d for n, _, d in rows if n == "cli"), "")
    return dict(re.findall(r"(\S+) (\d+(?:\.\d+)+)", detail))


def path_lmc_version(rows: list[tuple[str, str, str]]) -> tuple[str, str] | None:
    """doctor 의 path_lmc 줄에서 PATH 의 lmc 가 실제로 부르는 (설치본 경로, 버전)."""
    detail = next((d for n, _, d in rows if n == "path_lmc"), "")
    m = re.match(r"^lmc -> (.+?) \((\d+(?:\.\d+)+)\)", detail)
    return (m.group(1), m.group(2)) if m else None


def stale_installs(rows: list[tuple[str, str, str]]) -> tuple[bool, list[str]]:
    """(PATH 의 lmc 가 낡았는지, 낡은 고정 위치 설치본 이름들)."""
    mine = parse_version(__version__)
    path = path_lmc_version(rows)
    labels = [k for k, v in cli_versions(rows).items() if parse_version(v) < mine]
    return bool(path and parse_version(path[1]) < mine), labels


def fleet_update_command(os_name: str, labels: list[str], path_stale: bool = True) -> str:
    """원격에서 'lmc update'(PATH 가 부르는 설치본)와, 낡은 고정 위치 설치본마다 그 설치본으로 'update' 를 돌리는 명령 한 줄.

    같은 설치본을 두 번 갱신해도 두 번째는 '이미 최신' 으로 끝난다.
    """
    if os_name == "windows":
        # 원격 기본 셸이 cmd.exe·PowerShell 어느 쪽이어도 되게 PowerShell -EncodedCommand 로 보낸다.
        paths = {"linkmycom": r"$env:LOCALAPPDATA\linkmycom\linkmycom.cmd",
                 "tower": r"$env:LOCALAPPDATA\DeskTools\tower\linkmycom.cmd"}
        lines = (["lmc update"] if path_stale or not labels else []) + \
            [f'& "{paths[l]}" update' for l in labels if l in paths]
        return "powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps("\n".join(lines) + "\n")
    first = 'PATH="$HOME/.local/bin:/usr/local/bin:$PATH" lmc update; ' if path_stale or not labels else ""
    return (first + 'for f in "$HOME/.local/bin/linkmycom" /usr/local/bin/linkmycom; do '
            '[ -f "$f" ] && { python3 "$f" update || python "$f" update; }; done')


FLEET_INSTALL_PATHS = {
    "windows": {"tower": r"%LOCALAPPDATA%\\DeskTools\\tower\\linkmycom.py", "linkmycom": r"%LOCALAPPDATA%\\linkmycom\\linkmycom.py",
                "tssh": r"%LOCALAPPDATA%\\tssh\\linkmycom.py"},
    "unix": {"bin": "~/.local/bin/linkmycom", "usr": "/usr/local/bin/linkmycom"},
}


def fleet_push_script(data: bytes, version: str, paths: list[str]) -> str:
    """원격에서 실행할 파이썬: 관리 PC 가 서명 확인한 새 linkmycom.py(base64)를 SHA256 으로 대조한 뒤,
    주어진 설치 경로 중 실재하고 버전이 낮은 것만 원자적으로 바꾼다. 결과는 'LMCPUSH|경로|이전->새' 줄.

    원격 PC 의 옛 CLI 가 스스로 받게 하면 SSH 세션 안의 ssh-keygen 파이프 문제(0.4.6 이하)로 멈추므로
    검증은 관리 PC 가 하고 원격은 해시만 맞춘다. SSH 채널 자체가 인증·암호화되어 있다.
    """
    import base64
    import hashlib

    b64 = base64.b64encode(data).decode("ascii")
    return (
        "import base64, hashlib, os, re, shutil, sys\n"
        f"DATA = base64.b64decode({b64!r})\n"
        f"assert hashlib.sha256(DATA).hexdigest() == {hashlib.sha256(data).hexdigest()!r}, 'sha256 mismatch'\n"
        f"NEW = {version!r}\n"
        f"PATHS = {paths!r}\n"
        "def ver(t):\n"
        "    m = re.search(r'^__version__\\s*=\\s*[\"\\']([^\"\\']+)', t, re.M)\n"
        "    return tuple(int(x) for x in re.findall(r'\\d+', m.group(1))) if m else ()\n"
        "new_v = tuple(int(x) for x in re.findall(r'\\d+', NEW))\n"
        "seen = set()\n"
        "for raw in PATHS:\n"
        "    p = os.path.expanduser(os.path.expandvars(raw))\n"
        "    if p in seen or not os.path.isfile(p):\n"
        "        continue\n"
        "    seen.add(p)\n"
        "    try:\n"
        "        old = ver(open(p, encoding='utf-8', errors='replace').read())\n"
        "    except OSError as e:\n"
        "        print('LMCPUSH|%s|read failed: %s' % (p, e)); continue\n"
        "    if old >= new_v:\n"
        "        print('LMCPUSH|%s|already %s' % (p, '.'.join(map(str, old)))); continue\n"
        "    tmp = p + '.new'\n"
        "    with open(tmp, 'wb') as f:\n"
        "        f.write(DATA)\n"
        "    try:\n"
        "        shutil.copymode(p, tmp)\n"
        "    except OSError:\n"
        "        pass\n"
        "    os.replace(tmp, p)\n"
        "    print('LMCPUSH|%s|%s->%s' % (p, '.'.join(map(str, old)), NEW))\n"
    )


def fleet_push_command(os_name: str) -> tuple[str, bool]:
    """(원격 명령, 표준 입력 끝에 종료 표시 줄을 붙일지). 표준 입력으로 받은 파이썬을 파일에 써서 실행한다.

    Windows 는 명령줄 길이 한도(8191·32767자) 때문에 코드를 인수로 못 넘기고, 표준 입력 EOF 도 못 믿으므로
    doctor 와 같이 종료 표시 줄까지 읽어 임시 .py 로 실행한다.
    """
    if os_name == "windows":
        lines = [
            "$py = $null",
            "foreach ($n in @('python','python3','py')) { $c = Get-Command $n -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1; if ($c) { $py = $c.Source; break } }",
            "if (-not $py) { 'LMCPUSH|python|python 3 not found'; exit 0 }",
            "$f = Join-Path $env:TEMP ('lmc-push-' + [guid]::NewGuid().ToString('N') + '.py')",
            "$sb = New-Object System.Text.StringBuilder",
            "while ($null -ne ($l = [Console]::In.ReadLine())) { if ($l -eq '" + DOCTOR_STDIN_END + "') { break }; [void]$sb.AppendLine($l) }",
            "[IO.File]::WriteAllText($f, $sb.ToString())",
            "try { & $py $f } finally { Remove-Item $f -Force -ErrorAction SilentlyContinue }",
        ]
        return "powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps("\n".join(lines) + "\n"), True
    return "if command -v python3 >/dev/null 2>&1; then python3 -; else python -; fi", False


def fleet_push_paths(os_name: str, rows: list[tuple[str, str, str]]) -> list[str]:
    """밀어 넣을 설치 경로: PATH 의 lmc 가 가리키는 파일 + 고정 위치 설치본들."""
    path = path_lmc_version(rows)
    fixed = list(FLEET_INSTALL_PATHS["windows" if os_name == "windows" else "unix"].values())
    return ([path[0]] if path else []) + fixed


def fleet_rows(cfg: dict) -> list[dict]:
    blocks = ssh_config_blocks()
    peers, _ = cached_peers()
    targets = ssh_capable(peers)
    ssh = ssh_bin()

    def check(peer: dict) -> dict:
        skipped = skip_without_ssh(peer)
        if skipped:
            return skipped
        remote, stdin_text = doctor_remote_command(peer["os"], versions_only=True)
        rc, out, err = run_remote(peer, cfg, blocks, [remote], stdin_text, timeout=120, ssh=ssh)
        rows = parse_doctor_lines(out)
        return {"name": peer["name"], "ip": peer["ip"], "os": peer["os"], "peer": peer, "rows": rows,
                "error": remote_rows_error(rows, err)}

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        remote_f = pool.submit(parallel_map, check, targets, REMOTE_WORKERS)
        local = {"name": platform.node().split(".")[0], "ip": "(이 PC)", "os": platform.system().lower(), "peer": None,
                 "rows": local_doctor_rows(versions_only=True), "error": ""}
        return [local] + [r if isinstance(r, dict) else
                          {"name": t["name"], "ip": t["ip"], "os": t["os"], "peer": t, "rows": [], "error": f"오류: {r}"}
                          for t, r in zip(targets, remote_f.result())]


def cmd_fleet(cfg: dict, args: list[str]) -> int:
    sub = args[0] if args else "status"
    rest = args[1:]
    if sub == "status":
        results = fleet_rows(cfg)
        if "--json" in rest:
            print(json.dumps([{k: v for k, v in r.items() if k != "peer"} | {"rows": [list(x) for x in r["rows"]]}
                              for r in results], ensure_ascii=False, indent=2))
            return 1 if any(r["error"] for r in results) else 0
        table = []
        for r in results:
            if r.get("skipped"):
                table.append([r["name"], r["os"], "-", "-", "-", "-", c(f"건너뜀 ({r['skipped']})", "90")])
                continue
            if r["error"]:
                table.append([r["name"], r["os"], "-", "-", "-", "-", c(r["error"], "31")])
                continue
            d = {n: det for n, _, det in r["rows"]}
            vers = cli_versions(r["rows"])
            path = path_lmc_version(r["rows"])
            path_stale, labels = stale_installs(r["rows"])
            old = ([f"lmc {path[1]}"] if path_stale and path else []) + [f"{k} {vers[k]}" for k in labels]
            note = c("CLI 낡음: " + ", ".join(old), "33") if old else c("OK", "32")
            table.append([r["name"], r["os"], path[1] if path else "-",
                          ", ".join(f"{k} {v}" for k, v in vers.items()) or "-",
                          d.get("tower", "-"), d.get("native", "-"), note])
        print(c(f"linkmycom fleet status · 이 PC 의 CLI {__version__}", "1"))
        print_table(table, ["PC", "OS", "lmc", "CLI 설치본", "타워", "화면공유", "상태"])
        return 1 if any(r["error"] for r in results) else 0
    if sub == "update":
        what = next((a for a in rest if not a.startswith("-")), "cli")
        dry = "-n" in rest or "--dry-run" in rest
        if what in ("tower", "native"):
            print("타워·화면공유 앱의 원격 갱신은 아직 CLI 로 하지 않습니다. 타워는 각 PC 의 타워 업데이터(Update-LinkMyCom.ps1),"
                  " 화면공유 앱은 관리 PC 의 tools/native/Deploy-NativeHost.ps1 로 배포하세요.")
            return 0
        if what != "cli":
            die("사용법: linkmycom fleet update [cli|tower|native] [-n]")
        results = fleet_rows(cfg)
        stale = []
        for r in results:
            if r["error"] or r["peer"] is None:
                continue
            path_stale, labels = stale_installs(r["rows"])
            if path_stale or labels:
                stale.append((r, labels, path_stale))
        path_old, local_old = stale_installs(results[0]["rows"])
        local_old = (["lmc"] if path_old else []) + local_old
        if local_old:
            print(f"이 PC 의 {', '.join(local_old)} 설치본도 {__version__} 보다 낡았습니다. 여기서 'linkmycom update' 를 실행하세요.")
        for r in results:
            if r["error"]:
                warn(f"{r['name']}: {r['error']} (건너뜀)")
        if not stale:
            print(f"CLI {__version__} 보다 낡은 PC 가 없습니다.")
            return 0
        def what_of(labels: list[str], path_stale: bool) -> str:
            return ", ".join((["lmc(PATH)"] if path_stale else []) + labels)

        if dry:
            for r, labels, path_stale in stale:
                print(f"{r['name']}: {what_of(labels, path_stale)} 설치본에서 'update' 를 실행할 예정")
            return 0
        blocks = ssh_config_blocks()
        ssh = ssh_bin()
        # 관리 PC 가 릴리스를 받아 서명 확인한 뒤 그 파일을 밀어 넣는다(원격이 스스로 받게 하지 않는다).
        repo = cfg.get("update_repo") or DEFAULT_REPO
        try:
            src, remote_ver = fetch_release_source(repo, latest_release(repo, timeout=15))
        except Exception as e:  # noqa: BLE001
            die(f"거울의 최신 릴리스를 받지 못했습니다: {e}")
        if parse_version(remote_ver) < parse_version(__version__):
            die(f"거울의 릴리스({remote_ver})가 이 PC 의 {__version__} 보다 낡았습니다. 먼저 게시하세요(Publish-Cli.ps1).")
        print(f"서명 확인 완료: 거울의 linkmycom {remote_ver} 을(를) 밀어 넣습니다.")

        def upd(item) -> tuple[int, str]:
            r, labels, path_stale = item
            remote, sentinel = fleet_push_command(r["os"])
            script = fleet_push_script(src, remote_ver, fleet_push_paths(r["os"], r["rows"]))
            rc, out, err = run_remote(r["peer"], cfg, blocks, [remote], script + ("\n" + DOCTOR_STDIN_END + "\n" if sentinel else "\n"),
                                      timeout=180, ssh=ssh)
            changed = [l.split("|", 2)[1:] for l in out.splitlines() if l.startswith("LMCPUSH|")]
            if rc == 0 and "python 3 not found" not in out:
                # 원격이 Windows 면 경로 구분자가 역슬래시라 os.path 로는 Mac·Linux 에서 폴더 이름을 못 뽑는다.
                # (f-string 안의 역슬래시는 Python 3.9 에서 문법 오류라 밖에서 자른다.)
                def folder(p: str) -> str:
                    parts = re.split(r"[\\/]", p)
                    return parts[-2] if len(parts) >= 2 else p

                return 0, ("; ".join(f"{folder(p)}: {what}" for p, what in changed)
                           if changed else last_line(out, "변경 없음"))
            return rc or 1, last_line(out + "\n" + err, "출력 없음")

        bad = 0
        for (r, labels, path_stale), res in zip(stale, parallel_map(upd, stale)):
            rc, msg = res if isinstance(res, tuple) else (255, str(res))
            bad += rc != 0
            print(c(f"[{r['name']}]", "36") + f" {what_of(labels, path_stale)}: "
                  + (c("OK", "32") if rc == 0 else c(f"실패({rc})", "31")) + f" {msg}")
        return 1 if bad else 0
    die("사용법: linkmycom fleet status [--json] | fleet update [cli|tower|native] [-n]")


# ---------------------------------------------------------------- 파일 보내기·받기 (Taildrop).

SEND_WORKERS = 3


def tailscale_exe() -> str:
    cands = tailscale_candidates()
    if not cands:
        die("tailscale 명령을 찾지 못했습니다. Tailscale이 설치되어 있는지 확인하세요.")
    return cands[0]


def parse_send_args(args: list[str]) -> tuple[list[str], list[str]]:
    files: list[str] = []
    targets: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--to" and i + 1 < len(args):
            targets += [t for t in args[i + 1].split(",") if t.strip()]
            i += 2
            continue
        if a.startswith("--to="):
            targets += [t for t in a[5:].split(",") if t.strip()]
        else:
            files.append(a)
        i += 1
    if not files or not targets:
        die("사용법: linkmycom send <파일...> --to <이름,이름,...>")
    return files, targets


def cmd_send(cfg: dict, args: list[str]) -> int:
    """Taildrop 으로 파일을 보낸다. 대상마다 'tailscale file cp <파일들> <주소>:' 한 번, 대상은 최대 3곳 병렬."""
    files, names = parse_send_args(args)
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        die(f"보낼 파일이 없거나 폴더입니다: {', '.join(missing)}")
    blocks = ssh_config_blocks()
    peers: list[dict] = []
    for n in names:  # 모두 먼저 풀어 두고(모호하면 여기서 끝남) 보내기 시작한다.
        p, _ = pick_cached(cfg, blocks, n.strip())
        if all(x["name"] != p["name"] for x in peers):
            peers.append(p)
    exe = tailscale_exe()
    for p in peers:
        if not p["online"]:
            warn(f"{p['name']} 은(는) 오프라인으로 표시됩니다. 그래도 보냅니다.")
    total = sum(os.path.getsize(f) for f in files)
    print(c(f"→ 파일 {len(files)}개({total / 1048576:.1f} MiB) 를 {', '.join(p['name'] for p in peers)} 로 보냅니다", "36"))

    def send(peer: dict) -> tuple[int, str]:
        try:
            r = subprocess.run([exe, "file", "cp", *files, f"{peer['ip']}:"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
        except OSError as e:
            return 255, str(e)
        return r.returncode, last_line(r.stderr or r.stdout)

    bad = 0
    for peer, res in zip(peers, parallel_map(send, peers, SEND_WORKERS)):
        rc, msg = res if isinstance(res, tuple) else (255, str(res))
        bad += rc != 0
        print(c(f"[{peer['name']}]", "36") + " " + (c("보냄", "32") if rc == 0 else c(f"실패({rc}) {msg}", "31")))
    return 1 if bad else 0


def cmd_inbox(args: list[str]) -> int:
    """Taildrop 받은 편지함의 파일을 폴더(기본 Downloads)로 옮긴다. 같은 이름은 번호를 붙여 받는다."""
    if platform.system() == "Darwin":
        print("macOS 는 Tailscale 앱이 받은 파일을 바로 Downloads 에 둡니다('tailscale file get' 없음). Finder 의 다운로드를 보세요.")
        return 0
    wait = "--wait" in args
    rest = [a for a in args if a != "--wait"]
    target = Path(rest[0]).expanduser() if rest else Path.home() / "Downloads"
    if not target.is_dir():
        die(f"받을 폴더가 없습니다: {target}")
    cmd = [tailscale_exe(), "file", "get", "--conflict=rename"] + (["--wait"] if wait else []) + [str(target)]
    print(c(f"→ Taildrop 받은 파일을 {target} 로 옮깁니다", "36"))
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130


# ---------------------------------------------------------------- 포트 전달 (forward).

def parse_forward_spec(spec: str) -> str:
    """'로컬:원격' 또는 '로컬:원격호스트:원격' 을 ssh -L 값으로. 원격 호스트를 빼면 그 PC 의 127.0.0.1."""
    parts = spec.split(":")
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        return f"{parts[0]}:127.0.0.1:{parts[1]}"
    if len(parts) == 3 and parts[0].isdigit() and parts[2].isdigit() and parts[1]:
        return spec
    die(f"전달 형식이 맞지 않습니다: {spec}. 예: 8080:80 또는 8080:localhost:80")


def cmd_forward(cfg: dict, args: list[str]) -> int:
    """'ssh -N -L' 로 이 PC 의 포트를 그 PC 의 포트로 이어 둔다(Ctrl+C 로 끝)."""
    names = [a for a in args if not a.startswith("-")]
    if len(names) < 2:
        die("사용법: linkmycom forward <이름> <로컬포트:원격포트> [...]")
    blocks = ssh_config_blocks()
    peer, _ = pick_cached(cfg, blocks, names[0])
    specs = [parse_forward_spec(s) for s in names[1:]]
    extra = ["-N", "-o", "ExitOnForwardFailure=yes"]
    for s in specs:
        extra += ["-L", s]
    cmd = build_ssh_cmd(peer, host_settings(peer, cfg, blocks), cfg, extra, ssh_path=ssh_bin())
    if "-n" in args or "--dry-run" in args:
        print(quote_cmd(cmd))
        return 0
    for s in specs:
        lp, _, rest = s.partition(":")
        print(c(f"→ 127.0.0.1:{lp} → {peer['name']}:{rest.split(':', 1)[1]}", "36") + "  (Ctrl+C 로 끝)")
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130


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
        die("사용법: linkmycom set <이름> user=.. port=.. key=.. alias=.. args=\"-A -X\"")
    found = resolve(peers, args[0], cfg, blocks)
    if len(found) != 1:
        die(f"'{args[0]}' 에 맞는 피어가 {len(found)}개입니다. 정확한 이름을 쓰세요.")
    name = found[0]["name"]
    kv = parse_kv(args[1:])
    allowed = {"user", "port", "key", "alias", "args", "screen"}
    bad = set(kv) - allowed
    if bad:
        die(f"알 수 없는 키: {', '.join(sorted(bad))}. 가능한 키: {', '.join(sorted(allowed))}")
    entry = cfg["hosts"].get(name, {})
    for k, v in kv.items():
        if v == "":
            entry.pop(k, None)
        elif k == "args":
            try:
                entry[k] = split_args(v)
            except ValueError as e:
                die(f"args 값을 나누지 못했습니다({e}). 따옴표 짝을 확인하세요.")
        else:
            entry[k] = v
    cfg["hosts"][name] = entry
    save_json(CONFIG_PATH, cfg)
    print(f"{name}: {json.dumps(entry, ensure_ascii=False)}")


def cmd_unset(peers: list[dict], cfg: dict, blocks: list[dict], args: list[str]) -> None:
    if not args:
        die("사용법: linkmycom unset <이름>")
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
        elif k in ("default_user", "update_repo", "update_ref", "repo_dir", "keys_url", "keys_signer"):
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
                "repo_dir, keys_url, keys_signer, ssh_options.<옵션>)")
    save_json(CONFIG_PATH, cfg)
    print(json.dumps(cfg, ensure_ascii=False, indent=2))


def pick_one_or_die(peers: list[dict], cfg: dict, blocks: list[dict], query: str) -> dict:
    found = resolve(peers, query, cfg, blocks)
    if len(found) == 1:
        return found[0]
    if not found:
        die(f"'{query}' 에 맞는 피어가 없습니다. 'linkmycom list' 로 이름을 확인하세요.")
    if not sys.stdin.isatty():
        # 스크립트·원격 명령에서 엉뚱한 PC 로 들어가지 않도록 고르지 않고 후보만 알린다.
        names = ", ".join(p["name"] for p in found)
        print(c("오류: ", "31") + f"'{query}' 에 맞는 피어가 {len(found)}개입니다: {names}. 정확한 이름을 쓰세요.",
              file=sys.stderr)
        sys.exit(1)
    print(c(f"'{query}' 에 맞는 피어가 {len(found)}개입니다.", "33"))
    chosen = pick_interactive(found, cfg, blocks, [])
    if not chosen or chosen.get("__refresh__"):
        sys.exit(1)
    return chosen


def parse_connect_args(argv: list[str]) -> dict:
    """linkmycom 자체 옵션(호스트 이름 앞)과 호스트, 그 뒤 ssh 인자를 나눈다."""
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
            die(f"알 수 없는 옵션 {a}. ssh 옵션은 호스트 이름 뒤에 쓰세요. 예: linkmycom pfl -L 8080:localhost:80")
        else:
            opts["host"] = a
        i += 1
    if opts["host"] and "@" in opts["host"]:
        u, h = opts["host"].rsplit("@", 1)
        opts["user"] = opts["user"] or u
        opts["host"] = h
    return opts


# ---------------------------------------------------------------- 옛 이름(tssh) 설치본 옮기기.

LEGACY_NAMES = {"tssh", "tssh.py"}
FORWARDER_MARK = "linkmycom-forwarder"
INVOKED_AS_ENV = "LINKMYCOM_INVOKED_AS"


def forwarder_source(target_name: str) -> str:
    """옛 tssh 진입 파일을 대신할 짧은 파이썬. 옆의 새 파일을 같은 인자로 실행한다."""
    return (
        "#!/usr/bin/env python3\n"
        f"# {FORWARDER_MARK}: tssh 는 linkmycom 으로 이름이 바뀌었다. 옆의 {target_name} 를 같은 인자로 실행한다.\n"
        "import os, runpy, sys\n"
        "from pathlib import Path\n"
        f"os.environ.setdefault({INVOKED_AS_ENV!r}, 'tssh')\n"
        f"sys.argv[0] = str(Path(__file__).resolve().with_name({target_name!r}))\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )


def is_forwarder(src: str) -> bool:
    """넘김 파일은 둘째 줄이 표식 주석이다. 본 소스에도 표식 문자열이 있으므로 위치로 구별한다."""
    lines = src.splitlines()
    return len(lines) > 1 and lines[1].startswith(f"# {FORWARDER_MARK}:")


def replace_text(path: Path, text: str, mode: int | None = None) -> None:
    """임시 파일에 쓴 뒤 원자적으로 바꾼다. 줄바꿈은 그대로 쓴다."""
    tmp = path.with_name(path.name + ".new")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, path)


def shim_path(path: str | Path, ps: bool = False) -> str:
    """배치·PowerShell 파일에 넣을 경로. 사용자 폴더 아래면 환경 변수로 바꾼다.

    한글 사용자 이름이 든 경로를 파일에 그대로 쓰면 cmd.exe·PowerShell 5.1 이 다른 코드 페이지로 읽어 깨진다.
    """
    s = str(path)
    for var in ("LOCALAPPDATA", "APPDATA", "USERPROFILE"):
        base = (os.environ.get(var) or "").rstrip("\\")
        if base and s.lower().startswith(base.lower() + "\\"):
            return (f"$env:{var}" if ps else f"%{var}%") + s[len(base):]
    return s


def shim_encoding() -> str:
    """cmd.exe 가 배치 파일을 읽는 콘솔 코드 페이지(한국어 Windows 는 cp949)."""
    try:
        import ctypes
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return "utf-8"


def write_shim(path: Path, body: str) -> None:
    """실행 파일을 쓴다. .ps1 은 UTF-8 BOM(PowerShell 5.1·7 모두 읽음), .cmd 는 ASCII 또는 콘솔 코드 페이지."""
    if path.suffix.lower() == ".ps1":
        data = b"\xef\xbb\xbf" + body.encode("utf-8")
    else:
        data = body.encode("ascii" if body.isascii() else shim_encoding(), errors="replace")
    tmp = path.with_name(path.name + ".new")
    tmp.write_bytes(data)
    os.replace(tmp, path)


TSSH_CMD_FORWARDER = '@echo off\r\nsetlocal\r\nset LINKMYCOM_INVOKED_AS=tssh\r\ncall "%~dp0linkmycom.cmd" %*\r\n'
TSSH_PS1_FORWARDER = ('# tssh 는 linkmycom 으로 이름이 바뀌었다. 옆의 linkmycom 을 같은 인자로 실행한다.\r\n'
                      '$env:LINKMYCOM_INVOKED_AS = "tssh"\r\n'
                      'try { & (Join-Path $PSScriptRoot "linkmycom.cmd") @args } finally { Remove-Item Env:LINKMYCOM_INVOKED_AS -ErrorAction SilentlyContinue }\r\n'
                      'exit $LASTEXITCODE\r\n')


def broken_exe_path(path: Path) -> bool:
    """실행 파일 안의 따옴표 친 .exe 경로가 깨졌거나 없으면 True. .exe 경로가 없으면(PATH 의 python 을 찾는 방식) False."""
    raw = path.read_bytes()
    text = raw[3:].decode("utf-8", errors="replace") if raw.startswith(b"\xef\xbb\xbf") else raw.decode(shim_encoding(), errors="replace")
    m = re.search(r'"([^"]+\.exe)"', text)
    if not m:
        return False
    exe = re.sub(r"\$env:(\w+)", r"%\1%", m.group(1))  # PowerShell 의 $env:VAR 도 %VAR% 로 펼쳐 확인한다
    return "?" in exe or "�" in exe or not os.path.exists(os.path.expandvars(exe))


def python_shim(py: str) -> str:
    return f'@echo off\r\n"{shim_path(py)}" "%~dp0linkmycom.py" %*\r\n'


def repair_shims(here: Path) -> list[Path]:
    """linkmycom.py 옆의 옛 tssh.cmd·tssh.ps1 과 파이썬 경로가 깨진 linkmycom.cmd·linkmycom.ps1 을 고친다.

    옛 설치기는 파이썬 경로를 ASCII 로 써서 한글 사용자 이름이 '???'가 됐다. 그런 파일은 실행되지 않는다.
    PowerShell 은 같은 이름이면 .ps1 을 먼저 고르므로 .ps1 도 고친다. 고친 파일 목록을 돌려준다.
    """
    if here.name != "linkmycom.py" or not here.with_name("linkmycom.cmd").exists():
        return []
    fixed: list[Path] = []
    cmd = here.with_name("linkmycom.cmd")
    if broken_exe_path(cmd):
        write_shim(cmd, python_shim(sys.executable))
        fixed.append(cmd)
    ps1 = here.with_name("linkmycom.ps1")
    if ps1.exists() and broken_exe_path(ps1):
        write_shim(ps1, f'& "{shim_path(sys.executable, ps=True)}" "$PSScriptRoot\\linkmycom.py" @args\r\nexit $LASTEXITCODE\r\n')
        fixed.append(ps1)
    for legacy, body in ((here.with_name("tssh.cmd"), TSSH_CMD_FORWARDER), (here.with_name("tssh.ps1"), TSSH_PS1_FORWARDER)):
        if legacy.exists() and b"linkmycom" not in legacy.read_bytes().lower():
            write_shim(legacy, body)
            fixed.append(legacy)
    return fixed


def shim_python(candidate: str | None) -> str | None:
    """bin 심에 박아 둘 파이썬. pythonw.exe(예약 작업)는 옆의 python.exe 로 바꾸고, Store 스텁·없는 파일이면 None."""
    if not candidate:
        return None
    p = Path(candidate)
    if p.name.lower() == "pythonw.exe":
        p = p.with_name("python.exe")
    s = str(p)
    if "windowsapps" in s.lower() or not p.is_file():
        return None
    return s


def tower_bin_body(tower: str, python: str | None) -> str:
    """bin\\linkmycom.cmd·lmc.cmd 내용. 기록된 파이썬이 있으면 tower\\linkmycom.cmd(where·findstr)를 거치지 않고 바로 부른다.

    그 파이썬이 사라졌으면 예전처럼 tower\\linkmycom.cmd 가 PATH 에서 찾는다(WindowsApps 스텁은 그쪽이 건너뜀).
    """
    fallback = f'call "%~dp0..\\{tower}\\linkmycom.cmd" %*\r\n'
    if not python:
        return "@echo off\r\n" + fallback
    py = shim_path(python)
    return ("@echo off\r\n"
            f'if not exist "{py}" goto lmc_find\r\n'
            f'"{py}" "%~dp0..\\{tower}\\linkmycom.py" %*\r\n'
            "exit /b %errorlevel%\r\n"
            ":lmc_find\r\n" + fallback)


def remembered_python() -> str | None:
    """bin 심이 바로 부를 파이썬. state.json 의 'python' 을 쓰고, 없거나 사라졌으면 지금 파이썬을 기록한다."""
    state = load_json(STATE_PATH)
    py = shim_python(state.get("python"))
    if py:
        return py
    py = shim_python(sys.executable)
    if py and state.get("python") != py:
        state["python"] = py
        _save_state_quietly(state)
    return py


def ensure_tower_bin_shims(here: Path, python: str | None = None) -> list[Path]:
    """원클릭 설치기는 타워 폴더 옆 bin 에 tssh.cmd 만 두고 PATH 에 넣었다. 같은 자리에 linkmycom·lmc 도 둔다.

    타워 업데이터로 새 패키지를 받은 PC 는 옛 이름 파일이 이미 넘김 파일이라 옮기기가 일어나지 않으므로
    타워 폴더의 linkmycom.py 가 실행될 때마다 확인한다. 옛 설치기·옛 코드가 한글 사용자 이름을 깨뜨린 절대 경로로
    썼을 수 있으므로 내용이 기대와 다르면 다시 쓴다. 쓴 파일 목록을 돌려준다.
    python: linkmycom·lmc 심이 바로 부를 파이썬(main 이 state 에 기록해 둔 값). 없으면 지금 실행 중인 파이썬.
    tssh.cmd 는 LINKMYCOM_INVOKED_AS 를 넣어야 하므로 예전처럼 tower\\tssh.cmd 를 거친다.
    """
    bin_dir = here.parent.parent / "bin"
    tower = here.parent.name
    if tower.lower() != "tower" or not (bin_dir / "tssh.cmd").exists() or not here.with_name("linkmycom.cmd").exists():
        return []
    body = tower_bin_body(tower, shim_python(python) or shim_python(sys.executable))
    expected = {name: body for name in ("linkmycom.cmd", "lmc.cmd")}
    if here.with_name("tssh.cmd").exists():
        expected["tssh.cmd"] = f'@echo off\r\ncall "%~dp0..\\{tower}\\tssh.cmd" %*\r\n'
    made: list[Path] = []
    for name, text in expected.items():
        path = bin_dir / name
        data = text.encode("ascii" if text.isascii() else shim_encoding(), errors="replace")  # write_shim 과 같은 인코딩
        if not path.exists() or path.read_bytes() != data:
            write_shim(path, text)
            made.append(path)
    return made


def migrate_legacy_install(here: Path) -> list[Path]:
    """옛 이름 파일로 실행됐으면 옆에 linkmycom·lmc 를 설치하고 옛 파일을 넘김 파일로 바꾼다.

    tssh update 가 옛 파일 자리에 이 코드를 받아 처음 실행될 때 한 번 일어난다. 소스 저장소 안에서는 하지 않는다.
    새로 만든 파일 목록을 돌려준다.
    """
    if here.name not in LEGACY_NAMES or any((p / ".git").exists() for p in tuple(here.parents)[:3]):
        return []
    src = here.read_text(encoding="utf-8")
    if is_forwarder(src):
        return []
    made: list[Path] = []
    if here.suffix == ".py":  # Windows: %LOCALAPPDATA%\tssh, 타워 폴더
        new = here.with_name("linkmycom.py")
        replace_text(new, src)
        made.append(new)
        shims = {here.with_name("linkmycom.cmd"): python_shim(sys.executable),
                 here.with_name("lmc.cmd"): '@echo off\r\ncall "%~dp0linkmycom.cmd" %*\r\n'}
        if here.with_name("tssh.ps1").exists():
            shims[here.with_name("linkmycom.ps1")] = (f'& "{shim_path(sys.executable, ps=True)}" "$PSScriptRoot\\linkmycom.py" @args\r\n'
                                                      'exit $LASTEXITCODE\r\n')
        for path, body in shims.items():
            if not path.exists():
                write_shim(path, body)
                made.append(path)
        made += ensure_tower_bin_shims(new)
        replace_text(here, forwarder_source("linkmycom.py"))
    else:  # macOS/Linux: ~/.local/bin/tssh
        new = here.with_name("linkmycom")
        replace_text(new, src, 0o755)
        made.append(new)
        lmc = here.with_name("lmc")
        if not lmc.exists() and not lmc.is_symlink():
            try:
                lmc.symlink_to("linkmycom")
            except OSError:
                replace_text(lmc, src, 0o755)
            made.append(lmc)
        replace_text(here, forwarder_source("linkmycom"), 0o755)
    return made


def legacy_name_notice(invoked_as: str, made: list[Path], state: dict) -> str | None:
    """옛 이름 tssh 로 불렸을 때 사용자에게 보여 줄 안내. None 이면 아무것도 출력하지 않는다.

    invoked_as: 옛 이름으로 불렸으면 "tssh", 새 이름이면 "".
    made: 이번 실행에서 새로 설치한 파일(처음 옮긴 순간에만 비어 있지 않다).
    state: ~/.tssh/state.json 내용. 여기에 값을 넣으면 저장된다(예: 마지막 안내 날짜).
    """
    # 하루 한 번만 알린다. 옛 이름을 쓰는 스크립트·원격 명령을 방해하지 않으면서 잊지 않게 한다.
    today = datetime.now().date().isoformat()
    if not made and state.get("last_tssh_notice") == today:
        return None
    state["last_tssh_notice"] = today
    if made:
        return f"tssh 는 linkmycom(줄여서 lmc)으로 이름이 바뀌었습니다. 같은 폴더에 새 명령을 설치했습니다: {', '.join(p.name for p in made)}"
    return f"알림: {invoked_as} 는 linkmycom(줄여서 lmc)으로 이름이 바뀌었습니다. 옛 이름도 계속 동작합니다."


# ---------------------------------------------------------------- 명령별 도움말과 셸 자동 완성.

COMMAND_HELP = {
    "connect": "linkmycom <이름> [ssh 인자...]\n  이름(일부만 써도 됨)·user@이름·-u/-p/--dns/-n 으로 바로 접속. 호스트 뒤 인자는 ssh 에 그대로 넘긴다.\n"
               "  비대화형(파이프·스크립트)에서 이름이 여러 PC 에 맞으면 후보를 적고 종료 코드 1.",
    "list": "linkmycom list\n  tailscale 에서 바로 읽어 피어 목록을 출력하고, 피어 캐시(~/.tssh/peers.json, 45초 동안 resolve·screen·접속에 씀)와\n"
            "  자동 완성용 호스트 이름 캐시(~/.tssh/hosts.txt)를 갱신한다.",
    "last": "linkmycom last [ssh 인자...]\n  최근 접속한 호스트에 다시 접속.",
    "set": "linkmycom set <이름> user=.. port=.. key=.. alias=a,b args=\"-A -o 'ProxyJump x'\" screen=<다른 이름>\n"
           "  호스트별 접속 설정 저장. 빈 값(user=)은 그 키를 지운다. args 는 셸처럼 따옴표로 묶을 수 있다.",
    "unset": "linkmycom unset <이름>\n  저장한 호스트 설정 삭제.",
    "resolve": "linkmycom resolve <이름>\n  user@주소 를 출력(scp 등에 활용).",
    "export": "linkmycom export\n  ~/.ssh/config 에 관리 블록을 써서 일반 'ssh <이름>' 도 되게 한다.",
    "config": "linkmycom config [키=값 ...]\n  전역 설정: default_user, use_magicdns, update_repo, update_ref, auto_update_check, repo_dir,\n"
              "  keys_url, keys_signer, ssh_options.<옵션>. 인자 없이 쓰면 현재 설정을 보인다.",
    "update": "linkmycom update [--check]\n  거울(jekim14/linkmycom-cli) 최신 릴리스의 linkmycom.py 를 받아 서명(linkmycom.py.sig)·SHA256·문법을\n"
              "  확인한 뒤에만 교체한다. --check 는 확인만.",
    "version": "linkmycom version\n  버전 출력.",
    "help": "linkmycom help [명령]\n  전체 도움말, 또는 그 명령의 도움말.",
    "completion": "linkmycom completion powershell|bash|zsh\n  자동 완성 스크립트를 출력한다. 예:\n"
                  "    PowerShell: linkmycom completion powershell | Out-String | Invoke-Expression   ($PROFILE 에 넣으면 계속)\n"
                  "    bash: source <(linkmycom completion bash)      zsh: source <(linkmycom completion zsh)",
    "doctor": "linkmycom doctor [이름] [--all [--json]]\n  Tailscale, sshd·22 포트, 방화벽 규칙, authorized_keys 권한·내 키 등록, 게시된 키 목록 서명,\n"
              "  CLI·타워·화면공유 앱 버전, PATH 의 lmc, 타워 실행, 화면공유 서비스·21118, 마지막 키 갱신·갱신 예약을 OK/FAIL 표로.\n"
              "  이름을 주면 그 PC 에 같은 점검을 ssh 로 보낸다. --all 은 이 PC 와 온라인 PC 전부를 병렬(5대씩)로 점검해\n"
              "  한 표(행 = PC)로 보이고, --json 은 그 결과를 JSON 으로 출력한다. FAIL 이나 접속 실패가 있으면 종료 코드 1.",
    "exec": "linkmycom exec <이름|이름,이름|all> [--timeout 초] -- <명령...>\n"
            "  BatchMode SSH 로 여러 PC 에 같은 명령을 병렬 실행하고 줄마다 '[이름] ' 을 붙여 출력한다. '--' 뒤는 그대로 넘긴다.\n"
            "  all 은 온라인 PC 중 모바일이 아니고 SSH 포트가 열린 것. 하나라도 실패하면 종료 코드 1(건너뛴 PC 는 실패 아님).",
    "fleet": "linkmycom fleet status [--json]\n  이 PC 와 온라인 PC 의 CLI·타워·화면공유 앱 버전을 한 표로(낡은 CLI 표시).\n"
             "linkmycom fleet update [cli] [-n]\n  이 PC 의 CLI 보다 낡은 원격 설치본만 그 설치본으로 'update' 를 돌린다(-n: 할 일만 출력).\n"
             "  tower·native 는 아직 안내만 한다.",
    "send": "linkmycom send <파일...> --to <이름,이름,...>\n"
            "  Taildrop(tailscale file cp)으로 보낸다. 대상마다 한 번에 모든 파일, 대상은 최대 3곳 병렬. 실패는 대상별로 표시.",
    "inbox": "linkmycom inbox [폴더] [--wait]\n  Taildrop 으로 받은 파일을 폴더(기본 ~/Downloads)로 옮긴다(같은 이름은 번호를 붙임).\n"
             "  --wait: 받은 파일이 없으면 올 때까지 기다림. macOS 는 앱이 Downloads 에 바로 두므로 안내만 한다.",
    "forward": "linkmycom forward <이름> <로컬포트:원격포트>|<로컬포트:원격호스트:원격포트> [...] [-n]\n"
               "  ssh -N -L 로 이 PC 의 127.0.0.1:로컬포트 를 그 PC 의 포트로 잇는다(Ctrl+C 로 끝). -n 은 명령만 출력.",
    "setup": "linkmycom setup [--no-server] [--no-keys] [--no-schedule]\n  SSH 서버 켜기(Tailscale 대역·인터페이스만 허용) + 공개키 교환 + 하루 한 번 'keys refresh' 예약\n"
             "  (Windows 예약 작업 LinkMyCom-KeysRefresh, macOS launchd, Linux systemd 사용자 타이머).",
    "keys": "linkmycom keys [show | refresh [--force] [--quiet] | collect | publish [--collect]]\n"
            "  refresh: 서명된 목록만 적용. 빈 목록은 거부, 관리 블록이 절반 이하로 줄면 --force 가 있어야 적용.\n"
            "  publish: (관리 PC, 거울 클론에서만) ~/.ssh/linkmycom-signing 으로 서명해 authorized_keys·.sig 를 커밋·푸시.",
    "screen": "linkmycom screen <이름> [--gather] [--files | --terminal | --forward [로컬:원격]]\n"
              "  LinkMyCom 화면공유 앱으로 그 PC 화면 보기 창을 연다. --files 파일 전송, --terminal 터미널, --forward 포트 전달 창\n"
              "  (딥링크 file-transfer·terminal·port-forward 와 같은 창). 앱의 포트 전달 창은 규칙을 명령줄로 받지 않아\n"
              "  로컬:원격 은 안내만 한다(바로 이으려면 linkmycom forward). --gather 는 모으기를 기다리지 않고 뷰어를 먼저 띄운다.",
    "display": "linkmycom display <이름|self> [list|gather|single|extend] [--minutes N]\n  여러 모니터 PC 정리.",
    "password": "linkmycom password\n  화면공유 영구 비밀번호를 내 모든 PC 에 한 번에 설정.",
}
COMPLETION_SHELLS = ("powershell", "bash", "zsh")
COMPLETION_WORDS = {
    "keys": ["show", "refresh", "collect", "publish", "--force", "--quiet", "--collect"],
    "help": sorted(SUBCOMMANDS - {"ls"}),
    "completion": list(COMPLETION_SHELLS),
    "setup": ["--no-server", "--no-keys", "--no-schedule"],
    "update": ["--check"],
    "fleet": ["status", "update", "cli", "tower", "native", "--json", "-n"],
    "inbox": ["--wait"],
}
HOST_COMMANDS = ["set", "unset", "resolve", "screen", "display", "doctor", "exec", "forward", "send"]
# 호스트 이름과 함께 옵션도 완성하는 명령.
COMPLETION_HOST_FLAGS = {
    "screen": ["--gather", "--files", "--terminal", "--forward"],
    "doctor": ["--all", "--json"],
    "exec": ["all", "--timeout", "--"],
    "forward": ["-n"],
    "send": ["--to"],
}


def completion_script(shell: str) -> str:
    """셸 자동 완성 스크립트. 호스트 이름은 실행 때마다 ~/.tssh/hosts.txt(목록 캐시)에서 읽는다."""
    subs = " ".join(sorted(SUBCOMMANDS))
    plain_hosts = [h for h in HOST_COMMANDS if h not in COMPLETION_HOST_FLAGS]
    if shell == "powershell":
        cases = "\n".join(f"        '{k}' {{ $words = @({', '.join(repr(w) for w in v)}) }}" for k, v in COMPLETION_WORDS.items())
        cases += "\n" + "\n".join(f"        '{k}' {{ $words = @({', '.join(repr(w) for w in v)}) + $hosts }}"
                                  for k, v in COMPLETION_HOST_FLAGS.items())
        hosts = ", ".join(f"'{h}'" for h in plain_hosts)
        return f"""# linkmycom PowerShell 자동 완성 (linkmycom completion powershell)
Register-ArgumentCompleter -Native -CommandName linkmycom, lmc, tssh -ScriptBlock {{
    param($wordToComplete, $commandAst, $cursorPosition)
    $cache = Join-Path $HOME '.tssh\\hosts.txt'
    $hosts = @(); if (Test-Path -LiteralPath $cache) {{ $hosts = @(Get-Content -LiteralPath $cache -Encoding UTF8) }}
    $parts = @($commandAst.CommandElements | Select-Object -Skip 1 | ForEach-Object {{ $_.ToString() }})
    if ($wordToComplete) {{ $parts = @($parts | Select-Object -First ([Math]::Max(0, $parts.Count - 1))) }}
    $words = @()
    if ($parts.Count -eq 0) {{ $words = @('{subs.replace(' ', "','")}') + $hosts }}
    else {{
      switch ($parts[0]) {{
{cases}
        {{ @({hosts}) -contains $_ }} {{ $words = $hosts }}
      }}
    }}
    $words | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }}
}}
"""
    cases = "\n".join(f"        {k}) words=\"{' '.join(v)}\" ;;" for k, v in COMPLETION_WORDS.items())
    cases += "\n" + "\n".join(f"        {k}) words=\"{' '.join(v)} $hosts\" ;;" for k, v in COMPLETION_HOST_FLAGS.items())
    body = f"""# linkmycom {shell} 자동 완성 (linkmycom completion {shell})
_linkmycom_complete() {{
    local cur="${{COMP_WORDS[COMP_CWORD]}}" words=""
    local hosts=""
    [ -r "$HOME/.tssh/hosts.txt" ] && hosts="$(cat "$HOME/.tssh/hosts.txt")"
    if [ "$COMP_CWORD" -eq 1 ]; then
        words="{subs} $hosts"
    else
        case "${{COMP_WORDS[1]}}" in
{cases}
        {'|'.join(plain_hosts)}) words="$hosts" ;;
        esac
    fi
    COMPREPLY=($(compgen -W "$words" -- "$cur"))
}}
complete -F _linkmycom_complete linkmycom lmc tssh
"""
    if shell == "zsh":
        body = "autoload -U +X bashcompinit && bashcompinit\n" + body
    return body


def write_hosts_cache(peers: list[dict]) -> None:
    """자동 완성용 호스트 이름 목록(한 줄에 하나). 실패해도 조용히 넘어간다."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        replace_text(HOSTS_CACHE_PATH, "".join(p["name"] + "\n" for p in peers if p.get("name")))
    except OSError:
        pass


def cmd_help(args: list[str]) -> int:
    if not args:
        print(__doc__)
        return 0
    name = {"ls": "list"}.get(args[0], args[0])
    text = COMMAND_HELP.get(name)
    if not text:
        die(f"알 수 없는 명령 {args[0]}. 가능: {', '.join(sorted(COMMAND_HELP))}")
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Windows 에서 파이프·Git Bash 로 출력할 때 cp949 로 한글이 깨지지 않도록 UTF-8 로 고정한다.
    if not os.environ.get("PYTHONIOENCODING"):
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            except Exception:
                pass
    try:
        here = Path(__file__).resolve()
        made = migrate_legacy_install(here)
        if here.name == "linkmycom.py" and os.name == "nt":
            repair_shims(here)
            if here.parent.name.lower() == "tower":
                ensure_tower_bin_shims(here, remembered_python())
    except OSError as e:
        made = []
        print(f"새 이름(linkmycom·lmc) 설치를 건너뛰었습니다: {e}", file=sys.stderr)
    invoked_as = "tssh" if made else os.environ.get(INVOKED_AS_ENV, "")
    if invoked_as:
        state = load_json(STATE_PATH)
        message = legacy_name_notice(invoked_as, made, state)
        if message:
            print(message, file=sys.stderr)
            try:
                save_json(STATE_PATH, state)
            except OSError:
                pass
    cfg = load_config()
    sub = argv[0] if argv and argv[0] in SUBCOMMANDS else None

    if sub == "version":
        print(f"linkmycom {__version__}")
        return 0
    if sub == "help" or (argv and argv[0] in ("-h", "--help")):
        return cmd_help(argv[1:] if sub == "help" else [])
    if sub == "completion":
        if len(argv) < 2 or argv[1] not in COMPLETION_SHELLS:
            die(f"사용법: linkmycom completion {'|'.join(COMPLETION_SHELLS)}")
        print(completion_script(argv[1]), end="")
        return 0
    if sub == "doctor":
        return cmd_doctor(cfg, argv[1:])
    if sub == "update":
        return cmd_update(cfg, check_only="--check" in argv[1:])
    if sub == "config":
        cmd_config(cfg, argv[1:])
        return 0
    if sub == "setup":
        return cmd_setup(cfg, argv[1:])
    if sub == "password":
        return cmd_password()
    if sub == "keys":
        return cmd_keys(lambda: (load_peers(tailscale_status()), ssh_config_blocks()), cfg, argv[1:])
    if sub == "exec":
        return cmd_exec(cfg, argv[1:])
    if sub == "fleet":
        return cmd_fleet(cfg, argv[1:])
    if sub == "send":
        return cmd_send(cfg, argv[1:])
    if sub == "inbox":
        return cmd_inbox(argv[1:])
    if sub == "forward":
        return cmd_forward(cfg, argv[1:])

    blocks = ssh_config_blocks()
    # 이름 하나로 끝나는 명령(resolve·screen·display·접속)은 45초 캐시를 먼저 쓰고, 목록·선택기·export·set 은 바로 읽는다.
    host_arg = None
    if sub in ("resolve", "screen", "display"):
        host_arg = next((a for a in argv[1:] if not a.startswith("-")), None)
    elif sub is None and argv:
        host_arg = parse_connect_args(argv)["host"]
    elif sub == "last":
        host_arg = load_json(STATE_PATH).get("last_host")
    if host_arg and host_arg not in ("help", "self", "local", "."):
        peers, from_cache = cached_peers()
        if from_cache and len(resolve(peers, host_arg, cfg, blocks)) != 1:
            peers = fresh_peers()
    else:
        peers = fresh_peers()

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
    if sub == "display":
        return cmd_display(peers, cfg, blocks, argv[1:])
    if sub == "screen":
        return cmd_screen(peers, cfg, blocks, argv[1:])
    if sub == "resolve":
        if len(argv) < 2:
            die("사용법: linkmycom resolve <이름>")
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
        die("대화형 선택은 터미널에서만 됩니다. 'linkmycom <이름>' 으로 호스트를 지정하세요.")
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
