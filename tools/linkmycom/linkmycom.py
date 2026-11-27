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

  linkmycom list [--all] [--json]     피어 목록만 출력(즐겨찾기·최근·온라인 순, --json: 타워·Stream Deck 용).
                                 30일 넘게 꺼진 장비와 hide 로 숨긴 장비는 빼고 보인다(--all 로 표시)
  linkmycom hide <이름>               장비를 목록·선택기·all 대상에서 숨기기(~/.tssh/config.json 의 hidden)
  linkmycom unhide <이름>             숨긴 장비를 되돌리기
  linkmycom forget <이름> [-n]        없어진(꺼진) 노드의 로컬 흔적(설정·known_hosts·MAC 기억·캐시)을 지움
  linkmycom set <이름> user=.. port=.. key=.. alias=.. args=..   호스트별 접속 설정 저장
  linkmycom unset <이름>              저장한 호스트 설정 삭제
  linkmycom resolve <이름>            user@주소 형태로 출력 (scp 등에 활용)
  linkmycom export                    ~/.ssh/config 에 linkmycom 관리 블록 기록
  linkmycom config [키=값 ...]        전역 설정 보기/변경 (default_user, use_magicdns, update_repo, update_ref,
                                 auto_update_check, auto_update_apply, repo_dir, keys_url, keys_signer,
                                 ssh_options.<옵션>)
  linkmycom update [--check]          거울의 최신 릴리스를 서명 확인 뒤 적용(--check: 확인만). 대화형 실행이면 1시간에
                                 한 번 확인해 서명 확인 뒤 바로 교체(auto_update_apply=false 로 끔), 비대화형은 하루 한 번 확인만
  linkmycom update --all [--check] [-n]   이 PC 의 CLI·타워·화면공유 앱을 차례로 확인·적용
  linkmycom status [--json]           이 PC 요약(버전 3종·자동 업데이트·디스크·업데이터·예약 작업·켜진 장비·중계·받은 파일·포트 전달)
  linkmycom version                   버전 출력
  linkmycom help [명령]               도움말(명령을 주면 그 명령만)
  linkmycom completion powershell|bash|zsh   셸 자동 완성 스크립트 출력(호스트 이름은 list 캐시)
  linkmycom doctor [이름] [--json] [--all] [--fix [-n]] [--permissions]   이 PC(또는 그 PC, --all: 온라인 PC 전부 병렬)의
                                 Tailscale(Mac 은 설치별)·sshd·방화벽·authorized_keys·버전·키 갱신 예약·예약 작업·디스크·업데이터·
                                 화면공유 서비스·클립보드 수신·자동 업데이트 점검표. --permissions: Mac 의 화면 기록·손쉬운 사용·입력 모니터링 판정
  linkmycom exec <이름|a,b|all> -- <명령...>   여러 PC 에 같은 명령을 병렬 실행([이름] 접두어, 하나라도 실패면 1)
  linkmycom fleet status | update [cli] [-n] | update native|tower [--apply [--wait [초]]] | rollback <이름|all> cli
                                 각 PC 의 버전·거울 최신 판정·디스크·업데이터·자동 업데이트 표 / 낡은 PC 만 원격 CLI 업데이트 /
                                 원격의 화면공유·타워 업데이터 시작(--wait: 결과까지 기다림) / .prev 로 되돌리기
  linkmycom fleet fix [이름|a,b|all] [-n]   원격 PC 에서 관리자 권한 없는 복구(doctor --fix --no-admin)를 돌려 PC 별 결과 표
  linkmycom exec ... [--os windows|macos|linux] [--ps]   OS 로 거르기, Windows 대상 PowerShell 감싸기
  linkmycom send <파일...> --to <이름,...>     Taildrop 으로 파일 보내기(대상 병렬)
  linkmycom inbox [폴더] [--wait]     Taildrop 으로 받은 파일을 폴더(기본 Downloads)로 옮기기
  linkmycom clip <이름,...> [--text "..."] [--file <경로>...]
                                 클립보드(또는 텍스트·파일)를 그 PC 들의 LinkMyCom 앱(0.6.0 트레이, 21120)으로 보내기
  linkmycom forward <이름> [<로컬:원격>...] [--bg] | forward list | forward stop [번호|all]
                                 ssh -N -L 로 포트 잇기(--bg: 백그라운드, 규칙을 빼면 set <이름> forward=.. 저장 규칙)
  linkmycom open <이름> [경로]        그 PC 의 공유 폴더 열기(Windows 탐색기 UNC 경로, macOS smb://)
  linkmycom cp [-r] <원본...> <이름>:<경로> | cp <이름>:<경로>... <로컬>   scp 로 복사(Windows 대상은 scp -O)
  linkmycom wake <이름> [--via <켜진 PC>] [-n]   doctor 가 모은 MAC 주소로 같은 LAN 의 켜진 PC 에서 매직 패킷
  linkmycom profiles windows-terminal|iterm [-n]   PC 마다 터미널 프로필(관리 표시가 있는 파일만 다시 씀)
  linkmycom audit [이름|all] [--since 7d] [--json]   들어온 SSH 접속을 키 주석으로 풀어 누가·언제·어디서 표
  linkmycom history [이름] [--since 7d]   접속 기록(connect·screen·send·exec·forward·fleet)
  linkmycom hostkey reset <이름>      바뀐 호스트 키를 지우고 지문 확인 뒤 다시 등록
  linkmycom sessions close [-n]       화면공유 세션 창만 닫기(홈·트레이는 그대로)
  linkmycom maintain [--quiet]        일일 유지(키 갱신·타워 시작·관리자 필요 항목 기록, 예약 작업이 부름)

  linkmycom setup [--no-server] [--no-keys] [--no-schedule]
                                 이 컴퓨터를 SSH 서버로 켜고(Tailscale 대역만 허용) 공개키를 교환하고
                                 하루 한 번 'keys refresh' 를 예약
  linkmycom keys [show|refresh [--force] [--quiet]]   내 공개키 보기 / 서명된 공개키 목록을 받아 authorized_keys 갱신
  linkmycom keys collect | publish [--collect]   (관리 PC) 각 컴퓨터의 공개키를 모아(collect) 서명해 거울 저장소에 게시

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

__version__ = "0.7.2"

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
               "send", "inbox", "exec", "fleet", "forward", "clip", "maintain", "history", "hostkey", "sessions",
               "open", "cp", "wake", "profiles", "audit", "status", "hide", "unhide", "forget"}
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
    cfg.setdefault("auto_update_apply", True)
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
    record_history("connect", [peer["name"]])
    try:
        rc = subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130
    if rc == 255:
        # ssh 가 터미널에 직접 쓰므로 원인을 읽지 못한다. 흔한 원인 하나만 짧게 안내한다.
        print(c(f"ssh 가 255 로 끝났습니다. 위에 '{HOSTKEY_FAILED}' 가 보였다면: linkmycom hostkey reset {peer['name']}", "90"),
              file=sys.stderr)
    return rc


# ---------------------------------------------------------------- 목록과 선택기.

HEADER = ["#", " ", "이름", "OS", "Tailscale IP", "접속"]


def is_fav(peer: dict, cfg: dict) -> bool:
    return bool((cfg.get("hosts", {}).get(peer["name"]) or {}).get("fav"))


STALE_DAYS = 30


def hidden_names(cfg: dict) -> list[str]:
    """config.json 의 hidden(숨긴 장비 이름 목록). 앱·타워도 같은 키를 읽는다."""
    raw = cfg.get("hidden")
    return [str(x) for x in raw if isinstance(x, str)] if isinstance(raw, list) else []


def is_hidden(peer: dict, cfg: dict) -> bool:
    return peer.get("name", "").lower() in {h.lower() for h in hidden_names(cfg)}


def is_stale(peer: dict, now: datetime | None = None, days: int = STALE_DAYS) -> bool:
    """꺼져 있고 마지막으로 본 지 days 일이 넘은 장비. 마지막 시각을 모르면(0001-…) 낡았다고 보지 않는다."""
    if peer.get("online"):
        return False
    value = peer.get("last_seen") or ""
    if not value or value.startswith("0001-"):
        return False
    try:
        seen = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - seen).total_seconds() > days * 86400


def is_tucked_away(peer: dict, cfg: dict, now: datetime | None = None) -> bool:
    """list·선택기에서 기본으로 숨기는 장비(hide 한 것, 30일 넘게 꺼진 것)."""
    return is_hidden(peer, cfg) or is_stale(peer, now)


def ordered_peers(peers: list[dict], cfg: dict, show_mobile: bool = False, recent: list[str] | None = None,
                  show_hidden: bool = True) -> list[dict]:
    """선택기·list 의 순서: 즐겨찾기 → 최근 접속 5대(최근 순) → 온라인 → 오프라인, 각 묶음 안은 이름순.

    모바일(SSH 없음)은 show_mobile 일 때만 넣는다. 번호는 이 순서의 자리라서 검색으로 줄여 보여도 바뀌지 않는다.
    show_hidden 이 False 면 hide 한 장비와 30일 넘게 꺼진 장비를 뺀다(0.7.0, list·선택기의 기본).
    """
    recent = recent_hosts(5) if recent is None else recent
    if not show_hidden:
        peers = [p for p in peers if not is_tucked_away(p, cfg)]

    def key(p: dict) -> tuple:
        if is_fav(p, cfg):
            return (0, not p["online"], 0, p["name"].lower())
        if p["name"] in recent:
            return (1, 0, recent.index(p["name"]), p["name"].lower())
        return (2 if p["online"] else 3, 0, 0, p["name"].lower())

    return sorted((p for p in peers if show_mobile or p.get("os") not in MOBILE_OS), key=key)


def os_label(value: str) -> str:
    return value if value and value != "?" else "-"


def peer_rows(peers: list[dict], cfg: dict, blocks: list[dict], last: str | None,
              numbers: list[int] | None = None) -> list[list[str]]:
    rows = []
    for i, p in zip(numbers or range(1, len(peers) + 1), peers):
        if p.get("os") in MOBILE_OS:
            info = "SSH 없음"
        else:
            st = host_settings(p, cfg, blocks)
            user = st.get("user") or getpass.getuser()
            info = f"{user}@" + (f":{st['port']}" if st.get("port") else "")
        if not p["online"]:
            ls = humanize_last_seen(p["last_seen"])
            info += f"  (마지막 {ls})" if ls else ""
        mark = "*" if p["name"] == last else ("★" if is_fav(p, cfg) else " ")
        status = c("●", "32") if p["online"] else c("○", "90")
        rows.append([str(i), status, mark + p["name"], os_label(p["os"]), p["ip"], info])
    return rows


def peers_json(peers: list[dict], cfg: dict) -> list[dict]:
    """list --json 의 고정 형식(타워·Stream Deck 생성기가 읽는다). 키를 바꾸지 않는다."""
    return [{"name": p["name"], "ip": p["ip"], "dns": p.get("dns", ""), "os": p.get("os", "?"),
             "online": bool(p.get("online")), "cur_addr": p.get("cur_addr", ""), "relay": p.get("relay", ""),
             "fav": is_fav(p, cfg), "last_seen": p.get("last_seen", "")} for p in peers]


def _visible_len(s: str) -> int:
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def print_table(rows: list[list[str]], header: list[str]) -> None:
    widths = [max(_visible_len(r[i]) for r in [header] + rows) for i in range(len(header))]
    for r in [header] + rows:
        line = "  ".join(cell + " " * (widths[i] - _visible_len(cell)) for i, cell in enumerate(r))
        print(line.rstrip())


def show_list(peers: list[dict], cfg: dict, blocks: list[dict], show_all: bool = False, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(peers_json(peers, cfg), ensure_ascii=False, indent=2))
        return
    last = load_json(STATE_PATH).get("last_host")
    shown = ordered_peers(peers, cfg, show_mobile=show_all, show_hidden=show_all)
    if not shown:
        print("표시할 피어가 없습니다.")
    else:
        print_table(peer_rows(shown, cfg, blocks, last), HEADER)
    mobile = len([p for p in peers if p.get("os") in MOBILE_OS]) if not show_all else 0
    tucked = len([p for p in peers if is_tucked_away(p, cfg) and p.get("os") not in MOBILE_OS]) if not show_all else 0
    if mobile:
        print(c(f"SSH 가 없는 모바일 {mobile}대는 숨김(--all 로 표시)", "90"))
    if tucked:
        print(c(f"숨긴 장비·{STALE_DAYS}일 넘게 꺼진 장비 {tucked}대는 빼고 보임(--all 로 표시, 되돌리기: linkmycom unhide <이름>)", "90"))


def pick_interactive(peers: list[dict], cfg: dict, blocks: list[dict], notice: list[str]) -> dict | None:
    """번호나 이름 조각을 입력받아 피어 하나를 고른다. None 이면 종료. 번호는 ordered_peers 의 자리로 고정."""
    last = load_json(STATE_PATH).get("last_host")
    all_peers = peers
    peers = ordered_peers(all_peers, cfg, show_hidden=False) or ordered_peers(all_peers, cfg)
    shown = peers
    while True:
        print()
        online = sum(1 for p in peers if p["online"])
        print(c(f"Tailscale SSH 접속기 v{__version__}", "1") + f"   온라인 {online}/{len(peers)}")
        for line in notice[:3]:
            print(c(line, "33"))
        print_table(peer_rows(shown, cfg, blocks, last, [peers.index(p) + 1 for p in shown]), HEADER)
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
            if 1 <= idx <= len(peers):
                return peers[idx - 1]
            print(c(f"1~{len(peers)} 사이 번호를 입력하세요.", "31"))
            continue
        found = resolve(peers, raw, cfg, blocks)
        if len(found) == 1:
            return found[0]
        if not found:
            hidden_match = resolve(all_peers, raw, cfg, blocks)  # 숨긴 장비도 이름으로는 고를 수 있다
            if len(hidden_match) == 1:
                return hidden_match[0]
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


def env_without_fd_state() -> dict[str, str]:
    """환경 변수 사본에서 '*_POSIX_FD_STATE'(Windows OpenSSH 세션이 심는 표준 입력 대체 표시)를 뺀다."""
    return {k: v for k, v in os.environ.items() if not k.upper().endswith("_POSIX_FD_STATE")}


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
        # 0.7.0: Windows SSH 세션 환경의 '<해시>_POSIX_FD_STATE' 변수가 보이면 Windows ssh-keygen 이 표준 입력 대신 SSH 채널을
        # 읽어 멈추거나 죽는다(0xC0000005). 그 변수만 가리고 부른다.
        try:
            with open(data_path, "rb") as fin:
                r = subprocess.run([exe, "-Y", "verify", "-f", str(allowed), "-I", SIGNER_IDENTITY, "-n", namespace,
                                    "-s", str(sig_path)], stdin=fin, capture_output=True, timeout=30,
                                   env=env_without_fd_state())
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, f"ssh-keygen 을 실행하지 못했습니다: {e}"
    if r.returncode == 0:
        return True, ""
    msg = (r.stderr + r.stdout).decode("utf-8", "replace").strip()
    low = msg.lower()
    if "unknown option" in low or "illegal option" in low or "usage:" in low:
        return False, "이 ssh-keygen 은 서명 검증(-Y verify)을 지원하지 않습니다(OpenSSH 8.1 이상 필요)"
    return False, "서명이 맞지 않습니다" + (f" ({msg.splitlines()[-1]})" if msg else "")


CLI_TAG_RE = re.compile(r"^v\d+(\.\d+)+$")


def latest_release(repo: str, timeout: float = 10.0) -> dict:
    """거울 저장소의 최신 CLI 릴리스(태그 v<버전>, 비인증 API). 실패하면 예외.

    0.4.0 타워·0.6.0 앱부터 같은 거울에 tower-v*·native-v* 릴리스도 올라가므로 /releases/latest 는
    다른 구성요소를 돌려줄 수 있다. 목록을 받아 CLI 태그 중 가장 높은 버전을 고른다.
    """
    data = http_get(f"https://api.github.com/repos/{repo}/releases?per_page=30", timeout,
                    {"Accept": "application/vnd.github+json"})
    rels = json.loads(data.decode("utf-8"))
    if not isinstance(rels, list):
        raise RuntimeError(f"{repo} 의 릴리스 목록을 읽지 못했습니다.")
    cands = [r for r in rels if isinstance(r, dict) and CLI_TAG_RE.match(str(r.get("tag_name") or ""))
             and not r.get("draft") and not r.get("prerelease")]
    if not cands:
        raise RuntimeError(f"{repo} 에 CLI 릴리스(v<버전>)가 없습니다.")
    return max(cands, key=lambda r: parse_version(r["tag_name"]))


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
    state.pop("update_error", None)
    save_json(STATE_PATH, state)
    print(f"{target} 를 {remote} 으로 교체했습니다.")
    return 0


def auto_apply_allowed(cfg: dict) -> bool:
    """자동 적용 조건: 설정 auto_update_apply(기본 켬) + 대화형 터미널. 파이프·--json 같은 비대화형은 확인만 한다."""
    if not cfg.get("auto_update_apply", True):
        return False
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def apply_update_quietly(repo: str, rel: dict, st: dict, notice: list[str]) -> bool:
    """백그라운드에서 서명·SHA256 을 확인한 새 판으로 바로 교체한다. 실패는 st['update_error'] 에만 남긴다."""
    try:
        src, remote = fetch_release_source(repo, rel)
        if parse_version(remote) <= parse_version(__version__):
            return False
        write_self(update_target(Path(__file__).resolve()), src)
    except Exception as e:  # noqa: BLE001 - 접속 화면을 막지 않는다
        st["update_error"] = f"{datetime.now(timezone.utc).isoformat()[:19]} {e}"
        return False
    st.pop("update_available", None)
    st.pop("update_error", None)
    st["last_auto_update"] = remote
    notice.append(f"linkmycom {remote} 으로 업데이트했습니다. 다음 실행부터 적용.")
    return True


UPDATE_CHECK_INTERVAL = 86400  # 비대화형(확인만): 하루 한 번
UPDATE_CHECK_INTERVAL_APPLY = 3600  # 대화형 자동 적용: 1시간에 한 번(0.6.0, 실행 시 자동 업데이트 계약)


def seconds_since(stamp: str) -> float:
    """ISO 시각 문자열부터 지금까지 초. 비었거나 읽지 못하면 아주 큰 값."""
    try:
        t = datetime.fromisoformat(stamp) if stamp else None
    except ValueError:
        t = None
    if t is None:
        return 1e9
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds()


def background_update_check(cfg: dict, notice: list[str], apply: bool | None = None) -> threading.Thread | None:
    """새 버전을 조용히 확인한다. 자동 적용이 허용되면(대화형) 1시간에 한 번 확인해 서명 확인 뒤 바로 교체하고,
    아니면 하루 한 번 확인해 notice 에 알림 한 줄. 키 갱신은 확인 주기와 상관없이 하루 한 번만 한다."""
    if not cfg.get("auto_update_check", True):
        return None
    if apply is None:
        apply = auto_apply_allowed(cfg)
    state = load_json(STATE_PATH)
    interval = UPDATE_CHECK_INTERVAL_APPLY if apply else UPDATE_CHECK_INTERVAL
    if seconds_since(state.get("last_update_check", "")) < interval:
        if state.get("update_available"):
            notice.append(f"새 버전 {state['update_available']} 이(가) 있습니다. 'linkmycom update' 로 적용하세요.")
        return None

    def work() -> None:
        if state.get("setup_done") and seconds_since(state.get("last_keys_refresh", "")) >= UPDATE_CHECK_INTERVAL:
            try:
                refresh_keys(cfg, quiet=True)  # 상태 파일에 갱신 기록을 남기므로 아래에서 다시 읽는다.
            except Exception:  # noqa: BLE001
                pass
        st = load_json(STATE_PATH)
        st["last_update_check"] = datetime.now(timezone.utc).isoformat()
        try:
            repo = cfg.get("update_repo") or DEFAULT_REPO
            rel = latest_release(repo, timeout=4)
            remote = rel["tag_name"].lstrip("v")
            if remote and parse_version(remote) > parse_version(__version__):
                st["update_available"] = remote
                if not (apply and apply_update_quietly(repo, rel, st, notice)):
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


# 하루 한 번 'linkmycom maintain --quiet'(키 갱신 포함) 예약. 이름은 고정이라 setup 을 다시 해도 하나만 남는다.
SCHEDULE_TASK_NAME = "LinkMyCom-KeysRefresh"
LAUNCHD_LABEL = "com.linkmycom.keys-refresh"
SYSTEMD_UNIT = "linkmycom-keys"


def refresh_command(python: str, script: str) -> list[str]:
    # 0.5.0: 키 갱신만 하던 일일 작업을 maintain(키 갱신 + 관리자 권한 없는 복구 + 상태 기록)으로 넓혔다. 작업 이름은 그대로.
    return [python, script, "maintain", "--quiet"]


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
        "-Description 'linkmycom maintain: keys refresh and repairs (daily)' -Force | Out-Null",
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
    timer = ("[Unit]\nDescription=linkmycom maintain (daily)\n\n"
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
                warn("systemctl 이 없어 키 자동 갱신을 예약하지 못했습니다. cron 에 'linkmycom maintain --quiet' 를 넣으세요.")
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
        die("화면공유 앱(LinkMyCom, 옛 설치본은 DeskTools·RustDesk) 실행 파일을 찾지 못했습니다. LinkMyCom 설치기를 먼저 실행하세요.")
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
    record_history("screen", [peer["name"]], detail=switch)
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
UPD_TASKS = ("LinkMyCom-NativeUpdate", "LinkMyCom-TowerUpdate")
TOWER_TASK = "LinkMyCom-Tower"
UPD_ALL = UPD_TASKS + (TOWER_TASK,)
UPD_LAUNCHD = "com.linkmycom.native-update"
CLIP_PORT = 21120
PIPE = subprocess.PIPE
UPDATER_STUCK_MIN = 30
LOW_DISK_BYTES = 2 * 1024 ** 3
MAC_TS_APP = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
MAC_TS_SOCKET = "/var/run/tailscaled.socket"
# Updater processes (tower: Update-LinkMyCom.ps1, native: Update-Native.ps1) with their age in minutes. The regex text cannot match
# this query's own command line (it has no whitespace right after -File), and its own PID is skipped as well.
PS_UPDATERS = (r"Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.Name -match '^(powershell|pwsh)' "
               r"-and $_.CommandLine -match '-File\s+\S*Update-(LinkMyCom|Native)\.ps1' } | ForEach-Object { 'UPD;' + "
               r"$_.ProcessId + ';' + [int]((Get-Date) - $_.CreationDate).TotalMinutes }")

def gb_text(n):
    return "%.1f GB" % (n / 1073741824.0)

def disk_row(items):
    # items: [(label, free_bytes)] -> (status, detail); WARN when any of them is under 2 GB
    text = ", ".join("%s %s free" % (l, gb_text(f)) for l, f in items)
    if any(f < LOW_DISK_BYTES for _, f in items):
        return "WARN", text + " (low)"
    return "OK", text

def etime_minutes(text):
    # ps etime [[dd-]hh:]mm:ss -> whole minutes
    t = text.strip()
    days = 0
    if "-" in t:
        d, t = t.split("-", 1)
        days = int(d)
    parts = [int(x) for x in t.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return days * 1440 + parts[0] * 60 + parts[1]

def updater_row(procs):
    # procs: [(pid, minutes)] -> (status, detail); an updater running over 30 minutes is stuck
    if not procs:
        return "OK", "idle"
    pid, mins = max(procs, key=lambda p: p[1])
    if mins > UPDATER_STUCK_MIN:
        return "WARN", "stuck %d min (pid %s)" % (mins, pid)
    return "OK", "running %d min (pid %s)" % (mins, pid)

def ts_brief(st):
    # tailscale status dict -> (BackendState, node name, first IP, version)
    me = st.get("Self") or {}
    ips = me.get("TailscaleIPs") or []
    name = (me.get("DNSName") or me.get("HostName") or "").split(".")[0]
    return (st.get("BackendState") or "?", name, ips[0] if ips else "", str(st.get("Version") or "").split("-")[0])

def ts_install_rows(app, brew):
    # macOS: one row per Tailscale install (Tailscale.app / Homebrew tailscaled), plus a WARN when both are logged in.
    rows = []
    for key, label, st, none in (("ts_app", "Tailscale.app", app, "not installed or not responding"),
                                 ("ts_brew", "Homebrew tailscaled", brew, "no daemon socket")):
        if st is None:
            rows.append((key, "INFO", "%s: %s" % (label, none)))
            continue
        state, name, ip, ver = ts_brief(st)
        rows.append((key, "OK" if state == "Running" else "INFO",
                     "%s: %s %s %s (%s)" % (label, name or "-", ip or "-", ver or "?", state)))
    if app is not None and brew is not None:
        a, b = ts_brief(app), ts_brief(brew)
        if a[0] == "Running" and b[0] == "Running":
            rows.append(("ts_dup", "WARN", "both installs are logged in as separate nodes (%s %s / %s %s); keep one "
                         "(brew services stop tailscale, or log one out; tools/mac/Find-TailscaleInstalls.sh)"
                         % (a[1] or "-", a[2], b[1] or "-", b[2])))
    return rows

def jload(text):
    try:
        v = json.loads(text)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None

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

PSP = TASKP = NETP = PSOUT = None
if WIN:
    q = AK.replace("'", "''")
    # One PowerShell run does everything: the updater-process query always, the sshd/firewall/ACL/service checks unless --versions.
    PSP = start(["powershell", "-NoProfile", "-NonInteractive", "-Command", "\n".join([
        "$ErrorActionPreference = 'SilentlyContinue'",
        PS_UPDATERS] + ([] if ONLY_VERSIONS else [
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
        "$c = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | "
        "Sort-Object { $_.NetAdapter.MediaType -ne '802.3' } | Select-Object -First 1",
        "if ($c) { 'LAN;' + $c.NetAdapter.MacAddress + ';' + @($c.IPv4Address)[0].IPAddress + ';' + @($c.IPv4Address)[0].PrefixLength } else { 'LAN;' }",
    ]))])
    if not ONLY_VERSIONS:
        TASKP = start(["schtasks", "/Query", "/TN", TASK])
        NETP = start(["netstat", "-an", "-p", "TCP"])
UPDP = [start(["schtasks", "/Query", "/TN", t]) for t in UPD_ALL] if WIN else []

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
        PSOUT = finish(PSP, 90)[1]
        for line in PSOUT.splitlines():
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

# auto_update: daily updater jobs (native/tower) and the last result they wrote. Also in --versions mode (fleet status).
TASK_OK = {}
if WIN or MAC:
    have, miss = [], []
    if WIN:
        for name, p in zip(UPD_ALL, UPDP):
            # A standard user gets "access denied" from schtasks for the SYSTEM task, so also look for its file.
            TASK_OK[name] = finish(p, 30)[0] == 0 or os.path.exists(os.path.join(
                os.environ.get("SystemRoot", "C:/Windows"), "System32", "Tasks", name))
        for name, needed in ((UPD_TASKS[0], bool(nv)), (UPD_TASKS[1], bool(tower_ver))):
            if TASK_OK.get(name):
                have.append(name)
            elif needed:
                miss.append(name)
        spath = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "LinkMyCom", "update-state.json")
    else:
        dirs = ["/Library/LaunchDaemons", "/Library/LaunchAgents", os.path.join(HOME, "Library", "LaunchAgents")]
        if any(os.path.exists(os.path.join(d, UPD_LAUNCHD + ".plist")) for d in dirs):
            have.append(UPD_LAUNCHD)
        elif nv:
            miss.append(UPD_LAUNCHD)
        spath = os.path.join(HOME, "Library", "Application Support", "LinkMyCom", "update-state.json")
    try:
        ust = json.loads(read(spath) or "{}")
    except ValueError:
        ust = {"lastResult": "state file unreadable"}
    ust = ust if isinstance(ust, dict) else {}
    res = ust.get("lastResult")
    if isinstance(res, dict):
        res = res.get("result") or res.get("status") or json.dumps(res)
    last = ("%s %s" % (res or "?", str(ust.get("checked") or "")[:16].replace("T", " "))).strip() if ust else ""
    parts = (["tasks " + ",".join(have)] if have else []) + (["missing " + ",".join(miss)] if miss else [])
    parts.append(("last " + last) if last else "no run recorded")
    if not have and not miss:
        out("auto_update", "INFO", "no updater job (native/tower not installed)")
    elif miss or re.search(r"(?i)fail|error", last):
        out("auto_update", "WARN", "; ".join(parts))
    else:
        out("auto_update", "OK", "; ".join(parts))

# The three scheduled tasks one by one (also in --versions mode); the keys-refresh task is reported later as keys_task.
if WIN:
    for key, name, needed, hint in (
            ("task_tower", TOWER_TASK, bool(tower_ver), "run 'lmc doctor --fix'"),
            ("task_tower_update", UPD_TASKS[1], bool(tower_ver), "run 'lmc doctor --fix'"),
            ("task_native_update", UPD_TASKS[0], bool(nv), "re-run the LinkMyCom installer as administrator")):
        if not needed:
            out(key, "INFO", "%s not needed (not installed)" % name)
        elif TASK_OK.get(name):
            out(key, "OK", name)
        else:
            out(key, "WARN", "%s missing (%s)" % (name, hint))

# disk: free space of the system drive and the drive holding %LOCALAPPDATA% (Windows), or / and home. updater: stuck updater.
free = []
if WIN:
    seen_drives = []
    for d in (os.environ.get("SystemDrive", "C:"), os.path.splitdrive(LAD)[0]):
        if d and d.upper() not in seen_drives:
            seen_drives.append(d.upper())
    for d in seen_drives:
        try:
            free.append((d, shutil.disk_usage(d + "\\").free))
        except OSError:
            pass
else:
    seen_dev = set()
    for label, p in (("/", "/"), ("~", HOME)):
        try:
            dev = os.stat(p).st_dev
            if dev not in seen_dev:
                seen_dev.add(dev)
                free.append((label, shutil.disk_usage(p).free))
        except OSError:
            pass
if free:
    out("disk", *disk_row(free))
else:
    out("disk", "INFO", "free space unknown")

procs = []
if WIN:
    if PSOUT is None:
        PSOUT = finish(PSP, 60)[1]
    for line in PSOUT.splitlines():
        f = line.strip().split(";")
        if len(f) == 3 and f[0] == "UPD":
            try:
                procs.append((f[1], int(f[2])))
            except ValueError:
                pass
    out("updater", *updater_row(procs))
elif MAC:
    rc, o = run(["ps", "-axo", "pid=,etime=,command="], 15)
    for line in o.splitlines():
        f = line.split(None, 2)
        if len(f) == 3 and "Update-Native-Mac.sh" in f[2] and "LMCUPD" not in f[2]:
            try:
                procs.append((f[0], etime_minutes(f[1])))
            except ValueError:
                pass
    out("updater", *updater_row(procs))
else:
    out("updater", "INFO", "no updater on this OS")

if MAC and not ONLY_VERSIONS:
    app_st = brew_st = None
    if os.path.exists(MAC_TS_APP):
        rc, o = run([MAC_TS_APP, "status", "--json", "--peers=false"], 20)
        app_st = jload(o) if rc == 0 else None
    if os.path.exists(MAC_TS_SOCKET):
        exe = next((x for x in (shutil.which("tailscale") or "", "/opt/homebrew/bin/tailscale", "/usr/local/bin/tailscale",
                                MAC_TS_APP) if x and os.path.exists(x)), "")
        if exe:
            rc, o = run([exe, "--socket=" + MAC_TS_SOCKET, "status", "--json", "--peers=false"], 20)
            brew_st = jload(o) if rc == 0 else None
    for r in ts_install_rows(app_st, brew_st):
        out(*r)
    out("permissions", "INFO", "not checked (needs sudo): run 'lmc doctor --permissions' to check screen recording, accessibility and input monitoring")

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

    # clip_port: the tray process (linkmycom --tray, 0.6.0+) receives clipboard messages on 21120.
    if WIN or MAC:
        try:
            socket.create_connection(("127.0.0.1", CLIP_PORT), 1.0).close()
            out("clip_port", "OK", "%d listening (tray running)" % CLIP_PORT)
        except OSError:
            nvt = tuple(int(x) for x in re.findall(r"\d+", nv)[:3])
            if not nv:
                out("clip_port", "INFO", "screen-sharing app not installed")
            elif nvt < (0, 6, 0):
                out("clip_port", "INFO", "needs LinkMyCom 0.6.0+ (installed %s)" % nv)
            else:
                out("clip_port", "WARN", "%d not listening (tray process not running)" % CLIP_PORT)
    else:
        out("clip_port", "SKIP", "no tray app on this OS")

    # lan: MAC and IPv4/prefix of the default-route interface ('lmc wake' remembers them in ~/.tssh/macs.json).
    lan = ("", "", "")
    if WIN:
        p = (PS.get("LAN") or "").split(";")
        if len(p) >= 3 and p[0]:
            lan = (p[0].replace("-", ":").lower(), p[1], p[2])
    elif MAC:
        rc, o = run(["route", "-n", "get", "default"], 10)
        m = re.search(r"interface: (\S+)", o)
        if m:
            rc, o = run(["ifconfig", m.group(1)], 10)
            e = re.search(r"ether ([0-9a-fA-F:]{17})", o)
            i = re.search(r"inet (\d+\.\d+\.\d+\.\d+) netmask 0x([0-9a-fA-F]{8})", o)
            # Sessions through Tailscale SSH see a masked 'ether 02:00:00:00:00:00'; networksetup still gives the real one.
            rc, ns = run(["networksetup", "-getmacaddress", m.group(1)], 10)
            n = re.search(r"([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})", ns)
            mac = (n or e).group(1).lower() if (n or e) else ""
            if mac and i:
                lan = (mac, i.group(1), str(bin(int(i.group(2), 16)).count("1")))
    else:
        rc, o = run(["ip", "route", "show", "default"], 10)
        m = re.search(r"\bdev (\S+)", o)
        if m:
            mac = (read("/sys/class/net/%s/address" % m.group(1)) or "").strip()
            rc, o = run(["ip", "-4", "-o", "addr", "show", "dev", m.group(1)], 10)
            i = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", o)
            if mac and i:
                lan = (mac.lower(), i.group(1), i.group(2))
    if lan[0] in ("02:00:00:00:00:00", "00:00:00:00:00:00"):
        out("lan", "SKIP", "MAC address is masked in this session")
    elif lan[0]:
        out("lan", "INFO", "mac=%s ip=%s/%s" % lan)
    else:
        out("lan", "SKIP", "no default-route interface found")

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
        out("keys_task", "WARN", "no systemctl; schedule 'linkmycom maintain --quiet' with cron")
'''

DOCTOR_LABELS = {
    "python": "파이썬", "tailscale": "Tailscale", "ssh_port": "SSH 22 포트", "sshd": "sshd 서비스",
    "firewall": "방화벽 규칙", "authorized_keys": "authorized_keys", "ak_acl": "authorized_keys 권한",
    "my_key": "내 공개키 등록", "keys_list": "게시된 키 목록", "cli": "CLI 버전", "tower": "타워 버전",
    "native": "화면공유 앱 버전", "keys_refresh": "마지막 키 갱신",
    "path_lmc": "PATH 의 lmc", "tower_run": "타워 실행", "screen_svc": "화면공유 서비스·21118",
    "keys_task": "키 갱신 예약", "clip_port": "클립보드 수신·21120", "auto_update": "자동 업데이트",
    "lan": "LAN·MAC 주소", "screen_reach": "21118 도달(이 PC 에서)", "dup_node": "중복 Tailscale 노드",
    "disk": "디스크 여유", "updater": "업데이터 프로세스", "task_tower": "예약 작업 Tower",
    "task_tower_update": "예약 작업 TowerUpdate", "task_native_update": "예약 작업 NativeUpdate",
    "ts_app": "Tailscale.app", "ts_brew": "Tailscale(Homebrew)", "ts_dup": "Tailscale 중복 설치",
    "permissions": "Mac 권한", "perm_screen": "화면 기록", "perm_access": "손쉬운 사용(입력 보내기)",
    "perm_input": "입력 모니터링",
}
DOCTOR_COLORS = {"OK": "32", "FAIL": "31", "WARN": "33", "INFO": "36", "SKIP": "90"}


def doctor_oneliner() -> str:
    """DOCTOR_PY 를 zlib·base64 로 줄여 'python -c' 한 줄로 실행하는 코드."""
    import base64
    import zlib

    packed = base64.b64encode(zlib.compress(DOCTOR_PY.encode("ascii"), 9)).decode("ascii")
    return f"import base64,zlib;exec(zlib.decompress(base64.b64decode('{packed}')))"


DOCTOR_STDIN_END = "__LMCDOC_END__"

# 원격 Windows 에 파이썬이 없을 때 PowerShell 만으로 하는 점검(sshd·방화벽·버전 3개·21118). 같은 LMCDOC 줄을 낸다.
# python 줄을 WARN 으로 내므로 결과 표가 '점검 못 함' 대신 이 줄들로 채워진다. ASCII 만, 한 줄로 이어 붙인다.
WINDOWS_NOPY_DOCTOR_PS = "; ".join([
    "'LMCDOC|python|WARN|python 3 not found; PowerShell-only checks (install: winget install -e --id Python.Python.3.12)'",
    "$s = Get-Service sshd -ErrorAction SilentlyContinue",
    "'LMCDOC|sshd|' + $(if ($s.Status -eq 'Running') { 'OK|Running' } elseif ($s) { 'FAIL|' + $s.Status } else { 'FAIL|sshd service missing' })",
    "$r = Get-NetFirewallRule -Name 'tssh-OpenSSH' -ErrorAction SilentlyContinue",
    "'LMCDOC|firewall|' + $(if ($r -and \"$($r.Enabled)\" -eq 'True') { 'OK|tssh-OpenSSH' } else { 'FAIL|rule tssh-OpenSSH missing or disabled' })",
    "$v = @(); foreach ($p in @(@('linkmycom', 'linkmycom'), @('tower', 'DeskTools\\tower'))) { "
    "$m = Select-String -LiteralPath (Join-Path $env:LOCALAPPDATA ($p[1] + '\\linkmycom.py')) -Pattern '^__version__\\s*=\\s*\"([^\"]+)\"' "
    "-ErrorAction SilentlyContinue | Select-Object -First 1; if ($m) { $v += $p[0] + ' ' + $m.Matches[0].Groups[1].Value } }",
    "'LMCDOC|cli|' + $(if ($v.Count) { 'INFO|' + ($v -join ', ') } else { 'WARN|linkmycom not found in the usual places' })",
    "$t = ''; try { $t = (Get-Content -Raw (Join-Path $env:LOCALAPPDATA 'DeskTools\\tower\\release.json') -ErrorAction Stop | ConvertFrom-Json).version } catch {}",
    "'LMCDOC|tower|INFO|' + $(if ($t) { $t } else { 'not installed' })",
    "$n = ''; try { $n = (Get-Content -Raw (Join-Path $env:ProgramFiles 'LinkMyCom\\LINKMYCOM_VERSION') -ErrorAction Stop).Trim() } catch {}",
    "'LMCDOC|native|INFO|' + $(if ($n) { $n } else { 'not installed' })",
    "$u = @(foreach ($j in 'LinkMyCom-NativeUpdate', 'LinkMyCom-TowerUpdate') { schtasks /Query /TN $j 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { $j } })",
    "'LMCDOC|auto_update|' + $(if ($u.Count) { 'OK|tasks ' + ($u -join ',') } elseif ($n) { 'WARN|missing LinkMyCom-NativeUpdate' } "
    "else { 'INFO|no updater job (native/tower not installed)' })",
    # 0.7.2: 여기서 Net.Sockets.TcpClient 로 21118 에 붙어 보던 것을 뺐다. 이 블록은 -EncodedCommand 명령줄에 실리는데,
    # 소켓 클라이언트를 만드는 인코딩된 PowerShell 을 AhnLab V3 가 행위 탐지(Execution/MDP.Powershell.M2514)로 막아
    # 그 PC 의 원격 점검이 'exec request failed' 로 실패하고 점검 때마다 경고가 떴다(jekimlabtop, 2026-11-27).
    "$l = [bool](Get-NetTCPConnection -LocalPort 21118 -State Listen -ErrorAction SilentlyContinue)",
    "'LMCDOC|screen_svc|' + $(if ($l) { 'OK|21118 listening' } else { 'WARN|21118 not listening' })",
    "$c = Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | "
    "Sort-Object { $_.NetAdapter.MediaType -ne '802.3' } | Select-Object -First 1",
    "'LMCDOC|lan|' + $(if ($c) { 'INFO|mac=' + $c.NetAdapter.MacAddress.Replace('-', ':').ToLower() + ' ip=' + "
    "@($c.IPv4Address)[0].IPAddress + '/' + @($c.IPv4Address)[0].PrefixLength } else { 'SKIP|no default-route interface found' })",
])


STDIN_WAIT_SECONDS = 25
STDIN_TIMEOUT_MARK = "LMCSTDIN|timeout"


def windows_stdin_read_lines(var: str) -> list[str]:
    """Windows 원격 실행기가 표준 입력에서 종료 표시 줄까지 읽어 var 에 문자열로 담는 PowerShell 줄들(0.7.1).

    0.7.0 까지는 [Console]::In.ReadLine() 으로 종료 표시 줄을 기다렸다. sshd 기본 셸이 PowerShell 이면 명령이
    'powershell -c "powershell -EncodedCommand …"' 로 두 겹이 되고, 가끔 안쪽 PowerShell 에 종료 표시 줄이 닿지 않아
    영원히 기다렸다(jekim-1, 2026-11-26: 40시간 동안 멈춘 프로세스 36쌍). 이제 줄마다 시간 제한(STDIN_WAIT_SECONDS)을 두고
    읽고, 넘으면 STDIN_TIMEOUT_MARK 한 줄을 내고 프로세스를 끝낸다. 부르는 쪽(run_remote)이 그 줄을 보면 한 번 다시 시도한다.
    [Console]::In 의 비동기 읽기는 사실은 동기라 원시 스트림 위의 StreamReader 를 쓴다.
    sshd 기본 셸이 cmd.exe 면 명령줄 한도가 8191자라 변수 이름과 공백을 아꼈다(시험이 길이를 확인한다).
    """
    return [
        "$r=New-Object IO.StreamReader([Console]::OpenStandardInput());$a=@()",
        "while(1){$t=$r.ReadLineAsync();if(!$t.Wait(" + str(STDIN_WAIT_SECONDS * 1000) + ")){[Console]::WriteLine('" + STDIN_TIMEOUT_MARK
        + "');[Environment]::Exit(3)};$l=$t.Result;if($null -eq $l -or $l -eq '" + DOCTOR_STDIN_END + "'){break};$a+=$l}",
        var + "=($a -join \"`n\").Trim()",
    ]


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
            # -ea 0 과 ? 는 -ErrorAction SilentlyContinue 와 Where-Object 다(cmd.exe 명령줄 한도 8191자 안에 넣으려고 줄였다).
            "foreach ($n in @('python','python3','py')) { $c = Get-Command $n -ea 0 | "
            "? { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1; if ($c) { $py = $c.Source; break } }",
            "if (-not $py) { " + WINDOWS_NOPY_DOCTOR_PS + "; exit 0 }",
            # Windows OpenSSH sometimes never delivers the stdin EOF to a nested PowerShell, so ReadToEnd() hung
            # for the full timeout and left orphaned wrappers (officehermes, 2026-11-13). Read up to a sentinel line,
            # and give up after STDIN_WAIT_SECONDS when even the sentinel never arrives (0.7.1).
            *windows_stdin_read_lines("$code"),
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
    as_json = "--json" in args
    if "--all" in args:
        return cmd_doctor_all(cfg, as_json=as_json)
    host = next((a for a in args if not a.startswith("-")), None)
    if "--permissions" in args:
        return cmd_doctor_permissions(cfg, host, as_json)
    if not host and "--fix" in args:
        return cmd_doctor_fix(cfg, dry="-n" in args or "--dry-run" in args, no_admin="--no-admin" in args)
    if not host:
        # 게시된 키 목록 받기(네트워크)와 점검 스크립트(PowerShell 등)를 함께 돌린다.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as pool:
            keys_row = pool.submit(doctor_keys_list_row, cfg)
            rows = local_doctor_rows()
            row = keys_row.result()
        idx = next((i for i, x in enumerate(rows) if x[0] == "cli"), len(rows))
        rows.insert(idx, row)
        remember_lans([(None, rows)])
        if as_json:
            return print_doctor_json({"name": platform.node().split(".")[0], "ip": "(이 PC)",
                                      "os": platform.system().lower(), "rows": rows, "error": ""})
        return print_doctor(f"linkmycom doctor · 이 PC ({platform.node()}) · CLI {__version__}", rows)
    blocks = ssh_config_blocks()
    peer, peers = pick_cached(cfg, blocks, host)
    remote, stdin_text = doctor_remote_command(peer["os"], local_key_blob())
    if not as_json:
        print(c(f"→ {peer['name']} 에 점검 스크립트를 보냅니다...", "36"))
    # 이 PC 에서 그 PC 의 21118 도달성과 같은 장비의 중복 Tailscale 노드(C8)를 원격 점검과 함께 본다.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        extra_f = pool.submit(reach_rows, peer, peers, cfg, blocks)
        rc, out, err = run_remote(peer, cfg, blocks, [remote], stdin_text, timeout=180)
        try:
            extra = extra_f.result()
        except Exception:  # noqa: BLE001 - 보조 점검이 실패해도 원격 점검 결과는 보인다
            extra = []
    rows = parse_doctor_lines(out)
    remember_lans([(peer["name"], rows)])
    if as_json:
        return print_doctor_json({"name": peer["name"], "ip": peer["ip"], "os": peer["os"], "rows": rows + extra,
                                  "error": remote_rows_error(rows, err)})
    if not rows:
        reason = remote_rows_error(rows, err).replace("SSH 실패: ", "")
        print_doctor(f"linkmycom doctor · {peer['name']}", [("ssh_port", "FAIL", f"SSH 로 들어가지 못했습니다: {reason}")] + extra)
        return 1
    rows = rows + extra
    result = print_doctor(f"linkmycom doctor · {peer['name']} ({peer['ip']})", rows)
    if any(n == "python" and s in ("WARN", "FAIL") for n, s, _ in rows):
        print(c(f"그 PC 에 파이썬 3 이 없어 일부만 점검했습니다. 설치: linkmycom exec {peer['name']} -- "
                "winget install -e --id Python.Python.3.12", "33"))
    elif "--fix" in args:
        print(f"이 명령은 원격 PC 를 고치지 않습니다. 관리자 권한이 필요 없는 복구는 'linkmycom fleet fix {peer['name']}', "
              f"전부는 그 PC 에서 'linkmycom doctor --fix' 로 하세요(예: linkmycom {peer['name']} lmc doctor --fix).")
    return result


# ---------------------------------------------------------------- Mac 권한 판정 (doctor --permissions, 0.7.0 C2).

# Mac 에서 LinkMyCom 창을 잠깐 열면 권한 검사가 tccd 로그(com.apple.TCC)에 AUTHREQ 줄로 남는다. sudo 로 그 로그를 읽는다.
# 이 스크립트가 띄운 log stream 과 앱 창 프로세스만 끝내고 앱의 --server 프로세스(화면공유 서비스)는 건드리지 않는다.
# sudo 에 비밀번호가 필요하면(sudo -n 이 안 됨) 아무것도 실행하지 않고 'LMCTCC|NOSUDO' 만 낸다.
MAC_PERM_SCRIPT = r'''
APP=/Applications/LinkMyCom.app
BIN="$APP/Contents/MacOS/LinkMyCom"
if [ ! -d "$APP" ]; then echo "LMCTCC|NOAPP"; exit 0; fi
if ! sudo -n true 2>/dev/null; then echo "LMCTCC|NOSUDO"; exit 0; fi
OUT=$(mktemp /tmp/lmc-perm.XXXXXX)
before=$(pgrep -f "^$BIN\$" | tr '\n' ' ')
sudo -n log stream --info --debug --style compact --predicate '(subsystem == "com.apple.TCC" AND (eventMessage CONTAINS "AUTHREQ" OR eventMessage CONTAINS[c] "linkmycom"))' > "$OUT" 2>/dev/null &
STREAM=$!
sleep 2
open -g -a "$APP"
sleep 16
sudo -n pkill -P $STREAM 2>/dev/null; sudo -n kill $STREAM 2>/dev/null
after=$(pgrep -f "^$BIN\$" | tr '\n' ' ')
for p in $after; do case " $before " in *" $p "*) ;; *) kill "$p" 2>/dev/null ;; esac; done
echo "LMCTCC|BEGIN"
ids=$(grep -a -i 'linkmycom' "$OUT" | grep -a -o 'msgID=[0-9.]*' | sort -u)
for id in $ids; do grep -a -w -F "$id" "$OUT" | cut -c1-400 | head -12; done
echo "LMCTCC|END"
rm -f "$OUT"
'''

# tccd 의 service 이름 → 표 줄. 손쉬운 사용은 Accessibility 와 입력 보내기(PostEvent) 두 서비스를 한 줄로 합친다.
TCC_SERVICES = {"kTCCServiceScreenCapture": "perm_screen", "kTCCServiceAccessibility": "perm_access",
                "kTCCServicePostEvent": "perm_access", "kTCCServiceListenEvent": "perm_input"}
TCC_PANE = {"perm_screen": "화면 기록", "perm_access": "손쉬운 사용", "perm_input": "입력 모니터링"}
# authValue: 0 거부, 1 미결정, 2 허용, 3 제한. 합칠 때는 가장 나쁜 값을 쓴다(거부 < 미결정 < 제한 < 허용).
TCC_AUTH_TEXT = {0: "거부됨", 1: "미결정", 2: "허용됨", 3: "제한됨"}
TCC_AUTH_RANK = {0: 0, 1: 1, 3: 2, 2: 3}


def parse_tcc_log(text: str) -> dict[str, int]:
    """tccd 로그 줄에서 {표 줄 이름: authValue} 를 뽑는다. 같은 요청(msgID)의 service= 줄과 authValue= 줄을 묶고,
    같은 서비스를 여러 번 물었으면 마지막 값을, 한 줄로 합치는 서비스끼리는 가장 나쁜 값을 쓴다."""
    reqs: dict[str, dict] = {}
    for line in text.splitlines():
        m = re.search(r"msgID=([0-9.]+)", line)
        if not m:
            continue
        req = reqs.setdefault(m.group(1), {})
        s = re.search(r"service=(kTCCService\w+)", line)
        if s:
            req["service"] = s.group(1)
        a = re.search(r"authValue=(\d+)", line)
        if a:
            req["auth"] = int(a.group(1))
    last: dict[str, int] = {}
    for req in reqs.values():
        if req.get("service") in TCC_SERVICES and req.get("auth") in TCC_AUTH_RANK:
            last[req["service"]] = req["auth"]
    out: dict[str, int] = {}
    for service, auth in last.items():
        key = TCC_SERVICES[service]
        if key not in out or TCC_AUTH_RANK[auth] < TCC_AUTH_RANK[out[key]]:
            out[key] = auth
    return out


def permission_rows(parsed: dict[str, int]) -> list[tuple[str, str, str]]:
    """parse_tcc_log 결과를 doctor 줄로. 허용만 OK, 그 밖은 WARN 과 켜는 곳 안내. 로그에 안 잡힌 권한은 '판정 못 함'."""
    if not parsed:
        return [("permissions", "WARN", "판정 못 함: 로그에 LinkMyCom 의 권한 요청이 하나도 잡히지 않았습니다"
                 "(앱이 이미 떠 있어 검사가 다시 일어나지 않았을 수 있음. 앱을 끝낸 뒤 다시 실행)")]
    rows = []
    for key in ("perm_screen", "perm_access", "perm_input"):
        pane = TCC_PANE[key]
        if key not in parsed:
            rows.append((key, "INFO", "판정 못 함: 이번 로그에 이 권한 요청이 없었습니다"))
            continue
        auth = parsed[key]
        text = f"{TCC_AUTH_TEXT[auth]}(authValue={auth})"
        if auth == 2:
            rows.append((key, "OK", text))
        else:
            rows.append((key, "WARN", f"{text}: 시스템 설정 > 개인정보 보호 및 보안 > {pane} 에서 LinkMyCom 을 켜세요"))
    return rows


def permission_rows_from_output(out: str) -> list[tuple[str, str, str]]:
    """MAC_PERM_SCRIPT 의 출력을 doctor 줄로(마커 NOAPP·NOSUDO 포함)."""
    if "LMCTCC|NOAPP" in out:
        return [("permissions", "WARN", "LinkMyCom 앱이 설치돼 있지 않습니다(/Applications/LinkMyCom.app)")]
    if "LMCTCC|NOSUDO" in out:
        return [("permissions", "WARN", "sudo 가 비밀번호를 물어 실행하지 않았습니다. 그 Mac 터미널에서 'sudo -v' 로 인증한 직후 "
                 "'linkmycom doctor --permissions' 를 실행하세요(원격은 sudo -n 이 되도록 NOPASSWD 가 필요)")]
    if "LMCTCC|BEGIN" not in out:
        return [("permissions", "FAIL", "권한 확인 스크립트가 끝까지 돌지 않았습니다: " + last_line(out, "출력 없음"))]
    return permission_rows(parse_tcc_log(out))


def cmd_doctor_permissions(cfg: dict, host: str | None, as_json: bool = False) -> int:
    """doctor --permissions [이름]: Mac 의 화면 기록·손쉬운 사용·입력 모니터링을 tccd 로그로 판정한다(약 20초, sudo 필요)."""
    import shlex

    if host is None:
        if platform.system() != "Darwin":
            print("이 PC 는 macOS 가 아닙니다. Mac 은 'linkmycom doctor <Mac 이름> --permissions' 로 확인하세요.", file=sys.stderr)
            return 1
        name, ip, os_name, title = platform.node().split(".")[0], "(이 PC)", "macos", "linkmycom doctor --permissions · 이 Mac"
        if not as_json:
            print(c("→ LinkMyCom 을 잠깐 열어 권한 판정 로그를 읽습니다(약 20초)...", "36"))
        try:
            r = subprocess.run(["/bin/bash", "-c", MAC_PERM_SCRIPT], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=90, stdin=subprocess.DEVNULL)
            out, err = r.stdout, r.stderr
        except (OSError, subprocess.TimeoutExpired) as e:
            out, err = "", str(e)
    else:
        blocks = ssh_config_blocks()
        peer, _ = pick_cached(cfg, blocks, host)
        if str(peer.get("os")).lower() != "macos":
            print(f"{peer['name']} 은 macOS 가 아닙니다({peer.get('os')}).", file=sys.stderr)
            return 1
        name, ip, os_name, title = peer["name"], peer["ip"], "macos", f"linkmycom doctor --permissions · {peer['name']}"
        if not as_json:
            print(c(f"→ {peer['name']} 에서 LinkMyCom 을 잠깐 열어 권한 판정 로그를 읽습니다(약 20초)...", "36"))
        rc, out, err = run_remote(peer, cfg, blocks, ["bash -c " + shlex.quote(MAC_PERM_SCRIPT)], timeout=90)
    rows = permission_rows_from_output(out) if out.strip() else [
        ("permissions", "FAIL", "SSH 실패: " + last_line(err, "출력 없음"))]
    if as_json:
        return print_doctor_json({"name": name, "ip": ip, "os": os_name, "rows": rows, "error": ""})
    return print_doctor(title, rows)


def print_doctor_json(result: dict) -> int:
    """doctor --json 한 PC 결과: {"name","ip","os","rows":[[이름,상태,내용],...],"error"}. FAIL·오류면 1."""
    extra = {k: v for k, v in (("disk", row_object(result["rows"], "disk")), ("updater", row_object(result["rows"], "updater")))
             if v}
    print(json.dumps(dict(result, rows=[list(x) for x in result["rows"]], **extra), ensure_ascii=False, indent=2))
    return 1 if result["error"] or any(s == "FAIL" for _, s, _ in result["rows"]) else 0


# ---------------------------------------------------------------- 여러 PC 에 한꺼번에 (exec / doctor --all / fleet).

# accept-new: 처음 보는 PC 의 호스트 키는 묻지 않고 받되, 바뀐 키는 여전히 거부한다(대화형 접속에는 붙이지 않는다).
BATCH_SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new"]
HOSTKEY_FAILED = "Host key verification failed"
EXEC_REFUSED = "exec request failed on channel"
REMOTE_WORKERS = 5


def pick_cached(cfg: dict, blocks: list[dict], query: str) -> tuple[dict, list[dict]]:
    """캐시(45초)로 이름을 풀고, 캐시에서 하나로 정해지지 않으면 tailscale 을 다시 읽어 푼다."""
    peers, from_cache = cached_peers()
    if from_cache and len(resolve(peers, query, cfg, blocks)) != 1:
        peers = fresh_peers()
    return pick_one_or_die(peers, cfg, blocks, query), peers


def ssh_capable(peers: list[dict], cfg: dict | None = None) -> list[dict]:
    """'all' 대상: 온라인이고 모바일이 아니며 주소가 있는 PC. cfg 를 주면 hide 한 장비는 뺀다(0.7.0)."""
    return [p for p in peers if p.get("online") and p.get("os") not in MOBILE_OS and p.get("ip")
            and not (cfg and is_hidden(p, cfg))]


def resolve_targets(cfg: dict, blocks: list[dict], spec: str) -> list[dict]:
    """'all' 또는 쉼표로 나눈 이름들을 피어 목록으로. 이름이 모호하면 pick_one_or_die 규칙(비대화형이면 종료 1)."""
    if spec.lower() in ("all", "@all"):
        peers, _ = cached_peers()
        return ssh_capable(peers, cfg)
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


def stuck_launcher_reap_command(min_age_seconds: int = 100) -> str:
    """원격 Windows 에서 멈춘 채 남은 lmc 실행기만 끝내는 명령(0.7.1). 표준 입력을 쓰지 않는다.

    실행기는 '$py = $null' 로 시작하는 EncodedCommand 라 명령줄에 그 base64 앞머리가 있다. SSH 세션(세션 0)의 powershell 중
    그 앞머리를 가진, min_age_seconds 넘은 것만 고른다. 시간 초과가 난 직후에 불러 방금 멈춘 실행기도 치운다
    (2026-11-26: 치우지 않으면 PC 마다 수십~백여 개가 남아 메모리 수 GB 를 잡았다).
    """
    sig = encode_ps("$py = $null\n")[:32]
    lines = [
        "$s = '" + sig + "'",
        "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.ProcessId -ne $PID -and $_.SessionId -eq 0 "
        "-and $_.CommandLine -and $_.CommandLine.Contains($s) -and ((Get-Date) - $_.CreationDate).TotalSeconds -gt "
        + str(int(min_age_seconds)) + " } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; 'LMCREAP|' + $_.ProcessId }",
    ]
    return "powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps("\n".join(lines) + "\n")


def reap_stuck_launchers(peer: dict, cfg: dict, blocks: list[dict], ssh: str | None = None) -> int:
    """시간 초과가 난 Windows 원격에 남은 실행기를 치운다. 치운 개수(실패하면 0). 예외를 올리지 않는다."""
    try:
        cmd = remote_ssh_cmd(peer, cfg, blocks, [stuck_launcher_reap_command()], ssh)
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40,
                           stdin=subprocess.DEVNULL)
    except (SystemExit, OSError, subprocess.TimeoutExpired):
        return 0
    return sum(1 for line in (r.stdout or "").splitlines() if line.startswith("LMCREAP|"))


def run_remote(peer: dict, cfg: dict, blocks: list[dict], remote: list[str], stdin_text: str | None = None,
               timeout: float | None = 120, ssh: str | None = None) -> tuple[int, str, str]:
    """원격 명령을 돌려 (종료 코드, stdout, stderr). 예외·die 없이 실패도 값으로 돌려준다(작업 스레드에서 쓴다)."""
    try:
        cmd = remote_ssh_cmd(peer, cfg, blocks, remote, ssh)
    except SystemExit:
        return 255, "", "주소를 알 수 없음"
    kwargs: dict = {"input": stdin_text} if stdin_text is not None else {"stdin": subprocess.DEVNULL}
    # 표준 입력으로 보낸 스크립트가 원격 실행기에 닿지 않으면(STDIN_TIMEOUT_MARK) 한 번 다시 시도한다(0.7.1).
    for attempt in (1, 2):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                               **kwargs)
        except subprocess.TimeoutExpired:
            if stdin_text is not None and str(peer.get("os") or "").lower() == "windows":
                reap_stuck_launchers(peer, cfg, blocks, ssh)
            return 124, "", f"{int(timeout or 0)}초 안에 끝나지 않음"
        except OSError as e:
            return 255, "", str(e)
        if stdin_text is None or attempt == 2 or STDIN_TIMEOUT_MARK not in (r.stdout or ""):
            break
    if stdin_text is not None and STDIN_TIMEOUT_MARK in (r.stdout or ""):
        return 124, "", f"원격 실행기가 스크립트를 받지 못했습니다(표준 입력 {STDIN_WAIT_SECONDS}초 대기, 두 번 시도)"
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
        if HOSTKEY_FAILED in (err or ""):
            return "SSH 실패: 호스트 키가 바뀜('linkmycom hostkey reset <이름>' 으로 지문 확인 뒤 다시 등록)"
        if EXEC_REFUSED in (err or ""):
            # 로그인은 됐는데 sshd 가 명령 프로세스를 만들지 못했다. 그 PC 의 백신이 명령을 막았을 때 이렇게 보인다(0.7.2).
            return "SSH 실패: 원격 PC 가 명령 실행을 거부함(그 PC 의 백신·보안 프로그램 기록을 확인)"
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

    args, os_filter, wrap_ps = parse_exec_options(args)
    target, remote, timeout = parse_exec_args(args)
    blocks = ssh_config_blocks()
    peers = filter_by_os(resolve_targets(cfg, blocks, target), os_filter)
    if not peers:
        die("명령을 보낼 온라인 PC 가 없습니다." + (f" (--os {os_filter})" if os_filter else ""))
    is_all = target.lower() in ("all", "@all")
    ssh = ssh_bin()
    record_history("exec", [p["name"] for p in peers], detail=" ".join(remote)[:200])
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
                cmd = remote_ssh_cmd(peer, cfg, blocks, exec_remote_for(peer, remote, wrap_ps), ssh)
                proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace")
                timer = None
                if timeout:
                    timer = threading.Timer(timeout, proc.kill)
                    timer.start()
                assert proc.stdout is not None
                for line in proc.stdout:
                    lines.put((name, line.rstrip("\r\n")))
                    if HOSTKEY_FAILED in line:
                        lines.put((name, f"(호스트 키가 바뀌었습니다. 지문을 확인하고 다시 등록: linkmycom hostkey reset {name})"))
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
    targets = ssh_capable(peers, cfg)
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
    remember_lans([(None if r is local else r["name"], r["rows"]) for r in results])
    if as_json:
        print(json.dumps([dict(r, rows=[list(x) for x in r["rows"]],
                               **{k: v for k, v in (("disk", row_object(r["rows"], "disk")),
                                                    ("updater", row_object(r["rows"], "updater"))) if v})
                          for r in results], ensure_ascii=False, indent=2))
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

def auto_update_summary(rows: list[tuple[str, str, str]]) -> str:
    """doctor 의 auto_update 줄을 fleet 표 한 칸으로: '상태 마지막결과' (작업이 빠졌으면 '없음 <작업>')."""
    row = next(((s, d) for n, s, d in rows if n == "auto_update"), None)
    if not row:
        return "-"
    status, detail = row
    if status == "INFO":
        return "-"
    miss = re.search(r"missing ([^;\s]+)", detail)
    last = re.search(r"last ([^;\s]+)", detail)
    extra = ("없음 " + miss.group(1).replace("LinkMyCom-", "")) if miss else (last.group(1) if last else "기록 없음")
    return f"{status} {extra}"


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


# 원격 설치 경로. 예전엔 raw 문자열에 역슬래시를 두 겹 써서 결과 줄의 폴더 이름이 비어 보였다(0.6.0 에서 한 겹으로).
FLEET_INSTALL_PATHS = {
    "windows": {"tower": r"%LOCALAPPDATA%\DeskTools\tower\linkmycom.py", "linkmycom": r"%LOCALAPPDATA%\linkmycom\linkmycom.py",
                "tssh": r"%LOCALAPPDATA%\tssh\linkmycom.py"},
    "unix": {"bin": "~/.local/bin/linkmycom", "usr": "/usr/local/bin/linkmycom"},
}


def fleet_push_script(data: bytes, version: str, paths: list[str], payload_path: str | None = None) -> str:
    """원격에서 실행할 파이썬: 관리 PC 가 서명 확인한 새 linkmycom.py 를 SHA256 으로 대조한 뒤,
    주어진 설치 경로 중 실재하고 버전이 낮은 것만 원자적으로 바꾼다. 결과는 'LMCPUSH|경로|이전->새' 줄.

    payload 는 base64 로 스크립트에 품거나(Unix: 표준 입력으로 보냄), payload_path 의 파일에서 읽는다
    (Windows: Windows OpenSSH 가 200KB 넘는 표준 입력을 중첩 PowerShell 에 끝까지 못 넘겨 scp 로 먼저 보냄.
    읽은 뒤 그 파일은 지운다).
    원격 PC 의 옛 CLI 가 스스로 받게 하면 SSH 세션 안의 ssh-keygen 파이프 문제(0.4.6 이하)로 멈추므로
    검증은 관리 PC 가 하고 원격은 해시만 맞춘다. SSH 채널 자체가 인증·암호화되어 있다.
    """
    import base64
    import hashlib

    if payload_path:
        load = (f"P = os.path.expanduser(os.path.expandvars({payload_path!r}))\n"
                "DATA = open(P, 'rb').read()\n"
                "os.remove(P)\n")
    else:
        load = f"DATA = base64.b64decode({base64.b64encode(data).decode('ascii')!r})\n"
    return (
        "import base64, hashlib, os, re, shutil, sys\n"
        + load +
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
        "    try:\n"
        "        shutil.copy2(p, p + '.prev')\n"  # fleet rollback 이 되돌릴 이전 판
        "    except OSError:\n"
        "        pass\n"
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
            *windows_stdin_read_lines("$body"),
            "[IO.File]::WriteAllText($f, $body + \"`n\")",
            "try { & $py $f } finally { Remove-Item $f -Force -ErrorAction SilentlyContinue }",
        ]
        return "powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps("\n".join(lines) + "\n"), True
    return "if command -v python3 >/dev/null 2>&1; then python3 -; else python -; fi", False


def scp_base(peer: dict, cfg: dict, blocks: list[dict], extra: list[str] | None = None,
             user: str | None = None) -> tuple[str, list[str], str]:
    """(scp 실행 파일, build_ssh_cmd 와 같은 포트·키·-o 옵션을 scp 식으로 옮긴 인자, user@주소)."""
    settings = host_settings(peer, cfg, blocks)
    ssh_cmd = build_ssh_cmd(peer, settings, cfg, extra, user=user, ssh_path=ssh_bin())
    target = ssh_cmd[-1]
    scp = os.path.join(os.path.dirname(ssh_cmd[0]), "scp" + (".exe" if os.name == "nt" else "")) if os.path.dirname(ssh_cmd[0]) else "scp"
    opts: list[str] = []
    i = 1
    while i < len(ssh_cmd) - 1:
        a = ssh_cmd[i]
        if a == "-p":
            opts += ["-P", ssh_cmd[i + 1]]
            i += 2
        elif a in ("-o", "-i", "-F"):
            opts += [a, ssh_cmd[i + 1]]
            i += 2
        else:
            i += 1  # ssh 전용 플래그(-t 등)는 scp 에 넘기지 않는다
    return scp, opts, target


def remote_scp_cmd(peer: dict, cfg: dict, blocks: list[dict], local: str, remote_path: str) -> list[str]:
    """build_ssh_cmd 와 같은 주소·사용자·키·옵션으로 파일 하나를 보내는 scp 명령(-O: Windows OpenSSH 서버 호환)."""
    scp, opts, target = scp_base(peer, cfg, blocks, BATCH_SSH_OPTS)
    return [scp, "-O", "-q"] + opts + [local, f"{target}:{remote_path}"]


def path_folder(p: str) -> str:
    """설치 경로의 폴더 이름(fleet update 결과 줄). 원격이 Windows 면 구분자가 역슬래시라 os.path 대신 직접 자르고,
    겹친 구분자가 만드는 빈 조각은 버린다. (f-string 안의 역슬래시는 Python 3.9 에서 문법 오류라 밖에서 자른다.)"""
    parts = [x for x in re.split(r"[\\/]", p) if x]
    return parts[-2] if len(parts) >= 2 else p


def fleet_push_paths(os_name: str, rows: list[tuple[str, str, str]]) -> list[str]:
    """밀어 넣을 설치 경로: PATH 의 lmc 가 가리키는 파일 + 고정 위치 설치본들."""
    path = path_lmc_version(rows)
    fixed = list(FLEET_INSTALL_PATHS["windows" if os_name == "windows" else "unix"].values())
    return ([path[0]] if path else []) + fixed


def row_object(rows: list[tuple[str, str, str]], name: str) -> dict | None:
    """doctor 줄 하나를 {'status','detail'} 로(없으면 None). fleet status --json 의 disk·updater 키."""
    row = next(((s, d) for n, s, d in rows if n == name), None)
    return {"status": row[0], "detail": row[1]} if row else None


def row_warnings(rows: list[tuple[str, str, str]]) -> list[tuple[str, str]]:
    """fleet status 표의 상태 칸에 더할 경고: 디스크 부족, 업데이터 멈춤."""
    out = []
    for name, label in (("disk", "디스크"), ("updater", "업데이터")):
        row = next(((s, d) for n, s, d in rows if n == name), None)
        if row and row[0] == "WARN":
            out.append((label, row[1]))
    return out


def fleet_rows(cfg: dict) -> list[dict]:
    blocks = ssh_config_blocks()
    peers, _ = cached_peers()
    targets = ssh_capable(peers, cfg)
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
        # 각 PC 의 판을 거울의 구성요소별 최신(v*·tower-v*·native-v*)과 비교한다(C7). 거울을 못 읽으면 판정만 뺀다.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as pool:
            lf = pool.submit(fetch_latest_components, cfg, 10)
            results = fleet_rows(cfg)
            try:
                latest = lf.result()
            except Exception:  # noqa: BLE001
                latest = {}
        if "--json" in rest:
            # 타워가 읽는 형식(행 목록)은 그대로 두고 행마다 latest·outdated 를 더한다.
            # 행 목록(rows)에 disk·updater 줄(0.7.0)이 들어 있고, 읽기 쉽게 같은 값을 disk·updater 키로도 더한다.
            print(json.dumps([dict({k: v for k, v in r.items() if k != "peer"}, rows=[list(x) for x in r["rows"]],
                                   latest=latest, outdated=outdated_components(row_versions(r["rows"]), latest),
                                   disk=row_object(r["rows"], "disk"), updater=row_object(r["rows"], "updater"))
                              for r in results], ensure_ascii=False, indent=2))
            return 1 if any(r["error"] for r in results) else 0
        table = []
        for r in results:
            if r.get("skipped"):
                table.append([r["name"], os_label(r["os"]), "-", "-", "-", "-", "-", c(f"건너뜀 ({r['skipped']})", "90")])
                continue
            if r["error"]:
                table.append([r["name"], os_label(r["os"]), "-", "-", "-", "-", "-", c(r["error"], "31")])
                continue
            d = {n: det for n, _, det in r["rows"]}
            vers = cli_versions(r["rows"])
            path = path_lmc_version(r["rows"])
            path_stale, labels = stale_installs(r["rows"])
            old = ([f"lmc {path[1]}"] if path_stale and path else []) + [f"{k} {vers[k]}" for k in labels]
            newer = [COMPONENT_LABELS[k] for k in outdated_components(row_versions(r["rows"]), latest, r["os"]) if k != "cli"]
            notes = ([c("CLI 낡음: " + ", ".join(old), "33")] if old else []) + \
                ([c("새 판: " + ", ".join(newer), "33")] if newer else []) + \
                [c(f"{label}: {det}", "33") for label, det in row_warnings(r["rows"])]
            note = "; ".join(notes) if notes else c("OK", "32")

            def cell(name: str) -> str:
                v = d.get(name, "-")
                return version_cell(v, latest_for(latest, name, r["os"])) if VERSION_RE.match(v or "") else v

            table.append([r["name"], os_label(r["os"]), version_cell(path[1], latest.get("cli", "")) if path else "-",
                          ", ".join(f"{k} {v}" for k, v in vers.items()) or "-",
                          cell("tower"), cell("native"), auto_update_summary(r["rows"]), note])
        mirror = ", ".join(f"{COMPONENT_LABELS[k]} {latest[k]}" for k in ("cli", "tower", "native") if k in latest)
        print(c(f"linkmycom fleet status · 이 PC 의 CLI {__version__}"
                + (f" · 거울 최신: {mirror}" if mirror else " · 거울 최신을 읽지 못함"), "1"))
        print_table(table, ["PC", "OS", "lmc", "CLI 설치본", "타워", "화면공유", "자동 업데이트", "상태"])
        return 1 if any(r["error"] for r in results) else 0
    if sub == "update":
        plain, _wait = parse_wait(rest)
        what = next((a for a in plain if not a.startswith("-")), "cli")
        dry = "-n" in rest or "--dry-run" in rest
        if what in ("tower", "native"):
            return cmd_fleet_component(cfg, what, rest)
        if what != "cli":
            die("사용법: linkmycom fleet update [cli] [-n] | fleet update native|tower [이름|all] [--apply]")
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

        import tempfile

        def upd(item) -> tuple[int, str]:
            r, labels, path_stale = item
            remote, sentinel = fleet_push_command(r["os"])
            payload_path = None
            if r["os"] == "windows":
                # 큰 payload 는 scp 로 먼저 보낸다(상대 경로는 원격 홈 기준).
                payload_path = f"AppData/Local/Temp/lmc-push-{os.getpid()}-{int(time.time())}.py"
                with tempfile.NamedTemporaryFile("wb", prefix="lmc-push-", suffix=".py", delete=False) as f:
                    f.write(src)
                    local = f.name
                try:
                    cp = subprocess.run(remote_scp_cmd(r["peer"], cfg, blocks, local, payload_path), capture_output=True,
                                        text=True, encoding="utf-8", errors="replace", timeout=120, stdin=subprocess.DEVNULL)
                except (OSError, subprocess.TimeoutExpired) as e:
                    return 255, f"scp 실패: {e}"
                finally:
                    try:
                        os.remove(local)
                    except OSError:
                        pass
                if cp.returncode != 0:
                    return cp.returncode, "scp 실패: " + last_line(cp.stderr, "출력 없음")
                payload_path = "%USERPROFILE%/" + payload_path
            script = fleet_push_script(src, remote_ver, fleet_push_paths(r["os"], r["rows"]), payload_path)
            rc, out, err = run_remote(r["peer"], cfg, blocks, [remote], script + ("\n" + DOCTOR_STDIN_END + "\n" if sentinel else "\n"),
                                      timeout=180, ssh=ssh)
            changed = [l.split("|", 2)[1:] for l in out.splitlines() if l.startswith("LMCPUSH|")]
            if rc == 0 and "python 3 not found" not in out:
                return 0, ("; ".join(f"{path_folder(p)}: {what}" for p, what in changed)
                           if changed else last_line(out, "변경 없음"))
            return rc or 1, last_line(out + "\n" + err, "출력 없음")

        record_history("fleet update", [r["name"] for r, _, _ in stale], detail=f"cli {remote_ver}")
        bad = 0
        for (r, labels, path_stale), res in zip(stale, parallel_map(upd, stale)):
            rc, msg = res if isinstance(res, tuple) else (255, str(res))
            bad += rc != 0
            print(c(f"[{r['name']}]", "36") + f" {what_of(labels, path_stale)}: "
                  + (c("OK", "32") if rc == 0 else c(f"실패({rc})", "31")) + f" {msg}")
        return 1 if bad else 0
    if sub == "rollback":
        return cmd_fleet_rollback(cfg, rest)
    if sub == "fix":
        return cmd_fleet_fix(cfg, rest)
    die("사용법: linkmycom fleet status [--json] | fleet update [cli] [-n] | fleet update native|tower [이름|all] [--apply [--wait [초]]]"
        " | fleet fix [이름|all] [-n] | fleet rollback <이름|all> cli [-n]")


# ---------------------------------------------------------------- fleet fix: 원격 PC 의 관리자 권한 없는 복구 (0.7.0 C4).

FIX_MIN_CLI = "0.7.0"  # doctor --fix --no-admin 을 아는 첫 판


def fleet_fix_command(os_name: str, cli_label: str, dry: bool = False) -> str:
    """원격에서 'doctor --fix --no-admin' 을 돌리는 명령. 끝에 'LMCFIX|rc|<종료 코드>' 한 줄(없는 설치본은 nocli, 파이썬 없음은 nopython)."""
    tail = "doctor --fix --no-admin" + (" -n" if dry else "")
    if os_name == "windows":
        path = FLEET_INSTALL_PATHS["windows"].get(cli_label) or FLEET_INSTALL_PATHS["windows"]["linkmycom"]
        lines = [
            "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
            "$env:PYTHONIOENCODING = 'utf-8'",
            "$py = $null",
            "foreach ($n in @('python','python3','py')) { $c = Get-Command $n -ErrorAction SilentlyContinue | "
            "Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1; if ($c) { $py = $c.Source; break } }",
            "if (-not $py) { 'LMCFIX|nopython'; exit 0 }",
            "$cli = [Environment]::ExpandEnvironmentVariables('" + path + "')",
            "if (-not (Test-Path -LiteralPath $cli)) { 'LMCFIX|nocli'; exit 0 }",
            "& $py $cli " + tail + " 2>&1",
            "'LMCFIX|rc|' + $LASTEXITCODE",
        ]
        return "powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps("\n".join(lines) + "\n")
    return ('for p in "$HOME/.local/bin/linkmycom" /usr/local/bin/linkmycom; do if [ -f "$p" ]; then '
            f'PYTHONIOENCODING=utf-8 python3 "$p" {tail} 2>&1; echo "LMCFIX|rc|$?"; exit 0; fi; done; echo "LMCFIX|nocli"')


def parse_fix_output(text: str) -> dict:
    """원격 doctor --fix 출력을 {'rc','missing','none','plan','done','failed'} 로. 줄 모양은 cmd_doctor_fix 의 출력과 같다."""
    info: dict = {"rc": None, "missing": "", "none": False, "plan": [], "done": [], "failed": []}
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("LMCFIX|"):
            _, _, rest = line.partition("|")
            if rest.startswith("rc|"):
                try:
                    info["rc"] = int(rest[3:].strip())
                except ValueError:
                    pass
            else:
                info["missing"] = rest
        elif line.startswith("고칠 항목이 없습니다"):
            info["none"] = True
        elif line.startswith("OK  "):
            info["done"].append(line[4:].strip())
        elif line.startswith("실패 "):
            info["failed"].append(line[3:].strip())
        else:
            m = re.match(r"^\s+\d+\. \[[^\]]*\] (.+)$", line)
            if m:
                info["plan"].append(m.group(1).strip())
    return info


def fleet_fix_summary(info: dict, dry: bool) -> tuple[str, str]:
    """(결과 칸, 내용 칸)."""
    if info["missing"] == "nopython":
        return "건너뜀", "그 PC 에 파이썬 3 이 없음"
    if info["missing"] == "nocli":
        return "건너뜀", "그 PC 에 CLI 설치본을 찾지 못함"
    if info["rc"] is None:
        return "실패", "원격 출력에서 종료 코드를 읽지 못함"
    if info["none"]:
        return "OK", "고칠 항목 없음"
    if dry:
        return "OK", ("할 일 " + "; ".join(info["plan"])) if info["plan"] else "할 일 없음"
    text = "; ".join([f"고침 {x}" for x in info["done"]] + [f"실패 {x}" for x in info["failed"]]) or "출력 없음"
    return ("OK" if info["rc"] == 0 and not info["failed"] else "실패"), text


def cmd_fleet_fix(cfg: dict, rest: list[str]) -> int:
    """fleet fix [이름|a,b|all] [-n]: 원격 PC 에서 'doctor --fix --no-admin'(관리자 권한 없는 복구)을 돌리고 PC 별 결과 표를 보인다."""
    dry = "-n" in rest or "--dry-run" in rest
    names = [a for a in rest if not a.startswith("-")]
    blocks = ssh_config_blocks()
    results = fleet_rows(cfg)
    only = None if not names or names[0].lower() in ("all", "@all") else {p["name"] for p in resolve_targets(cfg, blocks, names[0])}
    table: list[list[str]] = []
    jobs = []
    for r in results:
        if r.get("peer") is None or (only is not None and r["name"] not in only):
            continue
        if r.get("skipped"):
            table.append([r["name"], c("건너뜀", "90"), r["skipped"]])
            continue
        if r["error"]:
            table.append([r["name"], c("실패", "31"), r["error"]])
            continue
        vers = cli_versions(r["rows"])
        best = max(vers.items(), key=lambda kv: parse_version(kv[1]), default=None)
        if not best or parse_version(best[1]) < parse_version(FIX_MIN_CLI):
            table.append([r["name"], c("건너뜀", "90"), f"CLI {FIX_MIN_CLI} 이상이 필요합니다(현재 {best[1] if best else '없음'}). "
                          "먼저 linkmycom fleet update cli"])
            continue
        jobs.append((r, best[0]))
    if not jobs and not table:
        print("고칠 원격 PC 가 없습니다(켜진 PC 가 없거나 이름이 맞지 않음). 이 PC 는 'linkmycom doctor --fix'.")
        return 0
    ssh = ssh_bin()
    if jobs:
        record_history("fleet fix", [r["name"] for r, _ in jobs], detail="-n" if dry else "")

    def go(item) -> tuple[str, str]:
        r, label = item
        rc, out, err = run_remote(r["peer"], cfg, blocks, [fleet_fix_command(r["os"], label, dry)], timeout=240, ssh=ssh)
        if not out.strip():
            return "실패", remote_rows_error([], err)
        return fleet_fix_summary(parse_fix_output(out), dry)

    bad = 0
    for (r, _), res in zip(jobs, parallel_map(go, jobs)):
        state, text = res if isinstance(res, tuple) else ("실패", str(res))
        bad += state == "실패"
        table.append([r["name"], c(state, "32" if state == "OK" else "31" if state == "실패" else "90"), text])
    print(c("linkmycom fleet fix" + (" -n (바꾸지 않음)" if dry else "") + " · 관리자 권한 없는 복구만(sshd·방화벽·중복 lmc 정리는 제외)", "1"))
    print_table(table, ["PC", "결과", "내용"])
    return 1 if bad else 0


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
    record_history("send", [p["name"] for p in peers], detail=f"{len(files)} files {total} bytes")
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


# ---------------------------------------------------------------- 클립보드 보내기 (clip).
# 받는 쪽은 LinkMyCom 앱 0.6.0 의 트레이 프로세스(TCP 21120, Tailscale 주소에서 온 연결만). 한 연결에 한 메시지:
# 첫 줄 "LMCCLIP 1 <text|files> <payload 바이트 수> <payload sha256 16진> <보낸 장비 이름>\n" + payload,
# 응답 "OK\n" 또는 "ERR <사유>\n". files 의 payload 는 파일 이름 목록(줄마다 하나)이고 실제 파일은 Taildrop 으로 먼저 보낸다.

CLIP_PORT = 21120
CLIP_WORKERS = 3
CLIP_TIMEOUT = 10.0
# files 는 받는 쪽이 Taildrop 받기 완료를 최대 60초 기다린 뒤 답하므로 응답만 더 기다린다.
CLIP_FILES_REPLY_TIMEOUT = 65.0
CLIP_MAX_TEXT = 1 << 20
CLIP_USAGE = "사용법: linkmycom clip <이름,...> [--text \"...\"] [--file <경로>...]"


def parse_clip_args(args: list[str]) -> tuple[list[str], str | None, list[str]]:
    """'<이름,...> [--text ..] [--file ..]...' 을 (대상 이름들, 텍스트 또는 None, 파일들) 로."""
    names: list[str] = []
    text: str | None = None
    files: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--text", "--file"):
            if i + 1 >= len(args):
                die(f"{a} 뒤에 값이 없습니다. {CLIP_USAGE}")
            if a == "--text":
                text = args[i + 1]
            else:
                files.append(args[i + 1])
            i += 2
            continue
        if a.startswith("--text="):
            text = a[len("--text="):]
        elif a.startswith("--file="):
            files.append(a[len("--file="):])
        elif a.startswith("-"):
            die(f"알 수 없는 옵션 {a}. {CLIP_USAGE}")
        else:
            names += [n.strip() for n in a.split(",") if n.strip()]
        i += 1
    if not names:
        die(CLIP_USAGE)
    if text is not None and files:
        die("--text 와 --file 은 함께 쓸 수 없습니다.")
    return names, text, files


def clipboard_tool_missing() -> str:
    return ("이 PC 의 클립보드를 읽을 도구가 없습니다. Wayland 는 wl-clipboard(wl-paste), X11 은 xclip 을 설치하거나 "
            "--text \"...\" / --file <경로> 로 직접 주세요.")


def read_local_clipboard() -> tuple[str, str | list[str]]:
    """로컬 클립보드를 ('text', 문자열) 또는 ('files', 경로 목록) 으로 읽는다. 읽지 못하면 die."""
    import base64

    system = platform.system()
    if system == "Windows":
        # 파일 목록(FileDropList)을 먼저 보고, 없으면 텍스트. 코드 페이지에 흔들리지 않게 UTF-8 base64 로 받는다.
        ps = ("$ErrorActionPreference = 'SilentlyContinue'\n"
              "$f = @(Get-Clipboard -Format FileDropList | Where-Object { $_ })\n"  # 없으면 @($null) 이 1개로 세지지 않게
              "$e = [Text.Encoding]::UTF8\n"
              "if ($f.Count -gt 0) { 'F' + [Convert]::ToBase64String($e.GetBytes((@($f | ForEach-Object { $_.FullName }) -join \"`n\"))) }\n"
              "else { $t = Get-Clipboard -Raw; if ($null -eq $t) { $t = '' }; 'T' + [Convert]::ToBase64String($e.GetBytes([string]$t)) }\n")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-STA", "-EncodedCommand", encode_ps(ps)],
                               capture_output=True, text=True, encoding="ascii", errors="replace", timeout=20,
                               stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as e:
            die(f"클립보드를 읽지 못했습니다(PowerShell): {e}")
        line = last_line(r.stdout)
        try:
            body = base64.b64decode(line[1:]).decode("utf-8") if line[:1] in ("F", "T") else None
        except ValueError:
            body = None
        if body is None:
            die("클립보드를 읽지 못했습니다(PowerShell Get-Clipboard 결과 없음).")
        if line[0] == "F":
            return "files", [p for p in body.split("\n") if p]
        return "text", body
    if system == "Darwin":
        cmd = ["pbpaste"]
    else:
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
            cmd = ["wl-paste", "--no-newline"]
        elif shutil.which("xclip"):
            cmd = ["xclip", "-selection", "clipboard", "-o"]
        elif shutil.which("wl-paste"):
            cmd = ["wl-paste", "--no-newline"]
        else:
            die(clipboard_tool_missing())
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        die(f"클립보드를 읽지 못했습니다({cmd[0]}): {e}")
    return "text", r.stdout.decode("utf-8", "replace")


def clip_sender_name() -> str:
    """머리 줄의 보낸 장비 이름: 공백 없는 한 토큰(ASCII 가 아닌 글자는 '_')."""
    name = platform.node().split(".")[0] or "unknown"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:63]


def clip_message(kind: str, payload: bytes, sender: str | None = None) -> bytes:
    """규약 메시지 한 개(머리 줄 + payload)."""
    import hashlib

    if kind not in ("text", "files"):
        raise ValueError(f"알 수 없는 종류 {kind}")
    head = f"LMCCLIP 1 {kind} {len(payload)} {hashlib.sha256(payload).hexdigest()} {sender or clip_sender_name()}\n"
    return head.encode("ascii") + payload


def send_clip(host: str, data: bytes, port: int | None = None, timeout: float = CLIP_TIMEOUT,
              reply_timeout: float | None = None) -> tuple[bool, str]:
    """메시지 하나를 보내고 응답 줄을 읽는다. (성공 여부, 사유). 예외를 올리지 않는다(작업 스레드에서 쓴다)."""
    port = CLIP_PORT if port is None else port
    try:
        sock = socket.create_connection((host, port), timeout)
    except ConnectionRefusedError:
        return False, f"{port} 포트가 닫혀 있음(상대 PC 에서 LinkMyCom 0.6.0 이상의 트레이가 켜져 있어야 함)"
    except socket.timeout:
        return False, f"{int(timeout)}초 안에 {port} 포트에 연결하지 못함"
    except OSError as e:
        return False, f"연결 실패: {e}"
    try:
        sock.settimeout(timeout)
        sock.sendall(data)
        try:
            sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        sock.settimeout(reply_timeout or timeout)
        buf = b""
        while b"\n" not in buf and len(buf) < 4096:
            chunk = sock.recv(1024)
            if not chunk:
                break
            buf += chunk
    except socket.timeout:
        return False, "응답 시간 초과"
    except OSError as e:
        return False, f"전송 실패: {e}"
    finally:
        sock.close()
    line = buf.split(b"\n", 1)[0].decode("utf-8", "replace").strip()
    if line == "OK":
        return True, ""
    if line.startswith("ERR"):
        return False, line[3:].strip() or "ERR"
    return False, f"알 수 없는 응답: {line[:80]}" if line else "응답 없이 연결이 끊김"


def cmd_clip(cfg: dict, args: list[str]) -> int:
    """로컬 클립보드(또는 --text / --file)를 대상 PC 들의 LinkMyCom 트레이(21120)로 보낸다. 대상은 최대 3곳 병렬."""
    names, text, files = parse_clip_args(args)
    if text is not None:
        kind, value = "text", text
    elif files:
        kind, value = "files", files
    else:
        kind, value = read_local_clipboard()
    if kind == "files":
        paths = [str(Path(p).expanduser()) for p in value]  # type: ignore[union-attr]
        missing = [p for p in paths if not os.path.isfile(p)]
        if missing:
            die(f"보낼 파일이 없거나 폴더입니다(폴더는 보내지 않음): {', '.join(missing)}")
        payload = "\n".join(os.path.basename(p) for p in paths).encode("utf-8")
    else:
        paths = []
        payload = str(value).encode("utf-8")
        if not payload:
            die("클립보드가 비었습니다. 보낼 내용이 없습니다.")
        if len(payload) > CLIP_MAX_TEXT:
            die(f"텍스트가 {len(payload)} 바이트로 1 MiB 를 넘습니다. 파일로 보내세요(linkmycom send).")
    data = clip_message(kind, payload)
    blocks = ssh_config_blocks()
    peers: list[dict] = []
    for n in names:  # 모두 먼저 풀어 두고(모호하면 여기서 끝남) 보내기 시작한다.
        p, _ = pick_cached(cfg, blocks, n)
        if all(x["name"] != p["name"] for x in peers):
            peers.append(p)
    exe = tailscale_exe() if kind == "files" else ""
    what = f"파일 {len(paths)}개" if kind == "files" else f"텍스트 {len(payload)}바이트"
    print(c(f"→ 클립보드({what}) 를 {', '.join(p['name'] for p in peers)} 로 보냅니다", "36"))

    def one(peer: dict) -> tuple[bool, str]:
        if kind == "files":
            try:
                r = subprocess.run([exe, "file", "cp", *paths, f"{peer['ip']}:"], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
            except OSError as e:
                return False, f"Taildrop 실패: {e}"
            if r.returncode != 0:
                return False, "Taildrop 실패: " + last_line(r.stderr or r.stdout, "출력 없음")
        return send_clip(peer["ip"], data, reply_timeout=CLIP_FILES_REPLY_TIMEOUT if kind == "files" else None)

    bad = 0
    for peer, res in zip(peers, parallel_map(one, peers, CLIP_WORKERS)):
        ok, msg = res if isinstance(res, tuple) else (False, str(res))
        bad += not ok
        print(c(f"[{peer['name']}]", "36") + " " + (c("보냄", "32") if ok else c(f"실패: {msg}", "31")))
    return 1 if bad else 0


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
    if names and names[0] in ("list", "ls"):
        return forward_list()
    if names and names[0] == "stop":
        return forward_stop(names[1] if len(names) > 1 else "")
    if not names:
        die("사용법: linkmycom forward <이름> [<로컬포트:원격포트> ...] [--bg] [-n] | forward list | forward stop [번호|all]")
    blocks = ssh_config_blocks()
    peer, _ = pick_cached(cfg, blocks, names[0])
    raw_specs = names[1:]
    if not raw_specs:
        # 저장 규칙: linkmycom set <이름> forward=8080:80,9000:9000
        saved = (cfg.get("hosts", {}).get(peer["name"]) or {}).get("forward") or ""
        raw_specs = [s.strip() for s in str(saved).split(",") if s.strip()]
        if not raw_specs:
            die(f"전달 규칙이 없습니다. 예: linkmycom forward {peer['name']} 8080:80 (저장: linkmycom set {peer['name']} forward=8080:80)")
    specs = [parse_forward_spec(s) for s in raw_specs]
    bg = "--bg" in args
    extra = (BATCH_SSH_OPTS if bg else []) + ["-N", "-o", "ExitOnForwardFailure=yes"]
    for s in specs:
        extra += ["-L", s]
    cmd = build_ssh_cmd(peer, host_settings(peer, cfg, blocks), cfg, extra, ssh_path=ssh_bin())
    if "-n" in args or "--dry-run" in args:
        print(quote_cmd(cmd))
        return 0
    record_history("forward", [peer["name"]], detail=",".join(raw_specs) + (" bg" if bg else ""))
    if bg:
        return forward_start_bg(peer, specs, cmd)
    for s in specs:
        lp, _, rest = s.partition(":")
        print(c(f"→ 127.0.0.1:{lp} → {peer['name']}:{rest.split(':', 1)[1]}", "36") + "  (Ctrl+C 로 끝)")
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130


def forwards_path() -> Path:
    return CONFIG_DIR / "forwards.json"


def pid_alive(pid: int) -> bool:
    """그 pid 의 프로세스가 아직 있는지. Windows 는 OpenProcess + 종료 코드, 그 밖은 kill(pid, 0)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            k32.CloseHandle(h)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        except Exception:  # noqa: BLE001
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def load_forwards(prune: bool = True) -> list[dict]:
    """~/.tssh/forwards.json 의 백그라운드 전달 목록. prune 이면 끝난 프로세스는 지우고 저장한다."""
    data = load_json(forwards_path()).get("forwards") or []
    items = [f for f in data if isinstance(f, dict) and isinstance(f.get("pid"), int)]
    if prune:
        alive = [f for f in items if pid_alive(f["pid"])]
        if len(alive) != len(items):
            try:
                save_json(forwards_path(), {"forwards": alive})
            except OSError:
                pass
        items = alive
    return items


def forward_start_bg(peer: dict, specs: list[str], cmd: list[str]) -> int:
    """ssh -N -L 을 창 없이 띄우고 pid·규칙을 forwards.json 에 남긴다. 2초 안에 끝나면 실패로 본다."""
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.PIPE}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError as e:
        die(f"ssh 를 띄우지 못했습니다: {e}")
    try:
        _, err = proc.communicate(timeout=2.0)
        msg = last_line(err.decode("utf-8", "replace") if err else "", "출력 없음")
        die(f"포트 전달이 바로 끝났습니다(종료 코드 {proc.returncode}): {msg}")
    except subprocess.TimeoutExpired:
        pass
    items = load_forwards()
    items.append({"pid": proc.pid, "name": peer["name"], "ip": peer["ip"], "specs": specs,
                  "time": datetime.now(timezone.utc).isoformat()[:19]})
    save_json(forwards_path(), {"forwards": items})
    for s in specs:
        lp, _, rest = s.partition(":")
        print(c(f"→ 127.0.0.1:{lp} → {peer['name']}:{rest.split(':', 1)[1]}", "36") + f"  (백그라운드 pid {proc.pid})")
    print(f"끝내려면: linkmycom forward stop {len(items)}")
    return 0


def forward_list() -> int:
    items = load_forwards()
    if not items:
        print("백그라운드 포트 전달이 없습니다.")
        return 0
    print_table([[str(i), str(f["pid"]), f.get("name", "?"), ", ".join(f.get("specs") or []), f.get("time", "")]
                 for i, f in enumerate(items, 1)], ["#", "pid", "PC", "규칙(로컬:호스트:원격)", "시작(UTC)"])
    return 0


def kill_pid(pid: int) -> bool:
    try:
        if os.name == "nt":
            return subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                                  stdin=subprocess.DEVNULL, timeout=15).returncode == 0
        import signal

        os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def forward_stop(which: str) -> int:
    items = load_forwards()
    if not items:
        print("백그라운드 포트 전달이 없습니다.")
        return 0
    if which in ("", "all"):
        if which == "" and len(items) > 1:
            die("여러 개가 있습니다. 'linkmycom forward stop <번호>' 또는 'forward stop all'(번호는 forward list).")
        targets = list(range(len(items)))
    elif which.isdigit() and 1 <= int(which) <= len(items):
        targets = [int(which) - 1]
    else:
        die(f"번호가 맞지 않습니다: {which}. 'linkmycom forward list' 로 확인하세요.")
    bad = 0
    for i in targets:
        f = items[i]
        ok = kill_pid(f["pid"])
        bad += not ok
        print(f"[{i + 1}] {f.get('name')} {', '.join(f.get('specs') or [])}: " + (c("끝냄", "32") if ok else c("끝내지 못함", "31")))
    keep = [f for i, f in enumerate(items) if i not in targets or pid_alive(f["pid"])]
    save_json(forwards_path(), {"forwards": keep})
    return 1 if bad else 0


# ---------------------------------------------------------------- 접속 기록 (history).

HISTORY_MAX_BYTES = 1_000_000
HISTORY_KEEP_LINES = 2000


def history_path() -> Path:
    return CONFIG_DIR / "history.jsonl"


def record_history(cmd: str, names: list[str], detail: str = "") -> None:
    """~/.tssh/history.jsonl 에 한 줄(시각 UTC·명령·PC·내용). 실패해도 명령을 막지 않는다. 1MB 를 넘으면 뒤 2000줄만 남긴다."""
    line = json.dumps({"time": datetime.now(timezone.utc).isoformat()[:19], "cmd": cmd, "names": list(names),
                       "detail": detail}, ensure_ascii=False)
    path = history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        if path.stat().st_size > HISTORY_MAX_BYTES:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-HISTORY_KEEP_LINES:]
            replace_text(path, "\n".join(lines) + "\n")
    except OSError:
        pass


def read_history() -> list[dict]:
    try:
        text = history_path().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("time"):
            out.append(item)
    return out


def recent_hosts(n: int = 5) -> list[str]:
    """최근 접속(connect·screen)한 PC 이름 n개, 최근 순. 기록이 없으면 state 의 last_host."""
    names: list[str] = []
    for item in reversed(read_history()):
        if item.get("cmd") in ("connect", "screen"):
            for name in item.get("names") or []:
                if name not in names:
                    names.append(name)
        if len(names) >= n:
            break
    if not names:
        last = load_json(STATE_PATH).get("last_host")
        if last:
            names.append(last)
    return names[:n]


def parse_since(text: str) -> float:
    """'7d'·'12h'·'30m' 을 초로."""
    m = re.fullmatch(r"(\d+)([dhm])", text.strip().lower())
    if not m:
        die(f"--since 는 7d, 12h, 30m 같은 형식이어야 합니다: {text}")
    return int(m.group(1)) * {"d": 86400, "h": 3600, "m": 60}[m.group(2)]


def cmd_history(args: list[str]) -> int:
    """접속 기록(connect·screen·send·exec·forward·fleet update)을 오래된 것부터 표로. 이름·기간으로 거른다."""
    since = None
    name = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--since" and i + 1 < len(args):
            since = parse_since(args[i + 1])
            i += 2
            continue
        if a.startswith("--since="):
            since = parse_since(a[len("--since="):])
        elif not a.startswith("-"):
            name = a.lower()
        i += 1
    now = datetime.now(timezone.utc)
    rows = []
    for item in read_history():
        try:
            t = datetime.fromisoformat(item["time"]).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if since is not None and (now - t).total_seconds() > since:
            continue
        names = item.get("names") or []
        if name and not any(name in str(n).lower() for n in names):
            continue
        rows.append([t.astimezone().strftime("%m-%d %H:%M"), str(item.get("cmd", "")), ", ".join(names),
                     str(item.get("detail", ""))[:60]])
    if not rows:
        print("기록이 없습니다." + ("" if history_path().exists() else f" ({history_path()})"))
        return 0
    print_table(rows[-100:], ["시각", "명령", "PC", "내용"])
    return 0


# ---------------------------------------------------------------- exec 거르기 (--os, --ps).

EXEC_OS = {"windows": "windows", "win": "windows", "macos": "macos", "mac": "macos", "darwin": "macos",
           "linux": "linux"}


def parse_exec_options(args: list[str]) -> tuple[list[str], str | None, bool]:
    """'--' 앞의 --os <종류>·--ps 를 떼어 (나머지 인자, OS 거르기, PowerShell 감싸기) 로. '--' 뒤는 건드리지 않는다."""
    rest: list[str] = []
    os_filter: str | None = None
    wrap_ps = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            rest += args[i:]
            break
        if a == "--os" and i + 1 < len(args):
            os_filter = args[i + 1]
            i += 2
            continue
        if a.startswith("--os="):
            os_filter = a[len("--os="):]
        elif a == "--ps":
            wrap_ps = True
        else:
            rest.append(a)
        i += 1
    if os_filter is not None:
        if os_filter.lower() not in EXEC_OS:
            die(f"--os 는 windows, macos, linux 중 하나입니다: {os_filter}")
        os_filter = EXEC_OS[os_filter.lower()]
    return rest, os_filter, wrap_ps


def filter_by_os(peers: list[dict], os_filter: str | None) -> list[dict]:
    if not os_filter:
        return peers
    return [p for p in peers if str(p.get("os", "")).lower() == os_filter]


def exec_remote_for(peer: dict, remote: list[str], wrap_ps: bool) -> list[str]:
    """--ps 면 Windows 대상의 명령을 PowerShell -EncodedCommand 로 감싼다(원격 기본 셸이 cmd 여도 같은 결과)."""
    if wrap_ps and peer.get("os") == "windows":
        return ["powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps(" ".join(remote))]
    return list(remote)


# ---------------------------------------------------------------- 점검 결과 고치기 (doctor --fix) 와 일일 유지 (maintain).

# 관리자 권한이 있어야 고칠 수 있는 점검 줄. maintain 은 이 줄이 FAIL·WARN 이면 state 에 적어 두고 다음 대화형 실행 때 알린다.
ADMIN_ROWS = ("sshd", "firewall", "ssh_port")


def tower_start_script() -> Path | None:
    if os.name != "nt":
        return None
    p = Path(os.environ.get("LOCALAPPDATA", "")) / "DeskTools" / "tower" / "Start-ControlTower.ps1"
    return p if p.is_file() else None


def start_tower() -> bool:
    """타워를 브라우저 없이 시작한다(Start-ControlTower.ps1 -NoBrowser, 창 없이 떼어 놓음)."""
    script = tower_start_script()
    if not script:
        return False
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File",
                          str(script), "-NoBrowser"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200)
    except OSError:
        return False
    return True


def path_lmc_installs() -> list[tuple[str, str, str]]:
    """PATH 에서 찾은 lmc 심마다 (심 경로, 실제 linkmycom.py, 버전). doctor 의 path_lmc 와 같은 규칙."""
    found: list[tuple[str, str, str]] = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        shim = os.path.join(d, "lmc.cmd" if os.name == "nt" else "lmc") if d else ""
        if not shim or not os.path.isfile(shim):
            continue
        if os.name == "nt":
            srcs = [os.path.join(d, "linkmycom.py"), os.path.join(d, "..", "tower", "linkmycom.py"),
                    os.path.join(d, "..", "linkmycom", "linkmycom.py")]
        else:
            srcs = [os.path.realpath(shim)]
        for s in srcs:
            try:
                ver = version_in_source(Path(s).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if ver:
                src = os.path.normpath(s)
                if all(os.path.normcase(src) != os.path.normcase(f[1]) for f in found):
                    found.append((shim, src, ver))
                break
    return found


def fix_path_lmc(found: list[tuple[str, str, str]] | None = None, ask=input) -> bool:
    """가장 새 설치본 하나만 남기고 나머지의 lmc 심을 묻고 지운다(설치본 파일은 지우지 않는다). 비대화형이면 건너뜀."""
    found = path_lmc_installs() if found is None else found
    if len(found) < 2:
        return True
    keep = max(found, key=lambda f: parse_version(f[2]))  # 같은 버전이면 PATH 에서 앞선 것
    if not sys.stdin.isatty() and ask is input:
        warn("PATH 의 lmc 가 여럿이지만 비대화형이라 지우지 않습니다. 터미널에서 'linkmycom doctor --fix' 를 실행하세요.")
        return False
    ok = True
    for shim, src, ver in found:
        if shim == keep[0]:
            continue
        try:
            ans = ask(f"{shim} ({src}, {ver}) 를 지울까요? {keep[1]} ({keep[2]}) 을 남깁니다 [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        if ans not in ("y", "yes"):
            ok = False
            continue
        try:
            os.remove(shim)
            print(f"지웠습니다: {shim}")
        except OSError as e:
            warn(f"{shim} 를 지우지 못했습니다: {e}")
            ok = False
    return ok


def plan_fixes(rows: list[tuple[str, str, str]], system: str | None = None) -> list[tuple[str, str]]:
    """doctor 결과 줄에서 고칠 일 목록 [(키, 설명)]. 한 줄에 고침 하나."""
    system = system or platform.system()
    st = {n: s for n, s, _ in rows}

    def bad(name: str, levels: tuple[str, ...] = ("FAIL", "WARN")) -> bool:
        return st.get(name) in levels

    plan: list[tuple[str, str]] = []
    if bad("keys_task"):
        plan.append(("keys_task", "일일 유지 작업(maintain, 키 갱신 포함) 다시 예약"))
    if bad("keys_refresh"):
        plan.append(("keys_refresh", "서명된 공개키 목록을 받아 authorized_keys 갱신"))
    if system == "Windows" and (bad("sshd", ("FAIL",)) or bad("firewall")):
        plan.append(("server", "sshd·방화벽 규칙 다시 설정(관리자 권한 UAC 한 번)"))
    elif system != "Windows" and bad("ssh_port", ("FAIL",)):
        plan.append(("server", "SSH 서버 켜기(관리자 비밀번호를 물을 수 있음)"))
    if bad("tower_run"):
        plan.append(("tower_run", "타워 시작(Start-ControlTower.ps1 -NoBrowser)"))
    if bad("path_lmc"):
        plan.append(("path_lmc", "PATH 의 중복 lmc 정리(가장 새 설치본만 남기고 하나씩 묻고 지움)"))
    if system == "Windows" and bad("task_tower"):
        plan.append(("task_tower", f"로그온 자동 시작 예약 작업 {TOWER_TASK_NAME} 등록(설치기와 같은 정의, 일반 권한)"))
    if system == "Windows" and bad("task_tower_update"):
        plan.append(("task_tower_update", f"타워 자동 업데이트 예약 작업 {TOWER_UPDATE_TASK} 등록(설치기와 같은 정의, 일반 권한)"))
    return plan


def fix_advice(rows: list[tuple[str, str, str]]) -> list[str]:
    """--fix 가 고치지 못하는(일반 권한으로 만들 수 없는) 항목의 안내."""
    st = {n: s for n, s, _ in rows}
    out = []
    if st.get("task_native_update") in ("WARN", "FAIL"):
        out.append(f"예약 작업 {NATIVE_UPDATE_TASK}(SYSTEM)은 일반 권한으로 만들 수 없습니다. LinkMyCom 설치기를 관리자 권한으로 다시 실행하세요.")
    if st.get("ts_dup") == "WARN":
        out.append("Tailscale 이 둘 다 로그인돼 있습니다. 하나만 남기세요(Homebrew 쪽: brew services stop tailscale).")
    return out


# 설치기(tools/installer/Install-LinkMyCom.ps1)의 Register-DeskTowerAutoStart·Register-DeskTowerUpdateTask 와 같은 정의다.
# 인수 문자열·트리거·권한·설정이 같아야 하며, 시험이 설치기 본문과 대조한다.
TOWER_TASK_NAME = "LinkMyCom-Tower"
TOWER_TASK_ARG_HEAD = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "'
TOWER_TASK_SPECS = {
    "tower": {"name": TOWER_TASK_NAME, "script": "Start-ControlTower.ps1", "tail": " -NoBrowser",
              "desc": "LinkMyCom 컨트롤 타워를 로그온할 때 백그라운드로 시작합니다(linkmycom doctor --fix 가 등록)."},
    "update": {"name": "LinkMyCom-TowerUpdate", "script": "Update-LinkMyCom.ps1", "tail": " -Mirror -Auto",
               "desc": "LinkMyCom 컨트롤 타워를 공개 거울의 서명된 릴리스로 업데이트합니다(linkmycom doctor --fix 가 등록)."},
}


def tower_task_argument(kind: str, tower_dir: str) -> str:
    """powershell.exe 에 줄 인수. 경로는 Windows 구분자로 잇는다(Mac 에서 시험해도 같게)."""
    import ntpath

    spec = TOWER_TASK_SPECS[kind]
    return TOWER_TASK_ARG_HEAD + ntpath.join(tower_dir, spec["script"]) + '"' + spec["tail"]


def tower_task_ps(kind: str, tower_dir: str) -> str:
    """타워 예약 작업을 설치기와 같은 정의로 등록하는 PowerShell(일반 권한, 지금 사용자, 대화형 로그온)."""
    spec = TOWER_TASK_SPECS[kind]
    head = [
        "$ErrorActionPreference = 'Stop'",
        "$UserId = [Security.Principal.WindowsIdentity]::GetCurrent().Name",
        f"$Dir = {ps_quote(tower_dir)}",
        "$deskAction = New-ScheduledTaskAction -Execute (Join-Path $env:SystemRoot 'System32\\WindowsPowerShell\\v1.0\\powershell.exe') "
        f"-Argument {ps_quote(tower_task_argument(kind, tower_dir))} -WorkingDirectory $Dir",
    ]
    if kind == "tower":
        mid = [
            "$deskTrigger = New-ScheduledTaskTrigger -AtLogOn -User $UserId",
            "$deskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
            "-MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)",
        ]
    else:
        mid = [
            "$deskLogon = New-ScheduledTaskTrigger -AtLogOn -User $UserId",
            "$deskLogon.Delay = 'PT15M'",
            "$deskDaily = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(9).AddMinutes(30))",
            "$deskTrigger = @($deskLogon, $deskDaily)",
            "$deskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
            "-MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::FromMinutes(30))",
        ]
    tail = [
        "$deskPrincipal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited",
        f"Register-ScheduledTask -TaskName {ps_quote(spec['name'])} -Action $deskAction -Trigger $deskTrigger "
        f"-Principal $deskPrincipal -Settings $deskSettings -Description {ps_quote(spec['desc'])} -Force | Out-Null",
        "'LMC_TASK_OK'",
    ]
    return "\n".join(head + mid + tail) + "\n"


def register_tower_task(kind: str) -> bool:
    """이 PC 에 타워 예약 작업(kind: tower|update)을 등록한다. 타워가 설치돼 있어야 한다."""
    if os.name != "nt":
        return False
    tower_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "DeskTools", "tower")
    if not os.path.isfile(os.path.join(tower_dir, TOWER_TASK_SPECS[kind]["script"])):
        warn(f"{tower_dir} 에 {TOWER_TASK_SPECS[kind]['script']} 가 없어 예약 작업을 만들지 못했습니다(타워 패키지를 다시 설치하세요).")
        return False
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand",
                            encode_ps(tower_task_ps(kind, tower_dir))],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        warn(f"예약 작업을 등록하지 못했습니다: {e}")
        return False
    if "LMC_TASK_OK" not in r.stdout:
        warn(f"예약 작업 {TOWER_TASK_SPECS[kind]['name']} 을 만들지 못했습니다: " + (r.stderr.strip().splitlines() or ["?"])[-1])
        return False
    return True


def run_fix(key: str, cfg: dict) -> bool:
    system = platform.system()
    if key == "keys_task":
        return schedule_keys_refresh()
    if key == "keys_refresh":
        return refresh_keys(cfg) >= 0
    if key == "server":
        return {"Windows": setup_server_windows, "Darwin": setup_server_macos}.get(system, setup_server_linux)()
    if key == "tower_run":
        return start_tower()
    if key == "path_lmc":
        return fix_path_lmc()
    if key == "task_tower":
        return register_tower_task("tower")
    if key == "task_tower_update":
        return register_tower_task("update")
    return False


# --no-admin(fleet fix 가 원격에서 부름)에서 뺄 고침: 관리자 권한(UAC)이 필요하거나 터미널에서 물어야 하는 것.
FIX_NEEDS_PROMPT = ("server", "path_lmc")


def cmd_doctor_fix(cfg: dict, dry: bool = False, rows: list[tuple[str, str, str]] | None = None,
                   no_admin: bool = False) -> int:
    """이 PC 를 점검하고 FAIL·WARN 줄마다 정해진 고침을 실행한다. -n 은 할 일만 보인다. 하나라도 실패면 1.
    no_admin 이면 관리자 권한·확인 질문이 필요한 고침(sshd·방화벽 서버 설정, 중복 lmc 정리)은 하지 않는다."""
    rows = local_doctor_rows() if rows is None else rows
    plan = [p for p in plan_fixes(rows) if not (no_admin and p[0] in FIX_NEEDS_PROMPT)]
    for line in fix_advice(rows):
        print(c("안내: ", "33") + line)
    if not plan:
        print("고칠 항목이 없습니다(자동으로 고치는 항목 기준). 전체 결과: linkmycom doctor")
        return 0
    print(c("linkmycom doctor --fix" + (" -n (바꾸지 않음)" if dry else ""), "1"))
    for i, (key, label) in enumerate(plan, 1):
        print(f"  {i}. [{DOCTOR_LABELS.get(key, '서버 설정' if key == 'server' else key)}] {label}")
    if dry:
        return 0
    bad = 0
    for key, label in plan:
        try:
            ok = run_fix(key, cfg)
        except Exception as e:  # noqa: BLE001
            warn(f"{label}: {e}")
            ok = False
        bad += not ok
        print(c("OK  ", "32") + label if ok else c("실패 ", "31") + label)
    print("다시 점검: linkmycom doctor")
    return 1 if bad else 0


def cmd_maintain(cfg: dict, args: list[str]) -> int:
    """일일 예약 작업이 부르는 유지: 키 갱신 + 관리자 권한 없이 되는 복구(타워 시작) + 결과를 state['maintain'] 에 기록.

    관리자 권한이 필요한 항목(sshd·방화벽·SSH 포트)은 고치지 않고 적어 두었다가 다음 대화형 실행 때 알린다.
    """
    quiet = "--quiet" in args
    if "-n" in args or "--dry-run" in args:
        print("할 일: 공개키 목록 갱신(keys refresh), 점검 후 꺼진 타워 시작, 관리자 권한이 필요한 항목은 기록만"
              " (~/.tssh/state.json 의 maintain).")
        return 0
    done: list[str] = []
    errors: list[str] = []
    n = refresh_keys(cfg, quiet=True)
    (done if n >= 0 else errors).append(f"keys_refresh {n}" if n >= 0 else "keys_refresh")
    try:
        rows = local_doctor_rows()
    except SystemExit:
        rows = []
        errors.append("doctor")
    st = {name: s for name, s, _ in rows}
    if st.get("tower_run") == "WARN" and tower_start_script():
        (done if start_tower() else errors).append("tower_run")
    needs_admin = [name for name in ADMIN_ROWS if st.get(name) in ("FAIL", "WARN")]
    state = load_json(STATE_PATH)
    state["maintain"] = {"time": datetime.now(timezone.utc).isoformat()[:19], "done": done, "errors": errors,
                         "needs_admin": needs_admin}
    _save_state_quietly(state)
    if not quiet:
        print(f"유지 완료: {', '.join(done) or '-'}" + (f"; 실패: {', '.join(errors)}" if errors else "")
              + (f"; 관리자 권한 필요: {', '.join(needs_admin)}" if needs_admin else ""))
    return 1 if errors else 0


def maintain_notices() -> list[str]:
    m = load_json(STATE_PATH).get("maintain") or {}
    need = [DOCTOR_LABELS.get(n, n) for n in (m.get("needs_admin") or []) if isinstance(n, str)]
    if need:
        return [f"관리자 권한이 필요한 항목이 있습니다({', '.join(need)}). 'linkmycom doctor --fix' 로 고치세요."]
    return []


# ---------------------------------------------------------------- 호스트 키 다시 등록 (hostkey reset).

def known_hosts_names(peer: dict, port: str | None) -> list[str]:
    names = []
    for h in (peer.get("ip"), peer.get("dns"), peer.get("name")):
        if h and h not in names:
            names.append(h)
    if port and str(port) != "22":
        return [f"[{h}]:{port}" for h in names]
    return names


def keyscan_bin() -> str | None:
    found = shutil.which("ssh-keyscan")
    if not found:
        kg = find_keygen()
        if kg:
            cand = os.path.join(os.path.dirname(kg), "ssh-keyscan" + (".exe" if os.name == "nt" else ""))
            found = cand if os.path.exists(cand) else None
    return found


def cmd_hostkey(cfg: dict, args: list[str]) -> int:
    """'hostkey reset <이름>': known_hosts 의 그 PC 항목(IP·DNS·이름)을 지우고, ssh-keyscan 으로 받은 키의 지문을 보여 준 뒤
    확인을 받아 다시 등록한다. -n 은 실행할 명령만, --yes 는 묻지 않음(비대화형에서는 --yes 가 있어야 등록)."""
    names = [a for a in args if not a.startswith("-")]
    if len(names) < 2 or names[0] != "reset":
        die("사용법: linkmycom hostkey reset <이름> [--yes] [-n]")
    blocks = ssh_config_blocks()
    peer, _ = pick_cached(cfg, blocks, names[1])
    port = host_settings(peer, cfg, blocks).get("port")
    hosts = known_hosts_names(peer, port)
    keygen = find_keygen()
    keyscan = keyscan_bin()
    if not keygen or not keyscan:
        die("ssh-keygen·ssh-keyscan 을 찾지 못했습니다(OpenSSH 클라이언트 필요).")
    scan = [keyscan, "-T", "5"] + (["-p", str(port)] if port else []) + [peer["ip"]]
    if "-n" in args or "--dry-run" in args:
        for h in hosts:
            print(quote_cmd([keygen, "-R", h]))
        print(quote_cmd(scan))
        return 0
    for h in hosts:
        subprocess.run([keygen, "-R", h], capture_output=True, stdin=subprocess.DEVNULL, timeout=30)
    print(f"known_hosts 에서 {', '.join(hosts)} 항목을 지웠습니다.")
    try:
        r = subprocess.run(scan, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        die(f"ssh-keyscan 을 실행하지 못했습니다: {e}")
    keys = [l.split(None, 1)[1] for l in r.stdout.splitlines() if l.strip() and not l.startswith("#") and len(l.split()) >= 3]
    if not keys:
        die(f"{peer['name']} 에서 호스트 키를 받지 못했습니다. 다음 접속 때 ssh 가 지문을 묻습니다.")
    import tempfile

    with tempfile.TemporaryDirectory(prefix="linkmycom-hostkey-") as d:
        tmp = Path(d) / "keys"
        tmp.write_text("".join(f"{peer['ip']} {k}\n" for k in keys), encoding="ascii", errors="replace")
        fp = subprocess.run([keygen, "-lf", str(tmp)], capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=30, stdin=subprocess.DEVNULL).stdout.strip()
    print(c(f"{peer['name']} ({peer['ip']}) 가 보낸 호스트 키 지문:", "1"))
    print(fp or "(지문을 계산하지 못함)")
    where = (r"C:\ProgramData\ssh\ssh_host_ed25519_key.pub" if peer.get("os") == "windows"
             else "/etc/ssh/ssh_host_ed25519_key.pub")
    print(f"그 PC 에서 같은지 확인: ssh-keygen -lf {where}")
    if "--yes" not in args:
        if not sys.stdin.isatty():
            print("비대화형이라 등록하지 않았습니다. 확인했다면 --yes 를 붙여 다시 실행하세요.")
            return 1
        try:
            ans = input("이 키를 등록할까요? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        if ans not in ("y", "yes"):
            print("등록하지 않았습니다.")
            return 1
    kh = SSH_DIR / "known_hosts"
    SSH_DIR.mkdir(parents=True, exist_ok=True)
    with open(kh, "a", encoding="utf-8") as f:
        for h in hosts:
            for k in keys:
                f.write(f"{h} {k}\n")
    print(f"{kh} 에 등록했습니다({len(keys)}개 키 × {len(hosts)}개 이름).")
    return 0


# ---------------------------------------------------------------- 장비 숨기기·잊기 (hide, unhide, forget, 0.7.0 C7·C8).

def cmd_hide(cfg: dict, args: list[str]) -> int:
    """hide <이름>: config.json 의 hidden 에 더한다. list·선택기·all 대상에서 빠지고 이름을 직접 쓰면 접속은 된다."""
    names = [a for a in args if not a.startswith("-")]
    if not names:
        die("사용법: linkmycom hide <이름>")
    peer, _ = pick_cached(cfg, ssh_config_blocks(), names[0])
    if is_hidden(peer, cfg):
        print(f"{peer['name']} 은 이미 숨겨져 있습니다(되돌리기: linkmycom unhide {peer['name']}).")
        return 0
    cfg["hidden"] = hidden_names(cfg) + [peer["name"]]
    save_json(CONFIG_PATH, cfg)
    print(f"{peer['name']} 을 숨겼습니다. list·선택기·all 대상에서 빠집니다(--all 로 표시, 되돌리기: linkmycom unhide {peer['name']}).")
    return 0


def cmd_unhide(cfg: dict, args: list[str]) -> int:
    """unhide <이름>: hidden 에서 뺀다. 이름은 숨긴 목록에서 먼저 찾는다(꺼져서 목록에 없어도 됨)."""
    names = [a for a in args if not a.startswith("-")]
    if not names:
        die("사용법: linkmycom unhide <이름>")
    hidden = hidden_names(cfg)
    q = names[0].lower()
    found = [h for h in hidden if h.lower() == q] or [h for h in hidden if h.lower().startswith(q)]
    if len(found) != 1:
        if found:
            die(f"'{names[0]}' 에 맞는 숨긴 장비가 {len(found)}개입니다: {', '.join(found)}. 정확한 이름을 쓰세요.")
        die(f"'{names[0]}' 은 숨긴 장비가 아닙니다. 숨긴 장비: {', '.join(hidden) or '없음'}")
    cfg["hidden"] = [h for h in hidden if h != found[0]]
    if not cfg["hidden"]:
        cfg.pop("hidden", None)
    save_json(CONFIG_PATH, cfg)
    print(f"{found[0]} 을 다시 보이게 했습니다.")
    return 0


def known_hosts_matches(field: str, names: list[str]) -> bool:
    """known_hosts 줄의 호스트 칸(쉼표로 나뉜 이름) 하나가 names 에 맞는가. [이름]:포트 모양과 대소문자를 무시한다."""
    lowered = {n.lower() for n in names}
    for item in field.split(","):
        item = item.strip().lower()
        m = re.match(r"^\[(.+)\]:\d+$", item)
        if (m.group(1) if m else item) in lowered:
            return True
    return False


def prune_known_hosts(path: Path, names: list[str], dry: bool = False) -> int:
    """known_hosts 에서 names 에 해당하는 항목을 지운다(해시된 |1| 줄은 건드리지 않음). 지운 줄 수. 바꾸기 전 원본을 known_hosts.old 로 남긴다."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    kept: list[str] = []
    removed = 0
    for line in text.splitlines(keepends=True):
        parts = line.split(None, 1)
        if parts and not parts[0].startswith(("#", "|")) and known_hosts_matches(parts[0], names):
            hosts = [h for h in parts[0].split(",") if not known_hosts_matches(h, names)]
            removed += 1
            if hosts and len(parts) > 1:  # 한 줄에 다른 이름도 있으면 그 이름은 남긴다
                kept.append(",".join(hosts) + " " + parts[1])
            continue
        kept.append(line)
    if removed and not dry:
        shutil.copy2(path, path.with_name(path.name + ".old"))
        replace_text(path, "".join(kept))
    return removed


def forget_names(peer: dict | None, query: str) -> list[str]:
    """forget 이 흔적을 찾을 이름들: 입력·피어 이름·호스트 이름·DNS·IP."""
    out: list[str] = []
    for h in ((peer or {}).get("name"), (peer or {}).get("hostname"), (peer or {}).get("dns"), (peer or {}).get("ip"), query):
        if h and h not in out:
            out.append(h)
    return out


def cmd_forget(cfg: dict, args: list[str]) -> int:
    """forget <이름> [-n]: 없어진 노드의 로컬 흔적(config 의 hosts·hidden, known_hosts, macs.json, 피어·호스트 이름 캐시)을 지운다.
    지금 켜져 있는 노드는 거부한다. 피어 목록에 없으면 입력한 이름과 캐시에 남은 주소로 찾는다. -n 은 지울 것만 보인다."""
    dry = "-n" in args or "--dry-run" in args
    names = [a for a in args if not a.startswith("-")]
    if not names:
        die("사용법: linkmycom forget <이름> [-n]")
    query = names[0]
    blocks = ssh_config_blocks()
    peers, _ = cached_peers()
    found = resolve(peers, query, cfg, blocks)
    # 퍼지 일치(철자 비슷)로 엉뚱한 노드를 지우지 않도록 이름·호스트 이름·별칭이 정확히 같은 것만 인정한다.
    q = query.strip().lower()
    exact = [p for p in found if q in (p["name"].lower(), p["hostname"].lower(), p["dns"].lower(), p["ip"])]
    peer = exact[0] if len(exact) == 1 else None
    cached = next((p for p in (read_peers_cache() or ([], 0))[0] if p.get("name", "").lower() == q), None)
    if peer is None:
        peer = cached
    if peer is not None and peer.get("online") and any(p["name"] == peer["name"] and p.get("online") for p in peers):
        die(f"{peer['name']} 은 지금 켜져 있습니다. 켜진 노드의 흔적은 지우지 않습니다(숨기려면 linkmycom hide {peer['name']}).")
    targets = forget_names(peer, query)
    name = (peer or {}).get("name") or query
    actions: list[str] = []
    entry_key = next((k for k in cfg.get("hosts", {}) if k.lower() == name.lower()), None)
    if entry_key is not None:
        actions.append(f"설정 hosts 항목 {entry_key}")
        if not dry:
            del cfg["hosts"][entry_key]
    hid = next((h for h in hidden_names(cfg) if h.lower() == name.lower()), None)
    if hid is not None:
        actions.append(f"숨김 목록의 {hid}")
        if not dry:
            cfg["hidden"] = [h for h in hidden_names(cfg) if h != hid]
            if not cfg["hidden"]:
                cfg.pop("hidden", None)
    if not dry and (entry_key is not None or hid is not None):
        save_json(CONFIG_PATH, cfg)
    kh = SSH_DIR / "known_hosts"
    n = prune_known_hosts(kh, targets, dry)
    if n:
        actions.append(f"known_hosts {n}줄(원본은 known_hosts.old)")
    macs = load_json(macs_path())
    mh = macs.get("hosts") if isinstance(macs.get("hosts"), dict) else {}
    mk = next((k for k in mh if k.lower() == name.lower()), None)
    if mk is not None:
        actions.append(f"macs.json 의 {mk}")
        if not dry:
            del mh[mk]
            macs["hosts"] = mh
            save_json(macs_path(), macs)
    cache = read_peers_cache()
    if cache and any(p.get("name", "").lower() == name.lower() for p in cache[0]):
        actions.append("피어 캐시·호스트 이름 캐시")
        if not dry:
            write_peers_cache([p for p in cache[0] if p.get("name", "").lower() != name.lower()], cache[1])
    if not actions:
        print(f"{name} 의 로컬 흔적이 없습니다.")
        return 0
    print(("지울 것(-n: 바꾸지 않음): " if dry else "지웠습니다: ") + ", ".join(actions))
    if peer is None:
        print(c("피어 목록에 없는 이름이라 입력한 이름으로만 찾았습니다(IP·DNS 로 남은 known_hosts 줄은 못 찾았을 수 있음).", "90"))
    return 0


# ---------------------------------------------------------------- 화면공유 세션 창 닫기 (sessions close).

SESSION_FLAGS = ("--connect", "--file-transfer", "--terminal")


def session_pids(procs: list[tuple[int, str]], me: int | None = None) -> list[int]:
    """(pid, 명령줄) 중 linkmycom 실행 파일이면서 세션 인자(--connect·--file-transfer·--terminal)가 있는 것만.
    홈 창·트레이(--tray)·서비스(--service)는 고르지 않는다."""
    me = os.getpid() if me is None else me
    out = []
    for pid, cmdline in procs:
        if pid == me:
            continue
        m = re.match(r'\s*(?:"([^"]+)"|(\S+))(.*)$', cmdline or "")
        if not m:
            continue
        exe = (m.group(1) or m.group(2) or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
        if not exe.startswith("linkmycom") or exe.endswith((".py", ".cmd", ".ps1")):
            continue
        if any(f in m.group(3).split() for f in SESSION_FLAGS):
            out.append(pid)
    return out


def list_processes() -> list[tuple[int, str]]:
    if os.name == "nt":
        ps = ("$OutputEncoding = [Text.Encoding]::UTF8; [Console]::OutputEncoding = [Text.Encoding]::UTF8\n"
              "Get-CimInstance Win32_Process -Filter \"Name like 'linkmycom%'\" | "
              "ForEach-Object { [string]$_.ProcessId + \"`t\" + $_.CommandLine }\n")
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encode_ps(ps)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                           stdin=subprocess.DEVNULL)
        lines = [l.split("\t", 1) for l in r.stdout.splitlines() if "\t" in l]
    else:
        r = subprocess.run(["ps", "-axww", "-o", "pid=,command="], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, stdin=subprocess.DEVNULL)
        lines = [l.strip().split(None, 1) for l in r.stdout.splitlines() if l.strip()]
    out = []
    for parts in lines:
        if len(parts) == 2 and parts[0].strip().isdigit():
            out.append((int(parts[0]), parts[1]))
    return out


def cmd_sessions(args: list[str]) -> int:
    """'sessions close [-n]': 화면공유 세션 창(--connect·--file-transfer·--terminal 로 뜬 linkmycom)만 닫는다."""
    sub = next((a for a in args if not a.startswith("-")), "")
    if sub not in ("close", "list"):
        die("사용법: linkmycom sessions list | sessions close [-n]")
    try:
        procs = list_processes()
    except (OSError, subprocess.TimeoutExpired) as e:
        die(f"프로세스 목록을 읽지 못했습니다: {e}")
    pids = session_pids(procs)
    if sub == "list" or "-n" in args or "--dry-run" in args:
        for pid, cmdline in procs:
            if pid in pids:
                print(f"{pid}  {cmdline}")
        print(f"세션 창 {len(pids)}개" + (" (-n: 닫지 않음)" if sub == "close" else ""))
        return 0
    if not pids:
        print("열린 세션 창이 없습니다.")
        return 0
    closed = sum(kill_pid(pid) for pid in pids)
    print(f"세션 창 {closed}/{len(pids)}개를 닫았습니다.")
    return 0 if closed == len(pids) else 1


# ---------------------------------------------------------------- fleet rollback.

def fleet_rollback_script(paths: list[str]) -> str:
    """원격 파이썬: 각 설치 경로 옆의 .prev(fleet update 가 남긴 이전 판)를 제자리로 되돌린다. 결과는 'LMCPUSH|경로|새->이전'."""
    return (
        "import os, re\n"
        f"PATHS = {paths!r}\n"
        "def ver(p):\n"
        "    try:\n"
        "        m = re.search(r'^__version__\\s*=\\s*[\"\\']([^\"\\']+)', open(p, encoding='utf-8', errors='replace').read(), re.M)\n"
        "    except OSError:\n"
        "        return '?'\n"
        "    return m.group(1) if m else '?'\n"
        "seen = set()\n"
        "n = 0\n"
        "for raw in PATHS:\n"
        "    p = os.path.expanduser(os.path.expandvars(raw))\n"
        "    prev = p + '.prev'\n"
        "    if p in seen or not os.path.isfile(prev):\n"
        "        continue\n"
        "    seen.add(p)\n"
        "    cur, old = ver(p), ver(prev)\n"
        "    os.replace(prev, p)\n"
        "    n += 1\n"
        "    print('LMCPUSH|%s|%s->%s' % (p, cur, old))\n"
        "if not n:\n"
        "    print('LMCPUSH|-|no .prev backup (fleet update from 0.5.0 keeps one)')\n"
    )


def cmd_fleet_rollback(cfg: dict, rest: list[str]) -> int:
    names = [a for a in rest if not a.startswith("-")]
    if not names:
        die("사용법: linkmycom fleet rollback <이름|이름,이름|all> cli [-n]")
    what = names[1] if len(names) > 1 else "cli"
    if what != "cli":
        die("되돌리기는 cli 만 됩니다(타워는 Update-LinkMyCom.ps1 -Rollback, 화면공유 앱은 Install-NativeHost -Rollback).")
    blocks = ssh_config_blocks()
    peers = resolve_targets(cfg, blocks, names[0])
    if not peers:
        die("되돌릴 온라인 PC 가 없습니다.")
    if "-n" in rest or "--dry-run" in rest:
        for p in peers:
            paths = list(FLEET_INSTALL_PATHS["windows" if p["os"] == "windows" else "unix"].values())
            print(f"{p['name']}: {', '.join(paths)} 옆의 .prev 가 있으면 되돌릴 예정")
        return 0
    ssh = ssh_bin()
    record_history("fleet rollback", [p["name"] for p in peers], detail="cli")

    def rb(peer: dict) -> tuple[int, str]:
        if skip_without_ssh(peer):
            return 0, "건너뜀(SSH 포트 닫힘)"
        paths = list(FLEET_INSTALL_PATHS["windows" if peer["os"] == "windows" else "unix"].values())
        remote, sentinel = fleet_push_command(peer["os"])
        script = fleet_rollback_script(paths)
        rc, out, err = run_remote(peer, cfg, blocks, [remote],
                                  script + ("\n" + DOCTOR_STDIN_END + "\n" if sentinel else "\n"), timeout=120, ssh=ssh)
        changed = [l.split("|", 2)[1:] for l in out.splitlines() if l.startswith("LMCPUSH|")]
        if rc == 0 and changed:
            return 0, "; ".join(f"{p}: {w}" for p, w in changed)
        return rc or 1, last_line(out + "\n" + err, "출력 없음")

    bad = 0
    for peer, res in zip(peers, parallel_map(rb, peers)):
        rc, msg = res if isinstance(res, tuple) else (255, str(res))
        bad += rc != 0
        print(c(f"[{peer['name']}]", "36") + " " + (c("OK", "32") if rc == 0 else c(f"실패({rc})", "31")) + f" {msg}")
    return 1 if bad else 0


# ---------------------------------------------------------------- 구성요소 판(CLI·타워·화면공유 앱)과 이 PC 의 업데이트 (update --all, C1).

# 거울에는 CLI(v*)·타워(tower-v*)·화면공유 앱(native-v*) 릴리스가 함께 있다. /releases/latest 는 셋 중 아무거나 줄 수 있어
# 목록에서 태그 접두어로 고른다.
COMPONENT_TAGS = {"cli": "v", "tower": "tower-v", "native": "native-v"}
COMPONENT_LABELS = {"cli": "CLI", "tower": "타워", "native": "화면공유 앱"}
NATIVE_UPDATE_TASK = "LinkMyCom-NativeUpdate"
TOWER_UPDATE_TASK = "LinkMyCom-TowerUpdate"
TOWER_UPDATE_ONCE_TASK = "LinkMyCom-TowerUpdate-Once"  # 0.7.0: 업데이트 작업이 없는 PC 에서 fleet update tower 가 잠깐 만드는 일회용 작업
MAC_NATIVE_UPDATER = "~/Library/Application Support/LinkMyCom/Update-Native-Mac.sh"
VERSION_RE = re.compile(r"^\d+(?:\.\d+)+$")


def latest_components(rels: list) -> dict[str, str]:
    """릴리스 목록에서 구성요소별 가장 높은 판. 초안·시험판은 뺀다."""
    out: dict[str, str] = {}
    for comp, prefix in COMPONENT_TAGS.items():
        pat = re.compile("^" + re.escape(prefix) + r"(\d+(?:\.\d+)+)$")
        best = ""
        for r in rels:
            if not isinstance(r, dict) or r.get("draft") or r.get("prerelease"):
                continue
            m = pat.match(str(r.get("tag_name") or ""))
            if m and (not best or parse_version(m.group(1)) > parse_version(best)):
                best = m.group(1)
        if best:
            out[comp] = best
    # 0.7.1: 화면공유 앱은 Mac 패키지가 실린 판만 Mac 의 최신이다(0.6.1·0.7.0·0.8.0 은 Windows 만 게시).
    # 그렇지 않으면 Mac 이 받을 수 없는 판 때문에 계속 '낡음'으로 잡히고 fleet update --wait 가 끝까지 기다린다.
    pat = re.compile("^" + re.escape(COMPONENT_TAGS["native"]) + r"(\d+(?:\.\d+)+)$")
    best = ""
    for r in rels:
        if not isinstance(r, dict) or r.get("draft") or r.get("prerelease"):
            continue
        m = pat.match(str(r.get("tag_name") or ""))
        assets = r.get("assets") if isinstance(r.get("assets"), list) else []
        if m and any("macos" in str((a or {}).get("name") or "").lower() and str((a or {}).get("name") or "").endswith(".zip")
                     for a in assets if isinstance(a, dict)):
            if not best or parse_version(m.group(1)) > parse_version(best):
                best = m.group(1)
    if best:
        out["native_macos"] = best
    return out


def latest_for(latest: dict[str, str], comp: str, os_name: str = "") -> str:
    """그 OS 가 실제로 받을 수 있는 최신 판. Mac 의 화면공유 앱은 Mac 패키지가 있는 판(native_macos)만 본다(없으면 빈 문자열)."""
    if comp == "native" and str(os_name or "").lower() in ("macos", "darwin", "mac"):
        return latest.get("native_macos", "")
    return latest.get(comp, "")


def local_os_name() -> str:
    return "macos" if platform.system() == "Darwin" else ""


def fetch_latest_components(cfg: dict, timeout: float = 10.0) -> dict[str, str]:
    """거울의 구성요소별 최신 판(비인증 API 한 번). 실패하면 예외."""
    repo = cfg.get("update_repo") or DEFAULT_REPO
    data = http_get(f"https://api.github.com/repos/{repo}/releases?per_page=100", timeout,
                    {"Accept": "application/vnd.github+json"})
    rels = json.loads(data.decode("utf-8"))
    if not isinstance(rels, list):
        raise RuntimeError(f"{repo} 의 릴리스 목록을 읽지 못했습니다.")
    return latest_components(rels)


def read_text_quiet(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def local_component_versions() -> dict[str, str]:
    """이 PC 의 CLI·타워·화면공유 앱 판. 설치되지 않았으면 빈 문자열(doctor 점검 스크립트와 같은 위치를 본다)."""
    out = {"cli": __version__, "tower": "", "native": ""}
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            try:
                out["tower"] = str(json.loads(read_text_quiet(os.path.join(local, "DeskTools", "tower", "release.json"))
                                              or "{}").get("version") or "")
            except (ValueError, AttributeError):
                pass
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        nv = read_text_quiet(os.path.join(pf, "LinkMyCom", "LINKMYCOM_VERSION")).strip()
        if not nv and local:
            try:
                nv = str(json.loads(read_text_quiet(os.path.join(local, "LinkMyComNative", "current.json")) or "{}")
                         .get("version") or "")
            except (ValueError, AttributeError):
                nv = ""
        out["native"] = nv
    elif platform.system() == "Darwin":
        try:
            import plistlib

            with open("/Applications/LinkMyCom.app/Contents/Info.plist", "rb") as f:
                out["native"] = str(plistlib.load(f).get("CFBundleShortVersionString") or "")
        except Exception:  # noqa: BLE001
            pass
    return out


def update_state_paths() -> dict[str, str]:
    """구성요소별 업데이터 상태 파일(lastResult 는 ok|deferred|error|none|installing)."""
    if os.name == "nt":
        return {"native": os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "LinkMyCom", "update-state.json"),
                "tower": os.path.join(os.environ.get("LOCALAPPDATA", ""), "DeskTools", "tower", "update-state.json")}
    if platform.system() == "Darwin":
        return {"native": str(Path.home() / "Library" / "Application Support" / "LinkMyCom" / "update-state.json")}
    return {}


def read_update_state(path: str) -> dict:
    """{'result','checked','available'}. 파일이 없으면 모두 빈 문자열."""
    text = read_text_quiet(path)
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        return {"result": "unreadable", "checked": "", "available": ""}
    data = data if isinstance(data, dict) else {}
    res = data.get("lastResult")
    if isinstance(res, dict):
        res = res.get("result") or res.get("status") or ""
    return {"result": str(res or ""), "checked": str(data.get("checked") or "")[:16].replace("T", " "),
            "available": str(data.get("available") or "")}


def tower_update_script() -> Path | None:
    if os.name != "nt":
        return None
    p = Path(os.environ.get("LOCALAPPDATA", "")) / "DeskTools" / "tower" / "Update-LinkMyCom.ps1"
    return p if p.is_file() else None


def native_task_exists() -> bool:
    return os.path.exists(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "Tasks", NATIVE_UPDATE_TASK))


NATIVE_TASK_REFUSED = (f"예약 작업 {NATIVE_UPDATE_TASK} 시작이 거부됐습니다. 0.7.0 이전 설치기로 깐 PC 는 일반 사용자가 시작할 수 없습니다."
                       f" 관리자 PowerShell 에서 'schtasks /run /tn {NATIVE_UPDATE_TASK}' 를 실행하거나 새벽 자동 업데이트를 기다리세요"
                       "(0.7.0 설치 뒤부터는 일반 권한으로 됩니다).")


def local_update_action(comp: str) -> str:
    """update --all 이 그 구성요소에 할 일(-n·안내용)."""
    if comp == "cli":
        return "거울 릴리스를 서명 확인 뒤 교체(linkmycom update)"
    if comp == "tower":
        return "타워 업데이터 Update-LinkMyCom.ps1 -Mirror -Auto 실행"
    if os.name == "nt":
        return f"예약 작업 {NATIVE_UPDATE_TASK} 시작(세션 중이면 업데이터가 미룸)"
    return "Update-Native-Mac.sh --auto 를 백그라운드로 시작(세션 중이면 미룸)"


def run_local_component_update(comp: str, cfg: dict) -> tuple[bool, str]:
    """이 PC 의 구성요소 하나를 갱신한다. (성공, 안내 한 줄)."""
    if comp == "cli":
        try:
            rc = cmd_update(cfg, False)
        except SystemExit:
            return False, "CLI 업데이트에 실패했습니다(위 오류)."
        return rc == 0, ""
    if comp == "tower":
        script = tower_update_script()
        if not script:
            return False, "타워 업데이터(Update-LinkMyCom.ps1)를 찾지 못했습니다."
        try:
            rc = subprocess.call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                                  "-Mirror", "-Auto"], stdin=subprocess.DEVNULL)
        except OSError as e:
            return False, f"타워 업데이터를 실행하지 못했습니다: {e}"
        return rc == 0, "" if rc == 0 else f"타워 업데이터 종료 코드 {rc}"
    if os.name == "nt":
        try:
            r = subprocess.run(["schtasks", "/Run", "/TN", NATIVE_UPDATE_TASK], capture_output=True, text=True,
                               errors="replace", timeout=30, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, f"schtasks 를 실행하지 못했습니다: {e}"
        if r.returncode == 0:
            return True, ("업데이터를 시작했습니다. 세션 중이면 미루고, 설치하면 앱이 잠시 닫혔다 다시 열립니다"
                          "(진행: linkmycom status).")
        if not native_task_exists():
            return False, f"예약 작업 {NATIVE_UPDATE_TASK} 이 없습니다. LinkMyCom 설치기를 다시 실행하세요."
        return False, NATIVE_TASK_REFUSED
    script = os.path.expanduser(MAC_NATIVE_UPDATER)
    if platform.system() == "Darwin" and os.path.isfile(script):
        try:
            subprocess.Popen(["/bin/bash", script, "--auto"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            return False, f"업데이터를 시작하지 못했습니다: {e}"
        return True, "업데이터를 백그라운드로 시작했습니다(진행: linkmycom status)."
    return False, "이 PC 에는 화면공유 앱 업데이터가 없습니다(Mac 은 앱이 설치한 Update-Native-Mac.sh)."


def cmd_update_all(cfg: dict, check_only: bool = False, dry: bool = False) -> int:
    """이 PC 의 CLI → 타워 → 화면공유 앱을 차례로 거울 최신과 비교하고, 새 판이 있으면 각자의 방식으로 적용한다."""
    have = local_component_versions()
    try:
        latest = fetch_latest_components(cfg, timeout=15)
    except Exception as e:  # noqa: BLE001
        warn(f"거울의 최신 판을 읽지 못했습니다({e}). 각 업데이터가 직접 확인합니다.")
        latest = {}
    bad = 0
    pending = 0
    for comp in ("cli", "tower", "native"):
        label = COMPONENT_LABELS[comp]
        cur, new = have.get(comp) or "", latest_for(latest, comp, local_os_name()) or ""
        if not cur:
            print(f"{label}: 설치되지 않음")
            continue
        if new and parse_version(cur) >= parse_version(new):
            print(f"{label} {cur}: " + c("최신", "32"))
            continue
        pending += 1
        head = f"{label} {cur} → {new or '확인 필요'}"
        if check_only:
            print(c(head, "33"))
            continue
        if dry:
            print(f"{head}: {local_update_action(comp)} (-n: 실행하지 않음)")
            continue
        print(c(f"{head}: {local_update_action(comp)}", "36"))
        ok, msg = run_local_component_update(comp, cfg)
        if msg:
            print("  " + (msg if ok else c(msg, "31")))
        bad += not ok
    if check_only and pending:
        print("적용하려면: linkmycom update --all")
    return 1 if bad else 0


# ---------------------------------------------------------------- 이 PC 요약 (status, C10).

def received_log_path() -> Path | None:
    """앱의 받은 파일 기록(received.json). 앱 lmc_received.dart 의 receivedLogPath 와 같은 위치."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "LinkMyCom" / "received.json" if appdata else None
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "LinkMyCom" / "received.json"
    return Path.home() / ".config" / "LinkMyCom" / "received.json"


def received_counts(now: datetime | None = None) -> tuple[int, int]:
    """(받은 파일 기록 수, 24시간 안의 수)."""
    p = received_log_path()
    text = read_text_quiet(p) if p else ""
    try:
        data = json.loads(text) if text.strip() else []
    except ValueError:
        return 0, 0
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return 0, 0
    now = now or datetime.now(timezone.utc)
    recent = 0
    for it in items:
        try:
            at = datetime.fromisoformat(str(it.get("at", "")).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if (now - at).total_seconds() <= 86400:
            recent += 1
    return len(items), recent


def local_time_text(stamp: str) -> str:
    """ISO(UTC) 시각을 이 PC 시간 'MM-DD HH:MM' 로. 읽지 못하면 그대로."""
    try:
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return stamp or ""
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone().strftime("%m-%d %H:%M")


def cli_auto_update_text(cfg: dict, state: dict) -> str:
    if not cfg.get("auto_update_check", True):
        mode = "꺼짐"
    elif cfg.get("auto_update_apply", True):
        mode = "대화형 실행 때 1시간마다 확인·적용"
    else:
        mode = "하루 한 번 확인만"
    parts = [mode]
    if state.get("last_update_check"):
        parts.append("마지막 확인 " + local_time_text(state["last_update_check"]))
    if state.get("update_available"):
        parts.append(f"새 판 {state['update_available']}")
    if state.get("update_error"):
        parts.append("오류 " + str(state["update_error"])[:80])
    return ", ".join(parts)


STATUS_TASK_ROWS = {"task_tower": TOWER_TASK_NAME, "task_tower_update": "LinkMyCom-TowerUpdate",
                    "task_native_update": "LinkMyCom-NativeUpdate"}


def status_next(disk: dict | None, updater: dict | None, tasks_missing: list[str]) -> list[str]:
    """status 가 문제를 보면 다음에 칠 명령(한 줄로 이어 보임)."""
    out: list[str] = []
    fixable = [t for t in tasks_missing if t != "LinkMyCom-NativeUpdate"]
    if fixable:
        out.append("linkmycom doctor --fix (빠진 예약 작업 등록)")
    if "LinkMyCom-NativeUpdate" in tasks_missing:
        out.append("LinkMyCom 설치기를 관리자 권한으로 다시 실행(LinkMyCom-NativeUpdate 는 SYSTEM 작업)")
    if updater and updater.get("status") == "WARN":
        m = re.search(r"pid (\d+)", updater.get("detail", ""))
        out.append((f"멈춘 업데이터 끝내기: Stop-Process -Id {m.group(1)} -Force" if m else "멈춘 업데이터를 끝내세요")
                   + " 뒤 linkmycom update --all")
    if disk and disk.get("status") == "WARN":
        out.append("디스크 여유 확보(업데이터가 여유 부족이면 중단함)")
    return out


def status_data(cfg: dict, latest: dict[str, str], peers: list[dict],
                rows: list[tuple[str, str, str]] | None = None) -> dict:
    """status 가 보이는 값. --json 도 이 구조 그대로. rows 는 이 PC 의 doctor 점검 줄(disk·updater·예약 작업 줄을 쓴다)."""
    rows = rows or []
    state = load_json(STATE_PATH)
    vers = local_component_versions()
    auto = {"cli": cli_auto_update_text(cfg, state)}
    for comp, path in update_state_paths().items():
        auto[comp] = read_update_state(path)
    online = [p for p in peers if p.get("online") and p.get("os") not in MOBILE_OS]
    relayed = [p["name"] for p in online if p.get("relay") and not p.get("cur_addr")]
    total, recent = received_counts()
    forwards = [{"name": f.get("name", "?"), "specs": f.get("specs") or [], "pid": f["pid"]}
                for f in load_forwards(prune=False) if pid_alive(f["pid"])]
    disk, updater = row_object(rows, "disk"), row_object(rows, "updater")
    tasks_missing = [name for key, name in STATUS_TASK_ROWS.items()
                     if next((s for n, s, _ in rows if n == key), "") in ("WARN", "FAIL")]
    return {"host": platform.node().split(".")[0], "versions": vers, "latest": latest, "auto_update": auto,
            "devices": {"online": len(online), "total": len([p for p in peers if p.get("os") not in MOBILE_OS]),
                        "relayed": relayed},
            "received": {"total": total, "last24h": recent}, "forwards": forwards,
            "disk": disk, "updater": updater, "tasks_missing": tasks_missing, "hidden": len(hidden_names(cfg)),
            "next": status_next(disk, updater, tasks_missing)}


def cmd_status(cfg: dict, args: list[str]) -> int:
    """이 PC 한 화면 요약: 버전 3종(거울 최신과 비교)·자동 업데이트 상태·켜진 장비 수·중계 장비·받은 파일 수·포트 전달."""
    as_json = "--json" in args
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        lf = pool.submit(fetch_latest_components, cfg, 5)
        rf = pool.submit(local_doctor_rows, True)  # 디스크·업데이터·예약 작업 줄(점검 스크립트의 버전 전용 모드)
        try:
            peers, _ = cached_peers()
        except SystemExit:
            peers = []
        try:
            latest = lf.result()
        except Exception:  # noqa: BLE001 - 오프라인이어도 요약은 보인다
            latest = {}
        try:
            health = rf.result()
        except (SystemExit, Exception):  # noqa: BLE001 - 점검 스크립트를 못 돌려도 나머지 요약은 보인다
            health = []
    data = status_data(cfg, latest, peers, health)
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    rows = []
    for comp in ("cli", "tower", "native"):
        cur = data["versions"].get(comp) or ""
        auto = data["auto_update"].get(comp)
        if isinstance(auto, dict):
            auto_text = " ".join(x for x in (auto["result"], auto["checked"]) if x) or "기록 없음"
            if auto.get("result") == "installing" and auto.get("available"):
                auto_text = f"새 버전 {auto['available']} 설치 중"
        else:
            auto_text = auto or "-"
        rows.append([COMPONENT_LABELS[comp], version_cell(cur, latest_for(latest, comp, local_os_name())) if cur else "설치 안 됨",
                     "자동 업데이트: " + auto_text if cur else "-"])
    dev = data["devices"]
    rows.append(["장비", f"켜짐 {dev['online']} / {dev['total']}",
                 ("중계(직접 연결 없음): " + ", ".join(dev["relayed"])) if dev["relayed"] else "중계 장비 없음"])
    rows.append(["받은 파일", f"{data['received']['total']}개", f"24시간 안 {data['received']['last24h']}개"])
    fw = data["forwards"]
    rows.append(["포트 전달", f"{len(fw)}개", "; ".join(f"{f['name']} {','.join(f['specs'])}" for f in fw) or "-"])
    for label, key in (("디스크", "disk"), ("업데이터", "updater")):
        item = data.get(key)
        if item:
            rows.append([label, c(item["status"], "32" if item["status"] == "OK" else "33"), item["detail"]])
    if data["tasks_missing"]:
        rows.append(["예약 작업", c("WARN", "33"), "없음: " + ", ".join(data["tasks_missing"])])
    if data["hidden"]:
        rows.append(["숨긴 장비", f"{data['hidden']}대", "linkmycom list --all 로 보기, unhide <이름> 으로 되돌리기"])
    print(c(f"linkmycom status · {data['host']}", "1"))
    print_table(rows, ["항목", "판·수", "내용"])
    if data["next"]:
        print(c("다음: " + "; ".join(data["next"]), "33"))
    if not latest:
        print(c("거울의 최신 판을 읽지 못해 '최신' 판정은 빠졌습니다.", "90"))
    return 0


# ---------------------------------------------------------------- fleet 의 구성요소 판정과 원격 업데이터 (C7).

def row_versions(rows: list[tuple[str, str, str]]) -> dict[str, str]:
    """doctor 줄에서 (PATH 의 lmc 또는 가장 높은 CLI 설치본, 타워, 화면공유 앱) 판."""
    d = {n: det for n, _, det in rows}
    path = path_lmc_version(rows)
    clis = list(cli_versions(rows).values())
    cli = path[1] if path else (max(clis, key=parse_version) if clis else "")

    def ver(x: str | None) -> str:
        x = (x or "").strip()
        return x if VERSION_RE.match(x) else ""

    return {"cli": cli, "tower": ver(d.get("tower")), "native": ver(d.get("native"))}


def outdated_components(vers: dict[str, str], latest: dict[str, str], os_name: str = "") -> list[str]:
    return [k for k in ("cli", "tower", "native")
            if vers.get(k) and latest_for(latest, k, os_name)
            and parse_version(vers[k]) < parse_version(latest_for(latest, k, os_name))]


def version_cell(cur: str, new: str) -> str:
    """표 칸: '0.5.0 최신' / '0.4.4 → 0.5.0' / 거울을 못 읽었으면 판만."""
    if not cur:
        return "-"
    if not new or not VERSION_RE.match(cur):
        return cur
    return f"{cur} 최신" if parse_version(cur) >= parse_version(new) else f"{cur} → {new}"


def component_update_command(what: str, os_name: str) -> str:
    """원격에서 업데이터를 시작하는 명령 한 줄. 결과는 'LMCUPD|started|ran|denied|missing|내용' 한 줄.

    Windows: 예약 작업(native: LinkMyCom-NativeUpdate(SYSTEM), tower: LinkMyCom-TowerUpdate)을 schtasks /Run 으로 시작한다.
    SSH 세션이 끝나도 계속 돈다. 타워 작업이 없으면(0.7.0) 세션 안에서 돌리지 않고 일회용 예약 작업(LinkMyCom-TowerUpdate-Once)을
    그 PC 에 로그온한 사용자의 대화형 세션에서 시작해 시작 뒤 지운다(로그온한 사용자가 없으면 'LMCUPD|nosession').
    세션 안에서 업데이터를 직접 돌리면 SSH 세션의 ssh-keygen 서명 확인이 멈추고 세션에서 띄운 타워가 세션과 함께 꺼진다.
    Mac(native): Update-Native-Mac.sh --auto 를 nohup 으로 떼어 놓는다. 세션 중이면 두 업데이터 모두 스스로 미룬다.
    """
    if os_name == "windows":
        task = NATIVE_UPDATE_TASK if what == "native" else TOWER_UPDATE_TASK
        lines = [
            "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
            "$t = '" + task + "'",
            "$has = Test-Path (Join-Path $env:SystemRoot ('System32\\Tasks\\' + $t))",
            "if (-not $has) { schtasks /Query /TN $t 2>$null | Out-Null; $has = ($LASTEXITCODE -eq 0) }",
            "if ($has) { $o = (schtasks /Run /TN $t 2>&1 | Out-String).Trim(); "
            "if ($LASTEXITCODE -eq 0) { 'LMCUPD|started|' + $t } else { 'LMCUPD|denied|' + ($o -replace '\\s+', ' ') }; exit 0 }",
        ]
        if what == "tower":
            lines += [
                "$s = Join-Path $env:LOCALAPPDATA 'DeskTools\\tower\\Update-LinkMyCom.ps1'",
                "if (-not (Test-Path $s)) { 'LMCUPD|missing|' + $t; exit 0 }",
                "$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name",
                "$short = $me.Split('\\')[-1]",
                "$cu = [string](Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue).UserName",
                "$q = (quser 2>$null | Out-String)",
                "if (-not (($cu -and $cu.EndsWith('\\' + $short)) -or ($q -match ('(?im)^[> ]*' + [regex]::Escape($short) + '\\s')))) "
                "{ 'LMCUPD|nosession|' + $short; exit 0 }",
                "$name = '" + TOWER_UPDATE_ONCE_TASK + "'",
                "$act = New-ScheduledTaskAction -Execute (Join-Path $env:SystemRoot 'System32\\WindowsPowerShell\\v1.0\\powershell.exe') "
                "-Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File \"' + $s + '\" -Mirror -Auto') "
                "-WorkingDirectory (Split-Path $s)",
                "$pr = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited",
                "$st = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew "
                "-ExecutionTimeLimit (New-TimeSpan -Minutes 30)",
                "try { Register-ScheduledTask -TaskName $name -Action $act -Principal $pr -Settings $st -Force -ErrorAction Stop | Out-Null; "
                "Start-ScheduledTask -TaskName $name -ErrorAction Stop } "
                "catch { 'LMCUPD|denied|' + ($_.Exception.Message -replace '\\s+', ' '); exit 0 }",
                "for ($i = 0; $i -lt 20; $i++) { if ((Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue).State -eq 'Running') { break }; "
                "Start-Sleep -Milliseconds 500 }",
                "Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue",
                "'LMCUPD|started|' + $name + ' (one-shot task, removed after start)'; exit 0",
            ]
        lines.append("'LMCUPD|missing|' + $t")
        return "powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps("\n".join(lines) + "\n")
    return ('f="$HOME/Library/Application Support/LinkMyCom/Update-Native-Mac.sh"; '
            'if [ -f "$f" ]; then nohup /bin/bash "$f" --auto >/dev/null 2>&1 </dev/null & '
            'echo "LMCUPD|started|Update-Native-Mac.sh"; else echo "LMCUPD|missing|Update-Native-Mac.sh"; fi')


def component_update_result(what: str, rc: int, out: str, err: str) -> tuple[bool, str]:
    line = next((l.strip() for l in out.splitlines() if l.startswith("LMCUPD|")), "")
    status, _, detail = line[len("LMCUPD|"):].partition("|") if line else ("", "", "")
    if status == "started":
        return True, f"업데이터를 시작했습니다({detail}). 세션 중이면 업데이터가 미룹니다. 결과: linkmycom fleet status"
    if status == "ran":
        return True, f"타워 업데이터 실행: {detail or '출력 없음'}"
    if status == "nosession":
        return False, (f"그 PC 에 로그온한 사용자({detail or '?'})가 없어 시작하지 못했습니다. 타워 업데이터는 로그온한 대화형 세션에서 "
                       "돌아야 합니다(SSH 세션 안에서 돌리면 멈춤). 그 PC 에 로그인한 뒤 다시 실행하세요.")
    if status == "denied":
        return False, NATIVE_TASK_REFUSED if what == "native" else f"예약 작업 시작이 거부됐습니다: {detail}"
    if status == "missing":
        return False, ("업데이터가 없습니다(" + detail + "). " +
                       ("LinkMyCom 설치기를 다시 실행하세요." if what == "native" else "타워 패키지를 다시 설치하세요."))
    return False, remote_rows_error([], err) if not out.strip() else last_line(out, "출력 없음")


WAIT_DEFAULT = 120.0


def parse_wait(rest: list[str]) -> tuple[list[str], float | None]:
    """'--wait [초]' / '--wait=초' 를 떼어 (나머지 인자, 기다릴 초). --wait 가 없으면 None, 초를 빼면 기본 120."""
    out: list[str] = []
    wait: float | None = None
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--wait":
            wait = WAIT_DEFAULT
            if i + 1 < len(rest) and re.fullmatch(r"\d+(?:\.\d+)?", rest[i + 1]):
                wait = float(rest[i + 1])
                i += 1
        elif a.startswith("--wait="):
            try:
                wait = float(a[len("--wait="):])
            except ValueError:
                die("--wait 에는 초(숫자)를 쓰세요. 예: --wait 120")
        else:
            out.append(a)
        i += 1
    return out, wait


def update_state_read_command(what: str, os_name: str) -> str:
    """원격의 update-state.json 을 한 줄('LMCSTATE|<json>')로 읽는 명령. 파일이 없으면 'LMCSTATE|'."""
    if os_name == "windows":
        where = ("Join-Path $env:LOCALAPPDATA 'DeskTools\\tower\\update-state.json'" if what == "tower"
                 else "Join-Path $env:ProgramData 'LinkMyCom\\update-state.json'")
        # 상태 파일은 BOM 없는 UTF-8 이고 message 에 한글이 든다. Windows PowerShell 은 그것을 기본 코드 페이지로 읽어 JSON 을 깨뜨리므로
        # (0.7.0 실기: --wait 가 'unreadable') UTF-8 로 읽고, 판정에 쓰는 세 필드만 ASCII JSON 으로 다시 만들어 보낸다.
        lines = ["$p = " + where,
                 "if (-not (Test-Path -LiteralPath $p)) { 'LMCSTATE|'; exit 0 }",
                 "try { $o = Get-Content -Raw -Encoding UTF8 -LiteralPath $p | ConvertFrom-Json; "
                 "'LMCSTATE|' + (([ordered]@{ lastResult = [string]$o.lastResult; checked = [string]$o.checked; "
                 "available = [string]$o.available }) | ConvertTo-Json -Compress) } catch { 'LMCSTATE|{bad' }"]
        return "powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps("\n".join(lines) + "\n")
    return ('printf "LMCSTATE|"; cat "$HOME/Library/Application Support/LinkMyCom/update-state.json" 2>/dev/null | tr "\\n" " "; echo')


def parse_state_line(out: str) -> dict | None:
    """'LMCSTATE|<json>' 줄을 {'result','checked','available'}(checked 는 자르지 않은 원문) 로. 줄이 없으면 None(읽지 못함)."""
    line = next((l for l in out.splitlines() if l.startswith("LMCSTATE|")), None)
    if line is None:
        return None
    body = line[len("LMCSTATE|"):].strip()
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        return {"result": "unreadable", "checked": "", "available": ""}
    data = data if isinstance(data, dict) else {}
    res = data.get("lastResult")
    if isinstance(res, dict):
        res = res.get("result") or res.get("status") or ""
    return {"result": str(res or ""), "checked": str(data.get("checked") or ""), "available": str(data.get("available") or "")}


UPDATE_RESULT_TEXT = {"ok": "업데이트 완료", "none": "새 판 없음", "deferred": "세션 중이라 미룸", "error": "업데이트 실패"}


def update_wait_verdict(before: dict, now: dict) -> tuple[bool, str] | None:
    """시작 전 상태(before)와 지금 상태(now)로 업데이터가 끝났는지. 끝났으면 (성공 여부, 설명), 아직이면 None.
    installing 이면 진행 중, 확인 시각(checked)이나 결과가 시작 전과 같으면 아직 이번 실행이 기록되지 않은 것으로 본다."""
    res = now.get("result", "")
    if res == "installing":
        return None
    if now.get("checked", "") == before.get("checked", "") and res == before.get("result", ""):
        return None
    text = UPDATE_RESULT_TEXT.get(res, res or "결과 없음")
    when = (now.get("checked") or "")[:16].replace("T", " ")
    return res != "error", text + (f" ({when})" if when else "")


def wait_update_result(read, before: dict, timeout: float, interval: float = 5.0, sleep=time.sleep,
                       clock=time.monotonic) -> tuple[bool, str]:
    """read()(상태 dict, 못 읽으면 None)를 interval 초마다 불러 update_wait_verdict 가 끝을 알리거나 timeout 초가 지날 때까지 기다린다."""
    end = clock() + timeout
    last: dict = {}
    while True:
        now = read()
        if now is not None:
            last = now
            verdict = update_wait_verdict(before, now)
            if verdict:
                return verdict
        if clock() >= end:
            break
        sleep(min(interval, max(0.0, end - clock())))
    state = last.get("result") or "기록 없음"
    return False, f"{int(timeout)}초 안에 결과가 기록되지 않았습니다(마지막 상태: {state}). 나중에 linkmycom fleet status 로 확인하세요."


def cmd_fleet_component(cfg: dict, what: str, rest: list[str]) -> int:
    """fleet update native|tower [이름|a,b|all] [--apply [--wait [초]]]: 거울 최신보다 낡은 원격 PC 의 업데이터를 SSH 로 시작한다.
    --apply 가 없으면(-n 포함) 할 일만 보인다. --wait 는 시작한 뒤 각 PC 의 update-state.json 을 읽어 결과를 기다린다(기본 120초).
    이 PC 는 'linkmycom update --all'."""
    rest, wait = parse_wait(rest)
    apply = "--apply" in rest and not ("-n" in rest or "--dry-run" in rest)
    names = [a for a in rest if not a.startswith("-") and a != what]
    label = COMPONENT_LABELS[what]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        lf = pool.submit(fetch_latest_components, cfg, 10)
        results = fleet_rows(cfg)
        try:
            latest = lf.result()
        except Exception as e:  # noqa: BLE001
            warn(f"거울의 최신 판을 읽지 못했습니다({e}). 설치된 PC 모두에 업데이터를 시작합니다(업데이터가 직접 확인).")
            latest = {}
    blocks = ssh_config_blocks()
    only = {p["name"] for p in resolve_targets(cfg, blocks, names[0])} if names else None
    new = latest.get(what, "")
    plan = []
    for r in results:
        if r.get("peer") is None or r.get("skipped") or r.get("error"):
            continue
        if only is not None and r["name"] not in only:
            continue
        if r["os"] not in (("windows",) if what == "tower" else ("windows", "macOS")):
            continue
        cur = row_versions(r["rows"]).get(what)
        if not cur:
            continue
        new_here = latest_for(latest, what, r["os"]) if latest else ""
        if latest and not new_here and only is None:
            continue  # 이 OS 용 패키지가 실린 판이 없다(Mac 의 화면공유 앱)
        if new_here and parse_version(cur) >= parse_version(new_here) and only is None:
            continue
        # 한 Mac 에 Tailscale 이 둘이면 같은 장비가 두 행으로 나온다. 업데이터는 한 번만 시작한다.
        twin = next((p for p, _ in plan if related_nodes(r["peer"], [p["peer"]])), None)
        if twin:
            print(f"{r['name']}: {twin['name']} 와 같은 장비로 보여 건너뜁니다.")
            continue
        plan.append((r, cur))
    for r in results:
        if r.get("error"):
            warn(f"{r['name']}: {r['error']} (건너뜀)")
    if results and results[0].get("peer") is None:
        local_cur = row_versions(results[0]["rows"]).get(what)
        if local_cur and new and parse_version(local_cur) < parse_version(new):
            print(f"이 PC 의 {label} {local_cur} 도 낡았습니다. 여기서는 'linkmycom update --all' 을 실행하세요.")
    if not plan:
        print(f"{label}을(를) 새로 받을 원격 PC 가 없습니다" + (f"(거울 최신 {new})." if new else "."))
        return 0
    for r, cur in plan:
        how = (f"예약 작업 {NATIVE_UPDATE_TASK if what == 'native' else TOWER_UPDATE_TASK} 시작" if r["os"] == "windows"
               else "Update-Native-Mac.sh --auto 시작")
        print(f"{r['name']}: {label} {cur} → {latest_for(latest, what, r['os']) or '확인 필요'} · {how}")
    if not apply:
        print("실행하려면 --apply 를 붙이세요(--apply --wait 는 결과까지 기다림). 화면공유 세션 중인 PC 는 업데이터가 스스로 미룹니다.")
        return 0
    ssh = ssh_bin()
    record_history("fleet update", [r["name"] for r, _ in plan], detail=f"{what} {new}".strip())

    def go(item) -> tuple[bool, str]:
        r, _ = item

        def read() -> dict | None:
            rc2, out2, _e = run_remote(r["peer"], cfg, blocks, [update_state_read_command(what, r["os"])], timeout=40, ssh=ssh)
            return parse_state_line(out2) if rc2 == 0 else None

        before = (read() or {}) if wait is not None else {}
        rc, out, err = run_remote(r["peer"], cfg, blocks, [component_update_command(what, r["os"])], timeout=90, ssh=ssh)
        ok, msg = component_update_result(what, rc, out, err)
        if wait is not None and ok and "LMCUPD|started|" in out:
            done, text = wait_update_result(read, before, wait)
            return done, f"{msg.split('. ')[0]}. 결과: {text}"
        return ok, msg

    bad = 0
    for (r, _), res in zip(plan, parallel_map(go, plan)):
        ok, msg = res if isinstance(res, tuple) else (False, str(res))
        bad += not ok
        print(c(f"[{r['name']}]", "36") + " " + (c("OK", "32") if ok else c("실패", "31")) + f" {msg}")
    return 1 if bad else 0


# ---------------------------------------------------------------- 화면공유 도달성·중복 Tailscale 노드 (doctor <이름>, C8).

SCREEN_PORT = 21118


def node_key(text) -> str:
    """이름 비교용: 소문자 영숫자만(한글이 든 '미니의 Mac mini' 호스트 이름은 'macmini' 가 된다)."""
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def related_nodes(peer: dict, peers: list[dict]) -> list[dict]:
    """같은 장비의 다른 Tailscale 노드 후보: 켜져 있고 OS 가 같으며, 이름·호스트 이름이 같거나 한쪽이 다른 쪽을 품는다(5자 이상).

    한 Mac 에 Homebrew tailscaled 와 Tailscale.app 이 함께 로그인하면 miniui-macmini 와 macmini('미니의 Mac mini')
    두 노드가 생기고 화면공유(21118)는 한쪽으로만 닿는다. 호스트 이름이 서로 달라서 이름 포함 관계로 찾는다.
    """
    mine = {node_key(peer.get("name")), node_key(peer.get("hostname"))} - {""}
    out = []
    for p in peers:
        if p.get("name") == peer.get("name") or not p.get("online") or not p.get("ip") or p.get("ip") == peer.get("ip"):
            continue
        if p.get("os") in MOBILE_OS or str(p.get("os", "")).lower() != str(peer.get("os", "")).lower():
            continue
        theirs = {node_key(p.get("name")), node_key(p.get("hostname"))} - {""}
        if mine & theirs or any(len(a) >= 5 and len(b) >= 5 and (a in b or b in a) for a in mine for b in theirs):
            out.append(p)
    return out


def host_key_blobs(ip: str, timeout: int = 5) -> set[str] | None:
    """ssh-keyscan 으로 받은 호스트 키의 base64 부분들. ssh-keyscan 이 없거나 받지 못하면 None."""
    exe = keyscan_bin()
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-T", str(timeout), ip], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout + 10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    blobs = {l.split()[2] for l in r.stdout.splitlines() if not l.startswith("#") and len(l.split()) >= 3}
    return blobs or None


def reach_rows(peer: dict, peers: list[dict], cfg: dict, blocks: list[dict]) -> list[tuple[str, str, str]]:
    """이 PC 에서 그 PC 의 21118 TCP 도달성(screen_reach)과, 같은 장비의 다른 노드 중 21118 이 한쪽만 열린 경우(dup_node)."""
    reach = port_open(peer["ip"], SCREEN_PORT, 1.5)
    desktop = peer.get("os") in ("windows", "macOS")
    rows = [("screen_reach", "OK" if reach else ("WARN" if desktop else "INFO"),
             f"{peer['ip']}:{SCREEN_PORT} " + ("열림" if reach else "닫힘(화면공유 앱이 꺼졌거나 이 노드로는 닿지 않음)"))]
    alt = str(host_settings(peer, cfg, blocks).get("screen") or "")
    for other in related_nodes(peer, peers):
        other_reach = port_open(other["ip"], SCREEN_PORT, 1.5)
        if other_reach == reach:
            continue
        mine, theirs = host_key_blobs(peer["ip"]), host_key_blobs(other["ip"])
        if mine is not None and theirs is not None and not (mine & theirs):
            continue  # 호스트 키가 다르면 다른 장비다
        same = "호스트 키가 같은 같은 장비" if mine and theirs else "이름·OS 로 보아 같은 장비"
        if reach:
            rows.append(("dup_node", "INFO", f"{other['name']}({other['ip']}) 도 {same}의 Tailscale 노드인데 그쪽은 "
                         f"{SCREEN_PORT} 이 닫혀 있습니다. 화면공유는 {peer['name']} 으로 하세요. Tailscale 을 하나만 남기면 정리됩니다."))
        elif alt and node_key(alt) == node_key(other["name"]):
            rows.append(("dup_node", "INFO", f"{other['name']}({other['ip']}) 는 {same}의 다른 노드이고 {SCREEN_PORT} 이 열려 "
                         f"있습니다. screen={alt} 설정으로 화면공유는 그쪽으로 접속합니다."))
        else:
            rows.append(("dup_node", "WARN", f"{other['name']}({other['ip']}) 는 {same}의 다른 Tailscale 노드이고 {SCREEN_PORT} 이 "
                         f"열려 있습니다. 'linkmycom set {peer['name']} screen={other['name']}' 로 화면공유를 그쪽으로 보내거나 "
                         "Tailscale 을 하나만 남기세요."))
    return rows


# ---------------------------------------------------------------- MAC 주소 기억과 깨우기 (wake, C4).

LAN_RE = re.compile(r"mac=([0-9a-f]{2}(?::[0-9a-f]{2}){5}) ip=(\d+\.\d+\.\d+\.\d+)/(\d+)")
WAKE_PORT = 9


def macs_path() -> Path:
    return CONFIG_DIR / "macs.json"


def lan_of(rows: list[tuple[str, str, str]]) -> dict | None:
    """doctor 의 lan 줄('mac=.. ip=../..')을 {'mac','ip','prefix'} 로."""
    detail = next((d for n, _, d in rows if n == "lan"), "")
    m = LAN_RE.search(detail or "")
    if not m or m.group(1) in ("02:00:00:00:00:00", "00:00:00:00:00:00"):  # 가려진 MAC 은 기억하지 않는다
        return None
    return {"mac": m.group(1), "ip": m.group(2), "prefix": int(m.group(3))}


def self_ts_name(rows: list[tuple[str, str, str]]) -> str:
    """이 PC 의 Tailscale 이름(doctor 의 tailscale 줄 첫 낱말)."""
    detail = next((d for n, s, d in rows if n == "tailscale" and s == "OK"), "")
    return (detail.split() or [""])[0].lower()


def remember_lans(items: list[tuple[str | None, list[tuple[str, str, str]]]]) -> None:
    """doctor 결과의 lan 줄을 ~/.tssh/macs.json 에 기억한다. 이름이 None 이면 이 PC(self). lan 줄이 없으면 쓰지 않는다."""
    found = [(name, rows, lan_of(rows)) for name, rows in items]
    found = [x for x in found if x[2]]
    if not found:
        return
    data = load_json(macs_path())
    hosts = data.get("hosts") if isinstance(data.get("hosts"), dict) else {}
    now = datetime.now(timezone.utc).isoformat()[:19]
    for name, rows, lan in found:
        entry = dict(lan, time=now)
        if name is None:
            data["self"] = entry
            name = self_ts_name(rows)
        if name:
            hosts[name] = entry
    data["hosts"] = hosts
    try:
        save_json(macs_path(), data)
    except OSError:
        pass


def magic_packet(mac: str) -> bytes:
    hexs = re.sub(r"[^0-9a-fA-F]", "", mac or "")
    if len(hexs) != 12:
        raise ValueError(f"MAC 주소가 아닙니다: {mac}")
    return b"\xff" * 6 + bytes.fromhex(hexs) * 16


def lan_broadcast(entry: dict) -> str:
    import ipaddress

    return str(ipaddress.ip_network(f"{entry['ip']}/{int(entry['prefix'])}", strict=False).broadcast_address)


def same_lan(a: dict, b: dict) -> bool:
    try:
        return int(a["prefix"]) == int(b["prefix"]) and lan_broadcast(a) == lan_broadcast(b)
    except (KeyError, ValueError, TypeError):
        return False


def send_magic(packet: bytes, bcast: str) -> int:
    """이 PC 에서 LAN 브로드캐스트와 255.255.255.255 의 9번 포트로 보낸다. 보낸 횟수."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sent = 0
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for addr in (bcast, "255.255.255.255"):
            try:
                s.sendto(packet, (addr, WAKE_PORT))
                sent += 1
            except OSError:
                pass
    finally:
        s.close()
    return sent


def wake_remote_command(os_name: str, packet: bytes, bcast: str) -> str:
    """켜진 PC 에서 매직 패킷을 보내는 명령 한 줄. 결과는 'LMCWAKE|sent|횟수' 또는 'LMCWAKE|fail|..'."""
    hexs = packet.hex()
    if os_name == "windows":
        lines = [
            "$h = '" + hexs + "'",
            "$m = New-Object byte[] " + str(len(packet)),
            "for ($i = 0; $i -lt $m.Length; $i++) { $m[$i] = [Convert]::ToByte($h.Substring($i * 2, 2), 16) }",
            "$u = New-Object Net.Sockets.UdpClient",
            "$u.EnableBroadcast = $true",
            "$n = 0",
            "foreach ($a in @('" + bcast + "', '255.255.255.255')) { try { [void]$u.Send($m, $m.Length, $a, " + str(WAKE_PORT)
            + "); $n++ } catch {} }",
            "$u.Close()",
            "if ($n) { 'LMCWAKE|sent|' + $n } else { 'LMCWAKE|fail|send failed' }",
        ]
        return "powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps("\n".join(lines) + "\n")
    code = ("import socket\n"
            "s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n"
            "s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)\n"
            "p = bytes.fromhex('" + hexs + "')\n"
            "n = 0\n"
            "for a in ('" + bcast + "', '255.255.255.255'):\n"
            "    try:\n"
            "        s.sendto(p, (a, " + str(WAKE_PORT) + "))\n"
            "        n += 1\n"
            "    except OSError:\n"
            "        pass\n"
            "print('LMCWAKE|%s|%d' % ('sent' if n else 'fail', n))\n")
    return f'python3 -c "{code}" || python -c "{code}"'


WAKE_USAGE = "사용법: linkmycom wake <이름> [--via <켜진 PC>] [-n]"


def cmd_wake(cfg: dict, args: list[str]) -> int:
    """'wake <이름>': doctor 가 모아 둔 MAC 주소로 매직 패킷. 그 PC 와 같은 LAN 의 켜진 PC(또는 이 PC)에서 보낸다."""
    via_name, rest, dry = None, [], False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--via" and i + 1 < len(args):
            via_name = args[i + 1]
            i += 2
            continue
        if a.startswith("--via="):
            via_name = a[len("--via="):]
        elif a in ("-n", "--dry-run"):
            dry = True
        elif a.startswith("-"):
            die(WAKE_USAGE)
        else:
            rest.append(a)
        i += 1
    if not rest:
        die(WAKE_USAGE)
    blocks = ssh_config_blocks()
    peer, peers = pick_cached(cfg, blocks, rest[0])
    data = load_json(macs_path())
    hosts = data.get("hosts") if isinstance(data.get("hosts"), dict) else {}
    entry = hosts.get(peer["name"])
    if not isinstance(entry, dict):
        die(f"{peer['name']} 의 MAC 주소 기록이 없습니다. 그 PC 가 켜져 있을 때 'linkmycom doctor {peer['name']}' 이나 "
            "'linkmycom doctor --all' 로 모아 두세요(~/.tssh/macs.json).")
    try:
        packet = magic_packet(entry["mac"])
        bcast = lan_broadcast(entry)
    except (KeyError, ValueError, TypeError) as e:
        die(f"macs.json 의 {peer['name']} 기록을 읽지 못했습니다: {e}")
    via = None
    if via_name:
        via, _ = pick_cached(cfg, blocks, via_name)
    else:
        me = data.get("self")
        if not (isinstance(me, dict) and same_lan(me, entry)):
            cands = [p for p in ssh_capable(peers) if p["name"] != peer["name"]
                     and isinstance(hosts.get(p["name"]), dict) and same_lan(hosts[p["name"]], entry)]
            if cands:
                via = cands[0]
            else:
                warn(f"{peer['name']} 와 같은 LAN 의 켜진 PC 를 찾지 못해 이 PC 에서 보냅니다(다른 LAN 이면 닿지 않습니다)."
                     " --via <이름> 으로 정할 수 있습니다.")
    where = via["name"] if via else "이 PC"
    msg = f"{peer['name']} ({entry['mac']}, {bcast}:{WAKE_PORT}) 에 매직 패킷 ← {where}"
    if dry:
        print(msg + " (-n: 보내지 않음)")
        return 0
    if peer.get("online"):
        print(f"{peer['name']} 은(는) 이미 켜진 것으로 보입니다. 그래도 보냅니다.")
    print(c("→ " + msg, "36"))
    record_history("wake", [peer["name"]], detail=f"via {where}")
    if via is None:
        if not send_magic(packet, bcast):
            die("매직 패킷을 보내지 못했습니다.")
    else:
        rc, out, err = run_remote(via, cfg, blocks, [wake_remote_command(via["os"], packet, bcast)], timeout=60)
        if "LMCWAKE|sent" not in out:
            reason = last_line(out + "\n" + err, "출력 없음")
            die(f"{via['name']} 에서 보내지 못했습니다: {reason}")
    print("보냈습니다. 켜지기까지 30초~2분 걸립니다. 그 PC 의 BIOS·네트워크 어댑터에서 Wake-on-LAN 이 켜져 있어야 합니다.")
    return 0


# ---------------------------------------------------------------- 공유 폴더 열기(open, C2)와 복사(cp, C3).

def share_open_cmd(peer: dict, sub_path: str = "", system: str | None = None) -> list[str]:
    """그 PC 의 SMB 공유를 여는 명령. Windows 탐색기는 UNC(\\\\IP\\경로), macOS 는 open smb://, 그 밖은 xdg-open."""
    import urllib.parse

    system = system or platform.system()
    p = (sub_path or "").replace("\\", "/").strip("/")
    if system == "Windows":
        unc = "\\\\" + peer["ip"] + ("\\" + p.replace("/", "\\") if p else "")
        return ["explorer.exe", unc]
    url = "smb://" + peer["ip"] + "/" + urllib.parse.quote(p, safe="/")
    return ["open", url] if system == "Darwin" else ["xdg-open", url]


def cmd_open(cfg: dict, args: list[str]) -> int:
    dry = "-n" in args or "--dry-run" in args
    rest = [a for a in args if not a.startswith("-")]
    if not rest:
        die("사용법: linkmycom open <이름> [공유 이름/경로] [-n]   예: linkmycom open pfl home/docs")
    blocks = ssh_config_blocks()
    peer, _ = pick_cached(cfg, blocks, rest[0])
    cmd = share_open_cmd(peer, rest[1] if len(rest) > 1 else "")
    if dry:
        print(quote_cmd(cmd))
        return 0
    if not peer["online"]:
        warn(f"{peer['name']} 은(는) 오프라인으로 표시됩니다. 그래도 엽니다.")
    print(c(f"→ {peer['name']} 공유 폴더 {cmd[-1]}", "36"))
    record_history("open", [peer["name"]], detail=cmd[-1])
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        die(f"{cmd[0]} 을(를) 실행하지 못했습니다: {e}")
    return 0


CP_USAGE = ("사용법: linkmycom cp [-r] [-n] <로컬 원본...> <이름>:<경로>\n"
            "        linkmycom cp [-r] [-n] <이름>:<경로>... <로컬 대상>   (경로를 비우면 그 PC 의 홈)")
REMOTE_SPEC_RE = re.compile(r"^(?:([^@/\\:\s]+)@)?([A-Za-z0-9][A-Za-z0-9._-]*):(.*)$", re.S)


def split_remote_spec(arg: str) -> tuple[str | None, str, str] | None:
    """'[사용자@]이름:경로' 면 (사용자, 이름, 경로). 로컬 경로(C:\\.. 드라이브 문자, 실재하는 파일)는 None."""
    m = REMOTE_SPEC_RE.match(arg)
    if not m or (len(m.group(2)) == 1 and not m.group(1)) or os.path.exists(arg):
        return None
    return m.group(1), m.group(2), m.group(3)


def cmd_cp(cfg: dict, args: list[str]) -> int:
    """scp 로 한쪽이 원격인 복사. 이름을 tailnet 주소로 풀고 저장된 사용자·포트·키를 쓰며, Windows 대상은 scp -O(옛 프로토콜)."""
    recursive = dry = False
    pos: list[str] = []
    for a in args:
        if a in ("-r", "-R", "--recursive"):
            recursive = True
        elif a in ("-n", "--dry-run"):
            dry = True
        elif a.startswith("-") and a != "-":
            die(f"알 수 없는 옵션 {a}.\n{CP_USAGE}")
        else:
            pos.append(a)
    if len(pos) < 2:
        die(CP_USAGE)
    specs = [split_remote_spec(a) for a in pos]
    srcs, dst = pos[:-1], pos[-1]
    src_specs, dst_spec = specs[:-1], specs[-1]
    if dst_spec and not any(src_specs):
        upload, remote_specs = True, [dst_spec]
    elif not dst_spec and all(src_specs):
        upload, remote_specs = False, src_specs
    else:
        die("한쪽만 원격이어야 합니다(로컬 → 이름:경로, 또는 이름:경로 → 로컬).\n" + CP_USAGE)
    names = {s[1] for s in remote_specs}
    if len(names) != 1:
        die("원격 원본은 한 PC 에서만 가져옵니다.")
    blocks = ssh_config_blocks()
    peer, _ = pick_cached(cfg, blocks, remote_specs[0][1])
    scp, opts, target = scp_base(peer, cfg, blocks, user=remote_specs[0][0])
    head = [scp] + (["-O"] if peer.get("os") == "windows" else []) + (["-r"] if recursive else []) + opts
    if upload:
        missing = [s for s in srcs if not os.path.exists(s)]
        if missing and not dry:
            die(f"보낼 파일이 없습니다: {', '.join(missing)}")
        cmd = head + srcs + [f"{target}:{dst_spec[2]}"]
    else:
        cmd = head + [f"{target}:{s[2]}" for s in src_specs] + [dst]
    if dry:
        print(quote_cmd(cmd))
        return 0
    record_history("cp", [peer["name"]], detail=("→ " if upload else "← ") + " ".join(pos)[:180])
    print(c(f"→ {'보내기' if upload else '받기'} {peer['name']} ({peer['ip']})", "36"))
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130
    except OSError as e:
        die(f"scp 를 실행하지 못했습니다: {e}")


# ---------------------------------------------------------------- 터미널 프로필 (profiles, C5).

PROFILE_MARK = "linkmycom profiles"
PROFILE_KINDS = {"windows-terminal": "wt", "wt": "wt", "windowsterminal": "wt", "iterm": "iterm", "iterm2": "iterm"}


def profile_targets(peers: list[dict]) -> list[dict]:
    """프로필을 만들 PC: SSH 가 있는(모바일 아닌) 주소 있는 피어, 이름순."""
    return sorted([p for p in peers if p.get("os") not in MOBILE_OS and p.get("ip")], key=lambda p: p["name"].lower())


def profile_launcher() -> list[str]:
    """프로필이 부를 명령. PATH 의 lmc 가 있으면 그것, 없으면 지금 파이썬으로 이 파일."""
    if os.name == "nt":
        return ["cmd.exe", "/c", "lmc"] if shutil.which("lmc") else [sys.executable, str(Path(__file__).resolve())]
    found = shutil.which("lmc")
    return [found] if found else [sys.executable, str(Path(__file__).resolve())]


def profile_guid(name: str) -> str:
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "linkmycom-profile." + name))


def wt_fragment(peers: list[dict], launcher: list[str]) -> dict:
    """Windows Terminal JSON 조각(fragment). 관리 표시 키 linkmycomManaged 가 있는 파일만 다시 쓴다."""
    return {"linkmycomManaged": PROFILE_MARK,
            "profiles": [{"name": f"LinkMyCom · {p['name']}", "guid": "{" + profile_guid(p["name"]) + "}",
                          "commandline": subprocess.list2cmdline(launcher + [p["name"]]), "tabTitle": p["name"],
                          "startingDirectory": "%USERPROFILE%"} for p in profile_targets(peers)]}


def iterm_profiles(peers: list[dict], launcher: list[str]) -> dict:
    """iTerm2 동적 프로필(DynamicProfiles)."""
    import shlex

    return {"linkmycomManaged": PROFILE_MARK,
            "Profiles": [{"Name": f"LinkMyCom · {p['name']}", "Guid": profile_guid(p["name"]), "Custom Command": "Yes",
                          "Command": " ".join(shlex.quote(x) for x in launcher + [p["name"]]), "Tags": ["LinkMyCom"]}
                         for p in profile_targets(peers)]}


def profile_path(kind: str) -> Path:
    if kind == "wt":
        return (Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Microsoft" /
                "Windows Terminal" / "Fragments" / "LinkMyCom" / "linkmycom.json")
    return Path.home() / "Library" / "Application Support" / "iTerm2" / "DynamicProfiles" / "linkmycom.json"


def write_managed_profile(path: Path, data: dict) -> None:
    """관리 표시가 있는 파일(또는 없는 파일)만 원자적으로 쓴다. 사람이 만든 파일이면 RuntimeError."""
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            old = None
        if not (isinstance(old, dict) and old.get("linkmycomManaged") == PROFILE_MARK):
            raise RuntimeError(f"{path} 는 linkmycom 이 만든 파일이 아니라 덮어쓰지 않습니다(옮기거나 지운 뒤 다시 실행).")
    path.parent.mkdir(parents=True, exist_ok=True)
    replace_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def cmd_profiles(cfg: dict, args: list[str]) -> int:
    dry = "-n" in args or "--dry-run" in args
    rest = [a for a in args if not a.startswith("-")]
    default = "iterm" if platform.system() == "Darwin" else "wt"
    kind = PROFILE_KINDS.get((rest[0] if rest else "").lower(), None) if rest else default
    if kind is None:
        die("사용법: linkmycom profiles windows-terminal|iterm [-n]")
    try:
        peers, _ = cached_peers()
    except SystemExit:
        return 1
    launcher = profile_launcher()
    data = wt_fragment(peers, launcher) if kind == "wt" else iterm_profiles(peers, launcher)
    path = profile_path(kind)
    count = len(data["profiles" if kind == "wt" else "Profiles"])
    if dry:
        print(f"{path} (-n: 쓰지 않음, 프로필 {count}개)")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    try:
        write_managed_profile(path, data)
    except (RuntimeError, OSError) as e:
        die(str(e))
    print(f"{path} 에 프로필 {count}개를 썼습니다. " +
          ("Windows Terminal 을 다시 열면 새 탭 메뉴에 보입니다." if kind == "wt" else "iTerm2 가 바로 읽습니다(Profiles 의 LinkMyCom 태그)."))
    return 0


# ---------------------------------------------------------------- 들어온 SSH 접속 기록 (audit, C6).

AUDIT_RE = re.compile(r"Accepted (\S+) for (\S+) from (\S+) port \d+(?: ssh2)?(?:: (\S+) (SHA256:[A-Za-z0-9+/=]+))?")
AUDIT_TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?")


def audit_ps(seconds: int) -> str:
    """Windows: OpenSSH/Operational 이벤트 로그에서 'Accepted' 줄을 'UTC시각Z 메시지' 로."""
    return "\n".join([
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
        "$since = (Get-Date).AddSeconds(-" + str(int(seconds)) + ")",
        "$ev = @()",
        "try { $ev = @(Get-WinEvent -FilterHashtable @{ LogName = 'OpenSSH/Operational'; StartTime = $since } -ErrorAction Stop) } "
        "catch { if ($_.FullyQualifiedErrorId -notmatch 'NoMatchingEventsFound') { 'LMCAUDERR|' + $_.Exception.Message } }",
        "foreach ($e in $ev) { $m = [string]$e.Message; if ($m -match 'Accepted ') { "
        "$e.TimeCreated.ToUniversalTime().ToString('s') + 'Z ' + ($m -replace '\\s+', ' ') } }",
    ]) + "\n"


def audit_sh(seconds: int) -> str:
    """macOS: 통합 로그(log show), Linux: journalctl(없거나 권한이 없으면 auth.log·secure)."""
    mins = max(1, int(seconds) // 60)
    return ('if [ "$(uname)" = Darwin ]; then '
            # zsh 에는 같은 이름의 내장 명령 log 가 있고, sshd-session 의 Accepted 줄은 Info 수준이라 --info 가 있어야 보인다.
            f"/usr/bin/log show --style syslog --info --last {mins}m --predicate "
            "'process BEGINSWITH \"sshd\" AND eventMessage CONTAINS \"Accepted\"' 2>/dev/null | grep 'Accepted '; "
            "else { "
            f"journalctl -o short-iso --no-pager --since=-{int(seconds)}s _COMM=sshd _COMM=sshd-session 2>/dev/null"
            " || cat /var/log/auth.log /var/log/secure 2>/dev/null; } | grep 'Accepted '; fi; true")


def audit_remote_command(os_name: str, seconds: int) -> str:
    if os_name == "windows":
        return "powershell -NoProfile -NonInteractive -EncodedCommand " + encode_ps(audit_ps(seconds))
    return audit_sh(seconds)


def parse_audit(text: str, pc: str) -> tuple[list[dict], list[str]]:
    """로그 줄에서 접속 기록과 오류('LMCAUDERR|..'). 시각을 읽지 못한 줄은 time=None, raw_time 에 앞부분."""
    events: list[dict] = []
    errors: list[str] = []
    for line in (text or "").splitlines():
        if line.startswith("LMCAUDERR|"):
            errors.append(line[len("LMCAUDERR|"):].strip())
            continue
        m = AUDIT_RE.search(line)
        if not m:
            continue
        when = None
        t = AUDIT_TIME_RE.search(line[:48])
        if t:
            tz = t.group(3) or ""
            if tz == "Z":
                tz = "+00:00"
            elif tz and ":" not in tz:
                tz = tz[:3] + ":" + tz[3:]
            try:
                when = datetime.fromisoformat(f"{t.group(1)}T{t.group(2)}{tz}")
                if when.tzinfo is None:
                    when = when.astimezone()
            except ValueError:
                when = None
        events.append({"pc": pc, "time": when, "raw_time": line[:19], "method": m.group(1), "user": m.group(2),
                       "from": m.group(3), "key_type": m.group(4) or "", "fp": m.group(5) or ""})
    return events, errors


def key_fingerprint(line: str) -> tuple[str, str]:
    """공개키 한 줄의 (SHA256 지문, 주석). sshd 로그의 'SHA256:...' 과 같은 형식. 키가 아니면 ('', '')."""
    import base64
    import hashlib

    parts = line.strip().split()
    for i, tok in enumerate(parts[:-1]):
        if (tok + " ").startswith(KEY_PREFIXES) or tok.startswith(("sk-", "ecdsa-sha2-")):
            try:
                blob = base64.b64decode(parts[i + 1], validate=True)
            except ValueError:
                return "", ""
            fp = "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")
            return fp, " ".join(parts[i + 2:])
    return "", ""


def key_comments(cfg: dict, fetch: bool = True) -> dict[str, str]:
    """지문 → 키 주석(예: tssh@miniui-Macmini). 게시된 서명 목록 + 이 PC 의 authorized_keys·~/.ssh/*.pub."""
    lines: list[str] = []
    if fetch:
        try:
            lines += fetch_remote_keys(cfg, timeout=8)
        except Exception:  # noqa: BLE001 - 목록을 못 받아도 지문은 보인다
            pass
    paths = [SSH_DIR / "authorized_keys"]
    try:
        paths += sorted(SSH_DIR.glob("*.pub"))
    except OSError:
        pass
    for p in paths:
        lines += read_text_quiet(p).splitlines()
    out: dict[str, str] = {}
    for line in lines:
        fp, comment = key_fingerprint(line)
        if fp:
            out.setdefault(fp, comment or "(주석 없음)")
    return out


AUDIT_USAGE = "사용법: linkmycom audit [이름|이름,이름|all] [--since 7d] [--json]"


def cmd_audit(cfg: dict, args: list[str]) -> int:
    """들어온 SSH 접속(sshd 'Accepted' 로그)을 PC 마다 모아 키 지문을 키 주석으로, 주소를 장비 이름으로 풀어 표로."""
    since, spec, as_json = 7 * 86400, None, False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--since" and i + 1 < len(args):
            since = int(parse_since(args[i + 1]))
            i += 2
            continue
        if a.startswith("--since="):
            since = int(parse_since(a[len("--since="):]))
        elif a == "--json":
            as_json = True
        elif a.startswith("-"):
            die(AUDIT_USAGE)
        else:
            spec = a
        i += 1
    blocks = ssh_config_blocks()
    try:
        peers, _ = cached_peers()
    except SystemExit:
        peers = []
    me = platform.node().split(".")[0]
    targets: list[tuple[str, dict | None]] = []
    if spec is None or spec in ("self", "local", "."):
        targets = [(me, None)]
    elif spec.lower() in ("all", "@all"):
        targets = [(me, None)] + [(p["name"], p) for p in ssh_capable(peers, cfg)]
    else:
        targets = [(p["name"], p) for p in resolve_targets(cfg, blocks, spec)]
    if not as_json:
        print(c(f"linkmycom audit · {', '.join(t[0] for t in targets)} · 최근 {since // 3600}시간", "36"), file=sys.stderr)
    ssh = ssh_bin() if any(p for _, p in targets) else None

    def one(t: tuple[str, dict | None]) -> tuple[list[dict], list[str]]:
        label, peer = t
        if peer is None:
            cmd = (["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encode_ps(audit_ps(since))]
                   if os.name == "nt" else ["sh", "-c", audit_sh(since)])
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                                   stdin=subprocess.DEVNULL)
            except (OSError, subprocess.TimeoutExpired) as e:
                return [], [str(e)]
            return parse_audit(r.stdout, label)
        if skip_without_ssh(peer):
            return [], ["SSH 포트 닫힘(건너뜀)"]
        rc, out, err = run_remote(peer, cfg, blocks, [audit_remote_command(peer["os"], since)], timeout=300, ssh=ssh)
        if rc != 0 and not out.strip():
            return [], [remote_rows_error([], err)]
        return parse_audit(out, label)

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        cf = pool.submit(key_comments, cfg)
        results = parallel_map(one, targets)
        comments = cf.result()
    by_ip = {p["ip"]: p["name"] for p in peers if p.get("ip")}
    try:  # 피어 목록에는 이 PC 가 없으므로 Tailscale 의 Self 주소도 이름으로 푼다.
        for ip in (tailscale_status(soft=True).get("Self") or {}).get("TailscaleIPs") or []:
            by_ip.setdefault(ip, me + " (이 PC)")
    except (Exception, SystemExit):  # noqa: BLE001
        pass
    events: list[dict] = []
    problems: list[str] = []
    now = datetime.now(timezone.utc)
    for (label, _), res in zip(targets, results):
        if isinstance(res, BaseException):
            problems.append(f"{label}: {res}")
            continue
        evs, errs = res
        problems += [f"{label}: {e}" for e in errs]
        events += [e for e in evs if e["time"] is None or (now - e["time"]).total_seconds() <= since]
    for e in events:
        e["key"] = comments.get(e["fp"], e["fp"] or "-")
        e["from_name"] = by_ip.get(e["from"], e["from"])
    events.sort(key=lambda e: e["time"].timestamp() if e["time"] else 0.0)
    if as_json:
        print(json.dumps({"events": [dict(e, time=e["time"].isoformat() if e["time"] else None) for e in events],
                          "errors": problems}, ensure_ascii=False, indent=2))
        return 1 if problems and not events else 0
    for p in problems:
        warn(p)
    if not events:
        print("들어온 SSH 접속 기록이 없습니다(로그를 읽을 권한이 없으면 비어 보일 수 있음).")
        return 1 if problems else 0
    rows = [[e["time"].astimezone().strftime("%m-%d %H:%M") if e["time"] else e["raw_time"], e["pc"], e["user"],
             e["from_name"], e["key"], e["method"]] for e in events[-200:]]
    print_table(rows, ["시각", "PC", "사용자", "어디서", "키", "방식"])
    return 0


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
    allowed = {"user", "port", "key", "alias", "args", "screen", "fav", "forward"}
    bad = set(kv) - allowed
    if bad:
        die(f"알 수 없는 키: {', '.join(sorted(bad))}. 가능한 키: {', '.join(sorted(allowed))}")
    entry = cfg["hosts"].get(name, {})
    for k, v in kv.items():
        if v == "" or (k == "fav" and v.lower() in ("0", "false", "no", "off", "n")):
            entry.pop(k, None)
        elif k == "fav":
            entry[k] = True
        elif k == "forward":
            entry[k] = ",".join(parse_forward_spec(s.strip()) and s.strip() for s in v.split(",") if s.strip())
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
    bools = {"use_magicdns", "auto_update_check", "auto_update_apply"}
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
                "auto_update_apply, repo_dir, keys_url, keys_signer, ssh_options.<옵션>)")
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
    "list": "linkmycom list [--all] [--json]\n  tailscale 에서 바로 읽어 피어 목록을 출력하고, 피어 캐시(~/.tssh/peers.json, 45초 동안 resolve·screen·접속에 씀)와\n"
            "  자동 완성용 호스트 이름 캐시(~/.tssh/hosts.txt)를 갱신한다. 순서는 즐겨찾기(★) → 최근 접속 5대 → 온라인 → 오프라인이며\n"
            "  번호는 선택기와 같다. SSH 가 없는 모바일은 숨기고 --all 이면 'SSH 없음' 으로 보인다.\n"
            "  --json: 모든 피어를 [{name, ip, dns, os, online, cur_addr, relay, fav, last_seen}] 배열로(타워·Stream Deck 용, 형식 고정).\n"
            "  0.7.0: 30일 넘게 꺼진 장비와 hide 로 숨긴 장비는 기본 목록·선택기에서 빼고 개수만 알린다(--all 로 표시).\n"
            "  이름을 직접 쓰는 접속·resolve 는 숨긴 장비에도 된다. 'all' 대상(exec·doctor --all·fleet·audit)은 숨긴 장비를 뺀다.",
    "hide": "linkmycom hide <이름>\n  그 장비를 ~/.tssh/config.json 의 hidden 에 더한다. list·선택기·all 대상에서 빠진다(앱·타워도 같은 키를 읽어 숨긴다).\n"
            "  이름을 직접 쓰면 접속은 그대로 된다. 되돌리기: linkmycom unhide <이름>, 숨긴 것까지 보기: linkmycom list --all.",
    "unhide": "linkmycom unhide <이름>\n  hide 한 장비를 hidden 에서 뺀다(숨긴 목록에서 이름을 찾으므로 꺼져 있어도 된다).",
    "forget": "linkmycom forget <이름> [-n]\n"
              "  Tailscale 에서 없어진(꺼진) 노드의 이 PC 쪽 흔적을 지운다: config.json 의 hosts·hidden 항목, ~/.ssh/known_hosts 의\n"
              "  그 노드(이름·DNS·IP) 줄, ~/.tssh/macs.json 의 MAC 기억, 피어·호스트 이름 캐시. known_hosts 는 바꾸기 전 known_hosts.old\n"
              "  로 남긴다. 지금 켜져 있는 노드는 거부한다. -n 은 지울 것만 보인다.",
    "last": "linkmycom last [ssh 인자...]\n  최근 접속한 호스트에 다시 접속.",
    "set": "linkmycom set <이름> user=.. port=.. key=.. alias=a,b args=\"-A -o 'ProxyJump x'\" screen=<다른 이름> fav=1\n"
           "                 forward=8080:80,9000:localhost:9000\n"
           "  호스트별 접속 설정 저장. 빈 값(user=)은 그 키를 지운다. args 는 셸처럼 따옴표로 묶을 수 있다.\n"
           "  fav=1 즐겨찾기(fav=0 해제), forward= 는 'linkmycom forward <이름>' 이 규칙 없이 부를 때 쓰는 저장 규칙.",
    "unset": "linkmycom unset <이름>\n  저장한 호스트 설정 삭제.",
    "resolve": "linkmycom resolve <이름> [--json]\n  user@주소 를 출력(scp 등에 활용). --json 은 list --json 의 항목에 user·port·ssh 를 더한 객체.",
    "history": "linkmycom history [이름] [--since 7d|12h|30m]\n"
               "  접속 기록(~/.tssh/history.jsonl: connect·screen·send·exec·forward·fleet update/rollback)을 표로. 최근 100줄.\n"
               "  선택기의 '최근 접속 5대' 도 이 기록에서 고른다.",
    "maintain": "linkmycom maintain [--quiet] [-n]\n"
                "  일일 예약 작업(LinkMyCom-KeysRefresh 등, setup 이 등록)이 부르는 유지: 공개키 목록 갱신 + 관리자 권한 없이 되는\n"
                "  복구(꺼진 타워 시작) + 결과를 ~/.tssh/state.json 의 maintain 에 기록. sshd·방화벽처럼 관리자 권한이 필요한\n"
                "  항목은 고치지 않고 적어 두었다가 다음 대화형 실행 때 'linkmycom doctor --fix' 를 안내한다.",
    "hostkey": "linkmycom hostkey reset <이름> [--yes] [-n]\n"
               "  'Host key verification failed' 때: known_hosts 의 그 PC 항목(IP·DNS·이름)을 지우고 ssh-keyscan 으로 받은 키의\n"
               "  지문을 보인 뒤 확인을 받아 다시 등록한다. 비대화형은 --yes 가 있어야 등록, -n 은 명령만 출력.\n"
               "  exec·doctor·fleet 의 BatchMode 접속은 처음 보는 키만 받는다(StrictHostKeyChecking=accept-new).",
    "sessions": "linkmycom sessions list | sessions close [-n]\n"
                "  화면공유 세션 창(--connect·--file-transfer·--terminal 로 뜬 linkmycom 프로세스)만 닫는다. 홈 창·트레이·서비스는 그대로.",
    "export": "linkmycom export\n  ~/.ssh/config 에 관리 블록을 써서 일반 'ssh <이름>' 도 되게 한다.",
    "config": "linkmycom config [키=값 ...]\n  전역 설정: default_user, use_magicdns, update_repo, update_ref, auto_update_check,\n"
              "  auto_update_apply, repo_dir, keys_url, keys_signer, ssh_options.<옵션>. 인자 없이 쓰면 현재 설정을 보인다.",
    "update": "linkmycom update [--check]\n  거울(jekim14/linkmycom-cli) 최신 릴리스의 linkmycom.py 를 받아 서명(linkmycom.py.sig)·SHA256·문법을\n"
              "  확인한 뒤에만 교체한다. --check 는 확인만.\n"
              "  자동 확인(auto_update_check): 대화형 실행이면 1시간에 한 번 확인하고 같은 확인 뒤 바로 교체한다(auto_update_apply,\n"
              "  기본 true. 끄기: linkmycom config auto_update_apply=false). 파이프·--json 같은 비대화형은 하루 한 번 확인만.\n"
              "  자동 적용 실패는 ~/.tssh/state.json 의 update_error 에 남긴다.\n"
              "linkmycom update --all [--check] [-n]\n"
              "  이 PC 의 CLI → 타워 → 화면공유 앱을 거울의 v*·tower-v*·native-v* 최신과 비교해 차례로 적용한다.\n"
              "  CLI 는 위와 같이 교체, 타워는 Update-LinkMyCom.ps1 -Mirror -Auto 실행, 화면공유 앱은 Windows 예약 작업\n"
              "  LinkMyCom-NativeUpdate 시작(0.7.0 이전 설치본이 거부하면 관리자 실행 안내) / Mac Update-Native-Mac.sh --auto.\n"
              "  화면공유 세션 중이면 업데이터가 미룬다. --check 는 비교만, -n 은 할 일만.",
    "status": "linkmycom status [--json]\n"
              "  이 PC 한 화면 요약: CLI·타워·화면공유 앱 판(거울 최신과 비교)과 각 자동 업데이트 상태(CLI 설정·마지막 확인,\n"
              "  update-state.json 의 lastResult·checked, installing 이면 '설치 중'), 켜진 장비 수, 직접 연결 없이 중계로 보이는\n"
              "  장비(CurAddr 없음), 앱의 받은 파일 기록 수(received.json, 24시간 안), 백그라운드 포트 전달.\n"
              "  0.7.0: 디스크 여유(2 GB 미만이면 경고), 멈춘 업데이터(30분 넘게 도는 것), 빠진 예약 작업, 숨긴 장비 수를 더하고\n"
              "  문제가 있으면 다음에 칠 명령을 한 줄로 안내한다(--json 은 disk·updater·tasks_missing·hidden·next 키).",
    "open": "linkmycom open <이름> [공유/경로] [-n]\n"
            "  그 PC 의 SMB 공유 폴더를 연다(Windows 탐색기 \\\\IP\\공유\\경로, macOS open smb://IP/공유/경로, Linux xdg-open).\n"
            "  경로를 빼면 그 PC 의 공유 목록. -n 은 명령만 출력.",
    "cp": "linkmycom cp [-r] [-n] <로컬 원본...> <이름>:<경로>\nlinkmycom cp [-r] [-n] <이름>:<경로>... <로컬 대상>\n"
          "  scp 로 복사한다. 이름은 tailnet 주소로 풀고 set 으로 저장한 사용자·포트·키를 쓴다([사용자@]이름:경로 도 됨).\n"
          "  Windows 대상은 scp -O(옛 프로토콜, Windows OpenSSH 서버 호환). 경로를 비우면 그 PC 의 홈. 한쪽만 원격이어야 한다.",
    "wake": "linkmycom wake <이름> [--via <켜진 PC>] [-n]\n"
            "  doctor(이름·--all)가 모아 ~/.tssh/macs.json 에 기억한 MAC 주소로 Wake-on-LAN 매직 패킷(UDP 9)을 보낸다.\n"
            "  이 PC 가 그 PC 와 같은 LAN 이면 여기서, 아니면 기록상 같은 LAN 의 켜진 PC 에서 SSH 로 보낸다(--via 로 지정).",
    "profiles": "linkmycom profiles windows-terminal|iterm [-n]\n"
                "  PC 마다 'lmc <이름>' 을 여는 터미널 프로필을 만든다. Windows Terminal 은 JSON 조각\n"
                "  %LOCALAPPDATA%\\Microsoft\\Windows Terminal\\Fragments\\LinkMyCom\\linkmycom.json, iTerm2 는\n"
                "  ~/Library/Application Support/iTerm2/DynamicProfiles/linkmycom.json. 관리 표시(linkmycomManaged)가 있는\n"
                "  파일만 다시 쓴다. -n 은 내용만 출력.",
    "audit": "linkmycom audit [이름|이름,이름|all] [--since 7d] [--json]\n"
             "  들어온 SSH 접속(sshd 의 Accepted 로그: Windows OpenSSH/Operational 이벤트, macOS log show, Linux journalctl·auth.log)\n"
             "  을 모아 키 지문을 게시된 키 목록·authorized_keys 의 주석으로, 접속 주소를 장비 이름으로 풀어 '누가·언제·어디서' 표로.\n"
             "  이름을 빼면 이 PC, all 은 이 PC 와 온라인 PC 전부(병렬). 로그를 읽을 권한이 없으면 비어 보일 수 있다.",
    "clip": "linkmycom clip <이름,...> [--text \"...\"] [--file <경로>...]\n"
            "  이 PC 의 클립보드(Windows Get-Clipboard, 파일 목록이면 files / macOS pbpaste / Linux wl-paste·xclip)나\n"
            "  --text·--file 을 그 PC 들의 LinkMyCom 앱 트레이(TCP 21120, 앱 0.6.0 이상)로 보낸다. 대상은 최대 3곳 병렬,\n"
            "  10초 시간 제한. 파일은 Taildrop 으로 먼저 보내고 이름 목록을 보내면 받는 쪽이 클립보드 파일 목록으로 올린다.\n"
            "  텍스트는 1 MiB 까지.",
    "version": "linkmycom version\n  버전 출력.",
    "help": "linkmycom help [명령]\n  전체 도움말, 또는 그 명령의 도움말.",
    "completion": "linkmycom completion powershell|bash|zsh\n  자동 완성 스크립트를 출력한다. 예:\n"
                  "    PowerShell: linkmycom completion powershell | Out-String | Invoke-Expression   ($PROFILE 에 넣으면 계속)\n"
                  "    bash: source <(linkmycom completion bash)      zsh: source <(linkmycom completion zsh)",
    "doctor": "linkmycom doctor [이름] [--json] [--all [--json]] [--fix [-n] [--no-admin]] [--permissions]\n  Tailscale, sshd·22 포트, 방화벽 규칙, authorized_keys 권한·내 키 등록, 게시된 키 목록 서명,\n"
              "  CLI·타워·화면공유 앱 버전, PATH 의 lmc, 타워 실행, 화면공유 서비스·21118, 마지막 키 갱신·갱신 예약,\n"
              "  클립보드 수신 21120(트레이), 자동 업데이트(예약 작업 LinkMyCom-NativeUpdate·TowerUpdate / launchd\n"
              "  com.linkmycom.native-update 와 update-state.json 의 마지막 결과)를 OK/FAIL 표로.\n"
              "  이름을 주면 그 PC 에 같은 점검을 ssh 로 보낸다. --all 은 이 PC 와 온라인 PC 전부를 병렬(5대씩)로 점검해\n"
              "  한 표(행 = PC)로 보이고, --json 은 그 결과를 JSON 으로 출력한다(이름을 줄 때·이 PC 도 --json 은\n"
              "  {name, ip, os, rows:[[점검, 상태, 내용]], error}). FAIL 이나 접속 실패가 있으면 종료 코드 1.\n"
              "  원격 Windows 에 파이썬이 없으면 PowerShell 만으로 sshd·방화벽·버전·21118 을 점검한다.\n"
              "  이름을 주면 이 PC 에서 그 PC 의 21118 TCP 도달성과, 같은 장비의 다른 Tailscale 노드(이름·OS 가 닮고 21118 이\n"
              "  한쪽만 열림, ssh-keyscan 호스트 키가 같음)를 함께 보고 'set <이름> screen=<다른 노드>' 를 안내한다.\n"
              "  LAN·MAC 줄은 wake 를 위해 ~/.tssh/macs.json 에 기억한다.\n"
              "  --fix: 이 PC 의 결과 줄마다 고침 하나(키 갱신 예약 → 다시 예약, 키 갱신 → keys refresh, sshd·방화벽 → setup 의\n"
              "  서버 설정(UAC 한 번), 타워 실행 → Start-ControlTower -NoBrowser, PATH 의 lmc 중복 → 묻고 지움, Windows 예약 작업\n"
              "  LinkMyCom-Tower·LinkMyCom-TowerUpdate 가 없으면 설치기와 같은 정의로 등록). -n 은 할 일만, --no-admin 은 관리자 권한·질문이\n"
              "  필요한 고침(서버 설정·중복 lmc 정리)을 뺀다(fleet fix 가 원격에서 쓴다). LinkMyCom-NativeUpdate(SYSTEM)는 일반 권한으로\n"
              "  못 만들어 설치기 안내만 한다.\n"
              "  0.7.0 점검 줄: 예약 작업 3종(Tower·TowerUpdate·NativeUpdate)과 키 갱신 작업을 따로, 디스크 여유(2 GB 미만 WARN),\n"
              "  업데이터 프로세스(Update-LinkMyCom.ps1·Update-Native.ps1·Update-Native-Mac.sh 가 30분 넘게 돌면 stuck WARN),\n"
              "  macOS 는 Tailscale.app 과 Homebrew tailscaled 를 설치별로(둘 다 로그인돼 있으면 WARN)와 권한 안내 한 줄.\n"
              "  --permissions: macOS 에서 LinkMyCom 을 잠깐 열고(약 20초) sudo 로 tccd 로그(AUTHREQ)를 읽어 화면 기록·손쉬운 사용·\n"
              "  입력 모니터링을 OK/WARN 으로 판정한다. 이름을 주면 그 Mac 에서(원격 sudo -n 이 될 때). sudo 가 비밀번호를 물으면\n"
              "  아무것도 실행하지 않고 안내만 한다. 이 명령이 띄운 log stream 과 앱 창만 닫고 화면공유 서비스는 건드리지 않는다.\n"
              "  disk·updater 줄은 --json 의 rows 에 들어 있고 disk·updater 키로도 보인다.",
    "exec": "linkmycom exec <이름|이름,이름|all> [--timeout 초] [--os windows|macos|linux] [--ps] -- <명령...>\n"
            "  BatchMode SSH 로 여러 PC 에 같은 명령을 병렬 실행하고 줄마다 '[이름] ' 을 붙여 출력한다. '--' 뒤는 그대로 넘긴다.\n"
            "  all 은 온라인 PC 중 모바일이 아니고 SSH 포트가 열린 것. 하나라도 실패하면 종료 코드 1(건너뛴 PC 는 실패 아님).\n"
            "  --os 는 그 OS 의 PC 만, --ps 는 Windows 대상의 명령을 PowerShell -EncodedCommand 로 감싼다.",
    "fleet": "linkmycom fleet status [--json]\n  이 PC 와 온라인 PC 의 CLI·타워·화면공유 앱 버전·자동 업데이트(예약 작업·마지막 결과)를 한 표로.\n"
             "  판마다 거울의 v*·tower-v*·native-v* 최신과 비교해 '최신' 또는 '현재 → 최신' 으로 보인다(--json 은 행마다 latest·outdated).\n"
             "  0.7.0: 디스크 여유 2 GB 미만이나 30분 넘게 도는 업데이터가 있으면 상태 칸에 경고하고, --json 의 rows 에 disk·updater\n"
             "  줄이(같은 값이 disk·updater 키로도) 들어간다. hide 한 장비는 뺀다.\n"
             "linkmycom fleet update [cli] [-n]\n  이 PC 의 CLI 보다 낡은 원격 설치본만 교체한다(-n: 할 일만 출력). 바꾸기 전 판은 옆에 .prev 로 남긴다.\n"
             "linkmycom fleet update native|tower [이름|a,b|all] [--apply [--wait [초]]]\n"
             "  거울 최신보다 낡은 원격 PC 에서 업데이터를 SSH 로 시작한다(Windows 예약 작업 LinkMyCom-NativeUpdate·TowerUpdate,\n"
             "  Mac Update-Native-Mac.sh --auto). --apply 가 없으면 할 일만 보인다. 화면공유 세션 중이면 업데이터가 미룬다.\n"
             "  타워 업데이트 작업(LinkMyCom-TowerUpdate)이 없는 PC 는 세션 안에서 돌리지 않고 그 PC 에 로그온한 사용자의 대화형\n"
             "  세션에서 도는 일회용 작업(LinkMyCom-TowerUpdate-Once)으로 시작해 시작 뒤 지운다(로그온한 사용자가 없으면 그 사실을 알림).\n"
             "  --wait [초]: 시작한 뒤 각 PC 의 update-state.json 을 읽어 PC 별 결과(완료·새 판 없음·미룸·실패)를 기다린다(기본 120초).\n"
             "linkmycom fleet fix [이름|a,b|all] [-n]\n"
             "  원격 PC 에서 'doctor --fix --no-admin'(관리자 권한 없는 복구: 키 갱신 예약·키 갱신·꺼진 타워 시작·타워 예약 작업 등록)을\n"
             "  돌리고 PC 별 결과 표를 보인다. CLI 0.7.0 미만 PC 는 건너뛴다. -n 은 각 PC 의 할 일만.\n"
             "linkmycom fleet rollback <이름|이름,이름|all> cli [-n]\n  fleet update 가 남긴 .prev 로 그 PC 들의 CLI 설치본을 되돌린다.",
    "send": "linkmycom send <파일...> --to <이름,이름,...>\n"
            "  Taildrop(tailscale file cp)으로 보낸다. 대상마다 한 번에 모든 파일, 대상은 최대 3곳 병렬. 실패는 대상별로 표시.",
    "inbox": "linkmycom inbox [폴더] [--wait]\n  Taildrop 으로 받은 파일을 폴더(기본 ~/Downloads)로 옮긴다(같은 이름은 번호를 붙임).\n"
             "  --wait: 받은 파일이 없으면 올 때까지 기다림. macOS 는 앱이 Downloads 에 바로 두므로 안내만 한다.",
    "forward": "linkmycom forward <이름> [<로컬포트:원격포트>|<로컬포트:원격호스트:원격포트> ...] [--bg] [-n]\n"
               "  ssh -N -L 로 이 PC 의 127.0.0.1:로컬포트 를 그 PC 의 포트로 잇는다(Ctrl+C 로 끝). -n 은 명령만 출력.\n"
               "  규칙을 빼면 'set <이름> forward=8080:80,...' 로 저장한 규칙을 쓴다. --bg 는 창 없이 띄우고 pid·규칙을\n"
               "  ~/.tssh/forwards.json 에 남긴다. linkmycom forward list 로 보기, forward stop [번호|all] 로 끝내기.",
    "setup": "linkmycom setup [--no-server] [--no-keys] [--no-schedule]\n  SSH 서버 켜기(Tailscale 대역·인터페이스만 허용) + 공개키 교환 + 하루 한 번 'maintain'(키 갱신 포함) 예약\n"
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
    "update": ["--check", "--all", "-n"],
    "fleet": ["status", "update", "fix", "rollback", "cli", "tower", "native", "--json", "--apply", "--wait", "-n"],
    "profiles": ["windows-terminal", "iterm", "-n"],
    "status": ["--json"],
    "inbox": ["--wait"],
    "list": ["--all", "--json"],
    "maintain": ["--quiet", "-n"],
    "sessions": ["list", "close", "-n"],
}
HOST_COMMANDS = ["set", "unset", "resolve", "screen", "display", "doctor", "exec", "forward", "send", "clip",
                 "history", "hostkey", "open", "cp", "wake", "audit", "hide", "unhide", "forget"]
# 호스트 이름과 함께 옵션도 완성하는 명령.
COMPLETION_HOST_FLAGS = {
    "screen": ["--gather", "--files", "--terminal", "--forward"],
    "doctor": ["--all", "--json", "--fix", "-n", "--no-admin", "--permissions"],
    "forget": ["-n"],
    "exec": ["all", "--timeout", "--os", "--ps", "--"],
    "forward": ["-n", "--bg", "list", "stop"],
    "history": ["--since"],
    "hostkey": ["reset", "--yes", "-n"],
    "send": ["--to"],
    "clip": ["--text", "--file"],
    "open": ["-n"],
    "cp": ["-r", "-n"],
    "wake": ["--via", "-n"],
    "audit": ["all", "--since", "--json"],
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
        if "--all" in argv[1:]:
            return cmd_update_all(cfg, check_only="--check" in argv[1:], dry="-n" in argv[1:] or "--dry-run" in argv[1:])
        return cmd_update(cfg, check_only="--check" in argv[1:])
    if sub == "status":
        return cmd_status(cfg, argv[1:])
    if sub == "open":
        return cmd_open(cfg, argv[1:])
    if sub == "cp":
        return cmd_cp(cfg, argv[1:])
    if sub == "wake":
        return cmd_wake(cfg, argv[1:])
    if sub == "profiles":
        return cmd_profiles(cfg, argv[1:])
    if sub == "audit":
        return cmd_audit(cfg, argv[1:])
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
    if sub == "clip":
        return cmd_clip(cfg, argv[1:])
    if sub == "maintain":
        return cmd_maintain(cfg, argv[1:])
    if sub == "history":
        return cmd_history(argv[1:])
    if sub == "hostkey":
        return cmd_hostkey(cfg, argv[1:])
    if sub == "sessions":
        return cmd_sessions(argv[1:])
    if sub == "forward":
        return cmd_forward(cfg, argv[1:])
    if sub == "hide":
        return cmd_hide(cfg, argv[1:])
    if sub == "unhide":
        return cmd_unhide(cfg, argv[1:])
    if sub == "forget":
        return cmd_forget(cfg, argv[1:])

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
        show_list(peers, cfg, blocks, show_all="--all" in argv[1:], as_json="--json" in argv[1:])
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
        if not host_arg:
            die("사용법: linkmycom resolve <이름> [--json]")
        peer = pick_one_or_die(peers, cfg, blocks, host_arg)
        st = host_settings(peer, cfg, blocks)
        target = peer["dns"] if cfg.get("use_magicdns") and peer["dns"] else peer["ip"]
        user = st.get("user") or getpass.getuser()
        if "--json" in argv[1:]:
            print(json.dumps(dict(peers_json([peer], cfg)[0], user=user, port=str(st.get("port") or ""),
                                  ssh=f"{user}@{target}"), ensure_ascii=False, indent=2))
        else:
            print(f"{user}@{target}")
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
    notice: list[str] = maintain_notices()
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
