"""
feature_importance.py - Lopez de Prado MDI/MDA + Andrew Ng error analysis.

Akademik Referans:
  - Breiman, L. (2001). *Random Forests*. Machine Learning 45(1), 5-32.
  - López de Prado, M. (2018). *Advances in Financial ML*, Ch.8
    (Feature Importance Analysis).
  - Ng, A. (2018). *Machine Learning Yearning* - bias/variance decomp.

Formuller (Math_Specs.md Bolum 7):
  MDI(j) = (1/B) * sum_b sum_{v in N_j(b)} (n_v / N) * Delta_I(v)
  MDA(j) = Acc(X, y) - (1/n) * sum_r Acc(X_perm_j, y)

1) MDI - hizli ama biased (high-cardinality bias).
2) MDA - 'gold standard', yansiz, hesaplama maliyetli.
3) Error Analysis (Andrew Ng) - bias / variance dekompozisyonu.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import accuracy_score

logger = logging.getLogger(__name__)


def feature_importance_mdi(model, feature_names: list[str]) -> pd.DataFrame:
    """sklearn'in feature_importances_ wrapper (hizli, biased)."""
    if not hasattr(model, "feature_importances_"):
        return pd.DataFrame(columns=["feature", "importance", "method"])
    arr = np.asarray(model.feature_importances_)
    df = pd.DataFrame({
        "feature": feature_names,
        "importance": arr,
        "method": "MDI",
    }).sort_values("importance", ascending=False)
    return df


def feature_importance_mda(
    model,
    X: pd.DataFrame,
    y: pd.Series | np.ndarray,
    n_repeats: int = 5,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Mean Decrease in Accuracy (Lopez de Prado, Ch.8).

    Her ozellik n_repeats kez permute -> accuracy dusumu MDA olarak rapor edilir.
    Negatif/sifir MDA = ozellik gereksiz (hatta zararli).
    """
    rng = np.random.default_rng(random_state)
    base_pred = model.predict(X)
    base_acc = accuracy_score(y, base_pred)

    rows = []
    for col in X.columns:
        deltas = []
        for _ in range(n_repeats):
            X_perm = X.copy()
            X_perm[col] = rng.permutation(X_perm[col].values)
            try:
                pred = model.predict(X_perm)
                acc = accuracy_score(y, pred)
                deltas.append(base_acc - acc)
            except Exception as e:
                logger.debug("MDA %s permute fail: %s", col, e)
        if deltas:
            rows.append({
                "feature": col,
                "importance": float(np.mean(deltas)),
                "std": float(np.std(deltas)),
                "method": "MDA",
            })

    df = pd.DataFrame(rows).sort_values("importance", ascending=False)
    df["pct_of_base_acc"] = df["importance"] / max(base_acc, 1e-9) * 100
    return df


def error_decomposition(
    train_err: float,
    val_err: float,
    test_err: float | None = None,
    bayes_err: float = 0.05,
) -> dict:
    """
    Andrew Ng'in 'Machine Learning Yearning' error decomposition'i.

    - Avoidable bias  = train_err - bayes_err
    - Variance        = val_err - train_err
    - Train/Val gap   = val_err - train_err (overfit gostergesi)
    - Optimization gap = bayes_err - train_err (negatifse: under-fit edilebilir)

    Sektorel cevrim icin daha agir 'overfit' surprise olur, bu yuzden bias < variance
    durumunda 'model duruyor ama olculmuyor' tani sini veriyoruz.
    """
    avoidable_bias = train_err - bayes_err
    variance = val_err - train_err

    diagnoses = []
    actions = []
    if avoidable_bias > 0.10:
        diagnoses.append("YUKSEK BIAS (UNDERFIT)")
        actions.extend(["Daha buyuk model (n_estimators ↑)",
                          "Daha cok ozellik / interaction term",
                          "Yeni veri kaynagi (Reddit, Patent, Capex)"])
    if variance > 0.10:
        diagnoses.append("YUKSEK VARIANCE (OVERFIT)")
        actions.extend(["Daha cok veri", "Regularization (min_samples_leaf ↑)",
                          "Feature MDA <= 0 olanlari at"])
    if avoidable_bias <= 0.05 and variance <= 0.05:
        diagnoses.append("DENGELI MODEL")
        actions.append("Model production'a uygun")

    return {
        "train_err": round(train_err, 4),
        "val_err": round(val_err, 4),
        "test_err": round(test_err, 4) if test_err is not None else None,
        "bayes_err_assumed": bayes_err,
        "avoidable_bias": round(avoidable_bias, 4),
        "variance": round(variance, 4),
        "diagnoses": diagnoses,
        "actions": actions,
    }


def top_features_report(mdi_df: pd.DataFrame, mda_df: pd.DataFrame | None = None,
                          top_n: int = 5) -> dict:
    """
    Son ML training'inde en yuksek tahmin gucune sahip top_n feature listesi.

    Sentiment vs SMA 'matematiksel ispat' karari uretir:
      ratio = MDA(sentiment) / MDA(sma_*)  > 1.2  -> sentiment hakim
      ratio                                < 0.8  -> SMA hakim
      Aksi                                       -> dengeli

    Returns:
      {
        'top_mdi':       list of {feature, importance, rank},
        'top_mda':       list of {feature, importance, rank, std},
        'sent_score':    aggregate MDA score for sentiment-like features,
        'sma_score':     aggregate MDA score for SMA-like features,
        'ratio':         sent_score / sma_score (matematiksel ispat),
        'verdict':       'SENTIMENT HAKIM' / 'SMA HAKIM' / 'DENGELI',
        'narrative':     dogal dil aciklama
      }
    """
    SENT_KEYS = ["sent", "news", "reddit", "vader", "polarity"]
    SMA_KEYS = ["sma", "ema", "cross", "ma_", "ma20", "ma50", "ma200"]

    def _aggregate(df, keys):
        if df is None or df.empty:
            return 0.0
        mask = df["feature"].str.contains("|".join(keys), case=False, regex=True)
        return float(df.loc[mask, "importance"].sum())

    top_mdi = []
    if mdi_df is not None and not mdi_df.empty:
        for i, row in mdi_df.head(top_n).reset_index(drop=True).iterrows():
            top_mdi.append({
                "rank": i + 1,
                "feature": row["feature"],
                "importance": float(row["importance"]),
            })

    top_mda = []
    if mda_df is not None and not mda_df.empty:
        for i, row in mda_df.head(top_n).reset_index(drop=True).iterrows():
            top_mda.append({
                "rank": i + 1,
                "feature": row["feature"],
                "importance": float(row["importance"]),
                "std": float(row.get("std", 0)),
            })

    sent = _aggregate(mda_df if mda_df is not None else mdi_df, SENT_KEYS)
    sma = _aggregate(mda_df if mda_df is not None else mdi_df, SMA_KEYS)
    ratio = sent / sma if sma > 1e-9 else (float("inf") if sent > 0 else 1.0)
    if ratio > 1.2:
        verdict = "SENTIMENT HAKIM"
        narrative = (f"Sentiment ozelliklerinin toplam MDA skoru ({sent:.4f}) "
                      f"SMA gruplarinin ({sma:.4f}) {ratio:.2f} katidir. "
                      "Haber + Reddit sinyalleri SMA kesisimlerinden daha "
                      "guclu tahmin gucune sahiptir (Lopez de Prado Ch.8).")
    elif ratio < 0.8 and sma > 1e-9:
        verdict = "SMA HAKIM"
        narrative = (f"SMA/trend ozellikleri ({sma:.4f}) sentiment "
                      f"gruplarinin ({sent:.4f}) {1/ratio:.2f} katidir. "
                      "Klasik trend takip teknigi bu modelde daha gucludur.")
    else:
        verdict = "DENGELI"
        narrative = (f"Sentiment ({sent:.4f}) ve SMA ({sma:.4f}) yaklasik "
                      f"esit tahmin gucune sahip (ratio={ratio:.2f}). "
                      "Karma sinyal aktif.")

    return {
        "top_mdi": top_mdi,
        "top_mda": top_mda,
        "sent_score": round(sent, 6),
        "sma_score": round(sma, 6),
        "ratio": round(ratio, 3),
        "verdict": verdict,
        "narrative": narrative,
    }


def diagnose_model(result: dict) -> dict:
    """
    `ml_model.full_analysis()` ciktisini al -> bias/variance dekompozisyonu uret.
    `result` icinde 'train_accuracy' ve 'test_accuracy' bekleniyor (ml_model.py).
    """
    train_acc = float(result.get("train_accuracy", result.get("accuracy", 0.5)))
    test_acc = float(result.get("test_accuracy", result.get("accuracy", 0.5)))
    return error_decomposition(
        train_err=1 - train_acc,
        val_err=1 - test_acc,
        bayes_err=0.10,  # Borsa icin 'irreducible' tahmini
    )
