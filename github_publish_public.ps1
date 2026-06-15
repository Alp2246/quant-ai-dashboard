# =============================================================================
#  github_publish_public.ps1 - Publish QuantAI as PUBLIC repo + launch kit
# =============================================================================
#  Run from repo root (PowerShell):
#    .\github_publish_public.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$env:Path = "C:\Program Files\Git\cmd;C:\Program Files\GitHub CLI;" + $env:Path

$RepoName = "quant-ai-dashboard"
$Description = "Open-source quant dashboard: Master Score, SEC/Reddit Alpha Engine, Telegram alerts, Streamlit, cloud deploy"

Write-Host ""
Write-Host "QuantAI -> GitHub PUBLIC publish" -ForegroundColor Cyan
Write-Host ""

# Auth
$auth = gh auth status 2>&1 | Out-String
if ($auth -notmatch "Logged in") {
    Write-Host "Login required:" -ForegroundColor Yellow
    gh auth login
}

$user = (gh api user --jq .login).Trim()
Write-Host "GitHub user: $user" -ForegroundColor Green

# Screenshots warning
$shots = Get-ChildItem docs\screenshots\*.png -ErrorAction SilentlyContinue
if (-not $shots) {
    Write-Host ""
    Write-Host "TIP: No PNG screenshots yet in docs/screenshots/" -ForegroundColor Yellow
    Write-Host "     Run: .\paylasim_baslat.bat then .\scripts\capture_screenshots.ps1" -ForegroundColor Yellow
    Write-Host "     Or copy hero: docs\screenshots\01-dashboard-overview.png" -ForegroundColor Yellow
    Write-Host ""
}

# Stage (respects .gitignore — no .env, no venv, no android-sdk)
git add -A
git status --short

$commitMsg = @"
docs: English README, promotion kit, unified verdict system, Alpha Engine

- Master Score v9 + verdict_rules single source of truth
- Alpha Engine early warning + Telegram
- Oracle deploy, app_lite, score_job, sharing scripts
- docs/PROMOTION.md marketing kit for launch
"@

$status = git status --porcelain
if ($status) {
    git commit -m $commitMsg
} else {
    Write-Host "Nothing to commit." -ForegroundColor Yellow
}

# Create public repo
$view = gh repo view "$user/$RepoName" 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $view -match "Could not resolve|not found") {
    gh repo create $RepoName --public --source=. --remote=origin `
        --description $Description
    Write-Host "Created PUBLIC repo: github.com/$user/$RepoName" -ForegroundColor Green
} else {
    Write-Host "Repo exists - pushing to origin/main" -ForegroundColor Yellow
    git remote get-url origin 2>$null
    if ($LASTEXITCODE -ne 0) {
        git remote add origin "https://github.com/$user/$RepoName.git"
    }
    # Make public if was private
    gh repo edit "$user/$RepoName" --visibility public --accept-visibility-change-consequences 2>$null
}

git push -u origin main

# Topics
gh repo edit "$user/$RepoName" `
    --add-topic quantitative-finance `
    --add-topic streamlit `
    --add-topic python `
    --add-topic machine-learning `
    --add-topic telegram-bot `
    --add-topic sec-edgar `
    --add-topic sentiment-analysis `
    --add-topic algorithmic-trading `
    --add-topic semiconductor `
    --add-topic dashboard 2>$null

$url = "https://github.com/$user/$RepoName"
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  LIVE: $url" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Upload docs/screenshots/*.png (Settings -> Social preview)" -ForegroundColor White
Write-Host "  2. Read docs/PROMOTION.md - post HN, Reddit, LinkedIn" -ForegroundColor White
Write-Host "  3. Star your own repo + share link" -ForegroundColor White
Write-Host ""
Start-Process $url
