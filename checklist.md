# tssh 작업 체크리스트.

- [x] 환경 확인: Windows 11, Tailscale 1.104.1 (MagicDNS 켜짐), OpenSSH 9.5, Python 3.14 (curses 없음), gh 로그인됨(jekim14).
- [x] 기존 구현 조사 (2026-10-12): tailscale-cli-helpers(bash, jq 필요, Windows 미지원), lazytailscale(Go TUI, Windows 미확인), sshs(ssh config 전용, Tailscale 인식 없음). 결론은 의존성 없는 Python 단일 파일 자체 구현.
- [x] `tssh.py` 본체: 피어 목록, 이름 해석(정확→별칭→접두→부분→유사), 대화형 선택, 호스트별 설정 저장, ~/.ssh/config 읽기, export, update.
- [x] 단위 테스트 `tests/test_tssh.py` 11개 통과 (2026-10-12).
- [x] 설치 스크립트 `install.ps1`(UTF-8 BOM 필요, Windows PowerShell 5.1 호환), `install.sh`, 배포 스크립트 `release.ps1`.
- [x] 실제 동작 확인: `tssh list`, `tssh -n mac`(기존 ssh config의 jemac 반영), 설치본 `tssh.cmd mac ... echo TSSH_OK` 가 Mac mini에서 TSSH_OK 반환.
- [x] 수정한 버그: 원격 명령이 호스트보다 앞에 놓이던 문제(`split_ssh_args` 로 해결), Windows 파이프 출력 cp949 깨짐(UTF-8 고정).
- [x] README.md, LICENSE, git 저장소 초기화와 커밋.
- [x] GitHub 저장소 게시와 첫 릴리스 v0.1.0 (2026-10-12, https://github.com/jekim14/tssh/releases/tag/v0.1.0). 설치본 `tssh update --check` 로 릴리스 조회 확인.
- [ ] 대화형 선택기를 실제 터미널에서 눌러 보기 (비대화형 환경에서는 검증 불가).
- [x] Mac mini(miniui-macmini) 설치: `~/.local/bin/tssh`, 테스트 13개 통과, 피어 11대 표시 (2026-10-12). CLI가 로그아웃된 시스템 확장에 붙는 문제를 소켓 LocalAPI 조회로 해결.
