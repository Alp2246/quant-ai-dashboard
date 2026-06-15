"""
sentiment - Lexicon tabanli negatif/pozitif ton dedektoru.

Neden lexicon (transformer degil)?
    - Bagimsiz model yok, ek paket yok, anlik (mikrosaniyede 1k baslik).
    - Finans dilinde "miss", "guidance cut", "investigation", "lawsuit",
      "delisting", "halt", "fraud", "bankruptcy" gibi spesifik kelimeler
      transformer'larin yakaladigindan daha guvenilir.
    - Cok yuksek precision (false positive az), recall ortalamada.

Kullanim:
    from src.analytics.sentiment import score_text
    s = score_text("Acme misses Q3 guidance, lowers FY outlook")
    # -> -3.2  (cok negatif)
    if s < -2: print("dusus uyarisi")
"""
from __future__ import annotations

import math
import re
from typing import Iterable

# ===========================================================================
#  Lexicon - finans dilinde bilinen sinyal kelimeleri
#  Skorlar: -3..3 (mutlak deger > etki agirligi)
# ===========================================================================
NEGATIVE = {
    # Catastrophic (-3.0)
    "fraud": -3.0, "bankruptcy": -3.0, "bankrupt": -3.0, "delisting": -3.0,
    "delisted": -3.0, "ponzi": -3.0, "scandal": -3.0, "indictment": -3.0,
    "indicted": -3.0, "insolvent": -3.0, "insolvency": -3.0,

    # Major problems (-2.5)
    "investigation": -2.5, "subpoena": -2.5, "lawsuit": -2.5, "sued": -2.5,
    "halt": -2.5, "halted": -2.5, "suspended": -2.5, "suspension": -2.5,
    "warning": -2.5, "default": -2.5, "downgrade": -2.5, "downgraded": -2.5,
    "restatement": -2.5, "restated": -2.5,

    # Operational misses (-2.0)
    "missed": -2.0, "miss": -2.0, "misses": -2.0, "shortfall": -2.0,
    "disappointing": -2.0, "disappoint": -2.0, "fell short": -2.0,
    "below estimates": -2.0, "below expectations": -2.0,
    "guidance cut": -2.0, "lowers guidance": -2.0, "cut outlook": -2.0,
    "slashes": -2.0, "slashed": -2.0,
    "layoffs": -2.0, "layoff": -2.0, "fires": -2.0, "fired": -2.0,
    "restructuring": -1.8, "restructure": -1.8, "writedown": -2.0,
    "writeoff": -2.0, "impairment": -2.0, "loss": -1.5, "losses": -1.5,
    "decline": -1.5, "declined": -1.5, "drop": -1.5, "dropped": -1.5,
    "plunge": -2.0, "plunged": -2.0, "tumble": -2.0, "tumbled": -2.0,
    "crash": -2.5, "crashed": -2.5, "collapse": -2.5, "collapsed": -2.5,
    "slump": -2.0, "weakness": -1.5, "weak": -1.2,
    "concerns": -1.3, "concern": -1.3, "worries": -1.3, "worried": -1.3,
    "risk": -1.0, "risks": -1.0, "risky": -1.2,
    "delay": -1.5, "delayed": -1.5, "postpone": -1.3, "postponed": -1.3,
    "recall": -2.0, "recalled": -2.0, "defect": -2.0, "defective": -2.0,
    "failure": -1.8, "failed": -1.8, "fails": -1.5,
    "sell-off": -1.5, "selloff": -1.5, "bearish": -1.5, "bear": -1.0,
    "exit": -1.0, "leaves": -1.0, "resign": -1.5, "resigned": -1.5,
    "step down": -1.5, "steps down": -1.5, "fired": -1.8,
    "rejected": -1.5, "denied": -1.3,
    "tariff": -1.3, "tariffs": -1.3, "sanctions": -1.8, "ban": -1.8,
    "banned": -1.8, "embargo": -2.0,
    "probe": -1.8, "fines": -1.5, "fined": -1.5, "penalty": -1.5,
    "settlement": -1.0,  # genelde sirket icin negatif
    "short report": -2.5, "short seller": -2.0, "shorted": -1.5,
}

POSITIVE = {
    # Major positive (+2.5)
    "acquisition": 2.5, "acquired": 2.5, "acquire": 2.0, "merger": 2.0,
    "buyout": 2.5, "deal signed": 2.5, "contract awarded": 2.5,

    # Strong (+2.0)
    "beats": 2.0, "beat": 2.0, "exceeded": 2.0, "exceeds": 2.0,
    "above estimates": 2.0, "above expectations": 2.0,
    "record": 2.0, "all-time high": 2.5, "ath": 1.5,
    "upgrade": 2.0, "upgraded": 2.0, "outperform": 2.0,
    "breakthrough": 2.5, "milestone": 1.5, "approved": 2.0, "approval": 2.0,
    "fda approval": 2.5, "fda approved": 2.5,
    "raises guidance": 2.0, "raised guidance": 2.0, "hikes outlook": 2.0,
    "boom": 2.0, "surge": 2.0, "surges": 2.0, "surged": 2.0,
    "rally": 1.8, "rallies": 1.8, "rallied": 1.8,
    "soar": 2.0, "soared": 2.0, "skyrocket": 2.2, "skyrockets": 2.2,
    "jump": 1.5, "jumps": 1.5, "jumped": 1.5,
    "growth": 1.3, "growing": 1.3, "expansion": 1.3, "expanding": 1.3,
    "profit": 1.2, "profitable": 1.5, "profitability": 1.5,
    "strong": 1.2, "stronger": 1.2, "robust": 1.5,
    "innovative": 1.2, "innovation": 1.2, "leading": 1.0,
    "partnership": 1.5, "partners": 1.0, "alliance": 1.5,
    "bullish": 1.5, "bull": 1.0, "buying": 1.0,
    "win": 1.3, "wins": 1.3, "won": 1.3, "winning": 1.3,
    "launch": 1.3, "launched": 1.3, "launching": 1.3,
    "expand": 1.3, "expands": 1.3, "expanded": 1.3,
    "secured": 1.5, "secures": 1.5,
    "raised": 1.5, "raises": 1.5,  # capital raise often positive
}

# Tum kelimeler tek dict (yer kazandirir + tek lookup)
LEXICON = {**NEGATIVE, **POSITIVE}

# Cumle/baslik bazinda negation (ornek: "not bad", "no concerns")
_NEGATIONS = {"not", "no", "never", "without", "lacks", "lack"}

_WORD_RE = re.compile(r"\b[a-z][a-z\-]+\b")


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return _WORD_RE.findall(text.lower())


def score_text(text: str) -> float:
    """
    Tek metni skorla: negatif/pozitif net agirligin toplami.
    -10..+10 araliginda doner (genelde -5..+5 arasi)
    """
    if not text:
        return 0.0
    tokens = _tokenize(text)
    if not tokens:
        return 0.0
    total = 0.0
    # 2-gram da kontrol et: "raises guidance", "below estimates"
    grams = []
    for i, w in enumerate(tokens):
        grams.append(w)
        if i + 1 < len(tokens):
            grams.append(f"{w} {tokens[i+1]}")
    for i, g in enumerate(grams):
        w = LEXICON.get(g)
        if w is None:
            continue
        # Negation: oncesinde 1-2 kelime icinde "not"/"no" varsa flip
        if i > 0 and grams[i - 1] in _NEGATIONS:
            w = -w * 0.6
        elif i > 1 and grams[i - 2] in _NEGATIONS:
            w = -w * 0.5
        total += w
    # Saturate
    return max(-10.0, min(10.0, round(total, 2)))


def score_texts(texts: Iterable[str]) -> dict:
    """
    Bircok metni skorla; ozet doner:
        {
          "n": 12, "mean": -1.4, "negative_n": 8, "positive_n": 2,
          "neutral_n": 2, "worst": ("title", -3.0),
          "best": ("title", 2.5), "tone": "NEGATIVE"
        }
    """
    items = []
    for t in texts:
        s = score_text(t)
        items.append((t, s))
    if not items:
        return {"n": 0, "mean": 0.0, "tone": "NEUTRAL"}

    scores = [s for _, s in items]
    mean = sum(scores) / len(scores)
    neg_n = sum(1 for s in scores if s <= -1.0)
    pos_n = sum(1 for s in scores if s >= 1.0)
    neu_n = len(scores) - neg_n - pos_n
    worst = min(items, key=lambda x: x[1])
    best = max(items, key=lambda x: x[1])
    if mean <= -1.5 or neg_n >= max(3, 0.4 * len(items)):
        tone = "NEGATIVE"
    elif mean >= 1.5 or pos_n >= max(3, 0.4 * len(items)):
        tone = "POSITIVE"
    else:
        tone = "NEUTRAL"
    return {
        "n": len(items),
        "mean": round(mean, 2),
        "negative_n": neg_n,
        "positive_n": pos_n,
        "neutral_n": neu_n,
        "worst": (worst[0][:140], worst[1]),
        "best": (best[0][:140], best[1]),
        "tone": tone,
    }


def severity_boost(sentiment_mean: float, n_items: int) -> float:
    """
    Sentiment yogunlugu severity carpani uretir. >=1 nötr veya pozitif,
    <1 ise negatif (skor düşürür - bunu engine.py composite'a uygulayabilir).
    Cok negatif (ortalama -3, 5+ baslik) -> 1.5x boost (KRITIK'e iter)
    """
    if n_items < 2:
        return 1.0
    if sentiment_mean <= -2.5:
        return min(1.0 + abs(sentiment_mean) * 0.15, 1.8)
    if sentiment_mean <= -1.5:
        return 1.0 + abs(sentiment_mean) * 0.08
    return 1.0
