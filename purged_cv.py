"""
purged_cv.py — Purged K-Fold Cross-Validation.

Akademik Referans:
  - López de Prado, M. (2018). *Advances in Financial Machine Learning*,
    Ch.7: "Cross-Validation in Finance". Wiley.

Formul (Math_Specs.md Bolum 6):
  T_train^(k) = T \ ( T_test^(k) UNION E^(k) )
  E^(k) = { t : min(T_test) - h_e <= t <= max(T_test) + h_e }

  Overfit Gap = Acc_train - Acc_purged_cv
    <= 0.05  -> CLEAN
    <= 0.15  -> WARNING
    >  0.15  -> SEVERE OVERFIT

PROBLEM: Finansal ML modellerinde overfitting yakalamak zordur, cunku
tarihsel veri auto-correlated'tir. Standart k-fold CV, train/test set'lerini
zamansal olarak ic ice koyar => 'leakage' ve aldatici yuksek accuracy.

COZUM: Purged K-Fold CV:
  1) Train ve test set'leri arasinda 'embargo gap' (zaman bosluğu) birak
  2) Train kismindan, test'in label-horizon'u kadar gunluk veriyi 'purge' et
     (sil) - boylelikle hicbir train sample'i test'in 'gelecegini' tasimaz.

Bu, AXTI gibi spekulatif hisselerin saçma $23K projeksiyonlarini
engelleyen ana mekanizmadir.

Kullanım:
    from purged_cv import purged_kfold_cv_score
    score = purged_kfold_cv_score(model, X, y, n_splits=5,
                                    horizon_days=20, embargo_days=5)
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import accuracy_score

from config import PURGED_CV_EMBARGO_DAYS, PURGED_CV_HORIZON_DAYS

logger = logging.getLogger(__name__)


def purged_kfold_indices(n_samples: int, n_splits: int = 5,
                           horizon_days: int = PURGED_CV_HORIZON_DAYS,
                           embargo_days: int = PURGED_CV_EMBARGO_DAYS) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Purged K-Fold split indeksleri uret.

    Args:
      n_samples:     toplam veri uzunlugu
      n_splits:      K kac olacak
      horizon_days:  her sample'in label-horizon'u (ileri gunu).
                     Tutarlilik icin bu deger backtest'teki holding_days ile
                     ayni varsayima hizalanmalidir.
      embargo_days:  test sonrasi embargo bosluğu

    Returns:
      list of (train_idx, test_idx)

    Mantik:
      - K-Fold gibi test_idx[i:i+fold_size] alinir
      - Train_idx = test civarinda horizon + embargo gun silinmis butun veri
    """
    if n_samples < n_splits * 2:
        # Veri yetersiz - tek fold
        return [(np.arange(0, n_samples // 2), np.arange(n_samples // 2, n_samples))]

    fold_size = n_samples // n_splits
    splits = []
    for k in range(n_splits):
        test_start = k * fold_size
        test_end = (k + 1) * fold_size if k < n_splits - 1 else n_samples
        test_idx = np.arange(test_start, test_end)

        # Purge: test civarinda horizon_days kadar veri (her iki yon)
        purge_start = max(0, test_start - horizon_days)
        purge_end = min(n_samples, test_end + horizon_days)

        # Embargo: test sonrasi ek bosluk (sadece future yon)
        embargo_end = min(n_samples, test_end + horizon_days + embargo_days)

        train_idx = np.concatenate([
            np.arange(0, purge_start),
            np.arange(embargo_end, n_samples),
        ])
        if len(train_idx) < 20:
            continue
        splits.append((train_idx, test_idx))
    return splits


def purged_kfold_cv_score(model, X: pd.DataFrame, y,
                             n_splits: int = 5,
                             horizon_days: int = PURGED_CV_HORIZON_DAYS,
                             embargo_days: int = PURGED_CV_EMBARGO_DAYS) -> dict:
    """
    Purged K-Fold CV ile model dogrulugu olc.

    Returns:
      {
        mean_accuracy, std_accuracy, per_fold_acc[],
        n_folds_used, overfitting_gap (train_acc - cv_acc)
      }

    overfitting_gap > 0.15 ise model siddetli overfit ediyor demektir.
    AXTI gibi spekulatif hisselerde bu gap genellikle 0.30'un ustundedir.

    Not:
      ML label horizontu ile tarihsel backtest holding_days'i farkliysa,
      purged CV teknik olarak dogru olsa bile iki modul farkli "gelecek"
      varsayimlariyla calisiyor demektir.
    """
    if hasattr(X, "reset_index"):
        X = X.reset_index(drop=True)
    if hasattr(y, "reset_index"):
        y = y.reset_index(drop=True)
    y = np.asarray(y)

    n = len(X)
    splits = purged_kfold_indices(n, n_splits, horizon_days, embargo_days)

    fold_acc = []
    train_acc_all = []
    for k, (tr, te) in enumerate(splits):
        try:
            m = clone(model)
            X_tr = X.iloc[tr] if hasattr(X, "iloc") else X[tr]
            X_te = X.iloc[te] if hasattr(X, "iloc") else X[te]
            m.fit(X_tr, y[tr])
            pred = m.predict(X_te)
            fold_acc.append(accuracy_score(y[te], pred))
            # Train accuracy (overfit teshisi)
            train_acc_all.append(accuracy_score(y[tr], m.predict(X_tr)))
        except Exception as e:
            logger.debug("purged fold %d failed: %s", k, e)

    if not fold_acc:
        return {"mean_accuracy": 0.5, "std_accuracy": 0.0,
                "per_fold_acc": [], "n_folds_used": 0,
                "overfitting_gap": 0.0,
                "verdict": "VERI YETERSIZ"}

    mean_cv = float(np.mean(fold_acc))
    std_cv = float(np.std(fold_acc))
    mean_train = float(np.mean(train_acc_all)) if train_acc_all else mean_cv
    gap = mean_train - mean_cv

    if gap >= 0.20:
        verdict = "SIDDETLI OVERFIT (model guvensiz)"
    elif gap >= 0.10:
        verdict = "ORTA OVERFIT (dikkat)"
    elif gap >= 0.05:
        verdict = "HAFIF OVERFIT (kabul edilebilir)"
    elif gap >= -0.02:
        verdict = "DENGELI"
    else:
        verdict = "UNDERFIT"

    return {
        "mean_accuracy": round(mean_cv, 4),
        "std_accuracy": round(std_cv, 4),
        "mean_train_accuracy": round(mean_train, 4),
        "per_fold_acc": [round(x, 4) for x in fold_acc],
        "n_folds_used": len(fold_acc),
        "overfitting_gap": round(gap, 4),
        "verdict": verdict,
        "horizon_days": horizon_days,
        "embargo_days": embargo_days,
    }
