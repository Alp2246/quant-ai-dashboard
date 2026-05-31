import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import monte_carlo as mc

print("=== NVTS Monte Carlo (10K path, 10Y) ===")
res = mc.run_simulation("NVTS", spot_price=7.0,
                          custom_drift=0.18, custom_sigma=0.65,
                          horizon_years=10.0, n_paths=10_000,
                          macro_stress={"cycle_phase": "EXPANSION",
                                          "inflation": 0.03})
s = res.stats
print(f"Spot: ${s['S0']}  |  mu_used: {s['mu_used']}  |  sigma_used: {s['sigma_used']}")
print(f"Median (10Y): ${s['median_T']}  (CAGR median %{s['cagr_median_pct']})")
print(f"95% CI: [${s['p05']}, ${s['p95']}]")
print(f"VaR 5%: ${s['VaR_5_price']} ({s['VaR_5_pct']}%)")
print(f"CVaR 5%: {s['CVaR_5_pct']}%")
print(f"P(bust):   {s['p_bust']}%   |  P(2x): {s['p_double']}%")
print(f"P(10x):    {s['p_10x']}%    |  20x cap hit: {s['p_20x_cap_hit']}%")
print(f"Worst 5: {s['worst_5']}")
print(f"Best 5:  {s['best_5']}")

print("\n=== SEALSQ (LAES) Monte Carlo (10K path, 10Y) ===")
res2 = mc.run_simulation("LAES", spot_price=3.5,
                           custom_drift=0.25, custom_sigma=0.85,
                           horizon_years=10.0, n_paths=10_000,
                           macro_stress={"cycle_phase": "EXPANSION",
                                           "inflation": 0.03})
s2 = res2.stats
print(f"Spot: ${s2['S0']}  |  mu_used: {s2['mu_used']}  |  sigma_used: {s2['sigma_used']}")
print(f"Median (10Y): ${s2['median_T']}  (CAGR median %{s2['cagr_median_pct']})")
print(f"95% CI: [${s2['p05']}, ${s2['p95']}]")
print(f"VaR 5%: ${s2['VaR_5_price']} ({s2['VaR_5_pct']}%)")
print(f"CVaR 5%: {s2['CVaR_5_pct']}%")
print(f"P(bust):   {s2['p_bust']}%   |  P(2x): {s2['p_double']}%")
print(f"P(10x):    {s2['p_10x']}%")

# Feature importance top-5 test (mock)
print("\n=== Feature Importance Top-5 (mock data) ===")
import pandas as pd
from feature_importance import top_features_report

mdi = pd.DataFrame([
    {"feature": "rsi_14",          "importance": 0.18},
    {"feature": "news_sentiment",  "importance": 0.16},
    {"feature": "sma20_cross",     "importance": 0.12},
    {"feature": "macd_hist",       "importance": 0.10},
    {"feature": "reddit_polarity", "importance": 0.08},
    {"feature": "volume_zscore",   "importance": 0.06},
    {"feature": "sma50_slope",     "importance": 0.04},
])
mda = pd.DataFrame([
    {"feature": "news_sentiment",  "importance": 0.062, "std": 0.005},
    {"feature": "reddit_polarity", "importance": 0.041, "std": 0.004},
    {"feature": "rsi_14",          "importance": 0.038, "std": 0.006},
    {"feature": "sma20_cross",     "importance": 0.025, "std": 0.003},
    {"feature": "macd_hist",       "importance": 0.022, "std": 0.002},
    {"feature": "sma50_slope",     "importance": 0.018, "std": 0.002},
    {"feature": "volume_zscore",   "importance": 0.014, "std": 0.001},
])
rep = top_features_report(mdi, mda, top_n=5)
for r in rep["top_mda"]:
    print(f"  {r['rank']}. {r['feature']:18s}  importance={r['importance']:.4f}  std={r['std']:.4f}")
print(f"  Sent score: {rep['sent_score']}  SMA score: {rep['sma_score']}  ratio: {rep['ratio']}")
print(f"  VERDICT: {rep['verdict']}")
print(f"  -> {rep['narrative']}")
