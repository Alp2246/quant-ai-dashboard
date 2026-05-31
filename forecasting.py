"""
forecasting.py — Prophet + Logistic Growth + Market Cap Saturation.

Akademik Referans:
  - Taylor, S. J., & Letham, B. (2018). *Forecasting at scale*.
    The American Statistician 72(1), 37-45. (Facebook Prophet.)
  - Verhulst, P. F. (1838). *Notice sur la loi que la population suit dans
    son accroissement*. (Lojistik buyume denklemi.)
  - Bessembinder, H. (2018). Long-tail return distribution justifies hard
    caps (20x global rule).

Formul (Math_Specs.md Bolum 5):
  Logistic growth:
      y_hat(t) = C(t) / (1 + exp(-k(t)(t - m(t))))

  Market cap saturation:
      C_price = min(C_Apple, C_NVDA, C_leader, C_TAM, C_ticker) / N_shares
      C_final = min(C_price, P_0 * 20)

Bu cap'ler AXTI $23K saçmaligini engelleyen ana mekanizmadir.
"""
from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=FutureWarning)

# Prophet'in cmdstanpy log'larini sustur
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


# =============================================================================
# Timezone helpers - tz-naive zorunlu (Prophet, pandas DateOffset arithmetic)
# =============================================================================
def _idx_to_tz_naive(idx) -> pd.DatetimeIndex:
    """DatetimeIndex tz-aware ise tz_localize(None) yap, degilse aynen don."""
    try:
        if hasattr(idx, "tz") and idx.tz is not None:
            return idx.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return idx


def _col_to_tz_naive(s: pd.Series) -> pd.Series:
    """Pandas Series icindeki datetime'i tz-naive yap (tz-aware veya degil)."""
    s = pd.to_datetime(s, errors="coerce")
    try:
        if getattr(s.dt, "tz", None) is not None:
            s = s.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return s


def _clean_outliers(data: pd.DataFrame, sigma: float = 6.0,
                      ret_clip_pct: float = 30.0) -> pd.DataFrame:
    """
    Ekstrem outlier temizligi - 10y projeksiyonun 'saçmalamamasi' icin sart.

    Iki katmanli filtre:
      1) GUNLUK LOG-RETURN clip: |return| > ret_clip_pct% (default 30%)
         olan gunlerin y degerini interpole et. Stock split / data hatasi
         genellikle bu sekilde tek-gun spike olur.
      2) MAD (Median Absolute Deviation) tabanli z-score: |z_mad| > sigma
         olan gunler de interpolasyona tabi tutulur.
         Mu/sigma yerine median/MAD kullaniyoruz cunku robust istatistik
         (extreme outlier'lar mu/sigma'yi bozar -> 'breakdown nokta')
    """
    if len(data) < 30:
        return data
    df = data.copy().sort_values("ds").reset_index(drop=True)

    # 1) Gunluk log-return outlier clip
    y = df["y"].astype(float).values
    log_ret = np.zeros_like(y)
    log_ret[1:] = np.log(y[1:] / y[:-1])
    ret_threshold = np.log(1 + ret_clip_pct / 100.0)
    outliers_ret = np.abs(log_ret) > ret_threshold
    if outliers_ret.any():
        bad_idx = np.where(outliers_ret)[0]
        # bad_idx[0] = 0 olabilir (log_ret[0]=0), bunu atla
        bad_idx = bad_idx[bad_idx > 0]
        if len(bad_idx) > 0:
            mask = np.ones(len(y), dtype=bool)
            mask[bad_idx] = False
            # ds index'e gore interpole et
            tmp = pd.Series(y, index=df["ds"])
            tmp.loc[df["ds"].iloc[bad_idx]] = np.nan
            tmp = tmp.interpolate(method="time").ffill().bfill()
            df["y"] = tmp.values

    # 2) MAD-based robust z-score (log-fiyat uzerinde - geometric)
    log_y = np.log(df["y"].astype(float).replace(0, np.nan))
    if log_y.notna().sum() > 20:
        # 60 gunluk hareketli MAD
        rolling_med = log_y.rolling(60, min_periods=20, center=True).median()
        rolling_mad = (log_y - rolling_med).abs().rolling(
            60, min_periods=20, center=True).median()
        # 0 MAD'i kucuk pozitifle degistir
        rolling_mad = rolling_mad.replace(0, np.nan).bfill().ffill()
        z_mad = 0.6745 * (log_y - rolling_med) / rolling_mad  # 'modified z-score'
        bad = (z_mad.abs() > sigma) & z_mad.notna()
        if bad.any():
            df.loc[bad, "y"] = np.nan
            df["y"] = df["y"].interpolate(method="linear").ffill().bfill()

    return df.dropna(subset=["y"])


def _build_prophet_input(df: pd.DataFrame, clean: bool = True) -> pd.DataFrame:
    """
    Prophet'e gidecek temiz tz-naive DataFrame uret. ds + y.

    clean=True (varsayilan): outlier temizligi de uygular.
    """
    series = df["Close"].dropna()
    # Index'i tz-naive yap
    idx_naive = _idx_to_tz_naive(series.index)
    data = pd.DataFrame({
        "ds": pd.to_datetime(idx_naive),
        "y":  series.values,
    })
    # Ek sigorta: kolon hala tz-aware kalsa bile zorla soyup at
    data["ds"] = _col_to_tz_naive(data["ds"])
    # NaN ve duplicate temizligi
    data = data.dropna(subset=["ds", "y"]).drop_duplicates(subset=["ds"])
    if clean:
        data = _clean_outliers(data)
    return data


def _get_shares_outstanding(ticker: str) -> float:
    """yfinance'tan shares outstanding (cap calculation icin)."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        for key in ("sharesOutstanding", "impliedSharesOutstanding"):
            v = info.get(key)
            if v and v > 0:
                return float(v)
    except Exception:
        pass
    return 0.0


def _apply_market_cap_saturation(
    ticker: str,
    forecast_df: pd.DataFrame,
    last_actual: float,
    horizon_years: int = 10,
) -> tuple[pd.DataFrame, dict]:
    """
    Market Cap Saturation kontrolu.

    Mantik:
      max_market_cap = TAM_10y * P/S_sector * realistic_share_pct * 50%
                     ----------- ---------    -------------------    -----
                       sektor    P/S sektor   sirketin TAM payi    saturation
                       yillik    ortalamasi   (monopol/niche)       sertligi
                       gelir
      = saturation_market_cap_threshold

    Eger 10y tahmin fiyati * shares > threshold => tahmin asagi revize.

    Returns:
      (revised_forecast_df, saturation_info)
    """
    from sector_tam import (get_ps_multiplier, get_realistic_share_pct,
                              get_sector, get_tam_projected_bn)

    shares = _get_shares_outstanding(ticker)
    ps_mult = get_ps_multiplier(ticker)
    info = {
        "ticker": ticker,
        "sector": get_sector(ticker),
        "shares_outstanding_m": round(shares / 1e6, 1) if shares else 0,
        "tam_projected_bn_10y": get_tam_projected_bn(ticker, horizon_years),
        "ps_multiplier": ps_mult,
        "realistic_share_pct": get_realistic_share_pct(ticker),
        "applied_saturation": False,
        "revision_factor": 1.0,
        "max_realistic_price": None,
        "max_realistic_market_cap_bn": None,
        "implied_market_cap_at_target_bn": None,
        "implied_share_pct_at_target": None,
        "warning": None,
    }

    if shares <= 0 or forecast_df is None or forecast_df.empty:
        info["warning"] = ("⚠️ Shares outstanding alinamadi - market cap "
                            "saturation kontrolu yapilamadi.")
        return forecast_df, info

    # --- GLOBAL & SEKTOR LIDERI CEILING ---
    # Hard-cap'ler (en kucuk sinir uygulanir):
    #   1) Apple piyasa degeri ($3.5T) - global hicbir hisse asamaz
    #   2) NVDA piyasa degeri ($3.3T) - 'Sektor Lideri Degerlemesi'
    #      kullanici talebi (hicbir tekno hisse NVDA'yi gecemez)
    #   3) Hissenin kendi sektor liderinin piyasa degeri (AI_ACCEL,
    #      EUV_LITHO, SECURE_MCU vs.) - Reality Check dizginleme
    try:
        from sector_tam import (get_absolute_market_cap_ceiling_usd,
                                  get_nvda_ceiling_usd,
                                  get_sector_leader_cap_usd,
                                  get_ticker_price_cap_10y)
        apple_cap_usd = get_absolute_market_cap_ceiling_usd()
        nvda_cap_usd = get_nvda_ceiling_usd()
        leader_cap_usd = get_sector_leader_cap_usd(ticker or "")
        # En sıkı cap'i uygula (en kucuk olan)
        applied_cap_usd = min(apple_cap_usd, nvda_cap_usd, leader_cap_usd)
        max_price_apple = applied_cap_usd / shares

        # PER-TICKER HARD CAP (kullanici talebi - NVTS $100 outlier esigi)
        ticker_price_cap = get_ticker_price_cap_10y(ticker or "")
        if ticker_price_cap is not None and ticker_price_cap < max_price_apple:
            max_price_apple = float(ticker_price_cap)
            applied_cap_usd = float(ticker_price_cap) * shares
            info["per_ticker_cap_applied"] = True
            info["per_ticker_price_cap"] = float(ticker_price_cap)

        info["apple_cap_usd"] = apple_cap_usd
        info["nvda_cap_usd"] = nvda_cap_usd
        info["sector_leader_cap_usd"] = leader_cap_usd
        info["applied_cap_usd"] = applied_cap_usd
        info["max_price_apple_ceiling"] = round(max_price_apple, 2)
        # Hangi cap aktif?
        if info.get("per_ticker_cap_applied"):
            info["cap_source"] = (f"Per-Ticker Hard Cap "
                                     f"(${ticker_price_cap:.0f} outlier esigi)")
        elif applied_cap_usd == leader_cap_usd:
            info["cap_source"] = "Sektor Lideri (Reality Check)"
        elif applied_cap_usd == nvda_cap_usd:
            info["cap_source"] = "NVDA tavani"
        else:
            info["cap_source"] = "Apple tavani"
    except Exception:
        apple_cap_usd = float("inf")
        max_price_apple = float("inf")

    # Eger Apple cap < sektor max ise Apple cap'i kullan (sert tavan)
    tam_bn = info["tam_projected_bn_10y"]
    share_pct = info["realistic_share_pct"]
    # Saturation esigi P/S carpani ile kalibre edilir:
    #   realistic_max_mcap_bn = TAM_bn * P/S * share_pct/100 * 0.80
    #   (0.80 -> share_pct zaten makul max'i kontrol ediyor; saturation
    #    bunun %80'inde tetiklenir = ilk %20'lik tampon)
    SATURATION_THRESHOLD = 0.80
    realistic_max_mcap_bn = (tam_bn * ps_mult * (share_pct / 100.0) *
                              SATURATION_THRESHOLD)
    realistic_max_mcap_usd = realistic_max_mcap_bn * 1e9
    max_price = realistic_max_mcap_usd / shares
    # Apple / NVDA / sektor-lideri cap'lerinden en kucuğu vs sektor TAM
    # limiti - hangisi daha sıkıysa onu uygula (Reality Check).
    if max_price_apple < max_price:
        max_price = max_price_apple
        realistic_max_mcap_bn = float(info.get("applied_cap_usd",
                                                   apple_cap_usd)) / 1e9
        info["apple_ceiling_active"] = True
    else:
        info["apple_ceiling_active"] = False
    info["max_realistic_price"] = round(max_price, 2)
    info["max_realistic_market_cap_bn"] = round(realistic_max_mcap_bn, 2)

    # Tahmin son satirini incele
    target_yhat = float(forecast_df["yhat"].iloc[-1])
    implied_mcap_bn = (target_yhat * shares) / 1e9
    info["implied_market_cap_at_target_bn"] = round(implied_mcap_bn, 2)
    if tam_bn > 0:
        info["implied_share_pct_at_target"] = round(
            implied_mcap_bn / (tam_bn * ps_mult) * 100, 2)

    # TAM-PS-share saturation esigini geciyor mu?
    if implied_mcap_bn > realistic_max_mcap_bn:
        factor = max_price / target_yhat
        factor = max(0.10, min(1.0, factor))
        info["applied_saturation"] = True
        info["revision_factor"] = round(factor, 3)

        # Future kismi orantili kucult, history kismi (son fiyata kadar) DOKUNMA
        revised = forecast_df.copy()
        revised["ds"] = pd.to_datetime(revised["ds"])
        # Future = son tarihten sonraki kisim. last_actual fiyat noktasini koru.
        # Lineer blend: idx ilerledikce factor artiyor; idx=0 (ilk satir) -> 1.0,
        # idx=N-1 -> factor. Boylelikle gecmis bozulmaz, gelecekte revize artar.
        n = len(revised)
        if n > 1:
            blend = np.linspace(1.0, factor, n)
            for col in ("yhat", "yhat_lower", "yhat_upper"):
                if col in revised.columns:
                    revised[col] = revised[col].values * blend
        info["warning"] = (
            f"🚨 **Market Cap Saturation** - {ticker} 10y tahmini "
            f"${implied_mcap_bn:,.1f}B market cap'e cikariyordu; sektor TAM "
            f"${tam_bn:,.1f}B x P/S {ps_mult:.0f}x x payi %{share_pct:.0f} "
            f"x %{SATURATION_THRESHOLD*100:.0f} saturasyon = "
            f"${realistic_max_mcap_bn:,.1f}B. "
            f"Tahmin {factor:.0%} olceginde revize edildi. "
            f"Makul max fiyat: ${max_price:,.2f}"
        )
        return revised, info

    info["warning"] = None
    return forecast_df, info


def _add_earnings_seasonality(model):
    """
    Rob Hyndman - Forecasting: Principles and Practice (Sec. 9.3) yaklasimi:
    Cyclic ozelliklerini Fourier seriileri ile yakalamak. Teknoloji hisseleri
    icin ceyrek kar aciklama (earnings cycle) ~91.25 gunluk periyot olusturur.
    """
    try:
        model.add_seasonality(name="earnings_quarter", period=91.25,
                               fourier_order=4, prior_scale=2.5)
    except Exception:
        pass
    return model


def forecast_prophet(df: pd.DataFrame, horizon_days: int = 180) -> dict:
    """
    Prophet ile 6 ay (180 gun) fiyat tahmini.
    Confidence interval %80 (yhat_lower / yhat_upper).
    Earnings seasonality (3 ayda bir) ek olarak ogrenilir.
    """
    try:
        from prophet import Prophet
    except ImportError:
        return forecast_naive(df, horizon_days)

    if len(df) < 100:
        return forecast_naive(df, horizon_days)

    # Prophet input formati - GARANTILI tz-naive
    data = _build_prophet_input(df)
    if len(data) < 100:
        return forecast_naive(df, horizon_days)

    try:
        # Hyndman ETS prensibi: muhafazakar trend (level smoothing dusuk
        # changepoint_prior_scale ile), ek olarak earnings (3-aylik) cycle.
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            interval_width=0.80,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=8.0,
        )
        _add_earnings_seasonality(model)
        model.fit(data)
        future = model.make_future_dataframe(periods=horizon_days)
        # Future de tz-naive olsun (Prophet zaten oyle uretir, sigorta)
        future["ds"] = _col_to_tz_naive(future["ds"])
        forecast = model.predict(future)
        forecast["ds"] = _col_to_tz_naive(forecast["ds"])

        last_actual = float(data["y"].iloc[-1])
        # Tahmin son satir
        target = forecast.iloc[-1]
        target_price = float(target["yhat"])
        lower = float(target["yhat_lower"])
        upper = float(target["yhat_upper"])

        # 30 / 90 / 180 gun ileri snapshot
        snapshots = {}
        for d in (30, 90, 180):
            if d <= horizon_days:
                row = forecast.iloc[len(data) + d - 1]
                snapshots[f"{d}d"] = {
                    "date": str(row["ds"].date()),
                    "price": round(float(row["yhat"]), 2),
                    "lower": round(float(row["yhat_lower"]), 2),
                    "upper": round(float(row["yhat_upper"]), 2),
                    "change_pct": round((row["yhat"] / last_actual - 1) * 100, 2),
                }

        return {
            "model": "Prophet",
            "horizon_days": horizon_days,
            "last_actual": round(last_actual, 2),
            "target_price": round(target_price, 2),
            "lower_band": round(lower, 2),
            "upper_band": round(upper, 2),
            "change_pct": round((target_price / last_actual - 1) * 100, 2),
            "snapshots": snapshots,
            "forecast_df": forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]],
            "history": data,
        }
    except Exception as e:
        logger.warning("Prophet hatasi: %s -> naive fallback", e)
        return forecast_naive(df, horizon_days)


def forecast_long_term(df: pd.DataFrame, years: int = 10,
                         ticker: str | None = None,
                         exponential_mode: bool = False) -> dict:
    """
    Uzun vadeli (5-10 yil) projeksiyon - LOGISTIC GROWTH + CAP.

    Saglik filtreleri:
      1) Outlier temizligi (_clean_outliers) - tarihsel split/glitch noktalari
      2) Prophet growth='logistic' - sinirsiz exponansiyel patlama yok
      3) Cap = mevcut fiyat x sector multiplier (default 10x, ASML/NVDA 15x,
         quantum/secure 8x). Hisse fiyati hicbir zaman cap'i asamaz.
      4) Floor = mevcut fiyat / 5 (dipte de saçmalamasin)
      5) Market Cap Saturation: TAM'nin %50'sini gecemez, gecerse revize.
    """
    try:
        from prophet import Prophet
    except ImportError:
        return forecast_naive(df, years * 365)

    series = df["Close"].dropna()
    if len(series) < 250:
        return forecast_naive(df, years * 365)

    # Prophet input formati - GARANTILI tz-naive + outlier cleaned
    data = _build_prophet_input(df, clean=True)
    if len(data) < 250:
        return forecast_naive(df, years * 365)

    last_actual = float(data["y"].iloc[-1])

    # --- LOGISTIC CAP ---
    cap_mult = 10.0
    if ticker:
        try:
            from sector_tam import get_cap_multiplier
            cap_mult = get_cap_multiplier(ticker)
        except Exception:
            pass
    # ATOM: Foundry MST kabulu -> 'Exponential' CAGR modu (daha yuksek cap)
    if exponential_mode:
        cap_mult = max(cap_mult, 20.0)

    # v8 GLOBAL HARD CAP (kullanici talebi):
    # Hicbir hisse mevcut fiyatinin 20x'ini gecemez (10y horizon)
    try:
        from sector_tam import (get_global_price_cap_multiplier,
                                  get_global_cagr_band)
        global_max_mult = get_global_price_cap_multiplier()
        cap_mult = min(cap_mult, global_max_mult)
        # Global CAGR ust bandi (max %25) ile cap'le
        _, cagr_max = get_global_cagr_band()
        cagr_max_mult = (1 + cagr_max/100.0) ** years
        cap_mult = min(cap_mult, cagr_max_mult)
    except Exception:
        pass

    cap_value = last_actual * cap_mult

    # PER-TICKER HARD CAP (NVTS $100 outlier esigi gibi sıkı kurallar)
    try:
        from sector_tam import (get_ticker_price_cap_10y,
                                  get_ticker_max_cagr_10y)
        if ticker:
            per_ticker_cap = get_ticker_price_cap_10y(ticker)
            if per_ticker_cap is not None and per_ticker_cap < cap_value:
                cap_value = float(per_ticker_cap)
                cap_mult = cap_value / last_actual if last_actual > 0 else 1.0
            # Max CAGR sıniri (NVTS %20 -> 10 yilda ~6.2x)
            max_cagr = get_ticker_max_cagr_10y(ticker)
            if max_cagr is not None:
                max_by_cagr = last_actual * ((1 + max_cagr / 100.0) ** years)
                if max_by_cagr < cap_value:
                    cap_value = float(max_by_cagr)
                    cap_mult = cap_value / last_actual if last_actual > 0 else 1.0
    except Exception:
        pass

    floor_value = max(last_actual / 5.0, 0.01)
    data["cap"] = cap_value
    data["floor"] = floor_value

    try:
        # Logistic growth ile cap'e dogru asimptotik yaklasim
        # exponential_mode: daha agresif trend (JDA / production line kabulu)
        cps = 0.06 if exponential_mode else 0.02
        model = Prophet(
            growth="logistic",
            daily_seasonality=False,
            weekly_seasonality=False,
            yearly_seasonality=True,
            interval_width=0.80,
            changepoint_prior_scale=cps,
            seasonality_prior_scale=2.0,
        )
        _add_earnings_seasonality(model)
        model.fit(data)
        horizon = years * 365
        future = model.make_future_dataframe(periods=horizon)
        future["ds"] = _col_to_tz_naive(future["ds"])
        # Future icin cap/floor da sart
        future["cap"] = cap_value
        future["floor"] = floor_value
        forecast = model.predict(future)
        forecast["ds"] = _col_to_tz_naive(forecast["ds"])

        # Ek hard clip: model nadiren cap'i hafifce asabilir
        for col in ("yhat", "yhat_upper"):
            if col in forecast.columns:
                forecast[col] = forecast[col].clip(upper=cap_value)
        for col in ("yhat", "yhat_lower"):
            if col in forecast.columns:
                forecast[col] = forecast[col].clip(lower=floor_value)

        # Tarihsel CAGR (son 5 yil) - karsilastirma icin (tz-naive aritmetik)
        last_ds = pd.Timestamp(data["ds"].iloc[-1])
        if last_ds.tz is not None:
            last_ds = last_ds.tz_localize(None)
        cutoff = last_ds - pd.DateOffset(years=5)
        hist5 = data[data["ds"] >= cutoff]
        hist_cagr = 0.0
        if len(hist5) > 100 and hist5["y"].iloc[0] > 0:
            n = (hist5["ds"].iloc[-1] - hist5["ds"].iloc[0]).days / 365.25
            hist_cagr = ((hist5["y"].iloc[-1] / hist5["y"].iloc[0]) ** (1 / n) - 1) * 100

        # Market Cap Saturation revizyonu (TAM %50)
        forecast_only_cols = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
        saturation_info = {"applied_saturation": False, "warning": None}
        if ticker:
            try:
                forecast_only_cols, saturation_info = _apply_market_cap_saturation(
                    ticker, forecast_only_cols, last_actual, horizon_years=years)
            except Exception as e:
                logger.warning("market cap saturation %s: %s", ticker, e)

        # Yillik snapshot
        snapshots = {}
        for yi in range(1, years + 1):
            idx = len(data) + yi * 365 - 1
            if idx < len(forecast_only_cols):
                row = forecast_only_cols.iloc[idx]
                snapshots[f"{yi}y"] = {
                    "date": str(pd.Timestamp(row["ds"]).date()),
                    "price": round(float(row["yhat"]), 2),
                    "lower": round(float(row["yhat_lower"]), 2),
                    "upper": round(float(row["yhat_upper"]), 2),
                    "change_pct": round((row["yhat"] / last_actual - 1) * 100, 1),
                    "multiple": round(row["yhat"] / last_actual, 2)
                                  if last_actual > 0 else 0,
                }

        # 10 yil cikari fiyatlar - implied CAGR
        target = forecast_only_cols.iloc[-1]
        implied_cagr = 0.0
        if last_actual > 0:
            implied_cagr = ((float(target["yhat"]) / last_actual) ** (1 / years) - 1) * 100

        return {
            "model": ("Prophet 10y (logistic + EXPONENTIAL)" if exponential_mode
                       else "Prophet 10y (logistic + cap)"),
            "exponential_mode": exponential_mode,
            "horizon_days": horizon,
            "years": years,
            "last_actual": round(last_actual, 2),
            "cap_value": round(cap_value, 2),
            "cap_multiplier": cap_mult,
            "floor_value": round(floor_value, 2),
            "target_price": round(float(target["yhat"]), 2),
            "lower_band": round(float(target["yhat_lower"]), 2),
            "upper_band": round(float(target["yhat_upper"]), 2),
            "change_pct": round((target["yhat"] / last_actual - 1) * 100, 1),
            "implied_cagr_pct": round(implied_cagr, 2),
            "historical_5y_cagr_pct": round(hist_cagr, 2),
            "snapshots": snapshots,
            "forecast_df": forecast_only_cols,
            "history": data[["ds", "y"]],
            "saturation": saturation_info,
        }
    except Exception as e:
        logger.warning("10y Prophet hatasi: %s -> naive fallback", e)
        return forecast_naive(df, years * 365)


def forecast_naive(df: pd.DataFrame, horizon_days: int = 180) -> dict:
    """
    Prophet calismazsa: log-return ortalamasi + volatilite ile basit bant.
    """
    close = df["Close"].dropna()
    if len(close) < 30:
        last = float(close.iloc[-1]) if len(close) else 0
        return {
            "model": "naive",
            "horizon_days": horizon_days,
            "last_actual": last,
            "target_price": last,
            "lower_band": last,
            "upper_band": last,
            "change_pct": 0,
            "snapshots": {},
            "forecast_df": pd.DataFrame(),
            "history": pd.DataFrame({"ds": close.index, "y": close.values}),
        }

    log_ret = np.log(close / close.shift(1)).dropna()
    mu = log_ret.mean()
    sigma = log_ret.std()
    last = float(close.iloc[-1])

    days = np.arange(1, horizon_days + 1)
    central = last * np.exp(mu * days)
    band = 1.28 * sigma * np.sqrt(days)         # ~%80 bant
    upper = last * np.exp(mu * days + band)
    lower = last * np.exp(mu * days - band)

    # tz-naive index
    close_idx_naive = _idx_to_tz_naive(close.index)
    last_idx = pd.Timestamp(close_idx_naive[-1])
    if last_idx.tz is not None:
        last_idx = last_idx.tz_localize(None)
    idx = pd.date_range(last_idx + pd.Timedelta(days=1), periods=horizon_days)
    forecast = pd.DataFrame({
        "ds": list(close_idx_naive) + list(idx),
        "yhat": list(close.values) + list(central),
        "yhat_lower": list(close.values) + list(lower),
        "yhat_upper": list(close.values) + list(upper),
    })
    forecast["ds"] = _col_to_tz_naive(forecast["ds"])

    snapshots = {}
    for d in (30, 90, 180):
        if d <= horizon_days:
            i = d - 1
            snapshots[f"{d}d"] = {
                "date": str(idx[i].date()),
                "price": round(float(central[i]), 2),
                "lower": round(float(lower[i]), 2),
                "upper": round(float(upper[i]), 2),
                "change_pct": round((central[i] / last - 1) * 100, 2),
            }

    return {
        "model": "naive (log-normal)",
        "horizon_days": horizon_days,
        "last_actual": round(last, 2),
        "target_price": round(float(central[-1]), 2),
        "lower_band": round(float(lower[-1]), 2),
        "upper_band": round(float(upper[-1]), 2),
        "change_pct": round((central[-1] / last - 1) * 100, 2),
        "snapshots": snapshots,
        "forecast_df": forecast,
        "history": pd.DataFrame({"ds": close_idx_naive, "y": close.values}),
    }
