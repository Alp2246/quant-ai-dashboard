"""
Alpha Engine Paneli - Streamlit dashboard sekmesi.

Ne yapar?
    - Engine state'inden (alpha_engine/data/signals.jsonl + cohort_baseline.json)
      okuyup son 24/72 saat olusan event'leri tablo + grafik olarak gosterir.
    - "EN ONEMLI HABER" basligi en ust (mobil-uyumlu metric karti).
    - Source bazinda sinyal hacmi grafigi.
    - Filtre: kohort (MEGA/MID/SMALL), source, ticker.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Sabitler / yollar
# ---------------------------------------------------------------------------
ENGINE_DIR = Path(__file__).parent / "alpha_engine"
STATE_DIR = ENGINE_DIR / "data" / "state"
SIGNALS_PATH = STATE_DIR / "signals.jsonl"
COHORT_PATH = STATE_DIR / "cohort_baseline.json"
COHORT_MAP_PATH = STATE_DIR / "cohort_map.json"
HEARTBEAT_PATH = ENGINE_DIR / "data" / "heartbeat.txt"

TR_TZ = timezone(timedelta(hours=3))

SOURCE_TR = {
    "sec_edgar":       ("📄 SEC 8-K",              "Resmi material event"),
    "sec_form4":       ("💰 Insider Buying",       "CEO/CFO hisse alimi"),
    "google_news":     ("📰 Haber",                "Google News patlamasi"),
    "reddit_rss":      ("💬 Reddit",               "Sosyal forum mention"),
    "reddit":          ("💬 Reddit (API)",         "Resmi Reddit API"),
    "polygon_options": ("📈 Opsiyon",              "Call/Put dengesizligi"),
}

SEVERITY_COLOR = {
    "KRITIK": "#ef4444",
    "YUKSEK": "#f59e0b",
}


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30, show_spinner=False)
def load_signals(lookback_h: float = 72.0) -> pd.DataFrame:
    if not SIGNALS_PATH.is_file():
        return pd.DataFrame()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_h)
    rows = []
    try:
        with SIGNALS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = obj.get("timestamp")
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    continue
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
                rows.append({
                    "ticker": (obj.get("ticker") or "").upper(),
                    "source": obj.get("source", ""),
                    "value": float(obj.get("value", 0) or 0),
                    "timestamp": ts,
                    "metadata": obj.get("metadata") or {},
                    "url": obj.get("url"),
                    "event_id": obj.get("event_id"),
                })
    except Exception:
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["age_h"] = (datetime.now(timezone.utc) - df["timestamp"]).dt.total_seconds() / 3600
    df["ts_tr"] = df["timestamp"].dt.tz_convert(TR_TZ)
    return df


@st.cache_data(ttl=60, show_spinner=False)
def load_cohort_map() -> dict[str, str]:
    if not COHORT_MAP_PATH.is_file():
        return {}
    try:
        data = json.loads(COHORT_MAP_PATH.read_text(encoding="utf-8"))
        # Format: {"cohorts": {"NVDA": "MEGA", ...}, "caps": {...}, "updated": ts}
        cohorts = data.get("cohorts", data) if isinstance(data, dict) else {}
        return {str(k).upper(): str(v) for k, v in cohorts.items()}
    except Exception:
        return {}


@st.cache_data(ttl=30, show_spinner=False)
def load_heartbeat() -> dict:
    """heartbeat.txt: son tick zamani + saglik."""
    if not HEARTBEAT_PATH.is_file():
        return {"alive": False, "message": "Engine heartbeat dosyasi yok"}
    try:
        text = HEARTBEAT_PATH.read_text(encoding="utf-8")
        try:
            obj = json.loads(text)
            return {"alive": True, **obj}
        except json.JSONDecodeError:
            return {"alive": True, "message": text.strip()}
    except Exception as exc:
        return {"alive": False, "message": str(exc)}


def _classify_event(group: pd.DataFrame, z_trigger: float = 3.0,
                     min_sources: int = 2) -> dict | None:
    """Bir ticker'in son 72h sinyallerinden basit composite event uretir."""
    if group.empty:
        return None
    # Source bazinda decay-adjusted toplam
    lam = math.log(2) / 6.0  # half-life 6h
    by_source = defaultdict(lambda: {"value": 0.0, "raw_peak": 0.0,
                                      "peak_age_h": 0.0, "peak_ts": None,
                                      "metadata": {}, "url": None})
    for _, row in group.iterrows():
        age_h = row["age_h"]
        decay = math.exp(-lam * max(0, age_h))
        d = by_source[row["source"]]
        d["value"] += row["value"] * decay
        if row["value"] > d["raw_peak"]:
            d["raw_peak"] = row["value"]
            d["peak_age_h"] = age_h
            d["peak_ts"] = row["ts_tr"]
            d["metadata"] = row["metadata"]
            d["url"] = row["url"]

    # Trigger'lar (basitlestirilmis - baseline yerine value esigi)
    triggers = []
    for source, d in by_source.items():
        if d["raw_peak"] <= 0:
            continue
        # Sosyal kaynaklar icin daha yuksek esik
        threshold = 3.0 if source in ("reddit_rss", "google_news") else 0.5
        if d["raw_peak"] < threshold and source not in ("sec_edgar", "sec_form4"):
            continue
        triggers.append({
            "source": source,
            **d,
        })

    if not triggers:
        return None

    has_sec = any(t["source"] == "sec_edgar" for t in triggers)
    has_insider = any(t["source"] == "sec_form4" and t["raw_peak"] >= 2.0
                        for t in triggers)
    n_sources = len(triggers)
    qualifies = n_sources >= min_sources or has_sec or has_insider
    if not qualifies:
        return None

    severity = "KRITIK" if (has_sec or has_insider or n_sources >= 3) else "YUKSEK"
    composite = sum(t["raw_peak"] for t in triggers)
    return {
        "ticker": group.iloc[0]["ticker"],
        "severity": severity,
        "n_sources": n_sources,
        "composite": round(composite, 1),
        "triggers": triggers,
        "has_sec": has_sec,
        "has_insider": has_insider,
        "latest_ts": max(t["peak_ts"] for t in triggers if t["peak_ts"] is not None),
    }


def _format_age(hours: float) -> str:
    mins = int(hours * 60)
    if mins < 1:
        return "az once"
    if mins < 60:
        return f"{mins} dk once"
    if mins < 60 * 24:
        h = mins // 60
        m = mins % 60
        return f"{h}s {m}dk once" if m else f"{h} saat once"
    d = mins // (60 * 24)
    return f"{d} gun once"


# ---------------------------------------------------------------------------
# UI ana fonksiyon
# ---------------------------------------------------------------------------
def render_alpha_engine_panel() -> None:
    st.subheader("🚨 Alpha Engine — Erken Uyari Sistemi")
    st.caption(
        "Cohort-based z-score + decay function. 5 kaynak (SEC 8-K, Form 4 insider, "
        "Reddit, Haber, Opsiyon) — 72 saat sliding window. "
        "**EN ONEMLI HABER** zamani ile birlikte."
    )

    # ---- Saglik durumu ----
    hb = load_heartbeat()
    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        status = "🟢 AKTIF" if hb.get("alive") else "🔴 KAPALI"
        st.metric("Engine durumu", status)
    with col_b:
        last_tick = hb.get("last_tick") or hb.get("message", "—")
        st.metric("Son tick", str(last_tick)[:19])
    with col_c:
        if not hb.get("alive"):
            st.info("Engine ayri bir surec - `alpha_engine\\run.bat` ile baslat. "
                    "Otomatik calistirmak icin `install_autostart.bat`.")

    st.divider()

    # ---- Filtreler ----
    f1, f2, f3 = st.columns([1, 1, 1])
    with f1:
        lookback = st.selectbox(
            "Donem",
            options=[("Son 1 saat", 1), ("Son 6 saat", 6),
                     ("Son 24 saat", 24), ("Son 72 saat", 72)],
            format_func=lambda x: x[0], index=2,
        )[1]
    with f2:
        sources_filter = st.multiselect(
            "Kaynaklar",
            options=list(SOURCE_TR.keys()),
            default=list(SOURCE_TR.keys()),
            format_func=lambda s: SOURCE_TR.get(s, (s, ""))[0],
        )
    with f3:
        min_severity = st.selectbox("Min onem", ["TUMU", "YUKSEK", "KRITIK"], index=0)

    df = load_signals(lookback_h=lookback)
    if df.empty:
        st.warning(
            "Hic sinyal bulunamadi. Engine'in calismasi gerekli — "
            "`cd alpha_engine && run.bat` ile baslat."
        )
        return

    df = df[df["source"].isin(sources_filter)]
    if df.empty:
        st.info("Filtreler tum sinyalleri eledi.")
        return

    cohort_map = load_cohort_map()

    # ---- Event hesapla (ticker bazinda) ----
    events = []
    for ticker, grp in df.groupby("ticker"):
        ev = _classify_event(grp)
        if ev is None:
            continue
        ev["cohort"] = cohort_map.get(ticker, "UNKNOWN")
        if min_severity != "TUMU":
            if min_severity == "KRITIK" and ev["severity"] != "KRITIK":
                continue
        events.append(ev)

    events.sort(key=lambda e: (e["severity"] == "YUKSEK", -e["composite"]))

    # ---- EN ONEMLI HABER (en ust banner) ----
    st.markdown("### ⏰ EN ONEMLI HABER")
    if not events:
        st.info("Su an aktif EVENT yok. Sinyaller geliyor ama henuz korrobore olmadi.")
    else:
        top = events[0]
        # En onemli trigger'i sec (SEC > insider > digerleri)
        triggers = top["triggers"]
        sec = [t for t in triggers if t["source"] == "sec_edgar"]
        insider = [t for t in triggers if t["source"] == "sec_form4" and t["raw_peak"] >= 2.0]
        head = (insider[0] if insider else (sec[0] if sec
                else max(triggers, key=lambda t: t["raw_peak"])))

        peak_ts = head["peak_ts"]
        age_h = head["peak_age_h"]
        clock = peak_ts.strftime("%H:%M") if peak_ts else "—"
        date = peak_ts.strftime("%d %b") if peak_ts else ""
        color = SEVERITY_COLOR.get(top["severity"], "#6b7280")
        source_label = SOURCE_TR.get(head["source"], (head["source"], ""))[0]

        meta = head.get("metadata") or {}
        headline_text = ""
        if head["source"] == "sec_edgar":
            headline_text = meta.get("title", "Resmi SEC bildirimi")
        elif head["source"] == "sec_form4":
            usd = meta.get("purchase_usd", 0)
            insider_name = meta.get("insider_name", "")
            titles = ", ".join((meta.get("insider_titles") or [])[:2]) or "Insider"
            headline_text = f"{titles} {insider_name} ${usd:,.0f} aldi"
        elif head["source"] == "google_news":
            headline_text = meta.get("latest_title", f"{int(head['raw_peak'])} yeni haber")
        elif head["source"] in ("reddit_rss", "reddit"):
            headline_text = f"{int(head['raw_peak'])} kez Reddit'te konusuldu"
        elif head["source"] == "polygon_options":
            headline_text = f"Call/Put orani {head['raw_peak']:.1f}x"

        st.markdown(
            f"""
            <div style="border-left: 6px solid {color}; padding: 12px 18px;
                background: rgba(239,68,68,0.05); border-radius: 4px;">
              <div style="font-size: 13px; color: #6b7280; margin-bottom: 4px;">
                {source_label} &nbsp;|&nbsp; <b>{top['ticker']}</b> ({top['cohort']})
                &nbsp;|&nbsp; <span style="color: {color}; font-weight: 600;">
                {top['severity']}</span>
              </div>
              <div style="font-size: 22px; font-weight: 700; margin: 4px 0;">
                ⏰ {clock} {date}  <span style="font-size: 14px; font-weight: 400;
                color: #6b7280;">({_format_age(age_h)})</span>
              </div>
              <div style="font-size: 16px;">{headline_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if head.get("url"):
            st.markdown(f"🔗 [Habere git]({head['url']})")

    st.divider()

    # ---- Event tablosu ----
    st.markdown(f"### 📋 Tum Event'ler ({len(events)})")
    if events:
        table_rows = []
        for ev in events:
            head = ev["triggers"][0]
            for t in ev["triggers"]:
                if t["source"] == "sec_edgar":
                    head = t
                    break
            sources_str = " + ".join(
                SOURCE_TR.get(t["source"], (t["source"], ""))[0]
                for t in sorted(ev["triggers"], key=lambda x: -x["raw_peak"])
            )
            latest_age = min(t["peak_age_h"] for t in ev["triggers"])
            latest_ts = max(t["peak_ts"] for t in ev["triggers"] if t["peak_ts"])
            table_rows.append({
                "Ticker": ev["ticker"],
                "Onem": ev["severity"],
                "Kohort": ev["cohort"],
                "Skor": ev["composite"],
                "Kaynak": sources_str,
                "Saat": latest_ts.strftime("%d %b %H:%M") if latest_ts else "—",
                "Ne kadar once": _format_age(latest_age),
            })
        ev_df = pd.DataFrame(table_rows)
        st.dataframe(ev_df, use_container_width=True, hide_index=True)

    # ---- Sinyal hacmi grafik (saatlik bucket) ----
    st.markdown("### 📈 Sinyal Hacmi (saatlik)")
    df["hour"] = df["ts_tr"].dt.floor("h")
    vol = df.groupby(["hour", "source"]).size().reset_index(name="count")
    if not vol.empty:
        vol["source_label"] = vol["source"].map(
            lambda s: SOURCE_TR.get(s, (s,))[0]
        )
        fig = px.bar(
            vol, x="hour", y="count", color="source_label",
            labels={"hour": "Saat (TR)", "count": "Sinyal sayisi",
                    "source_label": "Kaynak"},
            title=None, height=320,
        )
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend_title_text=None)
        st.plotly_chart(fig, use_container_width=True)

    # ---- Source breakdown ----
    st.markdown("### 🔍 Kaynak Dagilimi (son {} saat)".format(lookback))
    src_counts = Counter(df["source"])
    cols = st.columns(len(SOURCE_TR))
    for col, (src, (label, desc)) in zip(cols, SOURCE_TR.items()):
        n = src_counts.get(src, 0)
        col.metric(label, n, help=desc)

    # ---- En aktif ticker'lar ----
    st.markdown("### 🏆 En Aktif 10 Ticker")
    ticker_stats = df.groupby("ticker").agg(
        sinyal=("source", "count"),
        kaynak_sayisi=("source", "nunique"),
        son_sinyal=("ts_tr", "max"),
    ).sort_values(["kaynak_sayisi", "sinyal"], ascending=False).head(10)
    ticker_stats["son_sinyal"] = ticker_stats["son_sinyal"].dt.strftime("%d %b %H:%M")
    ticker_stats["kohort"] = [cohort_map.get(t, "UNKNOWN") for t in ticker_stats.index]
    st.dataframe(ticker_stats, use_container_width=True)
