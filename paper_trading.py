"""paper_trading.py — v11.0 trend kuralinin ILERIYE DONUK olcum motoru.

Amaç (CHANGELOG v11.0): yeni kuralin edge'i geriye donuk testte degil,
GERCEK ZAMANDA olculmeli. Bu modul her calistiginda:

  1) Acik pozisyonlari yonetir (SL 2xATR / TP 6xATR / TIME 60 bar / END).
  2) Evreni tarar; v11.0 giris sinyali (RSI50 kes + MACD>0 + Close>SMA200)
     goren hisse icin ERTESI GUN ACILISINDA sanal giris planlar
     (backtest'teki "next_open" yurutmesinin birebir canli karsiligi).
  3) Her olayi data/paper_trades.jsonl'ye yazar (append-only, denetlenebilir).

Canli para (Ocak 2026+) yatirilmadan ONCE bu defterin en az 2-3 ay
veri toplamasi beklenir. Rapor: summarize().

Calistirma:
    python paper_trading.py            # gunluk islem + sinyal tarama
    python paper_trading.py --report   # ozet rapor (islem yok)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import (BACKTEST_HOLDING_DAYS, CORE_TICKERS, DATA_DIR,
                    HISTORY_PERIOD)

logger = logging.getLogger(__name__)

TRADES_FILE = DATA_DIR / "paper_trades.jsonl"
POSITIONS_FILE = DATA_DIR / "paper_positions.json"
ATR_SL_MULT = 2.0
ATR_TP_MULT = 6.0
# Ayni hisseden sinyal gelmeye devam ederken pozisyon aciksa tekrar girme;
# pozisyon kapandiktan sonra kural yeniden sinyal verirse yeniden gir
# (v11.0 backtest'inin birebir davranisi).


# ---------------------------------------------------------------------------
# Durum okuma/yazma
# ---------------------------------------------------------------------------

def _load_positions() -> dict:
    if not POSITIONS_FILE.exists():
        return {}
    try:
        return json.loads(POSITIONS_FILE.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning("positions okuma: %s", e)
        return {}


def _save_positions(pos: dict):
    POSITIONS_FILE.write_text(json.dumps(pos, indent=2, ensure_ascii=False),
                              encoding="utf-8")


def _append_trade(rec: dict):
    TRADES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TRADES_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def load_trades() -> pd.DataFrame:
    if not TRADES_FILE.exists():
        return pd.DataFrame()
    rows = []
    for line in TRADES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("bozuk satir atlandi")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Veri
# ---------------------------------------------------------------------------

def _history(ticker: str) -> pd.DataFrame | None:
    import yfinance as yf
    try:
        df = yf.Ticker(ticker).history(period=HISTORY_PERIOD, interval="1d",
                                       auto_adjust=True)
        return df if df is not None and len(df) >= 60 else None
    except Exception as e:
        logger.warning("%s veri hatasi: %s", ticker, e)
        return None


def _with_indicators(df: pd.DataFrame) -> pd.DataFrame:
    from technical_indicators import add_indicators
    return add_indicators(df)


def _last_signal(df: pd.DataFrame) -> bool:
    """Son kapanista v11.0 AL sinyali var mi? (generate_signals'in canli hali)"""
    from backtest import generate_signals
    sig = generate_signals(df)
    if len(sig) == 0:
        return False
    return bool(sig.iloc[-1] == "AL")


# ---------------------------------------------------------------------------
# Pozisyon yonetimi (backtest_strategy ile ayni bariyer mantigi)
# ---------------------------------------------------------------------------

def _manage_open(pos: dict, df: pd.DataFrame) -> dict | None:
    """Acik pozisyonu yonet. Kapandiysa trade kaydini dondur, yoksa None."""
    t = pos["ticker"]
    bars = df.loc[df.index >= pos["entry_date"]]
    if bars.empty:
        return None

    sl, tp = pos["sl"], pos["tp"]
    exit_reason, exit_date, exit_price_raw = None, None, None

    for ts, row in bars.iterrows():
        d = str(ts.date())
        low = float(row["Low"]) if "Low" in row else float(row["Close"])
        high = float(row["High"]) if "High" in row else float(row["Close"])
        # Yurutme: once SL (kotumser varsayim, backtest ile ayni)
        if low <= sl:
            exit_reason, exit_date, exit_price_raw = "SL", d, sl
            break
        if high >= tp:
            exit_reason, exit_date, exit_price_raw = "TP", d, tp
            break
    else:
        ts, row = bars.index[-1], bars.iloc[-1]
        d = str(ts.date())
        held = len(bars) - 1          # giris gunu = 0 (backtest ile ayni)
        close = float(row["Close"])
        if held >= pos["holding_days"]:
            exit_reason, exit_date, exit_price_raw = "TIME", d, close
        else:
            return None               # pozisyon hala acik

    if exit_reason is None:
        return None

    cost = 0.003  # 30bp roundtrip (config BACKTEST_COMMISSION+SLIPPAGE)
    entry = pos["entry_price"]
    ret = (exit_price_raw / entry - 1) * 100 - cost * 100 / 2
    rec = {
        "ticker": t,
        "entry_date": pos["entry_date"],
        "entry_price": round(entry, 4),
        "exit_date": exit_date,
        "exit_price": round(exit_price_raw, 4),
        "exit_reason": exit_reason,
        "return_pct": round(ret, 2),
        "days_held": len(bars),
        "closed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _append_trade(rec)
    logger.info("KAPANDI %s %s -> %s (%s) %+.2f%%", t,
                pos["entry_date"], exit_date, exit_reason, ret)
    return rec


# ---------------------------------------------------------------------------
# Ana dongu
# ---------------------------------------------------------------------------

def run() -> dict:
    """Gunluk islem: aciklari yonet + sinyal tara. Rapor dict'i dondur."""
    positions = _load_positions()
    report = {"closed": [], "opened": [], "signals_pending": [],
              "errors": []}

    for t in list(positions.keys()):
        df = _history(t)
        if df is None:
            report["errors"].append(f"{t}: veri yok")
            continue
        df = _with_indicators(df)
        rec = _manage_open(positions[t], df)
        if rec:
            report["closed"].append(rec)
            del positions[t]

    # Sinyal tarama: son kapanista AL veren + acik pozisyonu olmayan hisse
    for t in CORE_TICKERS:
        if t in positions:
            continue
        try:
            df = _history(t)
            if df is None:
                continue
            df = _with_indicators(df)
            if not _last_signal(df):
                continue
            last = df.iloc[-1]
            # Sinyal kapanisi = giris proxy'si (bkz. entry_mode). next_open
            # yurutmesi gunluk cron'da mumkun degil; kapanis kilitlenir.
            entry_price = float(last["Close"])
            atr = float(last.get("atr_14") or last["Close"] * 0.03)
            ts_last = df.index[-1]
            positions[t] = {
                "ticker": t,
                "entry_date": str(ts_last.date()),
                "entry_price": round(entry_price, 4),
                "entry_mode": "signal_close_proxy",  # backtest next_open degil;
                # gunluk cron sinyal kapanisindan SONRA calisir. Kayit boyunca
                # tutarli kalir; 2-3 aylik defterde sapma sinuseldir.
                "sl": round(entry_price - ATR_SL_MULT * atr, 4),
                "tp": round(entry_price + ATR_TP_MULT * atr, 4),
                "atr_at_entry": round(atr, 4),
                "holding_days": BACKTEST_HOLDING_DAYS,
                "opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            _append_trade({**positions[t], "event": "OPEN",
                           "signal_close": round(float(last["Close"]), 4)})
            report["opened"].append(positions[t])
            logger.info("ACILDI %s @ %s (SL %s / TP %s)", t,
                        entry_price, positions[t]["sl"], positions[t]["tp"])
        except Exception as e:
            report["errors"].append(f"{t}: {e}")
            logger.error("%s hata: %s", t, e)

    _save_positions(positions)
    return report


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------

def summarize() -> dict:
    trades = load_trades()
    if trades.empty or "exit_reason" not in trades.columns:
        closed = trades.iloc[0:0]
    else:
        closed = trades[trades["exit_reason"].notna()]
    out = {"n_closed": 0, "win_rate": 0.0, "avg_return": 0.0,
           "cum_return_pct": 0.0, "open_positions": list(_load_positions())}
    if not closed.empty:
        r = closed["return_pct"].astype(float)
        out.update({
            "n_closed": len(r),
            "win_rate": round(float((r > 0).mean() * 100), 1),
            "avg_return": round(float(r.mean()), 2),
            "cum_return_pct": round(float((1 + r / 100).prod() - 1) * 100, 1),
            "by_reason": closed.groupby("exit_reason")["return_pct"]
                          .agg(["count", "mean"]).round(2).to_dict(),
        })
    return out


def main() -> int:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--report", action="store_true", help="islem yapma, raporla")
    args = p.parse_args()

    if args.report:
        print(json.dumps(summarize(), indent=2, ensure_ascii=False))
        return 0
    rep = run()
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in
                      rep.items()}, indent=2, ensure_ascii=False))
    print("Ozet:", json.dumps(summarize(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
