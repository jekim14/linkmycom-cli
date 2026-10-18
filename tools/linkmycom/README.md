# linkmycom · LinkMyCom의 SSH 접속기

Tailscale 네트워크(tailnet)의 내 기기 목록을 보여 주고 번호나 이름 일부로 바로 SSH로 접속하는 명령줄 도구입니다. 화면공유 창 열기(`linkmycom screen`), 여러 모니터 정리(`linkmycom display`), 화면공유 비밀번호 일괄 설정(`linkmycom password`)도 여기서 합니다. 줄임 명령 `lmc`가 함께 설치되며, 옛 이름 `tssh`도 계속 쓸 수 있고 같은 명령으로 넘어갑니다. LinkMyCom 컨트롤 타워의 `SSH 터미널` 버튼이 이 도구를 호출합니다. Python 3.10 이상, Tailscale, OpenSSH `ssh`만 있으면 되고 추가 패키지는 없습니다.

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
| `linkmycom -n pfl` | 실행할 ssh 명령만 출력. |
| `linkmycom list`, `linkmycom last`, `linkmycom resolve pfl` | 목록, 최근 호스트 재접속, `user@주소` 출력(scp 등에 활용). |
| `linkmycom set pfl user=ubuntu port=2222 key=~/.ssh/id alias=srv` / `linkmycom unset pfl` | 호스트별 설정 저장·삭제. |
| `linkmycom screen jekim-1 [--gather]` | 그 PC 의 화면공유 창을 연다. `set <이름> screen=<다른 이름>`으로 화면용 대상을 따로 지정. |
| `linkmycom display jekim-1 [list\|gather\|single\|extend]` | 여러 모니터 PC 정리. |
| `linkmycom password` | 화면공유 영구 비밀번호를 내 모든 PC 에 한 번에 설정(직접 입력). |
| `linkmycom export` | `~/.ssh/config`에 관리 블록을 써서 일반 `ssh pfl`도 되게 함. |
| `linkmycom config default_user=idonl use_magicdns=true` | 전역 설정. |
| `linkmycom setup [--no-server] [--no-keys]` | SSH 서버 켜기 + 키 교환. |
| `linkmycom keys show / refresh` | 내 공개키 / 저장소 목록을 받아 `authorized_keys` 갱신. |
| `linkmycom keys publish --collect` | (관리 PC) 각 컴퓨터의 공개키를 모아 거울 클론의 `tools/linkmycom/authorized_keys`에 커밋·푸시. `linkmycom config repo_dir=<거울 클론 경로>`가 필요. |
| `linkmycom update [--check]` | 거울 기본 브랜치의 `tools/linkmycom/linkmycom.py`로 자신을 교체. 하루 한 번 자동 확인. |

모든 명령은 `lmc`로도 됩니다. 사용자 이름은 저장값 → 기존 `~/.ssh/config`의 같은 주소 항목 → `default_user` → 현재 로그인 이름 순으로 정합니다. Tailscale CLI는 PATH, 앱 내장 CLI, Homebrew 순으로 시도해 `Running`인 것을 쓰고, macOS에서 Homebrew tailscaled와 Tailscale.app이 함께 있으면 `/var/run/tailscaled.socket`의 LocalAPI를 직접 읽습니다.

## 키 교환 모델

각 기기는 `linkmycom setup` 때 `~/.ssh/id_ed25519`를 만들고, 거울 저장소의 `authorized_keys` 목록을 받아 `~/.ssh/authorized_keys`의 관리 블록에 넣습니다. 목록을 바꿀 수 있는 사람은 저장소 주인뿐이므로 신뢰의 근거는 GitHub 계정입니다. 공개키는 공개돼도 안전합니다. 저장소 주인이 아닌 사람은 `linkmycom config keys_url=<자기 목록 주소>`로 바꾸세요.

## 개발

```bash
python -m unittest discover -s tools/linkmycom/tests -v
```

Windows 패키지 포함은 `ime-probe/package.ps1`, 업데이터의 관리 파일 목록은 `Update-LinkMyCom.ps1`에 있습니다. 옛 이름 파일 `tssh.py`·`tssh.cmd`·`tssh.ps1`은 패키지 안에서 새 이름으로 넘기는 얇은 파일입니다. 참고한 구현: [tailscale-cli-helpers](https://github.com/DigitalCyberSoft/tailscale-cli-helpers), [lazytailscale](https://github.com/mogglemoss/lazytailscale), [sshs](https://github.com/quantumsheep/sshs) (모두 MIT, 설계만 참고).
