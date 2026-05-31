"""Paper portfolio smoke test."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import paper_portfolio as pp
from config import TICKERS

# Sifirla
pp.reset()
state = pp.get_state()
assert not state, f"reset hatasi: {state}"
print("✓ reset OK")

# Baslat - sadece bir hisseyle hizli test
state = pp.initialize(["NVTS"], per_ticker_usd=1000.0)
assert "NVTS" in state["positions"], f"init hatasi: {state}"
pos = state["positions"]["NVTS"]
print(f"✓ init OK: NVTS @ ${pos['start_price']:.2f} -> {pos['shares']:.4f} shares")

# Anlik degerleme (quotes override)
val = pp.current_value(quotes={"NVTS": pos["start_price"] * 1.10})  # %10 yukari
print(f"✓ current_value: invested=${val['total_invested']:.2f}  "
      f"value=${val['total_value']:.2f}  pnl={val['total_pnl_pct']:+.2f}%")
assert abs(val['total_pnl_pct'] - 10.0) < 0.5, "pnl % yanlis"
print("✓ pnl % +10 dogru")

# Value history (yfinance cagrisi - basit dogrulama)
ts = pp.value_history()
print(f"✓ value_history: {len(ts)} satir  son deger=${ts['portfoy_value'].iloc[-1]:.2f}"
      if not ts.empty else "✓ value_history bos (baslangic icin normal)")

# Yeni hisse ekleme (mevcut NVTS dokunulmamali)
old_start = pos["start_price"]
state2 = pp.initialize(["NVTS", "IONQ"], per_ticker_usd=1000.0)
assert "IONQ" in state2["positions"]
assert state2["positions"]["NVTS"]["start_price"] == old_start, "NVTS start_price degisti!"
print("✓ ekleme: NVTS start_price kilitli kaldi")

# Cleanup
pp.reset()
print("\nOVERALL: PASS")
