# Opens dashboard tabs for manual screenshot capture (Win+Shift+S)
$base = "http://localhost:8501"
Write-Host "Ensure paylasim_baslat.bat or run.bat is running on port 8501" -ForegroundColor Yellow
Write-Host "Save screenshots to: docs\screenshots\" -ForegroundColor Cyan
Start-Process $base
Write-Host @"

Capture these (Win+Shift+S):
  1. Overview / Master Score table     -> 01-dashboard-overview.png
  2. Investor Executive Summary        -> 02-investor-summary.png
  3. Early Warning (Alpha Engine) tab   -> 03-alpha-engine.png
  4. Detail tab (pick IONQ or QBTS)    -> 04-detail-analysis.png
  5. Telegram alert on phone           -> 05-telegram-alert.png
  6. Mobile view (F12 device toolbar)  -> 06-mobile-pwa.png

"@
