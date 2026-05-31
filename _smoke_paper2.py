import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import paper_portfolio as pp

pp.reset()
state = pp.initialize(["NVTS", "QBTS", "POET"], per_ticker_usd=1000.0)
quotes = {"NVTS": 32.0, "QBTS": 26.84, "POET": 13.14}
val = pp.current_value(quotes=quotes)
print(f"current: ${val['total_value']:,.2f}  pnl={val['total_pnl_pct']:+.2f}%")

ts = pp.live_value_series(quotes=quotes)
print(f"live_series: {len(ts)} nokta  cols={list(ts.columns)}")
assert len(ts) >= 1, "grafik bos"
assert "spy_benchmark" in ts.columns

sc = pp.portfolio_scenarios(quotes=quotes)
print(f"10y temel: ${sc['scenarios']['10y']['base']:,.0f}")

dca = pp.dca_projection(monthly_usd=500, months=12, annual_return_pct=15)
print(f"DCA 12ay: ${dca.iloc[-1]['deger']:,.0f}")

pp.reset()
print("PASS")
