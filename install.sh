#!/usr/bin/env sh
# tssh(DeskTools 의 SSH 접속기)를 ~/.local/bin 에 설치하는 macOS/Linux 설치 스크립트.
# 원격 한 줄 설치 (tssh.py 가 옆에 없으면 공개 거울 저장소 jekim14/tssh 에서 내려받는다):
#   curl -fsSL https://raw.githubusercontent.com/jekim14/tssh/HEAD/tools/tssh/install.sh | sh
set -eu
repo="${TSSH_REPO:-jekim14/tssh}"
ref="${TSSH_REF:-HEAD}"
dest="${TSSH_BIN_DIR:-$HOME/.local/bin}"
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 가 필요합니다." >&2
    exit 1
fi
here=""
if [ -n "${0:-}" ] && [ -f "$0" ]; then
    here="$(cd "$(dirname "$0")" && pwd)"
fi
tmp=""
if [ -n "$here" ] && [ -f "$here/tssh.py" ]; then
    src="$here/tssh.py"
else
    url="https://raw.githubusercontent.com/$repo/$ref/tools/tssh/tssh.py"
    tmp="$(mktemp "${TMPDIR:-/tmp}/tssh.XXXXXX")"
    echo "tssh.py 를 내려받습니다: $url"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$tmp" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$tmp" "$url"
    else
        echo "curl 또는 wget 이 필요합니다." >&2
        exit 1
    fi
    src="$tmp"
fi
mkdir -p "$dest"
cp "$src" "$dest/tssh"
chmod 755 "$dest/tssh"
[ -n "$tmp" ] && rm -f "$tmp"
case ":$PATH:" in
    *":$dest:"*) ;;
    *) echo "주의: $dest 가 PATH 에 없습니다. 셸 설정에 'export PATH=\"$dest:\$PATH\"' 를 추가하세요." ;;
esac
echo "설치 완료: $("$dest/tssh" version) → $dest/tssh"
# 이 컴퓨터를 tailnet 안에서 SSH 로 들어올 수 있게 하고 공개키를 교환한다. 건너뛰려면 TSSH_NO_SETUP=1.
if [ -z "${TSSH_NO_SETUP:-}" ]; then
    if [ -t 0 ]; then
        "$dest/tssh" setup
    elif [ -r /dev/tty ]; then
        "$dest/tssh" setup < /dev/tty
    else
        "$dest/tssh" setup
    fi
fi
