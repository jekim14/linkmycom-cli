# linkmycom (lmc) - Tailscale SSH 접속기

LinkMyCom 의 SSH 접속기입니다. 옛 이름은 tssh 이고 이 저장소의 옛 이름은 `jekim14/tssh` 입니다. Tailscale 네트워크의 내 기기 목록에서 골라 바로 SSH 로 접속하고, 화면공유 창 열기·여러 모니터 정리·키 교환을 합니다. 줄임 명령 `lmc`가 함께 설치되며 옛 `tssh` 명령도 계속 동작합니다.

설치 (Windows PowerShell).

```powershell
irm https://raw.githubusercontent.com/jekim14/linkmycom-cli/HEAD/tools/linkmycom/install.ps1 | iex
```

설치 (macOS·Linux).

```bash
curl -fsSL https://raw.githubusercontent.com/jekim14/linkmycom-cli/HEAD/tools/linkmycom/install.sh | sh
```

이미 tssh 를 쓰고 있다면 `tssh update` 한 번이면 됩니다. 다음 실행부터 같은 폴더에 `linkmycom`·`lmc`가 생기고 설정(`~/.tssh`)은 그대로 씁니다. 사용법은 [tools/linkmycom/README.md](tools/linkmycom/README.md)를 보세요.

이 저장소는 비공개 저장소 LinkMyCom 의 `tools/linkmycom`을 내보낸 공개 거울입니다. `tools/tssh/`와 루트의 `tssh.py`·`install.*`는 옛 설치본의 업데이트 경로라서 같은 내용으로 유지합니다.
