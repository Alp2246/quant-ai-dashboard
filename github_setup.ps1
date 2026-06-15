# =============================================================================
#  github_setup.ps1  -  GitHub'a tek tikla yukleme (PRIVATE repo)
# =============================================================================
#  Bu scripti CIFT TIKLA ile calistir (PowerShell penceresi acilacak).
#  Akis:
#    1) gh auth login - tarayicida login (8 haneli kod ile)
#    2) Private repo olustur: Alp2246/quant-ai-dashboard
#    3) git push
# =============================================================================

$ErrorActionPreference = "Continue"
$env:Path = "C:\Program Files\Git\cmd;C:\Program Files\GitHub CLI;" + $env:Path

Write-Host ""
Write-Host "+===========================================+" -ForegroundColor Cyan
Write-Host "|  Quant AI Dashboard -> GitHub (PRIVATE)   |" -ForegroundColor Cyan
Write-Host "+===========================================+" -ForegroundColor Cyan
Write-Host ""

# 1) Auth durumu
$authState = gh auth status 2>&1 | Out-String
if ($authState -match "Logged in to github\.com") {
    Write-Host "[1/3] OK - GitHub'a zaten login" -ForegroundColor Green
} else {
    Write-Host "[1/3] GitHub login..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  ASAGIDAKI SORULARA SU CEVAPLARI VER:" -ForegroundColor Magenta
    Write-Host "    - What account?       -> GitHub.com"
    Write-Host "    - Protocol?           -> HTTPS"
    Write-Host "    - Authenticate Git?   -> Y (Yes)"
    Write-Host "    - How to authenticate -> Login with web browser"
    Write-Host ""
    Write-Host "  Sonra 8 haneli KOD verilecek (ekrana yazilacak)."
    Write-Host "  Tarayicida o kodu yapistir, ALP2246 hesabinla login ol."
    Write-Host ""
    Read-Host "  Anladim, baslat (ENTER)"
    gh auth login
}

# Hala login olmadiysa cik
$authState = gh auth status 2>&1 | Out-String
if ($authState -notmatch "Logged in to github\.com") {
    Write-Host ""
    Write-Host "HATA: Login basarisiz" -ForegroundColor Red
    Read-Host "Cikmak icin ENTER"
    exit 1
}

# 2) Repo olustur
Write-Host ""
Write-Host "[2/3] Private repo olusturuluyor..." -ForegroundColor Yellow
$user = (gh api user --jq .login).Trim()
Write-Host "  GitHub kullanici: $user" -ForegroundColor Green

$repoName = "quant-ai-dashboard"
$exists = gh repo view "$user/$repoName" 2>&1 | Out-String
if ($exists -match "Could not resolve|not found") {
    gh repo create $repoName --private --source=. --remote=origin --description "Quant AI Dashboard v9 - Master Score, Monte Carlo, Strategic Overlays, Telegram, PWA APK" --disable-issues=false --disable-wiki=true
    Write-Host "  Repo olusturuldu: github.com/$user/$repoName (PRIVATE)" -ForegroundColor Green
} else {
    Write-Host "  Repo zaten var: github.com/$user/$repoName" -ForegroundColor Yellow
    $remoteCheck = git remote -v 2>&1 | Out-String
    if ($remoteCheck -notmatch "origin") {
        git remote add origin "https://github.com/$user/$repoName.git"
    }
}

# 3) Push
Write-Host ""
Write-Host "[3/3] Push ediliyor..." -ForegroundColor Yellow
git push -u origin main 2>&1

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  TAMAMLANDI!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Repo: https://github.com/$user/$repoName" -ForegroundColor White
Write-Host "  Erisim: SADECE SEN (private)" -ForegroundColor White
Write-Host ""
Write-Host "  Kodlari guncelle:" -ForegroundColor Yellow
Write-Host "    git add . && git commit -m 'mesaj' && git push" -ForegroundColor White
Write-Host ""
Read-Host "Cikmak icin ENTER"
