#!/usr/bin/env sh
# tssh 를 ~/.local/bin 에 설치하는 macOS/Linux 설치 스크립트.
# 원격 한 줄 설치 (tssh.py 가 옆에 없으면 최신 릴리스에서 내려받는다):
#   curl -fsSL https://github.com/jekim14/tssh/releases/latest/download/install.sh | sh
set -eu
repo="${TSSH_REPO:-jekim14/tssh}"
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
    url="https://github.com/$repo/releases/latest/download/tssh.py"
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
