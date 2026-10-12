# 버전을 올리고 태그·GitHub 릴리스를 만드는 배포 스크립트. 설치본의 `tssh update` 가 이 릴리스를 받는다.
# 사용법:  powershell -ExecutionPolicy Bypass -File release.ps1 -Version 0.2.0 -Notes "바뀐 내용"
#          처음 한 번은 -CreateRepo 를 붙이면 gh 로 저장소를 만들고 origin 을 연결한다.
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$Notes = "",
    [string]$Repo = "jekim14/tssh",
    [switch]$CreateRepo
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "버전은 X.Y.Z 형식이어야 합니다: $Version" }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "gh CLI 가 필요합니다." }
if (git status --porcelain) { throw "커밋되지 않은 변경이 있습니다. 먼저 정리하세요." }

& python -m unittest discover -s tests -q
if ($LASTEXITCODE -ne 0) { throw "테스트가 실패해 배포를 중단합니다." }

$file = "tssh.py"
$text = [System.IO.File]::ReadAllText($file, [System.Text.Encoding]::UTF8)
$new = [regex]::Replace($text, '(?m)^__version__\s*=\s*"[^"]+"', "__version__ = `"$Version`"", 1)
if ($new -eq $text) { Write-Host "버전 문자열이 이미 $Version 입니다." }
[System.IO.File]::WriteAllText($file, $new, (New-Object System.Text.UTF8Encoding $false))

if ($CreateRepo) {
    gh repo create $Repo --public --source . --remote origin --push
    if ($LASTEXITCODE -ne 0) { throw "저장소 생성에 실패했습니다." }
}

git add $file
git commit -m "release: v$Version" | Out-Null
git tag -a "v$Version" -m "v$Version"
git push origin HEAD
git push origin "v$Version"

$body = if ($Notes) { $Notes } else { "tssh v$Version" }
$body += "`n`n업데이트: 설치된 tssh 에서 ``tssh update`` 를 실행하면 이 버전으로 바뀝니다. 처음 설치는 ``install.ps1`` 또는 ``install.sh`` 를 쓰세요."
gh release create "v$Version" $file install.ps1 install.sh --title "tssh v$Version" --notes $body
Write-Host "릴리스 v$Version 게시 완료: https://github.com/$Repo/releases/tag/v$Version"
