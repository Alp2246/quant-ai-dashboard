"""reality_check.py testleri — durustluk kurallari calisiyor mu?

Ag baglantisi gerektirmez: mevcut modulleri monkeypatch ile taklit eder.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

import reality_check as rc


# ---------------------------------------------------------------- yardimci

def _fake_rows(specs):
    """specs: [(ticker, alpha, n_trades, gap)]"""
    rows = []
    for tk, alpha, n, gap in specs:
        rows.append({
            "ticker": tk, "ok": True, "alpha_vs_bh": alpha, "n_trades": n,
            "significant": n >= rc.MIN_TRADES_FOR_SIGNIFICANCE,
            "significance_badge": ("" if n >= rc.MIN_TRADES_FOR_SIGNIFICANCE
                                   else "ISTATISTIKSEL OLARAK ANLAMSIZ"),
            "overfitting_gap": gap,
            "overfit_verdict": "SIDDETLI OVERFIT" if gap > 0.2 else "DENGELI",
            "model_trusted": gap <= rc.OVERFIT_UNTRUSTED_GAP,
        })
    return rows


# ---------------------------------------------------------------- testler

def test_alpha_hesabi_sentetik_veriyle():
    rows = _fake_rows([("A", 10.0, 40, 0.02), ("B", -4.0, 35, 0.03),
                       ("C", 2.0, 50, 0.01), ("D", -20.0, 31, 0.04)])
    a = rc._alpha_summary(rows)
    assert a["n"] == 4, a
    # medyan([-20,-4,2,10]) = (-4+2)/2 = -1.0
    assert a["median_alpha"] == -1.0, a["median_alpha"]
    assert a["mean_alpha"] == round((10 - 4 + 2 - 20) / 4, 2), a["mean_alpha"]
    assert a["positive_rate"] == 50.0, a["positive_rate"]
    assert a["best"][0]["ticker"] == "A"
    assert a["worst"][0]["ticker"] == "D"
    print(f"OK alpha hesabi: medyan={a['median_alpha']} pozitif=%{a['positive_rate']}")


def test_kucuk_orneklem_hukumden_dislanir():
    """n_trades < 30 olan satir ozete GIRMEZ ve rozet alir."""
    rows = _fake_rows([("AZ", 999.0, 5, 0.01), ("COK", -3.0, 40, 0.01)])
    a = rc._alpha_summary(rows)
    assert a["n"] == 1, "zayif orneklem hukme katilmamali"
    assert a["n_weak"] == 1
    assert a["median_alpha"] == -3.0, "999% outlier hukmu kirletmemeli"
    zayif = [r for r in rows if not r["significant"]][0]
    assert zayif["significance_badge"] == "ISTATISTIKSEL OLARAK ANLAMSIZ"
    print("OK n<30 rozeti var ve hukumden disland")


def test_havuz_yetersizse_hukum_verilmez():
    """Az hisse / az islem -> HUKUM VERILEMEZ."""
    p = rc._pooled_summary(_fake_rows([("X", 50.0, 10, 0.01)]))
    assert p["conclusive"] is False, p
    v = rc._verdict(p)
    assert v["level"] == "UNKNOWN", v
    assert "HUKUM VERILEMEZ" in v["text"], v["text"]
    print(f"OK hukum: {v['text']}")


def test_havuz_az_islemli_hisseyi_dislar():
    """n_trades < MIN_TRADES_TO_POOL havuza girmez."""
    rows = _fake_rows([("COK", 5.0, 20, 0.01), ("AZ", 999.0, 2, 0.01)])
    p = rc._pooled_summary(rows)
    assert p["n_tickers"] == 1, p
    assert p["median_alpha"] == 5.0, "2 islemli outlier havuzu kirletmemeli"
    print(f"OK havuz filtresi: n={p['n_tickers']}, medyan={p['median_alpha']}")


def test_hukum_negatifse_yumusatilmaz():
    rows = _fake_rows([(f"T{i}", -5.0, 12, 0.01) for i in range(15)])
    p = rc._pooled_summary(rows)
    assert p["conclusive"] is True, p
    v = rc._verdict(p)
    assert v["level"] == "LOSES"
    assert "YENMIYOR" in v["text"], v["text"]
    assert "ama" not in v["text"].lower(), "yumusatma metni olmamali"
    print(f"OK hukum: {v['text']}")


def test_isaret_testi_dogru():
    """Hepsi pozitifse p kucuk, yari yariyaysa p buyuk olmali."""
    assert rc._binom_p_two_sided(15, 15) < 0.001
    assert rc._binom_p_two_sided(8, 16) == 1.0
    # 4/18 pozitif -> anlamli (gercek olcumumuz)
    assert rc._binom_p_two_sided(4, 18) < 0.05
    print(f"OK isaret testi: 4/18 -> p={rc._binom_p_two_sided(4, 18):.4f}")


class _Patch:
    """pytest kurulu olmayabilir — basit yamalayici (kaydet/geri al)."""

    def __init__(self, bt_result, ml_result):
        self.bt_result, self.ml_result = bt_result, ml_result

    def __enter__(self):
        import backtest
        import ml_model

        self._mods = (backtest, ml_model)
        self._saved = (backtest.backtest_strategy, ml_model.train_model)
        backtest.backtest_strategy = lambda d, **k: dict(self.bt_result)
        ml_model.train_model = lambda d, **k: dict(self.ml_result)
        return self

    def __exit__(self, *exc):
        self._mods[0].backtest_strategy = self._saved[0]
        self._mods[1].train_model = self._saved[1]
        return False


_BT_OK = {"n_trades": 40, "alpha_vs_bh": 3.0, "cum_return": 10.0,
          "buy_hold_return": 7.0, "sharpe_ratio": 0.9,
          "max_drawdown_pct": -12.0, "win_rate": 55.0}


def _df():
    idx = pd.date_range("2024-01-01", periods=120, freq="D")
    return pd.DataFrame({"Close": np.linspace(10, 20, 120)}, index=idx)


def test_overfit_gapi_yuksekse_tahmin_gizlenir():
    """gap > 0.15 -> recommendation GIZLENDI, prob_up None."""
    ml = {"overfitting_gap": 0.42, "overfit_verdict": "SIDDETLI OVERFIT",
          "cv_mean_accuracy": 0.51, "cv_n_folds": 5,
          "prob_up": 0.88, "recommendation": "GUCLU AL"}
    with _Patch(_BT_OK, ml):
        r = rc.evaluate_ticker("TEST", _df())
    assert r["model_trusted"] is False, r
    assert r["prob_up"] is None, "guvenilmez modelin olasiligi gizlenmeli"
    assert r["recommendation"] == "GIZLENDI", r["recommendation"]
    assert r["trust_badge"] == "MODEL GUVENILMEZ"
    print(f"OK gap={r['overfitting_gap']} -> tahmin gizlendi")


def test_dusuk_gapde_tahmin_gorunur():
    ml = {"overfitting_gap": 0.04, "overfit_verdict": "DENGELI",
          "cv_mean_accuracy": 0.57, "cv_n_folds": 5,
          "prob_up": 0.61, "recommendation": "AL"}
    bt = dict(_BT_OK, alpha_vs_bh=-2.0, n_trades=45)
    with _Patch(bt, ml):
        r = rc.evaluate_ticker("TEST", _df())
    assert r["model_trusted"] is True
    assert r["prob_up"] == 0.61
    assert r["recommendation"] == "AL"
    assert r["alpha_vs_bh"] == -2.0
    print("OK dusuk gapde tahmin gorunur")


def test_bl_esit_agirlik_fallbacki_tespit_edilir():
    """market_caps yoksa prior uydurmadir — kaynak bunu soylemeli."""
    from black_litterman import portfolio_optimization

    idx = pd.date_range("2023-01-01", periods=200, freq="B")
    rng = np.random.default_rng(0)
    hist = {
        "AAA": pd.DataFrame({"Close": 100 * np.cumprod(1 + rng.normal(0, .01, 200))}, index=idx),
        "BBB": pd.DataFrame({"Close": 50 * np.cumprod(1 + rng.normal(0, .012, 200))}, index=idx),
    }
    no_caps = portfolio_optimization(hist, market_caps=None)
    assert no_caps.get("source") == "equal_weight_fallback", no_caps.get("source")

    with_caps = portfolio_optimization(hist, market_caps={"AAA": 1e10, "BBB": 5e9})
    assert with_caps.get("source") == "marketcap", with_caps.get("source")
    print("OK BL fallback tespit edildi (equal_weight_fallback / marketcap)")


def test_bl_saglik_uyarisi():
    h = rc._bl_health([], {})
    assert h["interpretable"] is False
    assert h["source"] in ("HESAPLANAMADI", "equal_weight_fallback")
    print("OK BL saglik: yorumlanamaz durum isaretlendi")


def test_kopru_join_calisir():
    bridge = {"available": True, "chokepoints": [
        {"symbol": "AAA", "name": "Alpha Inc", "verified": True, "ret_5y_pct": 100.0},
        {"symbol": "ZZZ", "name": "Yok", "verified": False, "ret_5y_pct": None},
    ]}
    rows = _fake_rows([("AAA", 12.0, 40, 0.02)])
    j = rc.join_bridge(bridge, rows)
    assert len(j) == 2
    a = [x for x in j if x["symbol"] == "AAA"][0]
    z = [x for x in j if x["symbol"] == "ZZZ"][0]
    assert a["evaluated"] is True and a["alpha_vs_bh"] == 12.0
    assert z["evaluated"] is False and z["alpha_vs_bh"] is None
    print("OK kopru: darbogaz sembolu alpha ile eslesti")


if __name__ == "__main__":
    # pytest kurulu degil — testleri dogrudan calistir
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} test gecti")
    sys.exit(1 if failed else 0)
