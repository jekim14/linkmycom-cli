#!/usr/bin/env sh
# tssh 를 ~/.local/bin 에 설치하는 macOS/Linux 설치 스크립트.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
dest="${TSSH_BIN_DIR:-$HOME/.local/bin}"
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 가 필요합니다." >&2
    exit 1
fi
mkdir -p "$dest"
cp "$here/tssh.py" "$dest/tssh"
chmod +x "$dest/tssh"
case ":$PATH:" in
    *":$dest:"*) ;;
    *) echo "주의: $dest 가 PATH 에 없습니다. 셸 설정에 'export PATH=\"$dest:\$PATH\"' 를 추가하세요." ;;
esac
echo "설치 완료: $("$dest/tssh" version) → $dest/tssh"
