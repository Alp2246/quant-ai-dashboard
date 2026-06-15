"""
app_lite.py - Sadece Erken Uyari paneli (hizli, Oracle icin).

Tam dashboard yerine: Alpha Engine son sinyalleri + skor ozeti.
Calistirma: streamlit run app_lite.py --server.port=8501
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from alpha_engine_panel import render_alpha_engine_panel

st.set_page_config(
    page_title="QuantAI Erken Uyari",
    page_icon="🚨",
    layout="wide",
)

st.title("🚨 QuantAI Erken Uyari")
st.caption("Tam analiz PC'de; sunucu = haber tarama + Telegram bildirimleri.")

render_alpha_engine_panel()

state = Path(__file__).parent / "alpha_engine" / "data" / "state" / "master_scores.json"
if state.exists():
    st.markdown("### 📊 Son Master Score (cekirdek)")
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
        rows = []
        for t, r in (data.get("tickers") or {}).items():
            if r.get("error"):
                continue
            rows.append({
                "Hisse": t,
                "Skor": r.get("master_score", 0),
                "Karar": r.get("verdict", "—"),
            })
        if rows:
            import pandas as pd
            df = pd.DataFrame(rows).sort_values("Skor", ascending=False)
            st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Guncelleme: {data.get('updated_at', '—')}")
    except Exception as e:
        st.warning(f"Skor dosyasi okunamadi: {e}")
else:
    st.info("Master skor henuz uretilmedi. `python score_job.py` veya alpha-engine bekleyin.")

st.markdown("---")
st.markdown(
    "**Telefon bildirimleri:** Alpha Engine Telegram kanaliniza "
    "KRITIK OLAY + KRITIK ALIM / GUCLU AL gonderir."
)
