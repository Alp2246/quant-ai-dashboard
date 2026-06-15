# Screenshots for GitHub & Marketing

Add PNG files here before publishing. Recommended captures (1920×1080 or 1440×900):

| File | What to capture |
|------|-----------------|
| `01-dashboard-overview.png` | Master Score table + gauges (Overview tab) |
| `02-investor-summary.png` | Investor Executive Summary with verdict colors |
| `03-alpha-engine.png` | 🚨 Early Warning panel + recent signals |
| `04-detail-analysis.png` | Single ticker detail (QBTS/IONQ) with breakdown |
| `05-telegram-alert.png` | Telegram KRITIK OLAY / KRITIK ALIM message (blur chat ID) |
| `06-mobile-pwa.png` | Phone browser or APK on dashboard |
| `07-architecture.png` | Optional: draw.io / Excalidraw pipeline diagram |

## Quick capture (Windows)

```powershell
cd C:\fpga_work\quant-dashboard
.\paylasim_baslat.bat
# Open http://localhost:8501 — Win+Shift+S for each screen
# Save into docs/screenshots/
```

Or run: `.\scripts\capture_screenshots.ps1`

**Privacy:** Blur API keys, chat IDs, and personal Tailscale hostnames if needed.
