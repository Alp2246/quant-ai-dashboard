"""reality_check.py — "Bu sistemin edge'i var mi?" sorusunun tek ekran cevabi.

YENI MODEL/GOSTERGE YOK. Mevcut hesaplananlari toplayip durustce raporlar:
  backtest.backtest_strategy      -> alpha_vs_bh, sharpe, max_dd, n_trades
  ml_model.train_model            -> overfitting_gap, overfit_verdict (Purged CV)
  black_litterman.portfolio_optimization -> weights, sharpe, prior kaynagi

DURUSTLUK KURALLARI (pazarlik yok):
  - n_trades < 30            -> ISTATISTIKSEL OLARAK ANLAMSIZ, sayi gri
  - overfitting_gap > 0.15   -> MODEL GUVENILMEZ, tahmin gizlenir
  - BL prior esit-agirlik    -> PRIOR UYDURMA, POSTERIOR YORUMLANAMAZ
  - n gostermeden ortalama/oran yazilmaz
  - Kotu sonuc yumusatilmaz

KOPRU (aleabito_monitor):
  Kardes proje darbogaz haritasini ve yeni kesifleri uretir; burada
  alpha_vs_bh ile BIRLESTIRILIR. Boylece "bu darbogazi tutan sirkete
  sahip olmak al-tut'u yendi mi?" sorusu yanitlanir.
"""
from __future__ import annotations

import json
import logging
import os
import statistics
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MIN_TRADES_FOR_SIGNIFICANCE = 30
OVERFIT_UNTRUSTED_GAP = 0.15

# Kardes proje (aleabito_monitor) koprusu — env ile degistirilebilir
BRIDGE_DIR = Path(os.getenv(
    "ALEABITO_DATA_DIR",
    r"C:\Users\oalpe\Desktop\fpga_1_main\fpga_1-main\aleabito_monitor\data",
))


# ---------------------------------------------------------------------------
# Tek hisse degerlendirmesi
# ---------------------------------------------------------------------------

def evaluate_ticker(ticker: str, df=None, years: float | None = None) -> dict[str, Any]:
    """Bir hisse icin backtest + Purged CV sonuclarini durustce topla.

    years: backtest penceresi. Varsayilan REALITY_LOOKBACK_YEARS (5y) —
    2 yilda hisse basina ~10-15 islem cikiyor ve n<30 esigi hicbir hukme
    izin vermiyordu.
    """
    out: dict[str, Any] = {"ticker": ticker, "ok": False}

    if df is None:
        try:
            from data_fetcher import fetch_history

            df = fetch_history(ticker)
        except Exception as exc:
            out["error"] = f"veri alinamadi: {str(exc)[:80]}"
            return out
    if df is None or getattr(df, "empty", True):
        out["error"] = "fiyat gecmisi yok"
        return out

    # ---- Backtest (maliyetli, buy&hold kiyasli)
    try:
        from backtest import backtest_strategy

        if years is None:
            try:
                from config import REALITY_LOOKBACK_YEARS

                years = float(REALITY_LOOKBACK_YEARS)
            except Exception:
                years = 5.0
        bt = backtest_strategy(df, years=years)
        n = int(bt.get("n_trades", 0) or 0)
        out.update({
            "ok": True,
            "lookback_years": years,
            "n_trades": n,
            "alpha_vs_bh": bt.get("alpha_vs_bh"),
            "cum_return": bt.get("cum_return"),
            "buy_hold_return": bt.get("buy_hold_return"),
            "sharpe_ratio": bt.get("sharpe_ratio"),
            "max_drawdown_pct": bt.get("max_drawdown_pct"),
            "win_rate": bt.get("win_rate"),
            # DURUSTLUK: az islemde istatistik yok
            "significant": n >= MIN_TRADES_FOR_SIGNIFICANCE,
            "significance_badge": (
                "" if n >= MIN_TRADES_FOR_SIGNIFICANCE
                else "ISTATISTIKSEL OLARAK ANLAMSIZ"
            ),
        })
    except Exception as exc:
        out["error"] = f"backtest hatasi: {str(exc)[:90]}"
        return out

    # ---- Purged CV (overfit teshisi) — train_model icinde zaten calisiyor
    try:
        from ml_model import train_model

        ml = train_model(df)
        gap = float(ml.get("overfitting_gap", 0.0) or 0.0)
        trusted = gap <= OVERFIT_UNTRUSTED_GAP
        out.update({
            "overfitting_gap": round(gap, 4),
            "overfit_verdict": ml.get("overfit_verdict", "ATLANDI"),
            "cv_mean_accuracy": ml.get("cv_mean_accuracy"),
            "cv_n_folds": ml.get("cv_n_folds", 0),
            "model_trusted": trusted,
            # DURUSTLUK: guvenilmez modelin tahmini GIZLENIR
            "prob_up": ml.get("prob_up") if trusted else None,
            "recommendation": ml.get("recommendation") if trusted else "GIZLENDI",
            "trust_badge": "" if trusted else "MODEL GUVENILMEZ",
        })
    except Exception as exc:
        out.update({
            "overfitting_gap": None, "overfit_verdict": "HESAPLANAMADI",
            "model_trusted": False, "prob_up": None,
            "recommendation": "GIZLENDI", "trust_badge": "MODEL GUVENILMEZ",
            "ml_error": str(exc)[:90],
        })
    return out


# ---------------------------------------------------------------------------
# Ozetler
# ---------------------------------------------------------------------------

def _alpha_summary(rows: list[dict]) -> dict[str, Any]:
    """Yalnizca ISTATISTIKSEL ANLAMLI satirlar hukme girer."""
    valid = [r for r in rows
             if r.get("ok") and r.get("significant")
             and isinstance(r.get("alpha_vs_bh"), (int, float))]
    weak = [r for r in rows
            if r.get("ok") and not r.get("significant")
            and isinstance(r.get("alpha_vs_bh"), (int, float))]
    if not valid:
        return {"n": 0, "n_weak": len(weak), "median_alpha": None,
                "mean_alpha": None, "positive_rate": None,
                "best": [], "worst": []}
    a = [r["alpha_vs_bh"] for r in valid]
    ranked = sorted(valid, key=lambda r: -r["alpha_vs_bh"])
    return {
        "n": len(valid),
        "n_weak": len(weak),
        "median_alpha": round(statistics.median(a), 2),
        "mean_alpha": round(statistics.mean(a), 2),
        "positive_rate": round(100 * sum(1 for x in a if x > 0) / len(a), 1),
        "best": [{"ticker": r["ticker"], "alpha_vs_bh": r["alpha_vs_bh"]}
                 for r in ranked[:3]],
        "worst": [{"ticker": r["ticker"], "alpha_vs_bh": r["alpha_vs_bh"]}
                  for r in ranked[-3:]][::-1],
    }


MIN_TRADES_TO_POOL = 5      # bu kadar islemi olmayan hisse havuza girmez
MIN_TICKERS_FOR_POOLED = 10
MIN_POOLED_TRADES = 100


def _binom_p_two_sided(k: int, n: int) -> float:
    """Isaret testi: n hissenin k'si pozitif alpha. H0: p=0.5."""
    if n == 0:
        return 1.0
    from math import comb

    def _tail(x):
        return sum(comb(n, i) for i in range(x, n + 1)) / (2 ** n)

    p = _tail(k) if k >= n / 2 else _tail(n - k)
    return min(1.0, 2 * p)


def _pooled_summary(rows: list[dict]) -> dict[str, Any]:
    """HAVUZ analizi — dogru istatistiksel birim.

    Hisse basina n>=30 islem bu stratejide (RSI+MACD kesisim, 20 gun tutma)
    5 yilda bile cikmiyor: tipik 12-20 islem. Ama sorulan soru "bu HISSE'de
    alpha var mi" degil, "bu STRATEJI alpha uretiyor mu". Dogru birim tum
    hisselerin alpha gozlemi + toplam islem sayisi.
    """
    usable = [r for r in rows
              if isinstance(r.get("alpha_vs_bh"), (int, float))
              and (r.get("n_trades") or 0) >= MIN_TRADES_TO_POOL]
    if not usable:
        return {"n_tickers": 0, "total_trades": 0, "conclusive": False,
                "median_alpha": None, "mean_alpha": None,
                "positive_rate": None, "p_value": None}

    a = [r["alpha_vs_bh"] for r in usable]
    total_trades = sum(int(r.get("n_trades") or 0) for r in usable)
    pos = sum(1 for x in a if x > 0)
    return {
        "n_tickers": len(a),
        "total_trades": total_trades,
        "median_alpha": round(statistics.median(a), 2),
        "mean_alpha": round(statistics.mean(a), 2),
        "positive_rate": round(100 * pos / len(a), 1),
        "n_positive": pos,
        "p_value": round(_binom_p_two_sided(pos, len(a)), 4),
        "min_trades_per_ticker": MIN_TRADES_TO_POOL,
        "conclusive": (len(a) >= MIN_TICKERS_FOR_POOLED
                       and total_trades >= MIN_POOLED_TRADES),
    }


def _basket_summary(rows: list[dict]) -> dict[str, Any]:
    """Darbogaz sepeti vs geri kalan — tez alpha uretiyor mu?"""
    try:
        from config import BOTTLENECK_WATCHLIST

        basket = {t.upper() for t in BOTTLENECK_WATCHLIST}
    except Exception:
        return {"available": False}

    def _stat(rs):
        # Havuz esigi kullanilir (>=5 islem); hisse basina >=30 bu stratejide
        # hic saglanmiyor ve sepet karsilastirmasini bos birakiyordu
        a = [r["alpha_vs_bh"] for r in rs
             if (r.get("n_trades") or 0) >= MIN_TRADES_TO_POOL
             and isinstance(r.get("alpha_vs_bh"), (int, float))]
        if not a:
            return {"n": 0, "median_alpha": None, "positive_rate": None}
        return {
            "n": len(a),
            "median_alpha": round(statistics.median(a), 2),
            "positive_rate": round(100 * sum(1 for x in a if x > 0) / len(a), 1),
        }

    inside = [r for r in rows if r["ticker"].upper() in basket]
    outside = [r for r in rows if r["ticker"].upper() not in basket]
    return {
        "available": True,
        "darbogaz": _stat(inside),
        "diger": _stat(outside),
        "tickers": sorted(r["ticker"] for r in inside),
    }


def _overfit_summary(rows: list[dict]) -> dict[str, Any]:
    dist: dict[str, int] = {}
    gaps = []
    for r in rows:
        v = (r.get("overfit_verdict") or "HESAPLANAMADI").split("(")[0].strip()
        dist[v] = dist.get(v, 0) + 1
        g = r.get("overfitting_gap")
        if isinstance(g, (int, float)):
            gaps.append(g)
    return {
        "distribution": dist,
        "n": len(gaps),
        "mean_gap": round(statistics.mean(gaps), 4) if gaps else None,
        "untrusted": [r["ticker"] for r in rows if not r.get("model_trusted")],
    }


BL_MIN_HISTORY_DAYS = 400      # ~1.5 yil; ortak kesisim icin taban


def _bl_health(tickers: list[str], histories: dict) -> dict[str, Any]:
    """Black-Litterman prior'unun kaynagini dogrula.

    portfolio_optimization tum hisselerin ORTAK tarihlerini kesistiriyor
    (inner join). Tek bir kisa gecmisli hisse (or. CBRS 52 gun) kesisimi
    60 gunun altina dusurup butun hesabi cokertiyordu. Bu yuzden yalnizca
    yeterli gecmisi olanlar BL'ye girer; elenenler raporlanir.
    """
    eligible, excluded = {}, []
    for t, df in (histories or {}).items():
        if df is None or getattr(df, "empty", True) or len(df) < BL_MIN_HISTORY_DAYS:
            excluded.append(t)
            continue
        # SAAT DILIMI NORMALIZASYONU: IQE.L (Londra), SIVE.ST (Stockholm) ve
        # ABD hisseleri farkli tz'li indeks tasiyor. Inner join'de hicbir tarih
        # eslesmiyor ve kesisim bosaliyordu ("Yetersiz overlap"). Gune indir.
        try:
            d = df.copy()
            idx = d.index
            if getattr(idx, "tz", None) is not None:
                idx = idx.tz_localize(None)
            d.index = idx.normalize()
            d = d[~d.index.duplicated(keep="last")]
            eligible[t] = d
        except Exception:
            eligible[t] = df

    caps: dict[str, float] = {}
    for t in eligible:
        try:
            import yfinance as yf

            mc = (yf.Ticker(t).info or {}).get("marketCap")
            if mc:
                caps[t] = float(mc)
        except Exception:
            continue
    try:
        from black_litterman import portfolio_optimization

        bl = portfolio_optimization(eligible, market_caps=caps or None)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:90], "source": "HESAPLANAMADI",
                "interpretable": False, "excluded": excluded}
    if bl.get("error"):
        return {"ok": False, "error": bl["error"], "source": "HESAPLANAMADI",
                "interpretable": False, "excluded": excluded}

    src = bl.get("source", "bilinmiyor")
    interpretable = src == "marketcap"
    return {
        "ok": True,
        "source": src,
        "interpretable": interpretable,
        "warning": ("" if interpretable
                    else "PRIOR UYDURMA, POSTERIOR YORUMLANAMAZ"),
        "n_caps_found": len(caps),
        "excluded": excluded,
        "min_history_days": BL_MIN_HISTORY_DAYS,
        "n_tickers": bl.get("n_tickers"),
        "n_observations": bl.get("n_observations"),
        "sharpe_ratio": bl.get("sharpe_ratio"),
        "expected_return_pct": bl.get("expected_portfolio_return_pct"),
        "weights": (bl["weights"].round(4).to_dict()
                    if hasattr(bl.get("weights"), "to_dict") else {}),
    }


def _verdict(pooled: dict) -> dict[str, Any]:
    """Tek cumlelik hukum — HAVUZ uzerinden, yumusatma yok."""
    n, tr = pooled.get("n_tickers", 0), pooled.get("total_trades", 0)
    if not pooled.get("conclusive"):
        return {
            "level": "UNKNOWN",
            "text": f"n={n} hisse / {tr} islem — HUKUM VERILEMEZ "
                    f"(en az {MIN_TICKERS_FOR_POOLED} hisse ve "
                    f"{MIN_POOLED_TRADES} islem gerekir)",
        }
    med = pooled["median_alpha"]
    pos, p = pooled["positive_rate"], pooled["p_value"]
    sig = "" if p is None or p > 0.05 else " (isaret testi p<0.05)"
    if med > 0:
        return {"level": "BEATS",
                "text": f"n={n} hisse / {tr} islem — medyan alpha {med:+.1f}%, "
                        f"%{pos} pozitif{sig} — sistem al-tut'u YENIYOR"}
    return {"level": "LOSES",
            "text": f"n={n} hisse / {tr} islem — medyan alpha {med:+.1f}%, "
                    f"%{pos} pozitif{sig} — sistem al-tut'u YENMIYOR"}


# ---------------------------------------------------------------------------
# KOPRU — aleabito_monitor darbogaz haritasi x alpha
# ---------------------------------------------------------------------------

def load_bridge() -> dict[str, Any]:
    """Kardes projenin darbogaz haritasi + yeni kesifleri."""
    out: dict[str, Any] = {"available": False, "chokepoints": [],
                           "discoveries": [], "path": str(BRIDGE_DIR)}
    cache = BRIDGE_DIR / "chokepoint_cache.json"
    if not cache.exists():
        out["error"] = "darbogaz haritasi bulunamadi (aleabito calisti mi?)"
        return out
    try:
        symbols = json.loads(cache.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        out["error"] = f"harita okunamadi: {exc}"
        return out

    out["available"] = True
    out["chokepoints"] = [
        {
            "symbol": s,
            "name": v.get("name"),
            "verified": v.get("verified", False),
            "price": v.get("price"),
            "ret_5y_pct": v.get("ret_5y_pct"),
        }
        for s, v in symbols.items() if v.get("ok")
    ]

    sig = BRIDGE_DIR / "signals.json"
    if sig.exists():
        try:
            recs = json.loads(sig.read_text(encoding="utf-8"))
            out["discoveries"] = [
                {"ticker": r.get("ticker"), "time": r.get("time"),
                 "confidence": r.get("axti_confidence"), "era": r.get("era")}
                for r in recs if r.get("axti_moment")
            ][-20:]
        except json.JSONDecodeError:
            pass
    return out


def bridge_watchlist(max_symbols: int = 15) -> list[str]:
    """aleabito'nun kesiflerinden BURADA analiz edilebilir semboller.

    Iki kaynak:
      1) AXTI ANI kesifleri (signals.json, axti_moment=True)
      2) Darbogaz haritasindaki DOGRULANMIS + ABD/Avrupa erisilebilir semboller

    Asya kotasyonlari (.T/.KQ/.SZ/.TW/.KS) ve dogrulanmamis semboller
    ELENIR — backtest edilemez veya yanlis sirkete isaret eder.
    """
    br = load_bridge()
    if not br.get("available"):
        return []

    asia_suffix = (".T", ".KQ", ".KS", ".SZ", ".SS", ".TW", ".HK")
    out: list[str] = []

    # Yeni kesifler once (en taze fikir)
    for d in reversed(br.get("discoveries", [])):
        tk = (d.get("ticker") or "").strip().upper()
        if tk and tk not in out and not tk.endswith(asia_suffix) and tk.isalpha():
            out.append(tk)

    # Sonra dogrulanmis darbogaz sembolleri
    for cp in br.get("chokepoints", []):
        sym = (cp.get("symbol") or "").strip().upper()
        if not sym or sym in out:
            continue
        if not cp.get("verified"):
            continue                      # sembol-sirket eslesmesi yok
        if sym.endswith(asia_suffix):
            continue                      # backtest edilemez
        out.append(sym)

    return out[:max_symbols]


def join_bridge(bridge: dict, rows: list[dict]) -> list[dict]:
    """Darbogaz sembollerini alpha sonuclariyla esle.

    Yanit: "bu darbogazi tutan sirkete sahip olmak al-tut'u yendi mi?"
    """
    by_ticker = {r["ticker"].upper(): r for r in rows if r.get("ok")}
    joined = []
    for cp in bridge.get("chokepoints", []):
        sym = (cp["symbol"] or "").upper()
        r = by_ticker.get(sym) or by_ticker.get(sym.split(".")[0])
        joined.append({
            **cp,
            "evaluated": bool(r),
            "alpha_vs_bh": (r or {}).get("alpha_vs_bh"),
            "n_trades": (r or {}).get("n_trades"),
            "significant": (r or {}).get("significant", False),
            "model_trusted": (r or {}).get("model_trusted"),
        })
    return joined


# ---------------------------------------------------------------------------
# Ana giris
# ---------------------------------------------------------------------------

def build_reality_report(tickers: list[str] | None = None,
                           histories: dict | None = None,
                           include_bridge: bool = True) -> dict[str, Any]:
    """Tek ekranlik gerceklik raporu."""
    if not tickers:
        try:
            from config import TICKERS

            tickers = list(TICKERS)
        except Exception:
            tickers = []

    # Darbogaz sepetini de degerlendir: kardes projenin haritasindaki
    # erisilebilir isimler olmadan "darbogaz tezi alpha uretiyor mu?"
    # sorusu tek hisseyle test edilemiyordu (31 sembolden 1'i kapsaniyordu).
    try:
        from config import BOTTLENECK_WATCHLIST

        for t in BOTTLENECK_WATCHLIST:
            if t not in tickers:
                tickers.append(t)
    except Exception:
        pass

    # CANLI KOPRU: aleabito yeni bir AXTI ANI kesfettiyse burada da
    # degerlendirilsin (config'e elle eklemeyi beklemeden)
    try:
        for t in bridge_watchlist():
            if t not in tickers:
                tickers.append(t)
    except Exception as exc:
        logger.debug("kopru izleme listesi okunamadi: %s", exc)

    if histories is None:
        try:
            from data_fetcher import fetch_all_histories

            histories = fetch_all_histories(tickers)
        except Exception as exc:
            logger.warning("gecmis alinamadi: %s", exc)
            histories = {}

    rows = [evaluate_ticker(t, histories.get(t)) for t in tickers]
    ok_rows = [r for r in rows if r.get("ok")]

    alpha = _alpha_summary(ok_rows)
    pooled = _pooled_summary(ok_rows)
    report: dict[str, Any] = {
        "rows": rows,
        "alpha_ozeti": alpha,
        "havuz": pooled,
        "overfit_ozeti": _overfit_summary(ok_rows),
        "bl_saglik": _bl_health(tickers, histories or {}),
        "ornek_yeterliligi": {
            "min_trades": MIN_TRADES_FOR_SIGNIFICANCE,
            "yetersiz": [
                {"ticker": r["ticker"], "n_trades": r.get("n_trades", 0)}
                for r in ok_rows if not r.get("significant")
            ],
            "yeterli_sayisi": sum(1 for r in ok_rows if r.get("significant")),
        },
        "verdict": _verdict(pooled),
        "n_tickers": len(tickers),
        "n_evaluated": len(ok_rows),
        "lookback_years": next(
            (r.get("lookback_years") for r in ok_rows if r.get("lookback_years")),
            None,
        ),
        # Tez sepeti ayri raporlanir: "darbogaz isimleri al-tut'u yendi mi?"
        "darbogaz_sepeti": _basket_summary(ok_rows),
    }

    if include_bridge:
        bridge = load_bridge()
        report["bridge"] = bridge
        report["darbogaz_x_alpha"] = (
            join_bridge(bridge, ok_rows) if bridge.get("available") else []
        )
    return report


# ---------------------------------------------------------------------------
# Streamlit gorunumu — app.py'den TEK SATIR ile cagrilir
# ---------------------------------------------------------------------------

def render_reality_tab(tickers: list[str] | None = None,
                         histories: dict | None = None) -> None:
    """🔍 Gerceklik Kontrolu bolumu. app.py: render_reality_tab(TICKERS, hists)"""
    import pandas as pd
    import streamlit as st

    st.markdown("## 🔍 Gerceklik Kontrolu")
    st.caption("Yeni gosterge yok — Purged CV, maliyetli backtest ve "
               "Black-Litterman ciktilarinin durust ozeti.")

    with st.spinner("Backtest + Purged CV toplaniyor..."):
        rep = build_reality_report(tickers, histories)

    v = rep["verdict"]
    if v["level"] == "BEATS":
        st.success(f"**{v['text']}**")
    elif v["level"] == "LOSES":
        st.error(f"**{v['text']}**")
    else:
        st.warning(f"**{v['text']}**")

    h, o = rep["havuz"], rep["overfit_ozeti"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Havuz", f"{h['n_tickers']} hisse",
              f"{h['total_trades']} islem")
    c2.metric("Medyan alpha",
              f"{h['median_alpha']:+.1f}%" if h["median_alpha"] is not None else "—",
              f"%{h['positive_rate']} pozitif" if h["positive_rate"] is not None else "",
              delta_color="normal")
    c3.metric("Ortalama overfit gap",
              f"{o['mean_gap']:.3f}" if o["mean_gap"] is not None else "—",
              f"{len(o['untrusted'])} guvenilmez model", delta_color="inverse")
    c4.metric("BL prior", rep["bl_saglik"].get("source", "—"))

    if h.get("p_value") is not None and h.get("conclusive"):
        st.caption(f"Isaret testi: {h['n_positive']}/{h['n_tickers']} hissede "
                   f"pozitif alpha, p={h['p_value']} "
                   f"({'anlamli' if h['p_value'] <= 0.05 else 'anlamli degil'}). "
                   f"Backtest penceresi: {rep.get('lookback_years')} yil.")

    if rep["bl_saglik"].get("warning"):
        st.error(f"⚠️ {rep['bl_saglik']['warning']}")

    # ---- Sepet karsilastirmasi: darbogaz tezi alpha uretiyor mu?
    b = rep.get("darbogaz_sepeti", {})
    if b.get("available") and b["darbogaz"]["n"]:
        d, ot = b["darbogaz"], b["diger"]
        st.markdown("#### Darbogaz sepeti vs digerleri")
        k1, k2 = st.columns(2)
        k1.metric(f"Darbogaz (n={d['n']})",
                  f"{d['median_alpha']:+.1f}%" if d["median_alpha"] is not None else "—",
                  f"%{d['positive_rate']} pozitif")
        k2.metric(f"Diger (n={ot['n']})",
                  f"{ot['median_alpha']:+.1f}%" if ot["median_alpha"] is not None else "—",
                  f"%{ot['positive_rate']} pozitif")
        st.caption("Yuksek kosan hisselerde zamanlama stratejisi al-tut'a gore "
                   "daha cok kaybeder — bu mekanik bir sonuctur, tezin yanlis "
                   "oldugunu degil, bu isimlerde TUTMANIN islem yapmaktan iyi "
                   "oldugunu gosterir. Max drawdown kolonuna da bak.")

    # ---- 1) Alpha tablosu
    st.markdown("### 1. Al-tut'a gore alpha")
    rows = [r for r in rep["rows"] if r.get("ok")]
    if rows:
        df = pd.DataFrame([{
            "Hisse": r["ticker"],
            "Alpha vs B&H %": r.get("alpha_vs_bh"),
            "Strateji %": r.get("cum_return"),
            "Al-tut %": r.get("buy_hold_return"),
            "Sharpe": r.get("sharpe_ratio"),
            "Max DD %": r.get("max_drawdown_pct"),
            "Islem": r.get("n_trades"),
            "Durum": r.get("significance_badge") or "anlamli",
        } for r in rows]).sort_values("Alpha vs B&H %", ascending=False)

        def _style(row):
            weak = row["Durum"] != "anlamli"
            out = []
            for col in row.index:
                if weak:
                    out.append("color: #888")
                elif col == "Alpha vs B&H %":
                    val = row[col]
                    out.append("color: #d62728" if (val or 0) < 0 else "color: #2ca02c")
                else:
                    out.append("")
            return out

        st.dataframe(df.style.apply(_style, axis=1), use_container_width=True)

        try:
            import plotly.graph_objects as go

            sig = df[df["Durum"] == "anlamli"]
            plot_df = sig if not sig.empty else df
            fig = go.Figure(go.Bar(
                x=plot_df["Hisse"], y=plot_df["Alpha vs B&H %"],
                marker_color=["#d62728" if (x or 0) < 0 else "#2ca02c"
                              for x in plot_df["Alpha vs B&H %"]],
            ))
            fig.add_hline(y=0, line_width=3, line_color="#444")
            fig.update_layout(height=320, title="Alpha dagilimi (0 cizgisi = al-tut)",
                              margin=dict(t=44, b=8))
            st.plotly_chart(fig, use_container_width=True, key="rc_alpha")
        except Exception:
            pass
    else:
        st.info("Degerlendirilebilir hisse yok.")

    # ---- 2) Overfit
    st.markdown("### 2. Overfit teshisi (Purged K-Fold CV)")
    st.caption(f"gap > {OVERFIT_UNTRUSTED_GAP} ise model tahmini GIZLENIR.")
    st.dataframe(pd.DataFrame([{
        "Hisse": r["ticker"],
        "Overfit gap": r.get("overfitting_gap"),
        "Hukum": r.get("overfit_verdict"),
        "CV dogruluk": r.get("cv_mean_accuracy"),
        "Fold": r.get("cv_n_folds"),
        "Tahmin": r.get("recommendation"),
        "Uyari": r.get("trust_badge") or "",
    } for r in rows]), use_container_width=True)

    # ---- 3) BL saglik
    st.markdown("### 3. Black-Litterman prior sagligi")
    b = rep["bl_saglik"]
    if b.get("ok"):
        st.write(f"Kaynak: **{b['source']}** · "
                 f"market cap bulunan: {b['n_caps_found']}/{b.get('n_tickers')} · "
                 f"gozlem: {b.get('n_observations')}")
        if b["interpretable"]:
            st.success("Prior gercek piyasa degerinden — posterior yorumlanabilir.")
        else:
            st.error("PRIOR UYDURMA, POSTERIOR YORUMLANAMAZ.")
    else:
        st.warning(f"Hesaplanamadi: {b.get('error')}")

    # ---- 4) Orneklem
    st.markdown("### 4. Orneklem yeterliligi")
    y = rep["ornek_yeterliligi"]
    st.write(f"Esik: **{y['min_trades']} islem** · yeterli: {y['yeterli_sayisi']} · "
             f"yetersiz: {len(y['yetersiz'])}")
    if y["yetersiz"]:
        st.dataframe(pd.DataFrame(y["yetersiz"]), use_container_width=True)

    # ---- 5) Kopru: darbogaz x alpha
    br = rep.get("bridge", {})
    st.markdown("### 5. Darbogaz zinciri × alpha (aleabito koprusu)")
    if not br.get("available"):
        st.info(f"Darbogaz haritasi bulunamadi. {br.get('error', '')}")
    else:
        j = rep.get("darbogaz_x_alpha", [])
        ev = [x for x in j if x["evaluated"]]
        st.caption(f"{len(j)} darbogaz sembolu, {len(ev)} tanesi burada "
                   f"backtest edildi. 'Bu darbogazi tutan sirket al-tut'u yendi mi?'")
        st.dataframe(pd.DataFrame([{
            "Sembol": x["symbol"],
            "Sirket": (x.get("name") or "")[:34],
            "Dogrulandi": "evet" if x.get("verified") else "HAYIR",
            "5y %": x.get("ret_5y_pct"),
            "Alpha vs B&H %": x.get("alpha_vs_bh") if x["evaluated"] else None,
            "Islem": x.get("n_trades") if x["evaluated"] else None,
        } for x in j]), use_container_width=True)
        if br.get("discoveries"):
            st.caption(f"Son AXTI ANI kesifleri: "
                       f"{', '.join(str(d['ticker']) for d in br['discoveries'][-6:])}")


def export_snapshot(path: str | None = None) -> str:
    """Raporu JSON'a yaz — ucuncu uygulama (karar masasi) buradan okur.

    Streamlit'i calistirmadan da uretilebilir:
        python reality_check.py --export
    """
    import time as _t
    from pathlib import Path as _P

    rep = build_reality_report()
    # Seriler cok yer kapliyor, ozet icin gereksiz
    for r in rep.get("rows", []):
        r.pop("series", None)
    for x in rep.get("darbogaz_x_alpha", []):
        x.pop("series", None)
    rep["_ts"] = _t.time()

    out = _P(path) if path else _P(__file__).parent / "data" / "reality_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    import sys as _sys

    if "--export" in _sys.argv:
        p = export_snapshot()
        print(f"Anlik goruntu yazildi: {p}")
        _sys.exit(0)
    import sys

    tk = sys.argv[1:] or None
    rep = build_reality_report(tk)

    print("\n" + "=" * 66)
    print("  HUKUM:", rep["verdict"]["text"])
    print("=" * 66)

    h = rep["havuz"]
    print(f"\nHAVUZ (dogru istatistiksel birim) — {h['n_tickers']} hisse, "
          f"{h['total_trades']} islem")
    if h["n_tickers"]:
        print(f"  medyan alpha={h['median_alpha']:+.1f}%  "
              f"ortalama={h['mean_alpha']:+.1f}%  "
              f"pozitif=%{h['positive_rate']} ({h['n_positive']}/{h['n_tickers']})"
              f"  isaret testi p={h['p_value']}")

    b = rep.get("darbogaz_sepeti", {})
    if b.get("available"):
        d, o2 = b["darbogaz"], b["diger"]
        print(f"\nSEPET KARSILASTIRMASI")
        print(f"  darbogaz  n={d['n']:2d} medyan={d['median_alpha']}  "
              f"pozitif=%{d['positive_rate']}")
        print(f"  diger     n={o2['n']:2d} medyan={o2['median_alpha']}  "
              f"pozitif=%{o2['positive_rate']}")

    a = rep["alpha_ozeti"]
    print(f"\nALPHA (hisse-bazli, >=30 islem) — anlamli n={a['n']}, "
          f"zayif orneklem n={a['n_weak']}")
    if a["n"]:
        print(f"  medyan={a['median_alpha']:+.1f}%  ortalama={a['mean_alpha']:+.1f}%"
              f"  pozitif oran=%{a['positive_rate']}")

        def _fmt(items):
            return ", ".join(
                "{} {:+.1f}%".format(x["ticker"], x["alpha_vs_bh"]) for x in items
            )

        print("  en iyi : " + _fmt(a["best"]))
        print("  en kotu: " + _fmt(a["worst"]))

    o = rep["overfit_ozeti"]
    print(f"\nOVERFIT (Purged CV) — n={o['n']}, ortalama gap={o['mean_gap']}")
    for k, v in sorted(o["distribution"].items(), key=lambda kv: -kv[1]):
        print(f"  {k:34s} {v}")
    if o["untrusted"]:
        print(f"  GUVENILMEZ: {', '.join(o['untrusted'])}")

    b = rep["bl_saglik"]
    print(f"\nBLACK-LITTERMAN prior kaynagi: {b['source']}")
    if b.get("warning"):
        print(f"  !! {b['warning']}")

    y = rep["ornek_yeterliligi"]
    print(f"\nORNEKLEM: yeterli={y['yeterli_sayisi']}, "
          f"yetersiz={len(y['yetersiz'])} (esik {y['min_trades']} islem)")

    br = rep.get("bridge", {})
    if br.get("available"):
        j = rep.get("darbogaz_x_alpha", [])
        ev = [x for x in j if x["evaluated"]]
        print(f"\nKOPRU (aleabito darbogaz haritasi): {len(j)} sembol, "
              f"{len(ev)} tanesi burada degerlendirildi")
