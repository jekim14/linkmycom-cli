# linkmycom · LinkMyCom의 SSH 접속기

Tailscale 네트워크(tailnet)의 내 기기 목록을 보여 주고 번호나 이름 일부로 바로 SSH로 접속하는 명령줄 도구입니다. 화면공유 창 열기(`linkmycom screen`), 여러 모니터 정리(`linkmycom display`), 화면공유 비밀번호 일괄 설정(`linkmycom password`)도 여기서 합니다. 줄임 명령 `lmc`가 함께 설치되며, 옛 이름 `tssh`도 계속 쓸 수 있고 같은 명령으로 넘어갑니다. LinkMyCom 컨트롤 타워의 `SSH 터미널` 버튼이 이 도구를 호출합니다. Python 3.9 이상, Tailscale, OpenSSH `ssh`·`ssh-keygen`(서명 확인에 8.1 이상)만 있으면 되고 추가 패키지는 없습니다.

개발은 비공개 저장소의 `tools/linkmycom`에서 하고, 배포는 공개 거울 [jekim14/linkmycom-cli](https://github.com/jekim14/linkmycom-cli)(옛 `jekim14/tssh`)의 같은 경로로 합니다. 설치 스크립트·`linkmycom update`·공개키 목록은 인증 없이 받을 수 있어야 하므로 거울을 봅니다. 변경 후 `tools\linkmycom\Publish-Cli.ps1 -MirrorDir <거울 클론>`으로 내보내고, `-Release`를 붙이면 태그와 GitHub 릴리스까지 만듭니다. 공개키 목록 `authorized_keys`의 원본은 거울이며 내보낼 때 되가져옵니다. 옛 tssh 설치본을 위해 거울의 `tools/tssh/tssh.py`와 `tools/tssh/authorized_keys`에도 같은 파일을 둡니다.

## 설치

LinkMyCom Windows ZIP에는 `linkmycom.py`, `linkmycom.ps1`, `linkmycom.cmd`, `lmc.cmd`가 들어 있어 ZIP 폴더에서 `.\linkmycom.ps1`로 바로 쓸 수 있습니다. 명령줄에서 어디서나 `linkmycom`(또는 `lmc`)으로 쓰려면 아래 한 줄로 설치합니다.

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/jekim14/linkmycom-cli/HEAD/tools/linkmycom/install.ps1 | iex
```

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/jekim14/linkmycom-cli/HEAD/tools/linkmycom/install.sh | sh
```

설치 끝에 `linkmycom setup`이 실행되어 그 컴퓨터를 SSH 서버로 켜고(Windows는 UAC 승인, Tailscale 대역만 허용) 키를 교환합니다. 건너뛰려면 Windows `-NoSetup`, macOS/Linux `LINKMYCOM_NO_SETUP=1`.

## 옛 tssh 에서 옮기기

따로 할 일은 없습니다. 이미 설치된 tssh 에서 `tssh update`를 실행하면 새 코드를 받고, 처음 실행할 때 같은 폴더에 `linkmycom`과 `lmc`를 만들며 옛 `tssh`는 새 명령으로 넘기는 파일이 됩니다. 설정 `~/.tssh/config.json`, 상태 `~/.tssh/state.json`, `~/.ssh/config`의 관리 블록, `~/.ssh/authorized_keys`의 키 블록, SSH 방화벽 규칙은 이름을 바꾸지 않고 그대로 씁니다. Windows 한 줄 설치를 다시 하면 새 설치 폴더는 `%LOCALAPPDATA%\linkmycom`이고 옛 `%LOCALAPPDATA%\tssh`에는 넘김용 `tssh.cmd`만 남습니다.

## 사용법

| 명령 | 설명 |
|---|---|
| `linkmycom` | 목록에서 번호 또는 이름(일부)으로 골라 접속. Enter만 누르면 최근 호스트. |
| `linkmycom pfl`, `linkmycom root@pfl`, `linkmycom -u bob -p 2222 pfl` | 바로 접속. 호스트 뒤 인자는 `ssh`에 그대로 전달 (`lmc pfl -L 8080:localhost:80`, `lmc pfl uptime`). |
| `linkmycom -n pfl` | 실행할 ssh 명령만 출력. 파이프·스크립트처럼 비대화형에서 이름이 여러 PC 에 맞으면 고르지 않고 후보를 적은 뒤 종료 코드 1. |
| `linkmycom list`, `linkmycom last`, `linkmycom resolve pfl` | 목록, 최근 호스트 재접속, `user@주소` 출력(scp 등에 활용). |
| `linkmycom set pfl user=ubuntu port=2222 key=~/.ssh/id alias=srv` / `linkmycom unset pfl` | 호스트별 설정 저장·삭제. `args="-A -o 'ProxyJump a b'"`처럼 따옴표로 묶은 값은 한 인자로 둡니다(Windows 경로의 역슬래시는 그대로). |
| `linkmycom screen jekim-1 [--gather] [--files\|--terminal\|--forward [로컬:원격]]` | 그 PC 의 화면공유 창(또는 파일 전송·터미널·포트 전달 창)을 연다. `--gather`는 창 모으기를 기다리지 않고 뷰어를 먼저 띄운다. 앱의 포트 전달 창은 규칙을 명령줄로 받지 않아 `로컬:원격`은 안내만 한다. `set <이름> screen=<다른 이름>`으로 화면용 대상을 따로 지정. |
| `linkmycom forward pfl 8080:80` | `ssh -N -L 8080:127.0.0.1:80`로 이 PC 의 포트를 그 PC 의 포트로 잇는다(`로컬:원격호스트:원격`도 됨, `-n`은 명령만 출력). |
| `linkmycom send a.pdf b.zip --to jekim-1,officehermes` | Taildrop 으로 보낸다. 대상마다 `tailscale file cp <파일들> <주소>:` 한 번, 대상은 최대 3곳 병렬, 실패는 대상별로 표시. |
| `linkmycom inbox [폴더] [--wait]` | Taildrop 으로 받은 파일을 폴더(기본 `~/Downloads`)로 옮긴다(같은 이름은 번호를 붙임). macOS 는 앱이 Downloads 에 바로 두므로 안내만. |
| `linkmycom exec <이름\|a,b\|all> -- <명령...>` | BatchMode SSH 로 여러 PC 에 병렬 실행, 줄마다 `[이름] ` 접두어. `all`은 온라인이고 모바일이 아니며 SSH 포트가 열린 PC. 하나라도 실패하면 종료 코드 1. |
| `linkmycom fleet status` / `fleet update [cli] [-n]` | 이 PC 와 온라인 PC 의 CLI·타워·화면공유 앱 버전 표 / 이 PC 의 CLI 보다 낡은 원격 설치본에서만 `update` 실행(`-n`: 할 일만 출력). 타워·화면공유 앱은 아직 안내만. |
| `linkmycom display jekim-1 [list\|gather\|single\|extend]` | 여러 모니터 PC 정리. |
| `linkmycom password` | 화면공유 영구 비밀번호를 내 모든 PC 에 한 번에 설정(직접 입력). |
| `linkmycom export` | `~/.ssh/config`에 관리 블록을 써서 일반 `ssh pfl`도 되게 함. |
| `linkmycom config default_user=idonl use_magicdns=true` | 전역 설정. |
| `linkmycom setup [--no-server] [--no-keys] [--no-schedule]` | SSH 서버 켜기 + 키 교환 + 하루 한 번 `keys refresh` 예약(Windows 예약 작업 `LinkMyCom-KeysRefresh`, macOS launchd `com.linkmycom.keys-refresh`, Linux systemd 사용자 타이머 `linkmycom-keys.timer`). |
| `linkmycom keys show / refresh [--force]` | 내 공개키 / 서명된 목록을 받아 `authorized_keys` 관리 블록 갱신. 빈 목록은 거부하고, 관리 블록의 키가 절반 이하로 줄면 `--force`가 있어야 적용. |
| `linkmycom keys publish --collect` | (관리 PC) 각 컴퓨터의 공개키를 모아 `~/.ssh/linkmycom-signing`으로 서명하고 거울 클론의 `tools/linkmycom/authorized_keys`·`authorized_keys.sig`를 커밋·푸시. `linkmycom config repo_dir=<거울 클론 경로>`가 필요하며 origin 이 `jekim14/linkmycom-cli`가 아니면 멈춤. |
| `linkmycom update [--check]` | 거울의 최신 GitHub 릴리스 자산 `linkmycom.py`를 받아 서명·SHA256·문법을 확인한 뒤에만 교체. 하루 한 번 자동 확인. |
| `linkmycom doctor [이름] [--all [--json]]` | Tailscale, sshd·22 포트, 방화벽 규칙(`tssh-OpenSSH`), `authorized_keys` 권한·내 키 등록, 게시된 키 목록 서명, CLI·타워·화면공유 앱 버전, PATH 의 `lmc`(설치본이 둘이면 경고), 타워 실행, 화면공유 서비스·21118, 마지막 키 갱신과 갱신 예약 작업 실재를 OK/FAIL 표로. 이름을 주면 같은 점검을 그 PC 에 ssh 로 보내 실행. `--all`은 이 PC 와 온라인 PC 전부를 5대씩 병렬로 점검해 한 표(행 = PC)로, `--json`은 JSON 으로. FAIL 이나 접속 실패가 있으면 종료 코드 1. |
| `linkmycom help [명령]` | 전체 또는 그 명령의 도움말. |
| `linkmycom completion powershell\|bash\|zsh` | 자동 완성 스크립트 출력. 호스트 이름은 `list` 등 피어를 읽을 때 갱신되는 `~/.tssh/hosts.txt`에서 가져옴(피어 캐시 `~/.tssh/peers.json`과 함께 갱신). PowerShell: `linkmycom completion powershell \| Out-String \| Invoke-Expression`(`$PROFILE`에 넣으면 계속), bash/zsh: `source <(linkmycom completion bash)`. |

모든 명령은 `lmc`로도 됩니다. 타워 설치본의 `bin\lmc.cmd`·`bin\linkmycom.cmd`는 `~/.tssh/state.json`에 기록한 파이썬을 바로 부르고, 그 파이썬이 사라졌으면 예전처럼 `tower\linkmycom.cmd`가 PATH 에서 찾습니다. `resolve`·`screen`·`display`·이름 접속은 45초 안의 피어 캐시(`~/.tssh/peers.json`)를 먼저 쓰고 이름이 캐시에 없으면 다시 읽습니다. Tailscale 을 읽지 못하면 오래된 캐시라도 경고와 함께 씁니다. `list`·선택기·`export`·`set`은 항상 바로 읽습니다. 사용자 이름은 저장값 → 기존 `~/.ssh/config`의 같은 주소 항목 → `default_user` → 현재 로그인 이름 순으로 정합니다. Tailscale CLI는 PATH, 앱 내장 CLI, Homebrew 순으로 시도해 `Running`인 것을 쓰고, macOS에서 Homebrew tailscaled와 Tailscale.app이 함께 있으면 `/var/run/tailscaled.socket`의 LocalAPI를 직접 읽습니다.

## 키 교환 모델

각 기기는 `linkmycom setup` 때 `~/.ssh/id_ed25519`를 만들고, 거울 저장소의 `authorized_keys` 목록을 받아 `~/.ssh/authorized_keys`의 관리 블록에 넣습니다. 쓸 때는 임시 파일에 쓴 뒤 교체하고(Windows 는 `ReplaceFileW`로 기존 ACL 유지), 받은 목록이 비었거나 관리 블록의 키가 절반 이하로 줄면 바꾸지 않고 경고합니다(오류 페이지를 받아 키가 전부 지워지는 사고 차단).

### 키 목록 서명

GitHub 계정만으로는 신뢰가 부족하므로 0.4.4 부터 목록에 서명합니다. 관리 PC(jekimlabtop)의 전용 서명키 `~/.ssh/linkmycom-signing`(ed25519)으로 `ssh-keygen -Y sign -n linkmycom-keys` 한 `tools/linkmycom/authorized_keys.sig`를 목록 옆에 게시하고, `keys refresh`·`setup`·`tools/installer/Add-SshUser.ps1`은 CLI·스크립트 안에 박은 공개키 하나로 확인한 뒤에만 적용합니다.

- allowed_signers 한 줄: `linkmycom ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGWKhtP9dXCC5mljTV/5DOf42NzaQ7EUHRAo9B+bX0+s`
- 확인 명령: `ssh-keygen -Y verify -f <allowed_signers> -I linkmycom -n linkmycom-keys -s authorized_keys.sig < authorized_keys`
- 목록과 서명은 같은 주소(API 또는 raw)에서 받고, 받은 바이트 그대로 확인합니다. `keys publish`는 LF 로 쓰고 `core.autocrlf=false`로 커밋한 뒤, 커밋된 바이트로 다시 확인하고서야 푸시합니다. 거울로 옮기는 쪽(Publish-Cli)도 두 파일을 바이트 그대로 옮겨야 합니다.
- 순서: 서명된 목록을 CLI 0.4.4 릴리스보다 먼저 거울에 올립니다. 0.4.4 는 `.sig`가 없거나 맞지 않으면 목록을 적용하지 않습니다.
- 저장소 주인이 아닌 사람은 `linkmycom config keys_url=<자기 목록 주소>`로 바꾸고, 그 주소 뒤에 `.sig`를 붙인 서명 파일을 함께 두며, `linkmycom config keys_signer="ssh-ed25519 AAAA..."`로 자기 서명 공개키를 지정합니다.

## 업데이트(`linkmycom update`)

0.4.4 부터는 거울 `jekim14/linkmycom-cli`의 최신 릴리스(`GET /repos/jekim14/linkmycom-cli/releases/latest`, 인증 없음) 자산을 받습니다.

| 자산 | 내용 |
|---|---|
| `linkmycom.py` | CLI 본체. |
| `linkmycom.py.sig` | `ssh-keygen -Y sign -f ~/.ssh/linkmycom-signing -n linkmycom-keys linkmycom.py` 결과. 없거나 맞지 않으면 교체하지 않습니다. |
| `linkmycom.py.sha256` | `<16진 SHA256>  linkmycom.py` 한 줄. 있으면 대조합니다. |

확인 순서는 서명 → SHA256 → `compile()` 문법 → 버전이며, 하나라도 어긋나면 설치된 파일을 그대로 둡니다. 받은 바이트를 그대로 써서 교체합니다. 같은 거울의 sha256 은 무결성만 보장하므로 진본성은 서명이 맡습니다.

이미 설치된 0.4.3 이하는 거울 기본 브랜치의 raw 파일 `tools/linkmycom/linkmycom.py`를 서명 확인 없이 받습니다. 그래서 0.4.3 → 0.4.4 첫 이동은 검증 없이 이뤄지고, 0.4.4 이후의 업데이트부터 서명을 확인합니다. 거울은 당분간 raw 파일과 릴리스 자산을 둘 다 갱신합니다.

## 개발

```bash
python -m unittest discover -s tools/linkmycom/tests -v
```

서명·`keys publish` 테스트는 실제 `ssh-keygen`·`git`으로 임시 키와 임시 저장소를 만들어 확인하고, 없으면 건너뜁니다. Windows 에서 `doctor` 점검 스크립트 실행 테스트는 PowerShell(방화벽 조회)을 띄워 몇 초 걸려 `LINKMYCOM_SLOW_TESTS=1`일 때만 돕니다. 0.4.5 부터 점검 스크립트는 PowerShell 을 한 번만 띄워 다른 점검과 겹쳐 돌리고, `doctor`는 키 목록 받기와 점검을 함께 돌립니다.

`setup`의 SSH 방화벽 규칙 `tssh-OpenSSH`는 Tailscale 대역(100.64.0.0/10, fd7a:115c:a1e0::/48)에 더해, 실행 시점에 `Get-NetAdapter`로 찾은 Tailscale 인터페이스에도 묶습니다(100.64/10 은 통신사 CGNAT 과 겹침). 새 규칙(`tssh-OpenSSH-next`)을 먼저 만든 뒤 옛 규칙을 지우고 이름을 `tssh-OpenSSH`로 바꾸며, Tailscale 인터페이스를 못 찾으면 기존 규칙을 바꾸지 않습니다.

Windows 패키지 포함은 `ime-probe/package.ps1`, 업데이터의 관리 파일 목록은 `Update-LinkMyCom.ps1`에 있습니다. 옛 이름 파일 `tssh.py`·`tssh.cmd`·`tssh.ps1`은 패키지 안에서 새 이름으로 넘기는 얇은 파일입니다. 참고한 구현: [tailscale-cli-helpers](https://github.com/DigitalCyberSoft/tailscale-cli-helpers), [lazytailscale](https://github.com/mogglemoss/lazytailscale), [sshs](https://github.com/quantumsheep/sshs) (모두 MIT, 설계만 참고).
