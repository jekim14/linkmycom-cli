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

0.5.0 부터 한 줄 설치는 raw 파일 대신 거울의 최신 릴리스 자산 `linkmycom.py`·`linkmycom.py.sig`·`linkmycom.py.sha256`을 받아, CLI 의 `update`와 같은 공개키로 `ssh-keygen -Y verify`(데이터는 파일 리디렉션)가 통과한 뒤에만 설치합니다. `ssh-keygen`이나 `.sig`가 없으면 SHA256 만 맞추고 경고하며, 둘 다 안 되면 설치하지 않습니다. 릴리스를 읽지 못할 때 예전처럼 raw 파일을 받으려면 Windows `-Unverified`, macOS/Linux `LINKMYCOM_UNVERIFIED=1`.

설치 끝에 `linkmycom setup`이 실행되어 그 컴퓨터를 SSH 서버로 켜고(Windows는 UAC 승인, Tailscale 대역만 허용) 키를 교환합니다. 건너뛰려면 Windows `-NoSetup`, macOS/Linux `LINKMYCOM_NO_SETUP=1`.

## 옛 tssh 에서 옮기기

따로 할 일은 없습니다. 이미 설치된 tssh 에서 `tssh update`를 실행하면 새 코드를 받고, 처음 실행할 때 같은 폴더에 `linkmycom`과 `lmc`를 만들며 옛 `tssh`는 새 명령으로 넘기는 파일이 됩니다. 설정 `~/.tssh/config.json`, 상태 `~/.tssh/state.json`, `~/.ssh/config`의 관리 블록, `~/.ssh/authorized_keys`의 키 블록, SSH 방화벽 규칙은 이름을 바꾸지 않고 그대로 씁니다. Windows 한 줄 설치를 다시 하면 새 설치 폴더는 `%LOCALAPPDATA%\linkmycom`이고 옛 `%LOCALAPPDATA%\tssh`에는 넘김용 `tssh.cmd`만 남습니다.

## 사용법

| 명령 | 설명 |
|---|---|
| `linkmycom` | 목록에서 번호 또는 이름(일부)으로 골라 접속. Enter만 누르면 최근 호스트. |
| `linkmycom pfl`, `linkmycom root@pfl`, `linkmycom -u bob -p 2222 pfl` | 바로 접속. 호스트 뒤 인자는 `ssh`에 그대로 전달 (`lmc pfl -L 8080:localhost:80`, `lmc pfl uptime`). |
| `linkmycom -n pfl` | 실행할 ssh 명령만 출력. 파이프·스크립트처럼 비대화형에서 이름이 여러 PC 에 맞으면 고르지 않고 후보를 적은 뒤 종료 코드 1. |
| `linkmycom list [--all] [--json]`, `linkmycom last`, `linkmycom resolve pfl [--json]` | 목록, 최근 호스트 재접속, `user@주소` 출력(scp 등에 활용). 목록과 선택기는 즐겨찾기(★) → 최근 접속 5대 → 온라인 → 오프라인 순이고 번호는 검색해도 바뀌지 않습니다. SSH 없는 모바일은 숨기고 `--all`이면 'SSH 없음'으로 보입니다. `list --json`은 모든 피어를 `[{name, ip, dns, os, online, cur_addr, relay, fav, last_seen}]`로(타워·Stream Deck 생성기가 읽는 고정 형식), `resolve --json`은 그 항목에 `user`·`port`·`ssh`를 더한 객체. 0.7.0 부터 목록·선택기는 30일 넘게 꺼진 장비와 `hide`로 숨긴 장비를 빼고 개수만 알립니다(`--all`로 표시, `list --json`은 그대로). 이름을 직접 쓰는 접속·`resolve`는 숨긴 장비에도 됩니다. |
| `linkmycom hide <이름>` / `linkmycom unhide <이름>` | 장비를 `~/.tssh/config.json`의 `"hidden": ["이름", ...]`에 더하거나 뺍니다(앱·타워는 같은 키를 읽기만). 숨긴 장비는 목록·선택기와 `all` 대상(`exec all`·`doctor --all`·`fleet`·`audit all`)에서 빠집니다. `unhide`는 숨긴 목록에서 이름을 찾으므로 꺼져 있어도 됩니다. |
| `linkmycom forget <이름> [-n]` | Tailscale 에서 없어진(꺼진) 노드의 이 PC 쪽 흔적을 지웁니다: `config.json`의 `hosts`·`hidden` 항목, `~/.ssh/known_hosts` 의 그 노드(이름·DNS·IP, `[이름]:포트` 형태 포함) 줄(해시된 줄은 건드리지 않고, 바꾸기 전 원본을 `known_hosts.old`로 남김), `~/.tssh/macs.json`의 MAC 기억, 피어·호스트 이름 캐시. 지금 켜져 있는 노드는 거부합니다. `-n`은 지울 것만 보입니다. |
| `linkmycom set pfl user=ubuntu port=2222 key=~/.ssh/id alias=srv fav=1 forward=8080:80` / `linkmycom unset pfl` | 호스트별 설정 저장·삭제. `args="-A -o 'ProxyJump a b'"`처럼 따옴표로 묶은 값은 한 인자로 둡니다(Windows 경로의 역슬래시는 그대로). `fav=1` 즐겨찾기(`fav=0` 해제), `forward=`는 `forward <이름>`의 저장 규칙. |
| `linkmycom history [이름] [--since 7d]` | 접속 기록 `~/.tssh/history.jsonl`(connect·screen·send·exec·forward·fleet update/rollback)을 표로. 선택기의 '최근 5대'도 여기서 고릅니다. |
| `linkmycom clip jekim-1,officehermes [--text "..."] [--file a.pdf ...]` | 이 PC 의 클립보드(Windows `Get-Clipboard`, 파일 목록이면 파일 / macOS `pbpaste` / Linux `wl-paste`·`xclip`)나 주어진 텍스트·파일을 그 PC 들의 LinkMyCom 앱 트레이(TCP 21120, 앱 0.6.0 이상)로 보냅니다. 규약은 첫 줄 `LMCCLIP 1 <text\|files> <바이트 수> <sha256> <보낸 장비>` + 내용, 응답 `OK`/`ERR <사유>`. 대상 최대 3곳 병렬, 10초 시간 제한, 텍스트 1 MiB 까지. 파일은 Taildrop 으로 먼저 보내고 이름 목록을 보내 받는 쪽 클립보드에 파일로 올립니다. |
| `linkmycom screen jekim-1 [--gather] [--files\|--terminal\|--forward [로컬:원격]]` | 그 PC 의 화면공유 창(또는 파일 전송·터미널·포트 전달 창)을 연다. `--gather`는 창 모으기를 기다리지 않고 뷰어를 먼저 띄운다. 앱의 포트 전달 창은 규칙을 명령줄로 받지 않아 `로컬:원격`은 안내만 한다. `set <이름> screen=<다른 이름>`으로 화면용 대상을 따로 지정. |
| `linkmycom forward pfl 8080:80 [--bg]` / `forward list` / `forward stop [번호\|all]` | `ssh -N -L 8080:127.0.0.1:80`로 이 PC 의 포트를 그 PC 의 포트로 잇는다(`로컬:원격호스트:원격`도 됨, `-n`은 명령만 출력). 규칙을 빼면 `set <이름> forward=...` 저장 규칙을 쓰고, `--bg`는 창 없이 띄워 pid·규칙을 `~/.tssh/forwards.json`에 남깁니다. |
| `linkmycom hostkey reset <이름> [--yes] [-n]` | `Host key verification failed` 때 known_hosts 의 그 PC 항목(IP·DNS·이름)을 지우고 `ssh-keyscan`으로 받은 키의 지문을 보인 뒤 확인을 받아 다시 등록. exec·doctor·fleet 의 BatchMode 접속은 `StrictHostKeyChecking=accept-new`(처음 보는 키만 받음). |
| `linkmycom sessions close [-n]` | 화면공유 세션 창(`--connect`·`--file-transfer`·`--terminal`로 뜬 linkmycom 프로세스)만 닫는다. 홈 창·트레이·서비스는 그대로. |
| `linkmycom send a.pdf b.zip --to jekim-1,officehermes` | Taildrop 으로 보낸다. 대상마다 `tailscale file cp <파일들> <주소>:` 한 번, 대상은 최대 3곳 병렬, 실패는 대상별로 표시. |
| `linkmycom inbox [폴더] [--wait]` | Taildrop 으로 받은 파일을 폴더(기본 `~/Downloads`)로 옮긴다(같은 이름은 번호를 붙임). macOS 는 앱이 Downloads 에 바로 두므로 안내만. |
| `linkmycom exec <이름\|a,b\|all> [--os windows\|macos\|linux] [--ps] -- <명령...>` | BatchMode SSH 로 여러 PC 에 병렬 실행, 줄마다 `[이름] ` 접두어. `all`은 온라인이고 모바일이 아니며 SSH 포트가 열린 PC. `--os`는 그 OS 만, `--ps`는 Windows 대상 명령을 PowerShell `-EncodedCommand`로 감쌉니다. 하나라도 실패하면 종료 코드 1. |
| `linkmycom fleet status` / `fleet update [cli] [-n]` / `fleet rollback <이름\|all> cli [-n]` | 이 PC 와 온라인 PC 의 CLI·타워·화면공유 앱 버전과 '자동 업데이트'(예약 작업 존재·마지막 결과) 표(파이썬 없는 Windows 는 PowerShell 점검 결과로 채움). 0.6.0 부터 판마다 거울의 `v*`·`tower-v*`·`native-v*` 최신과 비교해 `0.5.0 최신` 또는 `0.4.4 → 0.5.0`으로 보이고, `--json`은 행 목록 그대로 행마다 `latest`·`outdated`를 더합니다 / 이 PC 가 거울의 최신 릴리스를 받아 서명을 확인한 뒤, 이 PC 의 CLI 보다 낡은 원격 설치본(PATH 의 lmc·tower·linkmycom·tssh·~/.local/bin)에만 SSH 로 밀어 넣어 교체하고 바꾸기 전 판은 옆에 `.prev`로 남김(`-n`: 할 일만 출력) / `rollback`은 그 `.prev`로 되돌림. 원격이 스스로 받게 하지 않는 이유는 SSH 세션 안의 Windows `ssh-keygen` 이 파이프 입력에서 멈추기 때문(0.7.0 은 서명 확인 때 Windows SSH 세션 환경의 `*_POSIX_FD_STATE` 변수도 가려 `ssh-keygen` 이 표준 입력 대신 SSH 채널을 읽다 0xC0000005 로 죽는 일을 막습니다). 상태 칸에는 디스크 여유 2 GB 미만이나 30분 넘게 도는 업데이터도 경고합니다. |
| `linkmycom fleet fix [이름\|a,b\|all] [-n]` | 원격 PC 에서 `doctor --fix --no-admin`(관리자 권한이 필요 없는 복구: 키 갱신 예약·키 갱신·꺼진 타워 시작·타워 예약 작업 등록. sshd·방화벽·중복 `lmc` 정리는 뺌)을 돌려 PC 별 결과 표(OK·실패·건너뜀)를 보입니다. CLI 0.7.0 미만 PC 는 건너뜁니다(`fleet update cli` 먼저). `-n`은 PC 별 할 일만. |
| `linkmycom fleet update native\|tower [이름\|all] [--apply [--wait [초]]]` | 거울 최신보다 낡은 원격 PC 에서 업데이터를 SSH 로 시작합니다. Windows 는 예약 작업 `LinkMyCom-NativeUpdate`(SYSTEM)·`LinkMyCom-TowerUpdate`를 `schtasks /Run`으로, 타워 작업이 없으면(0.7.0) SSH 세션 안에서 돌리지 않고 그 PC 에 로그온한 사용자의 대화형 세션에서 도는 일회용 작업 `LinkMyCom-TowerUpdate-Once`로 시작해 시작 뒤 지웁니다(로그온한 사용자가 없으면 그 사실을 알림. 세션 안에서 직접 돌리면 `ssh-keygen` 서명 확인이 멈추고 세션에서 띄운 타워가 세션과 함께 꺼지기 때문). `--wait [초]`(기본 120)는 시작 전후의 `update-state.json`을 읽어 PC 별 결과(완료·새 판 없음·미룸·실패·시간 초과)를 기다립니다. Mac 은 `Update-Native-Mac.sh --auto`를 떼어 놓습니다. 화면공유 세션 중이면 업데이터가 스스로 미룹니다. 0.7.0 이전 설치기로 깐 PC 는 일반 사용자의 작업 시작을 거부하므로 관리자 실행을 안내합니다. 한 Mac 의 두 Tailscale 노드는 한 번만 시작합니다. `--apply`가 없으면 할 일만 보입니다. |
| `linkmycom update --all [--check] [-n]` | 이 PC 의 CLI → 타워 → 화면공유 앱을 거울 최신과 비교해 차례로 적용(CLI 는 서명 확인 뒤 교체, 타워는 업데이터 실행, 화면공유 앱은 예약 작업 시작 또는 Mac 업데이터). `--check`는 비교만, `-n`은 할 일만. |
| `linkmycom status [--json]` | 이 PC 한 화면 요약: 판 3종(거울 최신과 비교), 자동 업데이트 상태(CLI 설정·마지막 확인, `update-state.json`의 `lastResult`, `installing`이면 '설치 중'), 켜진 장비 수, 직접 연결 없이 중계로 보이는 장비, 앱의 받은 파일 기록 수(`received.json`, 24시간 안), 백그라운드 포트 전달. 0.7.0 부터 디스크 여유(2 GB 미만 경고), 멈춘 업데이터(30분 넘게 도는 것), 빠진 예약 작업, 숨긴 장비 수를 더하고 문제가 있으면 `다음: ...` 한 줄로 칠 명령을 안내합니다(`--json`은 `disk`·`updater`·`tasks_missing`·`hidden`·`next` 키). |
| `linkmycom open jekim-1 [공유/경로] [-n]` | 그 PC 의 SMB 공유 폴더를 연다(Windows 탐색기 `\\IP\공유\경로`, macOS `open smb://IP/...`, Linux `xdg-open`). |
| `linkmycom cp [-r] a.txt pfl:/tmp/` / `linkmycom cp pfl:/tmp/a.txt .` | 한쪽이 원격인 scp 복사. 이름을 tailnet 주소로 풀고 `set`으로 저장한 사용자·포트·키를 쓰며, Windows 대상은 `scp -O`(Windows OpenSSH 서버 호환). 경로를 비우면 그 PC 의 홈, `-n`은 명령만. |
| `linkmycom wake <이름> [--via <켜진 PC>] [-n]` | `doctor <이름>`·`doctor --all`이 모아 `~/.tssh/macs.json`에 기억한 MAC 주소로 Wake-on-LAN 매직 패킷(UDP 9, LAN 브로드캐스트와 255.255.255.255). 이 PC 가 같은 LAN 이면 여기서, 아니면 기록상 같은 LAN 의 켜진 PC 에서 SSH 로 보냅니다. Tailscale SSH 로 들어간 Mac 은 `ifconfig`가 MAC 을 `02:00:00:00:00:00`으로 가려 `networksetup -getmacaddress`를 씁니다. |
| `linkmycom profiles windows-terminal\|iterm [-n]` | PC 마다 `lmc <이름>`을 여는 터미널 프로필. Windows Terminal JSON 조각 `%LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\LinkMyCom\linkmycom.json`, iTerm2 동적 프로필 `~/Library/Application Support/iTerm2/DynamicProfiles/linkmycom.json`. 관리 표시 `linkmycomManaged`가 있는 파일만 다시 씁니다. |
| `linkmycom audit [이름\|a,b\|all] [--since 7d] [--json]` | 들어온 SSH 접속(sshd 의 `Accepted` 로그: Windows `OpenSSH/Operational` 이벤트, macOS `/usr/bin/log show --info`, Linux `journalctl`·`auth.log`)을 모아 키 지문을 게시된 키 목록·`authorized_keys`의 주석(예: `tssh@jekimlabtop`)으로, 접속 주소를 장비 이름으로 풀어 '누가·언제·어디서' 표로. 이름을 빼면 이 PC. |
| `linkmycom display jekim-1 [list\|gather\|single\|extend]` | 여러 모니터 PC 정리. |
| `linkmycom password` | 화면공유 영구 비밀번호를 내 모든 PC 에 한 번에 설정(직접 입력). |
| `linkmycom export` | `~/.ssh/config`에 관리 블록을 써서 일반 `ssh pfl`도 되게 함. |
| `linkmycom config default_user=idonl use_magicdns=true` | 전역 설정. |
| `linkmycom maintain [--quiet] [-n]` | 일일 예약 작업이 부르는 유지: 키 목록 갱신 + 관리자 권한 없이 되는 복구(꺼진 타워 시작) + 결과를 `~/.tssh/state.json`의 `maintain`에 기록. sshd·방화벽처럼 관리자 권한이 필요한 항목은 기록만 하고 다음 대화형 실행 때 `doctor --fix`를 안내합니다. |
| `linkmycom setup [--no-server] [--no-keys] [--no-schedule]` | SSH 서버 켜기 + 키 교환 + 하루 한 번 `maintain`(0.4.x 는 `keys refresh`) 예약(Windows 예약 작업 `LinkMyCom-KeysRefresh`, macOS launchd `com.linkmycom.keys-refresh`, Linux systemd 사용자 타이머 `linkmycom-keys.timer`). |
| `linkmycom keys show / refresh [--force]` | 내 공개키 / 서명된 목록을 받아 `authorized_keys` 관리 블록 갱신. 빈 목록은 거부하고, 관리 블록의 키가 절반 이하로 줄면 `--force`가 있어야 적용. |
| `linkmycom keys publish --collect` | (관리 PC) 각 컴퓨터의 공개키를 모아 `~/.ssh/linkmycom-signing`으로 서명하고 거울 클론의 `tools/linkmycom/authorized_keys`·`authorized_keys.sig`를 커밋·푸시. `linkmycom config repo_dir=<거울 클론 경로>`가 필요하며 origin 이 `jekim14/linkmycom-cli`가 아니면 멈춤. |
| `linkmycom update [--check]` | 거울의 최신 GitHub 릴리스 자산 `linkmycom.py`를 받아 서명·SHA256·문법을 확인한 뒤에만 교체. 대화형 터미널이면 1시간에 한 번(0.6.0, 이전은 하루) 자동 확인해 같은 확인 뒤 바로 교체해 "linkmycom 0.5.x 으로 업데이트했습니다. 다음 실행부터 적용." 한 줄을 보입니다(`auto_update_apply`, 기본 켬, `linkmycom config auto_update_apply=false`로 끔). 파이프·`--json` 같은 비대화형은 하루 한 번 확인만(키 갱신은 어느 쪽이든 하루 한 번), 자동 적용 실패는 `~/.tssh/state.json`의 `update_error`에 남깁니다. |
| `linkmycom doctor [이름] [--json] [--all [--json]] [--fix [-n] [--no-admin]] [--permissions]` | 0.7.0 에서 더한 점검: ① 예약 작업 3종(`LinkMyCom-Tower`·`LinkMyCom-TowerUpdate`·`LinkMyCom-NativeUpdate`)을 따로(Windows), `--fix`가 앞의 둘(일반 권한)을 설치기와 같은 정의로 등록하고 NativeUpdate(SYSTEM)는 설치기 재실행을 안내 ② `디스크 여유`(Windows 는 시스템·설치 드라이브, Mac·Linux 는 `/`와 홈, 2 GB 미만 WARN)와 `업데이터 프로세스`(`Update-LinkMyCom.ps1`·`Update-Native.ps1`·`Update-Native-Mac.sh` 가 30분 넘게 돌면 `stuck` WARN), 둘 다 `fleet status --json`·`doctor --json` 의 rows 에 `disk`·`updater` 줄로 들어가고 같은 값이 `disk`·`updater` 키로도 보임 ③ macOS 는 Tailscale.app 과 Homebrew tailscaled 를 설치별 줄(`Tailscale.app`·`Tailscale(Homebrew)`, Homebrew 쪽은 `--socket=/var/run/tailscaled.socket`)로 보이고 둘 다 로그인돼 있으면 WARN 과 정리 안내 ④ `--permissions`(macOS, sudo 필요): LinkMyCom 앱을 잠깐 열고(약 20초) `sudo log stream` 으로 tccd(`com.apple.TCC`)의 `AUTHREQ` 줄을 읽어 화면 기록(ScreenCapture)·손쉬운 사용(Accessibility·PostEvent)·입력 모니터링(ListenEvent)을 `authValue` 로 판정합니다(0 거부, 1 미결정, 2 허용 → OK, 3 제한). 줄이 안 잡히면 '판정 못 함', `sudo -n` 이 안 되면 아무것도 실행하지 않고 안내만 하며, 이 명령이 띄운 `log stream` 과 앱 창만 닫고 화면공유 서비스는 건드리지 않습니다. `doctor <Mac 이름> --permissions`는 원격에서(원격 `sudo -n` 이 될 때). 평소 `doctor`(Mac)에는 `확인하려면 --permissions` 한 줄. `--no-admin`은 `--fix`에서 관리자 권한·확인 질문이 필요한 고침(서버 설정·중복 lmc 정리)을 뺍니다(`fleet fix`가 원격에서 씀). 기본 점검: Tailscale, sshd·22 포트, 방화벽 규칙(`tssh-OpenSSH`), `authorized_keys` 권한·내 키 등록, 게시된 키 목록 서명, CLI·타워·화면공유 앱 버전, PATH 의 `lmc`(설치본이 둘이면 경고), 타워 실행, 화면공유 서비스·21118, 클립보드 수신 21120(트레이), 자동 업데이트(예약 작업 `LinkMyCom-NativeUpdate`·`LinkMyCom-TowerUpdate` / launchd `com.linkmycom.native-update`와 `update-state.json`의 `lastResult`·`checked`), 마지막 키 갱신과 갱신 예약 작업 실재를 OK/FAIL 표로. 이름을 주면 같은 점검을 그 PC 에 ssh 로 보내 실행하고, 그 PC 가 Windows 인데 파이썬이 없으면 PowerShell 만으로 sshd·방화벽·버전·21118 을 점검합니다(설치 안내 `winget install -e --id Python.Python.3.12`). `--all`은 이 PC 와 온라인 PC 전부를 5대씩 병렬로 점검해 한 표(행 = PC)로, `--json`은 JSON 으로(한 PC 는 `{name, ip, os, rows, error}`). 이름을 주면 이 PC 에서 그 PC 의 21118 TCP 도달성과, 같은 장비의 다른 Tailscale 노드(이름·OS 가 닮고 21118 이 한쪽만 열림, `ssh-keyscan` 호스트 키가 같음. 한 Mac 의 `miniui-macmini`·`macmini` 같은 경우)를 함께 보고 `set <이름> screen=<다른 노드>`를 안내합니다. LAN·MAC 줄은 `wake`를 위해 `~/.tssh/macs.json`에 기억합니다. `--fix`는 이 PC 의 줄마다 고침 하나(키 갱신 예약 → 다시 예약, 키 갱신 → keys refresh, sshd·방화벽 → 서버 설정(UAC 한 번), 타워 실행 → `Start-ControlTower -NoBrowser`, PATH 의 lmc 중복 → 묻고 지움), `-n`은 할 일만. FAIL 이나 접속 실패가 있으면 종료 코드 1. |
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

0.4.4 부터는 거울 `jekim14/linkmycom-cli`의 최신 CLI 릴리스 자산을 받습니다. 거울에는 타워(`tower-v*`)·화면공유 앱(`native-v*`) 릴리스도 함께 있어 `/releases/latest`는 다른 구성요소를 줄 수 있으므로, 릴리스 목록(`GET /repos/jekim14/linkmycom-cli/releases?per_page=30`, 인증 없음)에서 `v<버전>` 태그 중 가장 높은 것을 고릅니다.

| 자산 | 내용 |
|---|---|
| `linkmycom.py` | CLI 본체. |
| `linkmycom.py.sig` | `ssh-keygen -Y sign -f ~/.ssh/linkmycom-signing -n linkmycom-keys linkmycom.py` 결과. 없거나 맞지 않으면 교체하지 않습니다. |
| `linkmycom.py.sha256` | `<16진 SHA256>  linkmycom.py` 한 줄. 있으면 대조합니다. |

확인 순서는 서명 → SHA256 → `compile()` 문법 → 버전이며, 하나라도 어긋나면 설치된 파일을 그대로 둡니다. 받은 바이트를 그대로 써서 교체합니다. 같은 거울의 sha256 은 무결성만 보장하므로 진본성은 서명이 맡습니다.

0.7.1 에서 고친 것(0.7.0 실기에서 드러남).

- 원격 점검이 가끔 끝나지 않고 그 PC 에 PowerShell 프로세스가 남던 문제: Windows 원격 실행기가 점검 스크립트를 25초 안에 받지 못하면 스스로 끝나고, 부른 쪽이 한 번 다시 시도합니다. 시간 초과가 나면 그 PC 에 남은 실행기를 바로 치웁니다. 0.7.0 이하가 남긴 것은 PC 마다 수십~백여 개(메모리 수 GB)였습니다.
- `fleet update … --wait` 가 Windows 의 상태 파일(UTF-8, 한글)을 읽지 못해 "읽을 수 없음"으로 끝나던 문제.
- Mac 의 화면공유 앱 최신 판은 Mac 패키지가 실린 판만 봅니다. Windows 만 게시한 판 때문에 Mac 이 계속 "낡음"으로 보이고 `fleet update native --wait` 가 끝까지 기다리던 문제를 고쳤습니다.

이미 설치된 0.4.3 이하는 거울 기본 브랜치의 raw 파일 `tools/linkmycom/linkmycom.py`를 서명 확인 없이 받습니다. 그래서 0.4.3 → 0.4.4 첫 이동은 검증 없이 이뤄지고, 0.4.4 이후의 업데이트부터 서명을 확인합니다. 거울은 당분간 raw 파일과 릴리스 자산을 둘 다 갱신합니다.

## 개발

```bash
python -m unittest discover -s tools/linkmycom/tests -v
```

서명·`keys publish` 테스트는 실제 `ssh-keygen`·`git`으로 임시 키와 임시 저장소를 만들어 확인하고, 없으면 건너뜁니다. Windows 에서 `doctor` 점검 스크립트 실행 테스트는 PowerShell(방화벽 조회)을 띄워 몇 초 걸려 `LINKMYCOM_SLOW_TESTS=1`일 때만 돕니다. 0.4.5 부터 점검 스크립트는 PowerShell 을 한 번만 띄워 다른 점검과 겹쳐 돌리고, `doctor`는 키 목록 받기와 점검을 함께 돌립니다.

`setup`의 SSH 방화벽 규칙 `tssh-OpenSSH`는 Tailscale 대역(100.64.0.0/10, fd7a:115c:a1e0::/48)에 더해, 실행 시점에 `Get-NetAdapter`로 찾은 Tailscale 인터페이스에도 묶습니다(100.64/10 은 통신사 CGNAT 과 겹침). 새 규칙(`tssh-OpenSSH-next`)을 먼저 만든 뒤 옛 규칙을 지우고 이름을 `tssh-OpenSSH`로 바꾸며, Tailscale 인터페이스를 못 찾으면 기존 규칙을 바꾸지 않습니다.

Windows 패키지 포함은 `ime-probe/package.ps1`, 업데이터의 관리 파일 목록은 `Update-LinkMyCom.ps1`에 있습니다. 옛 이름 파일 `tssh.py`·`tssh.cmd`·`tssh.ps1`은 패키지 안에서 새 이름으로 넘기는 얇은 파일입니다. 참고한 구현: [tailscale-cli-helpers](https://github.com/DigitalCyberSoft/tailscale-cli-helpers), [lazytailscale](https://github.com/mogglemoss/lazytailscale), [sshs](https://github.com/quantumsheep/sshs) (모두 MIT, 설계만 참고).
