# -*- coding: utf-8 -*-
"""decision_log.py - quant-dashboard'un kendi karar kaydi + kalibrasyon motoru.

Aleabito Monitor'daki decision_log/verdict_scorecard deseninin bu projenin
kendi dilinde karsiligi. Amaç: "geçen ay AL/DIKKAT/BEKLE dediklerimiz bugün
ne durumda?" sorusunu veriyle cevaplamak. Iki sistem (aleabito + bu) birbirini
bagimsiz denetler.

Veri modeli: data/decision_log.json = {"YYYY-MM-DD:TICKER": satir}
  satir = {date, ticker, master_score, verdict, allow_push, gates_reasons,
           ret_30d, bench_30d, alpha_30d, resolved_date}

Aksiyon:
  1) score_job her gun calisirken log_daily(results) cagrilir (bir satir/
     hisse/gun; ayni gun tekrar koşulursa uzerine yazar).
  2) resolve() 30 gunu doldurmus cozulmemis satirlari fiyat gecmisiyle
     kapatir (hisse getirisi - SMH getirisi = alpha_30d).
  3) scorecard() verdict bazli ortalama alpha + pencere_edge + hit rate
     uretir; n<30 olan her kova "ORNEKLEM YETERSIZ" damgasi tasir.

Bu modul YALNIZCA okuma/yazma + saf matematik icerir; ag cagrisi yalnizca
resolve() icinde yapilir (gunluk cron'da bir kez).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

LOG_FILE = DATA_DIR / "decision_log.json"
RESOLVE_AFTER_DAYS = 30
MIN_N = 30
BENCHMARK_TICKER = "SMH"


# ---------------------------------------------------------------------------
# Kayit
# ---------------------------------------------------------------------------

def _load() -> dict:
    if not LOG_FILE.exists():
        return {}
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning("decision_log okuma: %s", e)
        return {}


def _save(rows: dict):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                        encoding="utf-8")


def log_daily(results: dict, when: date | None = None) -> int:
    """score_job'un urettigi {ticker: sonuc} sozlugunu kayda isler.

    Ayni gun icin tekrar cagrida uzerine yazar (guncel skor korunur).
    Hata alan hisseler (results[t]['error']) kayda girmez.
    Donus: yazilan satir sayisi.
    """
    when = when or date.today()
    rows = _load()
    n = 0
    for t, r in results.items():
        if not isinstance(r, dict) or r.get("error"):
            continue
        if r.get("master_score") is None or not r.get("verdict"):
            continue
        key = f"{when.isoformat()}:{t}"
        old = rows.get(key, {})
        rows[key] = {
            "date": when.isoformat(),
            "ticker": t,
            "master_score": float(r["master_score"]),
            "verdict": r["verdict"],
            "allow_push": bool(r.get("allow_push", True)),
            "gates_reasons": (r.get("gates") or {}).get("reasons", [])[:3],
            # Cozum alanlari: eski kayit korunur (resolve tek yazar)
            "ret_30d": old.get("ret_30d"),
            "bench_30d": old.get("bench_30d"),
            "alpha_30d": old.get("alpha_30d"),
            "resolved_date": old.get("resolved_date"),
        }
        n += 1
    _save(rows)
    return n


# ---------------------------------------------------------------------------
# Cozumleme (30 gun sonra ne oldu?)
# ---------------------------------------------------------------------------

def _close_on_or_before(closes, day: date) -> float | None:
    """DatetimeIndex'li Close serisinde verilen gunden onceki son kapanis."""
    s = closes[closes.index.date <= day]
    if s.empty:
        return None
    return float(s.iloc[-1])


def resolve(today: date | None = None, history_fn=None) -> dict:
    """Cozulmemis ve 30+ gunluk satirlari kapat.

    history_fn(ticker, start_date) -> DataFrame (Close kolonlu) cagrisi
    verilir; verilmezse yfinance kullanilir. Ag erisimi testlerde taklit
    edilir (history_fn ile).
    Donus: {resolved: n, errors: [...]}
    """
    today = today or date.today()
    rows = _load()
    pending = [k for k, s in rows.items()
               if s.get("alpha_30d") is None
               and (today - date.fromisoformat(s["date"])).days >= RESOLVE_AFTER_DAYS]
    if not pending:
        return {"resolved": 0, "errors": []}

    if history_fn is None:
        import yfinance as yf
        history_fn = lambda t, start: yf.Ticker(t).history(  # noqa: E731
            start=start.isoformat(), auto_adjust=True)

    bench_df = history_fn(BENCHMARK_TICKER, date.fromisoformat(
        min(rows[k]["date"] for k in pending)))
    if bench_df is None or bench_df.empty:
        return {"resolved": 0, "errors": ["benchmark verisi yok"]}
    bench_close = bench_df["Close"]

    resolved, errors = 0, []
    for k in pending:
        s = rows[k]
        d0 = date.fromisoformat(s["date"])
        try:
            df = history_fn(s["ticker"], d0)
            if df is None or df.empty:
                errors.append(f"{s['ticker']}: veri yok")
                continue
            closes = df["Close"]
            p0 = _close_on_or_before(closes, d0)
            p1 = _close_on_or_before(closes, d0.fromordinal(
                d0.toordinal() + RESOLVE_AFTER_DAYS))
            b0 = _close_on_or_before(bench_close, d0)
            b1 = _close_on_or_before(bench_close, d0.fromordinal(
                d0.toordinal() + RESOLVE_AFTER_DAYS))
            if None in (p0, p1, b0, b1) or p0 <= 0 or b0 <= 0:
                errors.append(f"{s['ticker']}: eksik fiyat")
                continue
            s["ret_30d"] = round((p1 / p0 - 1) * 100, 2)
            s["bench_30d"] = round((b1 / b0 - 1) * 100, 2)
            s["alpha_30d"] = round(s["ret_30d"] - s["bench_30d"], 2)
            s["resolved_date"] = today.isoformat()
            resolved += 1
        except Exception as e:
            errors.append(f"{s['ticker']}: {e}")
    _save(rows)
    return {"resolved": resolved, "errors": errors}


# ---------------------------------------------------------------------------
# Skor karti
# ---------------------------------------------------------------------------

def scorecard(min_n: int = MIN_N) -> dict:
    """Verdict bazli performans. n<30 kovalar 'ORNEKLEM YETERSIZ' damgalidir.

    pencere_edge = AL grubu ort. alpha - digerleri ort. alpha.
    Pozitifse AL sinyalleri bilgi tasiyor; sifirin altinda ise 'alma' karari
    'al'dan iyi demektir. Hukum ancak iki grup da yeterli orneklemdeyse verilir.
    """
    rows = [s for s in _load().values() if s.get("verdict")]
    cozulmus = [s for s in rows if s.get("alpha_30d") is not None]

    def _grp(filt):
        g = [s for s in cozulmus if filt(s)]
        if not g:
            return {"n": 0, "n_alpha": 0, "avg_alpha": None, "hit_rate": None,
                    "sample_insufficient": True, "label": "ORNEKLEM YETERSIZ"}
        alphas = [s["alpha_30d"] for s in g]
        avg = sum(alphas) / len(alphas)
        hit = sum(1 for a in alphas if a > 0) / len(alphas) * 100
        yetersiz = len(g) < min_n
        return {"n": len(g), "n_alpha": len(g), "avg_alpha": round(avg, 2),
                "hit_rate": round(hit, 1), "sample_insufficient": yetersiz,
                "label": "ORNEKLEM YETERSIZ" if yetersiz else "YETERLI"}

    al = _grp(lambda s: s["verdict"] in ("AL", "PENCERE", "GUCLU AL",
                                         "KRITIK ALIM", "ALIM"))
    bekleyen = _grp(lambda s: s["verdict"] not in
                    ("AL", "PENCERE", "GUCLU AL", "KRITIK ALIM", "ALIM"))
    edge = (al["avg_alpha"] - bekleyen["avg_alpha"]
            if al["avg_alpha"] is not None and bekleyen["avg_alpha"] is not None
            else None)

    by_verdict: dict[str, dict] = {}
    for v in sorted({s["verdict"] for s in rows}):
        by_verdict[v] = _grp(lambda s, v=v: s["verdict"] == v)

    hukum = None
    if edge is not None and not al["sample_insufficient"] \
            and not bekleyen["sample_insufficient"]:
        hukum = ("AL sinyalleri bilgi tasiyor (edge pozitif)"
                 if edge > 0 else
                 "AL sinyalleri bilgi TASIMIYOR — beklemek daha iyi")
    else:
        hukum = "ORNEKLEM YETERSIZ — hukum icin iki grupta da n>=30 bekle"

    return {
        "total_rows": len(rows),
        "resolved": len(cozulmus),
        "pending": len(rows) - len(cozulmus),
        "resolve_after_days": RESOLVE_AFTER_DAYS,
        "min_n": min_n,
        "benchmark": BENCHMARK_TICKER,
        "pencere": al,
        "kontrol": bekleyen,
        "pencere_edge": round(edge, 2) if edge is not None else None,
        "by_verdict": by_verdict,
        "hukum": hukum,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    print(json.dumps(resolve(), ensure_ascii=False))
    print(json.dumps(scorecard(), ensure_ascii=False, indent=1))
