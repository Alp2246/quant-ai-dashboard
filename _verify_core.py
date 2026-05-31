"""Cekirdege tasinan 4 hisse + mevcut 6 hisse icin tam doluluk testi."""
from config import TICKERS, COMPANY_NAMES, EXTRA_WATCHLIST
from sector_tam import (INVESTOR_CATEGORY, STRATEGIC_FOCUS, get_sector,
                          TICKER_TO_SECTOR, SECTOR_PS_MULTIPLIER,
                          SECTOR_TAM_BN_USD, SECTOR_TAM_CAGR_PCT,
                          SECTOR_LEADER_MARKET_CAP_USD)
from engineering_notes import BASE_NOTE, CRITICAL_THRESHOLD
from moonshot_detector import EXPLOSIVE_FACTOR, MOONSHOT_CANDIDATES, SECONDARY_MOONSHOT
from competitor_benchmark import COMPETITOR_GROUPS

print(f"TICKERS ({len(TICKERS)}): {TICKERS}")
print(f"EXTRA_WATCHLIST ({len(EXTRA_WATCHLIST)}): {EXTRA_WATCHLIST}")
print(f"Overlap (olmamali): {set(TICKERS) & set(EXTRA_WATCHLIST)}\n")

# Hangi field'lar bir hissenin gozukmesi icin DOLU olmali
def check(t):
    rows = []
    rows.append(("COMPANY_NAMES",  t in COMPANY_NAMES))
    rows.append(("INVESTOR_CATEGORY", t in INVESTOR_CATEGORY))
    rows.append(("STRATEGIC_FOCUS",   t in STRATEGIC_FOCUS))
    rows.append(("TICKER_TO_SECTOR",  t in TICKER_TO_SECTOR))
    rows.append(("BASE_NOTE",         t in BASE_NOTE))
    rows.append(("CRITICAL_THRESHOLD",t in CRITICAL_THRESHOLD))
    rows.append(("EXPLOSIVE_FACTOR",  t in EXPLOSIVE_FACTOR))
    sec = TICKER_TO_SECTOR.get(t)
    rows.append(("Sector PS multiplier", sec in SECTOR_PS_MULTIPLIER))
    rows.append(("Sector TAM",           sec in SECTOR_TAM_BN_USD))
    rows.append(("Sector CAGR",          sec in SECTOR_TAM_CAGR_PCT))
    rows.append(("Sector leader cap",    sec in SECTOR_LEADER_MARKET_CAP_USD))
    rows.append(("Moonshot/Secondary",
                  t in (MOONSHOT_CANDIDATES | SECONDARY_MOONSHOT)))
    rows.append(("Competitor group",     t in COMPETITOR_GROUPS))
    ok = all(v for _, v in rows)
    miss = [n for n, v in rows if not v]
    print(f"  {t:6}  sector={sec!s:20}  {'OK' if ok else 'EKSIK: '+','.join(miss)}")
    return ok

print("Cekirdek hisseler (Investor Summary'ye girecek):")
all_ok = True
for t in TICKERS:
    if not check(t):
        all_ok = False

print(f"\nResult: {'OK - hepsi tam' if all_ok else 'EKSIK ALAN VAR'}")
