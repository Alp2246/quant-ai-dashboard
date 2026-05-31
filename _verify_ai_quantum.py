from config import EXTRA_WATCHLIST, COMPANY_NAMES, AI_QUANTUM_WATCHLIST
from sector_tam import INVESTOR_CATEGORY, STRATEGIC_FOCUS, get_sector
from engineering_notes import BASE_NOTE, CRITICAL_THRESHOLD
from moonshot_detector import EXPLOSIVE_FACTOR, MOONSHOT_CANDIDATES
from competitor_benchmark import COMPETITOR_GROUPS

missing = []
for t in AI_QUANTUM_WATCHLIST:
    if t not in COMPANY_NAMES:
        missing.append(f"{t}: COMPANY_NAMES")
    if t not in INVESTOR_CATEGORY:
        missing.append(f"{t}: INVESTOR_CATEGORY")
    if t not in BASE_NOTE:
        missing.append(f"{t}: BASE_NOTE")
    if t not in EXPLOSIVE_FACTOR:
        missing.append(f"{t}: EXPLOSIVE_FACTOR")

print(f"EXTRA_WATCHLIST total: {len(EXTRA_WATCHLIST)}")
print(f"AI_QUANTUM_WATCHLIST: {len(AI_QUANTUM_WATCHLIST)}")
print(f"Missing: {missing or 'NONE'}")
print(f"QBTS in MOONSHOT: {'QBTS' in MOONSHOT_CANDIDATES}")
print(f"CRDO competitors: {COMPETITOR_GROUPS.get('CRDO')}")
print("OK" if not missing else "FAIL")
