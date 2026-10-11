# -*- coding: utf-8 -*-
"""test_panels_v113.py - v11.3 panellerinin birim testleri (ag'siz).

Kapsar:
  decision_log : log_daily / resolve(history_fn taklidiyle) / scorecard
  radar_scanner: scan_row bayraklari + aday filtreleme + cache TTL
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"OK  {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {extra}")


# ---------------------------------------------------------------------------
# decision_log
# ---------------------------------------------------------------------------

def test_decision_log(tmp_path, monkeypatch=None):
    import decision_log as dlog

    # Gecici dosya yonlendirmesi (dogrudan modul sabitini degistir)
    dlog.LOG_FILE = tmp_path / "decision_log.json"

    bugun = date(2026, 10, 11)
    results = {
        "IONQ": {"master_score": 38.7, "verdict": "DIKKAT",
                 "allow_push": False, "gates": {"reasons": ["r1"]}},
        "NVDA": {"master_score": 42.1, "verdict": "BEKLE", "allow_push": False},
        "HATA": {"error": "veri yok"},
    }
    n = dlog.log_daily(results, when=bugun)
    check("log_daily 2 satir yazar (hata satiri dislanir)", n == 2)

    # Ayni gun tekrar -> uzerine yazar, satir sayisi degismez
    results["IONQ"]["master_score"] = 40.0
    dlog.log_daily(results, when=bugun)
    rows = json.loads(dlog.LOG_FILE.read_text(encoding="utf-8"))
    check("ayni gun tekrar kayit sayisini artirmaz", len(rows) == 2)
    check("tekrar yazim guncel skoru korur",
          rows[f"{bugun}:IONQ"]["master_score"] == 40.0)

    # 31 gun oncesine cozulebilir satir ekle (AL + BEKLE ikisi de olmali ki
    # pencere_edge hesaplanabilsin)
    eski = bugun - timedelta(days=31)
    dlog.log_daily({"IONQ": {"master_score": 70.0, "verdict": "AL",
                             "allow_push": True},
                    "NVDA": {"master_score": 42.0, "verdict": "BEKLE",
                             "allow_push": False}}, when=eski)
    rows = json.loads(dlog.LOG_FILE.read_text(encoding="utf-8"))
    check("eski satirlar eklendi", len(rows) == 4)

    # Sentetik fiyat gecmisi: IONQ (AL) guclu büyür, NVDA (BEKLE) SMH ile
    # ayni yurur -> AL grubu alpha'si pozitif ve daha buyuk, edge > 0 beklenir
    idx_eskiden = pd.date_range(end=pd.Timestamp(bugun.isoformat()),
                                periods=70, freq="B")

    def history_fn(ticker, start):
        base = 200.0 if ticker == "SMH" else 100.0
        fakt = {"SMH": 1.0005, "IONQ": 1.003}.get(ticker, 1.0005)
        closes = [base * fakt ** i for i in range(len(idx_eskiden))]
        return pd.DataFrame({"Close": closes}, index=idx_eskiden)

    # NOT: yukaridaki seri duz bilesik; 30 gunluk fark ~%3.0 hisse / ~%1.5 SMH.
    r = dlog.resolve(today=bugun, history_fn=history_fn)
    check("resolve en az 1 satir cozdu", r["resolved"] >= 1, str(r))
    rows = json.loads(dlog.LOG_FILE.read_text(encoding="utf-8"))
    eski_satir = rows[f"{eski}:IONQ"]
    check("cozulen satir alpha tasiyor",
          eski_satir.get("alpha_30d") is not None,
          str(eski_satir))
    check("hisse getirisi benchmark ustunde (synt bilesik)",
          eski_satir["alpha_30d"] > 0)

    sc = dlog.scorecard()
    check("scorecard toplam 4 karar gorur", sc["total_rows"] == 4)
    check("scorecard cozulmus sayisi 2", sc["resolved"] == 2)
    check("pencere_edge uretildi", sc["pencere_edge"] is not None)
    check("pencere_edge isaret dogru (AL grubu daha iyi)",
          sc["pencere_edge"] > 0)
    check("orneklem yetersiz hukmu (n<30)",
          "YETERSIZ" in sc["hukum"].upper())
    check("AL kovasi ORNEKLEM YETERSIZ damgali",
          sc["by_verdict"]["AL"]["sample_insufficient"])


# ---------------------------------------------------------------------------
# radar_scanner
# ---------------------------------------------------------------------------

def _df(n=300, vol_base=1_000_000, close_start=50.0, mom=0.0,
        vol_last_mult=1.0):
    idx = pd.date_range(end="2026-10-10", periods=n, freq="B")
    closes = [close_start * (1 + mom) ** i for i in range(n)]
    vols = [vol_base] * n
    vols[-1] = vol_base * vol_last_mult
    return pd.DataFrame({"Close": closes, "Volume": vols}, index=idx)


def test_radar_scanner(tmp_path, monkeypatch=None):
    import radar_scanner as rs

    rs.CACHE_FILE = tmp_path / "radar_scan.json"

    # Sessiz hisse: hafif dusen seri (zirvede sayilmasin), hic bayrak
    row = rs.scan_row("AAAA", _df(mom=-0.001))
    check("sessiz hisse puan 0 (watchlist, darbogaz disi)",
          row["puan"] == 0, str(row))

    # Hacim patlamasi + momentum
    row = rs.scan_row("BBBB", _df(mom=0.01, vol_last_mult=3.0))
    check("hacim patlamasi + momentum bayraklari",
          row["hacim_patlamasi"] and row["momentum_20g"])
    check("2 bayrak puani agirlik toplami (2+2+trend 1+zirve 1)",
          row["puan"] == 6, str(row["puan"]))

    # Yeni listeleme: 100 gun
    row = rs.scan_row("CBRS", _df(n=100))
    check("yeni listeleme bayragi", row["yeni_listeleme"] is True)

    # Darbogaz uyesi bayragi: LITE cekirdekte degil, yalniz darbogaz listesinde
    row = rs.scan_row("LITE", _df())
    check("darbogaz uyesi bayragi", row["darbogaz"] is True)
    check("LITE DARBOGAZ uyeligi",
          row["liste"] == "DARBOGAZ" and "LITE" not in rs.CORE_TICKERS)

    # SNDK 11.10'da cekirdege tasindi -> uyelik CEKIRDEK olmali (regresyon kilidi)
    row = rs.scan_row("SNDK", _df())
    check("SNDK artik CEKIRDEK uyeliginde",
          row["liste"] == "CEKIRDEK")

    # Dusuk likidite: $50K hacim x $50 = $2.5M < $5M esik -> damga
    row = rs.scan_row("CCCC", _df(vol_base=50_000))
    check("dusuk likidite damgasi", row["dusuk_likidite"] is True)
    row = rs.scan_row("DDDD", _df(vol_base=200_000))
    check("normal likidite damga tasimaz", row["dusuk_likidite"] is False)

    # Cache: history_fn taklidiyle tara, TTL icinde ikinci cagri ag'siz doner
    def hist(t,):
        return _df()
    res1 = rs.scan(force=True, history_fn=hist, tickers=["AAAA", "BBBB"])
    check("scan cache dosyasi yazdi", rs.CACHE_FILE.exists())
    cagri = [0]
    def hist_sayili(t):
        cagri[0] += 1
        return _df()
    res2 = rs.scan(force=False, history_fn=hist_sayili, tickers=["AAAA"])
    check("TTL icinde cache dondu (ag cagrilmadi)", cagri[0] == 0)
    check("scan satirlari sirali (puan azalan)",
          all(res1["rows"][i]["puan"] >= res1["rows"][i + 1]["puan"]
              for i in range(len(res1["rows"]) - 1)))
    check("adaylar esik filtresi",
          all(r["puan"] >= 3 for r in rs.adaylar(res1)))

    # Cache'i bayatlat -> force'suz tarama ag cagirir
    stale = json.loads(rs.CACHE_FILE.read_text(encoding="utf-8"))
    stale["scanned_at"] = (datetime.now(timezone.utc) -
                           timedelta(hours=rs.CACHE_TTL_HOURS + 1)) \
        .isoformat(timespec="seconds")
    rs.CACHE_FILE.write_text(json.dumps(stale), encoding="utf-8")
    rs.scan(force=False, history_fn=hist_sayili, tickers=["AAAA"])
    check("bayat cache'te yeniden tarama ag cagirdi", cagri[0] == 1)


# ---------------------------------------------------------------------------

def main():
    import tempfile
    for fn in (test_decision_log, test_radar_scanner):
        with tempfile.TemporaryDirectory() as td:
            fn(Path(td))
    print(f"\n{'=' * 60}\n  {PASS}/{PASS + FAIL} test gecti\n{'=' * 60}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
