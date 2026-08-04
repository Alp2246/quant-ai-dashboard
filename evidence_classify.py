"""evidence_classify.py — BAGLAYICI TICARI KANIT vs NIYET/PR DILI.

NEDEN VAR (olculmus vaka — ATOM, 02.08.2026):
strategic_overlays.ATOM_FOUNDRY_INTEGRATION_PATTERNS icinde CIPLAK bir
`\\bGAA\\b` kalibi var (satir ~204). "Atomera (ATOM) Makes Progress Towards
Adoption of MST by GAA Manufacturers" basligi bu iki harfe takilip
"FOUNDRY INTEGRATION (+30 + EXP MODE)" uretti. Ayni donemde ATOM'un geliri
YoY -%78 idi ve sistemin kendi moonshot modulu -5 ile "J-Curve kirildi"
diyordu. Yani tek bir PR basligi, hicbir baglayici taahhut icermeden
skorun ucte birini tasidi.

Kalip seti Aleabito Monitor'daki scoring.classify_evidence ile ayni
MANTIGI tasir ama BAGIMSIZ bir kopyadir — iki proje arasinda Python
import bagi YOKTUR (ayri repo, ayri venv, ayri yasam dongusu).

TEMEL AYRIM:
  A) BAGLAYICI  : para/kapasite taahhudu var (LTA, imzali sozlesme,
                  take-or-pay, on odeme, backlog buyumesi, siparis defteri)
  B) NIYET/PR   : gelecek vaadi var, taahhut YOK ("progress towards",
                  "exploring", "MoU", "roadmap", "unveils")

B sinifi ASLA A sinifi gibi puanlanamaz.
"""

from __future__ import annotations

from typing import Any

# A — Baglayici ticari kanit
BINDING_KEYS = [
    "long-term agreement", "long term agreement", "lta signed", "binding",
    "take-or-pay", "take or pay", "purchase order", "supply contract",
    "purchase contract", "prepayment", "prepaid", "capacity reservation",
    "backlog grew", "backlog up", "backlog increased", "order book",
    "definitive agreement", "multi-year deal", "multiyear deal",
    "signed a joint development agreement", "jda signed", "jda executed",
    "production qualified", "qualified for production",
    "uzun vadeli anlasma", "uzun vadeli tedarik", "baglayici",
    "siparis defteri", "on odeme", "kapasite rezervasyonu",
]

# B — Niyet / PR dili (taahhut icermez)
PR_ONLY_KEYS = [
    "progress towards", "progress toward", "makes progress", "aims to",
    "plans to", "exploring", "in talks", "mou", "memorandum of understanding",
    "letter of intent", "loi signed", "evaluation kit", "evaluation phase",
    "pilot program", "pilot project", "partnership to develop",
    "roadmap", "unveils", "showcases", "demonstrates", "announces plans",
    "moving towards", "moving toward", "towards adoption", "toward adoption",
    "niyet mektubu", "gorusme asamasinda", "degerlendirme asamasi",
    "pilot uygulama", "yol haritasi", "tanitti",
]

# PR_ONLY tespit edildiginde stratejik/moonshot uplift'in TAVANI.
# +30'luk FOUNDRY INTEGRATION sinifi tek PR ile alinamaz.
PR_ONLY_UPLIFT_CAP = 8


def classify_evidence(text: str) -> dict[str, Any]:
    """Metni ticari kanit gucune gore siniflandirir.

    Donen alanlar:
      binding : baglayici ticari kanit var mi
      pr_only : niyet dili var AMA baglayici kanit YOK
      hits    : eslesen ifadeler (denetlenebilirlik icin)
    """
    low = (text or "").lower()
    binding = [k for k in BINDING_KEYS if k in low]
    intent = [k for k in PR_ONLY_KEYS if k in low]
    return {
        "binding": bool(binding),
        "pr_only": bool(intent) and not binding,
        "hits": {"binding": binding[:3], "intent": intent[:3]},
    }


def classify_news_items(news_items: list[dict] | None) -> dict[str, Any]:
    """Haber listesini (title+summary) tek metin gibi siniflandirir."""
    parts = []
    for it in (news_items or [])[:25]:
        parts.append(str(it.get("title") or ""))
        parts.append(str(it.get("summary") or ""))
    return classify_evidence(" ".join(parts))


def clip_uplift(bonus: int | float, ev: dict[str, Any]) -> tuple[int, str | None]:
    """PR_ONLY ise stratejik/moonshot uplift'i tavana kirp.

    Donen: (kirpilmis_bonus, uyari_metni | None)
    Negatif bonuslar (uyari/ceza) ASLA kirpilmaz — yalnizca yukari yonlu
    sismeler sinirlanir.
    """
    b = int(bonus or 0)
    if b <= PR_ONLY_UPLIFT_CAP or not ev.get("pr_only"):
        return b, None
    return PR_ONLY_UPLIFT_CAP, (
        f"PR_ONLY: baglayici kanit yok ({', '.join(ev['hits']['intent'][:2])}) "
        f"— uplift +{b} → +{PR_ONLY_UPLIFT_CAP} kirpildi"
    )
