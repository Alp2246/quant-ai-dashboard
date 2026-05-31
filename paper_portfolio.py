"""
paper_portfolio.py - Sanal portfoy simulasyonu (paper trading).

Mantik:
  - Kullanici her hisseye sabit USD miktari (default $1000) yatirir.
  - Yatirim **anindaki** fiyat kilitlenir -> hisse adedi (shares) = USD / fiyat.
  - O andan itibaren toplam portfoy degeri canli olarak izlenir.
  - Veri json dosyasinda kalir; tekrar acildiginda baslangic ayni kalir.

Dosya: data/paper_portfolio.json
Format:
  {
    "created_at":  "2026-05-27T15:30:00",
    "per_ticker_usd": 1000.0,
    "positions": {
       "WOLF": {"start_date": "...", "start_price": 12.34, "shares": 81.0,
                "invested": 1000.0, "currency": "USD"},
       ...
    }
  }
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from config import DATA_DIR, TICKERS

logger = logging.getLogger(__name__)

PAPER_FILE = DATA_DIR / "paper_portfolio.json"
DEFAULT_PER_TICKER_USD = 1000.0


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def _load() -> dict:
    if not PAPER_FILE.exists():
        return {}
    try:
        with open(PAPER_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        logger.warning("paper portfolio okuma: %s", e)
        return {}


def _save(state: dict):
    PAPER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PAPER_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Fiyat
# ---------------------------------------------------------------------------

def _today_price(ticker: str) -> Optional[tuple[float, str]]:
    """Bugunku son kapanis fiyatini dondur (price, currency)."""
    try:
        t = yf.Ticker(ticker)
        # Once fast_info (cabuk)
        try:
            fi = t.fast_info
            price = (getattr(fi, "last_price", None)
                       or getattr(fi, "lastPrice", None))
            curr = getattr(fi, "currency", "USD") or "USD"
            if price and float(price) > 0:
                return float(price), str(curr)
        except Exception:
            pass
        # Fallback: 1-gunluk history
        df = t.history(period="5d", auto_adjust=True)
        if not df.empty:
            return float(df["Close"].iloc[-1]), "USD"
    except Exception as e:
        logger.warning("%s fiyat alinamadi: %s", ticker, e)
    return None


def initialize(tickers: list[str],
                per_ticker_usd: float = DEFAULT_PER_TICKER_USD,
                force_reset: bool = False) -> dict:
    """
    Paper portfoyu ilk defa kur veya yeni tickerleri ekle.
    force_reset=True ise sil ve sifirdan kur.

    Returns: tam state dict.
    """
    state = {} if force_reset else _load()
    if not state:
        state = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "per_ticker_usd": float(per_ticker_usd),
            "positions": {},
        }

    positions = state.setdefault("positions", {})
    state.setdefault("per_ticker_usd", float(per_ticker_usd))

    for t in tickers:
        if t in positions and not force_reset:
            continue  # zaten alindi - baslangic kilitli
        q = _today_price(t)
        if q is None:
            logger.warning("%s baslangic fiyati alinamadi, atlandi", t)
            continue
        price, currency = q
        usd = float(state["per_ticker_usd"])
        shares = round(usd / price, 6)
        positions[t] = {
            "start_date":  datetime.now().isoformat(timespec="seconds"),
            "start_price": round(price, 4),
            "shares":      shares,
            "invested":    round(usd, 2),
            "currency":    currency,
        }
        logger.info("paper: %s @ %.4f - %.4f shares", t, price, shares)

    _save(state)
    return state


def reset() -> None:
    """Paper portfoyu sil."""
    if PAPER_FILE.exists():
        PAPER_FILE.unlink()


def get_state() -> dict:
    return _load()


# ---------------------------------------------------------------------------
# Anlik degerleme
# ---------------------------------------------------------------------------

def current_value(state: dict | None = None,
                    quotes: dict[str, float] | None = None) -> dict:
    """
    Mevcut portfoy degerini hesapla.

    quotes parametresi verilirse onun fiyatlari kullanilir (cache hit -
    Streamlit baglamlari icin), aksi halde yfinance'den canli cekilir.

    Returns:
      {
        "total_invested": float,
        "total_value":    float,
        "total_pnl":      float,
        "total_pnl_pct":  float,
        "per_ticker": {
          ticker: {invested, shares, start_price, current_price,
                    value, pnl, pnl_pct, days_held}
        }
      }
    """
    state = state or _load()
    if not state or not state.get("positions"):
        return {"total_invested": 0, "total_value": 0,
                "total_pnl": 0, "total_pnl_pct": 0, "per_ticker": {}}

    per = {}
    total_inv = 0.0
    total_val = 0.0
    now = datetime.now()
    for t, pos in state["positions"].items():
        if quotes and t in quotes:
            cur = float(quotes[t])
        else:
            q = _today_price(t)
            cur = q[0] if q else pos["start_price"]
        inv = float(pos["invested"])
        shares = float(pos["shares"])
        val = shares * cur
        pnl = val - inv
        pnl_pct = (pnl / inv * 100) if inv > 0 else 0.0
        try:
            start = datetime.fromisoformat(pos["start_date"])
            days = max(1, (now - start).days)
        except Exception:
            days = 1
        per[t] = {
            "invested":      round(inv, 2),
            "shares":        round(shares, 6),
            "start_price":   round(float(pos["start_price"]), 4),
            "current_price": round(cur, 4),
            "value":         round(val, 2),
            "pnl":           round(pnl, 2),
            "pnl_pct":       round(pnl_pct, 2),
            "days_held":     days,
            "start_date":    pos["start_date"],
        }
        total_inv += inv
        total_val += val

    tot_pnl = total_val - total_inv
    tot_pct = (tot_pnl / total_inv * 100) if total_inv > 0 else 0.0
    return {
        "total_invested": round(total_inv, 2),
        "total_value":    round(total_val, 2),
        "total_pnl":      round(tot_pnl, 2),
        "total_pnl_pct":  round(tot_pct, 2),
        "per_ticker":     per,
        "created_at":     state.get("created_at"),
    }


# ---------------------------------------------------------------------------
# Tarihsel toplam deger (zaman serisi)
# ---------------------------------------------------------------------------

def value_history(state: dict | None = None,
                    histories: dict[str, pd.DataFrame] | None = None
                    ) -> pd.DataFrame:
    """
    Her gun icin toplam portfoy degerini hesapla (baslangic gununden itibaren).

    histories: {ticker: DataFrame(Close)} verilirse o cache kullanilir
               (Streamlit ile entegrasyon). Aksi halde yfinance'den cekilir.

    Returns: DataFrame(index=Date, columns=['portfoy_value', 'invested'])
    """
    state = state or _load()
    positions = state.get("positions", {})
    if not positions:
        return pd.DataFrame(columns=["portfoy_value", "invested"])

    start_dates = []
    for pos in positions.values():
        try:
            start_dates.append(datetime.fromisoformat(pos["start_date"]))
        except Exception:
            pass
    if not start_dates:
        return pd.DataFrame()
    global_start = min(start_dates).date()

    # Her ticker icin Close serisini start tarihinden itibaren al
    series_map = {}
    for t, pos in positions.items():
        try:
            if histories and t in histories and histories[t] is not None:
                df = histories[t]
            else:
                df = yf.Ticker(t).history(
                    start=global_start.isoformat(),
                    auto_adjust=True,
                )
            if df is None or df.empty or "Close" not in df.columns:
                continue
            s = df["Close"].copy()
            # tz-naive cast
            try:
                s.index = pd.to_datetime(s.index).tz_localize(None)
            except (TypeError, AttributeError):
                s.index = pd.to_datetime(s.index)
            # her hisse kendi start_date'inden once 0 olmali
            try:
                ts_start = pd.to_datetime(pos["start_date"]).tz_localize(None)
            except Exception:
                ts_start = pd.to_datetime(pos["start_date"])
            s = s[s.index >= ts_start.normalize()]
            series_map[t] = s * float(pos["shares"])
        except Exception as e:
            logger.warning("paper value_history %s: %s", t, e)

    if not series_map:
        return pd.DataFrame(columns=["portfoy_value", "invested"])

    # Birlestir + forward fill (tatil gunleri icin)
    df_all = pd.concat(series_map, axis=1).sort_index()
    df_all = df_all.ffill().fillna(0)
    total = df_all.sum(axis=1)

    invested = _total_invested(state)
    out = pd.DataFrame({
        "portfoy_value": total.values,
        "invested":      invested,
    }, index=total.index)
    return out


def get_default_tickers() -> list[str]:
    return list(TICKERS)


def _total_invested(state: dict) -> float:
    positions = state.get("positions", {})
    return sum(float(p.get("invested", 0)) for p in positions.values())


# ---------------------------------------------------------------------------
# Canli zaman serisi (bugun basladiysa bile grafik dolu)
# ---------------------------------------------------------------------------

def live_value_series(state: dict | None = None,
                       quotes: dict[str, float] | None = None,
                       histories: dict[str, pd.DataFrame] | None = None
                       ) -> pd.DataFrame:
    """
    Portfoy deger zaman serisi. Baslangic gunu + bugun canli nokta garanti.
    Kolonlar: portfoy_value, invested, spy_benchmark (esit agirlikli SPY)
    """
    state = state or _load()
    positions = state.get("positions", {})
    if not positions:
        return pd.DataFrame()

    invested_line = _total_invested(state)

    # Tarihsel portfoy (mumkunse)
    ts = value_history(state=state, histories=histories)
    if ts.empty:
        ts = pd.DataFrame(columns=["portfoy_value", "invested"])

    # Canli bugun noktasi
    val = current_value(state=state, quotes=quotes)
    now = pd.Timestamp.now().normalize()
    live_row = pd.DataFrame({
        "portfoy_value": [val["total_value"]],
        "invested":      [invested_line],
    }, index=[now])

    if ts.empty:
        combined = live_row
    else:
        combined = pd.concat([ts, live_row])
        combined = combined[~combined.index.duplicated(keep="last")]

    combined["invested"] = invested_line
    combined = combined.sort_index()

    # Baslangic + simdi: ayni gunde basladiysa bile 2 nokta (cizgi icin)
    try:
        starts = [datetime.fromisoformat(p["start_date"]) for p in positions.values()]
        t0 = pd.Timestamp(min(starts))
        t_now = pd.Timestamp.now()
        anchor = pd.DataFrame({
            "portfoy_value": [invested_line, val["total_value"]],
            "invested":      [invested_line, invested_line],
        }, index=[t0, t_now])
        if combined.empty:
            combined = anchor
        else:
            combined = pd.concat([combined, anchor])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
        # Hala tek nokta ise yapay 1 saat once ekle
        if len(combined) < 2:
            t_prev = t_now - pd.Timedelta(hours=1)
            extra = pd.DataFrame({
                "portfoy_value": [invested_line],
                "invested":      [invested_line],
            }, index=[t_prev])
            combined = pd.concat([extra, combined]).sort_index()
    except Exception:
        pass

    # SPY benchmark: ayni baslangictan esit agirlikli yatirim
    try:
        t0 = combined.index.min()
        spy = yf.Ticker("SPY").history(start=t0.date().isoformat(), auto_adjust=True)
        if not spy.empty and len(combined) >= 1:
            spy.index = pd.to_datetime(spy.index)
            try:
                spy.index = spy.index.tz_localize(None)
            except Exception:
                pass
            spy0 = float(spy["Close"].iloc[0])
            spy_norm = (spy["Close"] / spy0) * invested_line
            combined = combined.join(spy_norm.rename("spy_benchmark"), how="left")
            combined["spy_benchmark"] = combined["spy_benchmark"].ffill()
    except Exception as e:
        logger.debug("SPY benchmark: %s", e)
        combined["spy_benchmark"] = invested_line

    return combined


# ---------------------------------------------------------------------------
# Aylik DCA projeksiyonu
# ---------------------------------------------------------------------------

def suggest_dca_return(state: dict | None = None,
                        quotes: dict[str, float] | None = None) -> float:
    """
    Portfoyun mevcut bilesimine gore makul bir DCA yillik getiri varsayimi
    onerir. portfolio_scenarios'in 10y BASE etkin CAGR'i baz alinir.
    Tipik: %3-8 araliginda (spekulatif teknoloji sepeti, gercekci).
    """
    try:
        sc = portfolio_scenarios(state=state, quotes=quotes)
        inv = sc["current"]["invested"]
        base10 = sc["scenarios"]["10y"]["base"]
        if inv > 0 and base10 > 0:
            cagr = ((base10 / inv) ** (1/10) - 1) * 100
            return round(max(-5.0, min(cagr, 18.0)), 1)
    except Exception:
        pass
    return 6.0


def dca_projection(monthly_usd: float = 500.0,
                    months: int = 12,
                    annual_return_pct: float | None = None) -> pd.DataFrame:
    """
    Baslangic portfoye her ay ekleme simulasyonu (gelecek projeksiyon).
    annual_return_pct: None ise portfoy bilesimine gore dinamik onerilir.
    """
    if annual_return_pct is None:
        annual_return_pct = suggest_dca_return()
    state = _load()
    if not state.get("positions"):
        return pd.DataFrame()
    base = current_value(state=state)
    start_val = base["total_value"]
    start_inv = base["total_invested"]
    monthly_r = (1 + annual_return_pct / 100) ** (1 / 12) - 1

    rows = []
    val = start_val
    inv = start_inv
    today = pd.Timestamp.now().normalize()
    rows.append({"ay": 0, "tarih": today, "yatirilan": inv,
                  "deger": val, "k_z_pct": 0.0})

    for m in range(1, months + 1):
        inv += monthly_usd
        val = val * (1 + monthly_r) + monthly_usd
        pnl_pct = (val - inv) / inv * 100 if inv > 0 else 0
        rows.append({
            "ay": m,
            "tarih": today + pd.DateOffset(months=m),
            "yatirilan": round(inv, 2),
            "deger": round(val, 2),
            "k_z_pct": round(pnl_pct, 2),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Gelecek senaryolar (1y / 5y / 10y)
# ---------------------------------------------------------------------------

def portfolio_scenarios(state: dict | None = None,
                          quotes: dict[str, float] | None = None,
                          results: dict | None = None) -> dict:
    """
    Hisse-bazli, GERCEKCI senaryo modeli.

    Her hisse icin:
      - Sektor CAGR'i (sector_tam'dan) baz alinir
      - Spekulatif hisselere iflas/yarisi riski uygulanir
      - 20x global hard cap her hisseye uygulanir
      - Per-ticker cap (NVTS $100 vb.) uygulanir
      - Kotumser senaryoda spekulatif hisselerin %50'si '0' kabul edilir
        (basari oranina gore portfoy ortalamasi)
      - SPY proxy ortalamasi gozlenir (10y ~7-10%)

    Bu, '20% CAGR herseye' yerine MAKUL bir pencere uretir.
    """
    from sector_tam import (
        get_global_cagr_band, get_ticker_max_cagr_10y,
        get_ticker_price_cap_10y, get_sector, SECTOR_TAM_CAGR_PCT,
        get_global_price_cap_multiplier,
    )
    try:
        from strategic_overlays import SPECULATIVE_TICKERS
    except Exception:
        SPECULATIVE_TICKERS = set()

    state = state or _load()
    val = current_value(state=state, quotes=quotes)

    global_min, global_max = get_global_cagr_band()  # 15..25
    global_cap_mult = get_global_price_cap_multiplier()  # 20x

    def _ticker_cagr(t: str, scenario: str) -> tuple[float, float]:
        """
        Hisseye-ozel CAGR ve 'success probability' dondur.

        Akademik kalibrasyon (Bessembinder 2018 - hisse senedi getiri
        dagilimi). Kucuk-cap spekulatif teknolojide:
          - %50+ uzun vadede S&P'yi yenemez
          - %20'si toplam degerin %80'ini yaratir
        Bu yuzden 'sektor CAGR'i' hisseye dogrudan uygulanamaz, agir iskonto
        edilmelidir.

        scenario: 'pessimistic' / 'base' / 'optimistic'
        Returns: (cagr_pct, p_success)
        """
        sec = get_sector(t)
        sector_cagr = SECTOR_TAM_CAGR_PCT.get(sec, 10.0)
        max_per_ticker = get_ticker_max_cagr_10y(t)  # NVTS 20% vb.
        if max_per_ticker is not None:
            sector_cagr = min(sector_cagr, max_per_ticker)

        is_spec = t.upper() in SPECULATIVE_TICKERS

        # IDEAL absolut limit (hicbir hisse 10y bunu surdurulebilir gecmez):
        ABS_MAX_CAGR = 22.0   # NVDA-class moat dahi ~%25-30 uzun vade tutamaz
        ABS_MIN_CAGR_PES = -25.0

        if scenario == "pessimistic":
            # Cogu spekulatif teknoloji daralma/iflas; istikrarli moonshot
            # bile drawdown yer
            cagr = ABS_MIN_CAGR_PES if is_spec else -8.0
            p_success = 0.30 if is_spec else 0.85   # %30 hayatta = %70 buyuk kayip
        elif scenario == "optimistic":
            # Tarihin en iyi 10 yili: hisseye sektor CAGR'inin yarisi,
            # toplam %22 ust sinir
            cagr = min(sector_cagr * 0.55, ABS_MAX_CAGR)
            p_success = 0.80 if is_spec else 0.95
        else:  # base (Bessembinder beklenti)
            # Sektor CAGR'inin %35'i + spekulatif iskonto
            cagr = min(sector_cagr * 0.35, 12.0)   # %12 portfoy ust siniri
            p_success = 0.55 if is_spec else 0.85
        return cagr, p_success

    def _future_value(t: str, pos: dict, years: int,
                       cagr: float, p_success: float, cur_price: float) -> float:
        """Hisse basina projeksiyon (20x cap + per-ticker cap uygulanir)."""
        shares = float(pos["shares"])
        invested = float(pos["invested"])

        # Hisse fiyat projeksiyonu
        future_price = cur_price * ((1 + cagr / 100) ** years)

        # GLOBAL 20x cap (10y horizon icin; daha kisa vadede orantili)
        cap_mult_horizon = 1 + (global_cap_mult - 1) * (years / 10)
        global_cap_price = cur_price * cap_mult_horizon
        future_price = min(future_price, global_cap_price)

        # Per-ticker hard cap (NVTS $100 vb.)
        per_cap = get_ticker_price_cap_10y(t)
        if per_cap is not None:
            per_cap_horizon = cur_price + (per_cap - cur_price) * (years / 10)
            per_cap_horizon = max(per_cap_horizon, cur_price)
            future_price = min(future_price, per_cap_horizon)

        future_price = max(future_price, 0.01)
        gross_value = shares * future_price

        # Basari olasiligi: ortalama = p_success * full_value + (1-p)*partial
        # Basarisizlik degeri senaryoya gore degisir:
        #   pessimistic: %10 (neredeyse sifir)
        #   base:        %25
        #   optimistic:  %40 (hayatta kalir ama az kazanir)
        failure_pct = 0.10 if cagr < 0 else (0.25 if cagr < 15 else 0.40)
        failure_value = invested * failure_pct
        expected = p_success * gross_value + (1 - p_success) * failure_value
        return expected

    positions = state.get("positions", {})
    per_ticker_view = {scenario: {} for scenario in
                         ("pessimistic", "base", "optimistic")}

    scenarios = {}
    for label, years in [("1y", 1), ("5y", 5), ("10y", 10)]:
        sc_data = {}
        for scenario in ("pessimistic", "base", "optimistic"):
            total = 0.0
            for t, pos in positions.items():
                if quotes and t in quotes:
                    cur = float(quotes[t])
                else:
                    cur = float(pos["start_price"])
                cagr, p_s = _ticker_cagr(t, scenario)
                fv = _future_value(t, pos, years, cagr, p_s, cur)
                total += fv
                if label == "10y":
                    per_ticker_view[scenario][t] = {
                        "cagr_pct":   round(cagr, 1),
                        "p_success":  p_s,
                        "future_val": round(fv, 2),
                    }
            sc_data[scenario] = round(total, 2)
        sc_data["years"] = years
        scenarios[label] = sc_data

    return {
        "current": {
            "value":    val["total_value"],
            "invested": val["total_invested"],
            "pnl_pct":  val["total_pnl_pct"],
        },
        "scenarios": scenarios,
        "cagr_band": (global_min, global_max),
        "per_ticker_10y": per_ticker_view,
        "notes": [
            "Sektor CAGR'i baz alinir; her hisseye ayri uygulanir.",
            "Spekulatif hisselerde basari olasiligi <100% (Lopez de Prado).",
            f"Global 20x ({global_cap_mult:.0f}x) hard cap her hisseye uygulanir.",
            "Per-ticker cap (NVTS $100 vb.) ayrica devreye girer.",
            "Basarisizlik = yatirimin %30'u (toptan iflas degil).",
        ],
    }
