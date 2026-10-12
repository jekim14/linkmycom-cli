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
