#!/usr/bin/env sh
# linkmycom(LinkMyCom 의 SSH 접속기, 옛 tssh)을 ~/.local/bin 에 설치하는 macOS/Linux 설치 스크립트.
# 원격 한 줄 설치 (linkmycom.py 가 옆에 없으면 공개 거울 저장소 jekim14/linkmycom-cli 에서 내려받는다):
#   curl -fsSL https://raw.githubusercontent.com/jekim14/linkmycom-cli/HEAD/tools/linkmycom/install.sh | sh
# 줄임 명령 lmc 를 함께 만들고, 옛 tssh 가 있으면 linkmycom 으로 넘기는 파일로 바꾼다.
set -eu
repo="${LINKMYCOM_REPO:-${TSSH_REPO:-jekim14/linkmycom-cli}}"
ref="${LINKMYCOM_REF:-${TSSH_REF:-HEAD}}"
dest="${LINKMYCOM_BIN_DIR:-${TSSH_BIN_DIR:-$HOME/.local/bin}}"
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 가 필요합니다." >&2
    exit 1
fi
here=""
if [ -n "${0:-}" ] && [ -f "$0" ]; then
    here="$(cd "$(dirname "$0")" && pwd)"
fi
tmp=""
if [ -n "$here" ] && [ -f "$here/linkmycom.py" ]; then
    src="$here/linkmycom.py"
else
    url="https://raw.githubusercontent.com/$repo/$ref/tools/linkmycom/linkmycom.py"
    tmp="$(mktemp "${TMPDIR:-/tmp}/linkmycom.XXXXXX")"
    echo "linkmycom.py 를 내려받습니다: $url"
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
cp "$src" "$dest/linkmycom"
chmod 755 "$dest/linkmycom"
ln -sf linkmycom "$dest/lmc"
[ -n "$tmp" ] && rm -f "$tmp"
# 옛 tssh 는 지우지 않고 linkmycom 을 부르는 넘김 파일로 바꾼다. 설정(~/.tssh)은 그대로 함께 쓴다.
if [ -f "$dest/tssh" ] && ! sed -n 2p "$dest/tssh" | grep -q '^# linkmycom-forwarder:'; then
    python3 - "$dest/tssh" <<'PY'
import importlib.machinery, importlib.util, sys
from pathlib import Path
sys.dont_write_bytecode = True
target = Path(sys.argv[1])
loader = importlib.machinery.SourceFileLoader("linkmycom", str(target.with_name("linkmycom")))
spec = importlib.util.spec_from_loader("linkmycom", loader)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.replace_text(target, mod.forwarder_source("linkmycom"), 0o755)
PY
    echo "옛 tssh 명령은 이제 linkmycom 으로 넘어갑니다."
fi
case ":$PATH:" in
    *":$dest:"*) ;;
    *) echo "주의: $dest 가 PATH 에 없습니다. 셸 설정에 'export PATH=\"$dest:\$PATH\"' 를 추가하세요." ;;
esac
echo "설치 완료: $("$dest/linkmycom" version) → $dest/linkmycom (줄임 명령 lmc)"
# 이 컴퓨터를 tailnet 안에서 SSH 로 들어올 수 있게 하고 공개키를 교환한다. 건너뛰려면 LINKMYCOM_NO_SETUP=1.
if [ -z "${LINKMYCOM_NO_SETUP:-${TSSH_NO_SETUP:-}}" ]; then
    if [ -t 0 ]; then
        "$dest/linkmycom" setup
    elif [ -r /dev/tty ]; then
        "$dest/linkmycom" setup < /dev/tty
    else
        "$dest/linkmycom" setup
    fi
fi
