import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import paper_portfolio as pp

pp.reset()
pp.initialize(["WOLF", "IONQ", "RGTI", "ATOM", "LAES", "NVTS",
                "QBTS", "POET", "ARQQ", "SMCI"], per_ticker_usd=1000.0)
# Senaryolar
sc = pp.portfolio_scenarios()
inv = sc["current"]["invested"]
print(f"Yatirilan: ${inv:,.0f}\n")
for h, d in sc["scenarios"].items():
    print(f"{h.upper():4}: "
          f"Kotumser ${d['pessimistic']:>9,.0f}  ({(d['pessimistic']/inv-1)*100:+.1f}%)  |  "
          f"Temel ${d['base']:>9,.0f}  ({(d['base']/inv-1)*100:+.1f}%)  |  "
          f"Iyimser ${d['optimistic']:>9,.0f}  ({(d['optimistic']/inv-1)*100:+.1f}%)")

# Etkin CAGR
print()
for h, d in sc["scenarios"].items():
    y = d["years"]
    for k in ("pessimistic", "base", "optimistic"):
        cagr = ((d[k]/inv)**(1/y)-1)*100 if inv > 0 else 0
        print(f"  {h} {k:14s}: etkin CAGR %{cagr:+.1f}")

# Hisse-bazli 10y base
print("\n10Y BASE per-ticker:")
for t, d in (sc.get("per_ticker_10y") or {}).get("base", {}).items():
    print(f"  {t:6s}  CAGR %{d['cagr_pct']:+.1f}  p_success={d['p_success']:.2f}  10Y=${d['future_val']:,.0f}")

pp.reset()
