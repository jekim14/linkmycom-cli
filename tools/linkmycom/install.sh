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
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    echo "Python 3.9 이상이 필요합니다(지금: $(python3 -V 2>&1))." >&2
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
    # 거울의 최신 릴리스 자산(linkmycom.py·.sig·.sha256)을 받아 서명을 확인한 뒤에만 설치한다(CLI 의 update 와 같은 키).
    # ssh-keygen 이나 .sig 가 없으면 SHA256 만 맞추고 경고한다. LINKMYCOM_UNVERIFIED=1 이면 예전처럼 raw 파일(ref)을 받는다.
    fetch() {
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL -H "User-Agent: linkmycom-installer" -o "$2" "$1"
        elif command -v wget >/dev/null 2>&1; then
            wget -q -O "$2" "$1"
        else
            echo "curl 또는 wget 이 필요합니다." >&2
            return 1
        fi
    }
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/linkmycom.XXXXXX")"
    src="$tmp/linkmycom.py"
    if [ -n "${LINKMYCOM_UNVERIFIED:-}" ]; then
        url="https://raw.githubusercontent.com/$repo/$ref/tools/linkmycom/linkmycom.py"
        echo "경고: LINKMYCOM_UNVERIFIED — 서명 확인 없이 내려받습니다: $url" >&2
        fetch "$url" "$src"
    else
        # 거울에는 tower-v*·native-v* 릴리스도 있어 /releases/latest 를 쓰지 않고 CLI 태그(v<버전>) 중 최신을 고른다.
        if ! fetch "https://api.github.com/repos/$repo/releases?per_page=30" "$tmp/release.json"; then
            echo "$repo 의 최신 릴리스를 읽지 못했습니다. 잠시 뒤 다시 하거나 LINKMYCOM_UNVERIFIED=1 로 서명 확인 없이 설치하세요." >&2
            rm -rf "$tmp"
            exit 1
        fi
        python3 - "$tmp/release.json" "$tmp/assets" <<'PY'
import json, re, sys
rels = json.load(open(sys.argv[1], encoding="utf-8"))
def ver(t):
    return tuple(int(x) for x in re.findall(r"\d+", t))
cands = [r for r in rels if re.match(r"^v\d+(\.\d+)+$", str(r.get("tag_name") or "")) and not r.get("draft") and not r.get("prerelease")]
if not cands:
    sys.exit("CLI 릴리스(v<버전>)가 없습니다.")
rel = max(cands, key=lambda r: ver(r["tag_name"]))
with open(sys.argv[2], "w") as f:
    f.write("tag %s\n" % rel.get("tag_name", "?"))
    for a in rel.get("assets") or []:
        if a.get("name") in ("linkmycom.py", "linkmycom.py.sig", "linkmycom.py.sha256"):
            f.write("%s %s\n" % (a["name"], a["browser_download_url"]))
PY
        asset() { sed -n "s|^$1 ||p" "$tmp/assets" | head -n 1; }
        tag="$(asset tag)"
        py_url="$(asset linkmycom.py)"
        if [ -z "$py_url" ]; then
            echo "릴리스 $tag 에 linkmycom.py 자산이 없습니다." >&2
            rm -rf "$tmp"
            exit 1
        fi
        echo "linkmycom.py 를 내려받습니다: $repo 릴리스 $tag"
        fetch "$py_url" "$src"
        verified=""
        sig_url="$(asset linkmycom.py.sig)"
        if [ -n "$sig_url" ] && command -v ssh-keygen >/dev/null 2>&1; then
            fetch "$sig_url" "$tmp/linkmycom.py.sig"
            echo "linkmycom ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGWKhtP9dXCC5mljTV/5DOf42NzaQ7EUHRAo9B+bX0+s" > "$tmp/allowed_signers"
            if ssh-keygen -Y verify -f "$tmp/allowed_signers" -I linkmycom -n linkmycom-keys -s "$tmp/linkmycom.py.sig" < "$src" >/dev/null 2>&1; then
                verified=1
                echo "서명 확인 완료(linkmycom, linkmycom-keys)."
            else
                echo "linkmycom.py 서명 확인에 실패했습니다($tag). 설치하지 않았습니다." >&2
                rm -rf "$tmp"
                exit 1
            fi
        fi
        sha_url="$(asset linkmycom.py.sha256)"
        if [ -n "$sha_url" ]; then
            fetch "$sha_url" "$tmp/linkmycom.py.sha256"
            if ! python3 - "$src" "$tmp/linkmycom.py.sha256" <<'PY'
import hashlib, sys
expected = (open(sys.argv[2], encoding="utf-8").read().split() or [""])[0].lower()
sys.exit(0 if hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest() == expected else 1)
PY
            then
                echo "linkmycom.py 의 SHA256 이 linkmycom.py.sha256 과 다릅니다. 설치하지 않았습니다." >&2
                rm -rf "$tmp"
                exit 1
            fi
            [ -z "$verified" ] && echo "경고: 서명은 확인하지 못했습니다(ssh-keygen 8.1+ 또는 .sig 없음). SHA256 만 맞췄습니다." >&2
        elif [ -z "$verified" ]; then
            echo "서명도 SHA256 도 확인할 수 없어 설치하지 않았습니다(LINKMYCOM_UNVERIFIED=1 로 무시 가능)." >&2
            rm -rf "$tmp"
            exit 1
        fi
    fi
fi
mkdir -p "$dest"
cp "$src" "$dest/linkmycom"
chmod 755 "$dest/linkmycom"
ln -sf linkmycom "$dest/lmc"
if [ -n "$tmp" ]; then rm -rf "$tmp"; fi
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
