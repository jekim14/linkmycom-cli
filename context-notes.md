# tssh 맥락 메모.

## 결정.
- 언어: Python 3 표준 라이브러리만 사용. 이 PC의 Python 3.14에는 `_curses`가 없어 커서 기반 TUI 대신 번호·이름 입력 방식의 선택기를 쓴다.
- 피어 정보는 `tailscale status --json`에서 읽는다. Windows에서는 `C:\Program Files\Tailscale\tailscale.exe`가 PATH에 있다.
- 접속 대상은 기본적으로 Tailscale IPv4를 쓰고, 설정 `use_magicdns`로 MagicDNS 이름을 쓸 수 있다 (tailscale-cli-helpers의 방식 참고).
- 사용자 이름은 호스트별 저장값 → 기존 `~/.ssh/config`의 같은 주소 항목 → 전역 기본값 → 현재 로그인 이름 순으로 정한다. 기존 `Host mac` 항목(jemac@100.82.231.21)이 자동으로 반영되어야 한다.
- 설정 파일: `~/.tssh/config.json`, 상태 파일: `~/.tssh/state.json`.
- 업데이트 경로: GitHub 릴리스(`update_repo`, 기본 `jekim14/tssh`)에서 최신 태그의 `tssh.py`를 받아 자기 자신을 교체한다. 저장소 게시는 사용자 승인 후 `release.ps1`로 한다.

## 주의할 점.
- 피어 이름은 `DNSName`의 첫 구간(MagicDNS 이름)을 기준으로 쓴다. 이 PC처럼 `HostName`(jekim)과 MagicDNS 이름(jekim-1)이 다를 수 있다.
- `tailscale ssh` 하위 명령은 Windows 클라이언트에서 쓸 수 없으므로 항상 일반 `ssh`를 호출한다.
- ssh 인자는 호스트 이름 뒤의 모든 인자를 그대로 넘긴다. tssh 자체 옵션은 호스트 이름 앞에만 둔다.

## macOS(miniui-macmini) 설치에서 배운 것 (2026-10-12).
- 이 Mac에는 Homebrew `tailscaled`(1.102.3, 로그인됨, 실제 연결 담당, `/var/run/tailscaled.socket` 소유)와 Tailscale.app 시스템 확장(macsys 1.98.9, 로그아웃)이 함께 떠 있다. `tailscale` CLI는 두 경로 모두 로그아웃된 시스템 확장에 붙어 `NeedsLogin`을 돌려준다.
- tssh는 CLI 후보가 모두 Running이 아니면 유닉스 소켓의 LocalAPI(`GET /localapi/v0/status`)를 직접 읽어 해결했다. 소켓 접근에는 별도 인증이 필요 없었다.
- Mac 설치 위치는 `~/.local/bin/tssh`(PATH에 이미 있음). 기본 사용자 이름이 `jemac`이라 Windows 피어에 붙을 때는 `tssh set <이름> user=idonl` 또는 `tssh config default_user=idonl`이 필요하다.
- Windows 설치본에 `tssh.ps1` 래퍼를 추가했다. PowerShell에서 `.cmd` 셈을 거치면 큰따옴표가 든 인자가 cmd.exe에 의해 깨지기 때문이다. 실행 정책이 Restricted/AllSigned면 만들지 않는다.
- 원격 명령 전달 시 PowerShell → ssh → zsh 의 따옴표 해석이 세 겹이라, 큰따옴표로 감싼 문자열 안에 작은따옴표를 쓰는 편이 안전했다.

## 다른 기기 설치 시도와 한 줄 설치 (2026-10-12).
- 온라인 피어 중 jekimlabtop·pfl 은 22번 포트 접속 거부, officehermes·pfl-sever 는 같은 LAN(192.168.0.x)에서 tailscale ping 은 되지만 22/5985 모두 닫힘, muse 는 ping 무응답. SSH·WinRM 서버가 없으므로 원격 설치는 불가능하고, 각 기기에서 한 줄 설치 명령을 직접 실행해야 한다.
- `install.ps1` 은 ASCII 전용으로 유지한다. Windows PowerShell 5.1 의 `irm` 은 GitHub 의 `application/octet-stream` 응답을 Latin-1 로 해석하므로 BOM 이나 한글이 있으면 첫 줄이 `ï»¿#` 토큰이 되어 param 블록부터 깨진다. 한글 역할 주석 규칙의 예외로 둔 이유다.
- `releases/latest/download/...` 주소는 릴리스 게시 직후 수십 초 동안 CDN(varnish) 캐시 때문에 이전 릴리스 자산으로 리다이렉트될 수 있다. 게시 직후 바로 검증하면 옛 파일이 내려온다. 1분쯤 뒤에 다시 확인하면 된다.
- 설치 스크립트가 `latest/download/tssh.py` 를 받으므로 릴리스 자산에는 항상 `tssh.py`, `install.ps1`, `install.sh` 세 파일이 있어야 한다 (`release.ps1` 이 올린다).
