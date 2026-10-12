# tssh - Tailscale SSH 접속기

Tailscale 네트워크(tailnet)에 있는 내 기기 목록을 보여 주고, 번호나 이름 일부만 입력해 바로 SSH로 접속하는 명령줄 도구입니다. Python 3.10 이상과 Tailscale, OpenSSH `ssh` 만 있으면 되고 추가 패키지는 없습니다. Windows, macOS, Linux에서 같은 파일 하나로 동작합니다.

```
Tailscale SSH 접속기 v0.1.0   온라인 6/11
#      이름             OS       Tailscale IP     접속
1   ●  *jekimlabtop     windows  100.100.191.24   idonl@
2   ●   miniui-macmini  macOS    100.82.231.21    jemac@
3   ●   pfl             linux    100.97.45.34     idonl@
7   ○   macmini         macOS    100.103.180.115  idonl@  (마지막 19일 전)
접속할 번호 또는 이름  (Enter = * jekimlabtop)  [r 새로고침, q 종료]:
```

## 설치

설치할 기기에서 명령 한 줄을 실행하면 최신 릴리스를 받아 설치합니다. Python 3.10 이상이 먼저 설치되어 있어야 합니다.

Windows (PowerShell):

```powershell
irm https://github.com/jekim14/tssh/releases/latest/download/install.ps1 | iex
```

`%LOCALAPPDATA%\tssh` 에 설치하고 사용자 PATH에 등록합니다. 새 터미널을 열면 `tssh` 명령을 쓸 수 있습니다. 저장소를 받아 둔 상태라면 `powershell -ExecutionPolicy Bypass -File install.ps1` 로도 설치되며, PATH를 건드리지 않으려면 `-NoPath` 를 붙입니다.

macOS / Linux:

```bash
curl -fsSL https://github.com/jekim14/tssh/releases/latest/download/install.sh | sh
```

`~/.local/bin/tssh` 로 설치됩니다. 다른 위치를 쓰려면 `TSSH_BIN_DIR=/usr/local/bin` 을 앞에 붙이고, 저장소를 받아 둔 상태라면 `sh install.sh` 로도 설치됩니다.

SSH 서버가 켜져 있는 기기라면 다른 기기에서 `tssh <이름> "curl -fsSL .../install.sh | sh"` 처럼 원격으로 설치할 수도 있습니다. SSH 서버가 없는 Windows PC에는 그 PC에서 직접 위 명령을 실행하세요.

## 사용법

| 명령 | 설명 |
|---|---|
| `tssh` | 피어 목록을 보여 주고 번호 또는 이름(일부)으로 골라 접속. Enter만 누르면 최근 접속 호스트로 접속. |
| `tssh pfl` | 이름으로 바로 접속. `pf` 처럼 일부만 써도 되고, 여러 개면 목록에서 고릅니다. |
| `tssh root@pfl` | 사용자 이름을 지정해 접속. |
| `tssh pfl -L 8080:localhost:80` | 호스트 이름 뒤의 인자는 그대로 `ssh` 에 전달됩니다. `tssh pfl uptime` 처럼 원격 명령도 됩니다. |
| `tssh -u bob -p 2222 pfl` | 이번 한 번만 사용자·포트를 바꿔 접속. |
| `tssh --dns pfl` | Tailscale IP 대신 MagicDNS 이름으로 접속. |
| `tssh -n pfl` | 실행할 ssh 명령만 보여 줌 (dry-run). |
| `tssh last` | 최근 접속한 호스트로 다시 접속. |
| `tssh list` | 목록만 출력. |
| `tssh set pfl user=ubuntu port=2222 key=~/.ssh/id_ed25519 alias=srv` | 호스트별 접속 설정 저장. `args="-A -X"` 로 ssh 옵션도 저장할 수 있습니다. 값을 비우면(`port=`) 지웁니다. |
| `tssh unset pfl` | 저장한 호스트 설정 삭제. |
| `tssh resolve pfl` | `user@주소` 를 출력. 예: `scp file $(tssh resolve pfl):/tmp/` |
| `tssh export` | `~/.ssh/config` 에 tssh 관리 블록을 써서 일반 `ssh pfl` 로도 접속되게 함. 기존 내용은 보존하고 `config.bak-tssh` 로 백업합니다. |
| `tssh config` | 전역 설정 보기. `tssh config default_user=ubuntu use_magicdns=true` 처럼 변경. |
| `tssh update` | 새 릴리스가 있으면 자신을 교체. `--check` 는 확인만. |

### 사용자 이름이 정해지는 순서

1. `tssh set <이름> user=...` 로 저장한 값
2. 기존 `~/.ssh/config` 에서 같은 Tailscale IP 또는 MagicDNS 이름을 가리키는 `Host` 항목의 `User`, `Port`, `IdentityFile` (그 항목의 별칭으로도 접속할 수 있습니다)
3. `tssh config default_user=...`
4. 현재 로그인 사용자 이름

대화형 목록에서 처음 접속하는 호스트를 고르면 사용자 이름을 한 번 묻고 저장합니다.

### Tailscale CLI를 고르는 방식

`tailscale status --json`을 PATH의 `tailscale`, Windows·macOS 앱에 든 CLI, Homebrew 경로 순으로 시도해 실제로 `Running` 상태인 것을 씁니다. macOS에서 Homebrew `tailscaled`와 Tailscale.app이 함께 떠 있으면 CLI가 로그아웃된 쪽에 붙는 경우가 있는데, 이때는 `/var/run/tailscaled.socket`의 LocalAPI를 직접 읽어 연결된 데몬의 상태를 가져옵니다. 특정 CLI를 강제하려면 환경 변수 `TSSH_TAILSCALE=/경로/tailscale`을 설정하세요.

### 파일 위치

- 설정: `~/.tssh/config.json`
- 상태(최근 접속, 업데이트 확인 시각): `~/.tssh/state.json`

## 업데이트

설치된 tssh는 하루에 한 번 GitHub 릴리스를 조용히 확인하고, 새 버전이 있으면 목록 위에 한 줄 알립니다. `tssh update` 를 실행하면 최신 릴리스의 `tssh.py` 로 자신을 교체합니다. 확인을 끄려면 `tssh config auto_update_check=false`, 다른 저장소를 쓰려면 `tssh config update_repo=<owner/repo>` 로 바꿉니다.

릴리스 게시(관리자용): `release.ps1 -Version 0.2.0 -Notes "..."` 가 테스트를 돌리고 버전을 올린 뒤 태그와 GitHub 릴리스를 만듭니다. 저장소가 아직 없으면 `-CreateRepo` 를 붙입니다.

## 개발

```bash
python -m unittest discover -s tests -v
```

## 참고한 구현

- [tailscale-cli-helpers](https://github.com/DigitalCyberSoft/tailscale-cli-helpers) (MIT): 이름 조각 해석 순서(정확 → 부분 → 유사)와 온라인 우선 선택기, IP 기본·MagicDNS 선택 방식을 설계 참고했습니다. bash·jq 전용이라 코드는 가져오지 않았습니다.
- [lazytailscale](https://github.com/mogglemoss/lazytailscale) (MIT): 피어 상태 표시 방식을 참고했습니다.
- [sshs](https://github.com/quantumsheep/sshs) (MIT): `~/.ssh/config` 연동 아이디어를 참고했습니다.

## 라이선스

MIT
