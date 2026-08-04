# Changelog

Bu dosya surum bazinda NEYIN neden degistigini tutar. Her madde bir
OLCUME dayanir — "iyilestirdik" demez, once/sonra sayisini yazar.

---

## [v10.0] — 2026-08-04 — Carpimsal Veto Katmani (Gated Scoring)

### Neden bu surum var

Additive skorlama, celisen kanitlari **uzlastiriyordu**. Olculmus vaka
(02.08.2026, canli calistirma):

| Sembol | Skor | Verdict | Ayni paketin icinde ne vardi |
|---|---|---|---|
| LAES | 94.5 | KRITIK ALIM + telefona push | `prob_up=0.376` (SAT), `SIDDETLI OVERFIT` (CV %51.6, gap 0.42), fiyat 2.54 < SMA20 2.57 < SMA50 2.99, net marj **-%187**, isletme nakdi **-31.3M$**, rakiplere karsi 120 gunde **-69pp** |
| ATOM | 82.2 | GUCLU AL | `+30`'un TAMAMI tek basliktan: *"Makes Progress Towards Adoption of MST by GAA Manufacturers"*. Baglayici hicbir sey yok (JDA/LTA/backlog yok), gelir YoY **-%78**, kendi moonshot modulu **-5** ile "J-Curve kirildi" diyor |

Kok neden: `-15` rakip cezasi ve `sma_pt=0` kaybi, tek kalemlik `+20`
moonshot ile silindi. **Toplama islemi celiskiyi yok ediyordu; oysa
celiskinin kendisi bilgidir.**

ATOM'un `+30`'unun teknik sebebi de bulundu:
`strategic_overlays.py` icindeki **ciplak `\bGAA\b`** kalibi — baslikta
gecen iki harf "FOUNDRY INTEGRATION + EXP MODE" esigini tetikliyordu.

### Eklenen

- **`score_gate.py`** — carpimsal veto motoru:
  `Final = Score_raw x M_market x M_overfit x M_fund`
  - `M_market = 0.60` — fiyat **hem** SMA20 **hem** SMA50 altindaysa
    (tek ortalamanin alti FAIL degil; dip alimi stratejisi korunur)
  - `M_overfit = 0.70` — `SIDDETLI/ŞİDDETLİ OVERFIT` **veya** CV < %55
  - `M_fund = 0.70` — OCF<0 **ve** net marj<-%50 **ve** gelir YoY<0
    (ucu birden; tek basina nakit yakmak erken evrede normaldir)
  - `cap_news_uplift()` — temel FAIL veya PR_ONLY iken stratejik+moonshot
    katkisi taban skorun **max %40**'i
- **`evidence_classify.py`** — BAGLAYICI ticari kanit vs NIYET/PR dili.
  `progress towards`, `MoU`, `roadmap`, `unveils` → **PR_ONLY**;
  `long-term agreement`, `backlog grew`, `take-or-pay`, `purchase order`
  → **BINDING**. PR_ONLY iken uplift tavani **+8**.
- **`verdict_rules.gated_verdict()`** ve **`allow_push()`** — overfit ve
  trend bilgisi artik KARARA girer. (Onceden `ml_model.py` Lopez de Prado
  Purged CV ile overfit'i **hesapliyordu ama hicbir imzada yoktu** — yani
  hesaplanip atiliyordu.)
- **`test_funnel_dashboard.py`** — 11 regresyon; her biri gercek olcume dayali.

### Degisen

- **`ticker_analyze_core.py` / `app.py`** — kapilar boru hattina baglandi.
  `master["gates"]`, `score_raw`, `final_score` tasinir.
- **`score_job.py`** — `allow_push=False` ise **gercek Telegram cagrisi hic
  yapilmaz** (verdict string'ini degistirmek yetmiyordu).
- **`notifications.py`** — `handle_master_score(..., gates=)`. Arka kapi olan
  `score >= CRITICAL_THRESHOLD` bypass'i kapatildi.
- **`strategic_overlays.py`** — ATOM ve LAES overlay'lerine PR_ONLY kirpmasi;
  EXP MODE kapanir. **Regex gevsetilmedi**, uzerine kanit kapisi konuldu.
- **`investor_summary.py`** — Investor Executive Summary tablosu verdict'i
  HAM `master_score`'dan yeniden hesapliyordu ve kapilari **atliyordu**.
  Artik kapi varsa `final_score` + `gated_verdict` gosterilir; seffaflik icin
  **Ham Skor** ve **Kapi** sutunlari eklendi.

### Olculmus sonuc (canli, gercek boru hatti)

| | ONCE | SONRA |
|---|---|---|
| LAES skor | 94.5 | **42.0** (`raw=100.0` x 0.6 x 0.7) |
| LAES verdict | KRITIK ALIM | **BEKLE** |
| LAES push | gidiyordu | **bastirildi** |
| ATOM overlay | +30 (EXP MODE) | **+8** (`pr_only=True`) |
| ATOM skor | 82.2 | **26.5** |
| ATOM verdict | GUCLU AL | **DIKKAT** |

**Huni "her seyi reddet" makinesi degildir:** baglayici kanit + saglikli
temel + fiyat>SMA50 + temiz model senaryosu testte hala `KRITIK ALIM` ve
`allow_push=True` uretiyor (`test_tam_gecis_hala_push_uretebilir`).

### Bilincli olarak YAPILMAYANLAR / acik riskler

- **Edge iddiasi YOK.** Kapilar yanlis AL/push sayisini azaltir; pozitif
  alpha uretimi ayri ve **kanitlanmamis** bir hipotezdir.
- `compute_master_score` additive formulu **silinmedi** — panel kirilimi
  aynen gorunur; karar ve push `final_score` uzerinden verilir.
- `_system_validation.py` 115/116: tek basarisiz kontrol (`NVTS Verdict`)
  **onceden var olan** sozluk uyumsuzlugudur — test eski
  `EKLE/TUT/AZALT` sozlugunu bekler, `investor_summary` ise
  `verdict_rules` sozlugune gecirilmistir. Bu surumde dokunulmadi.
- Aleabito Monitor <-> Dashboard koprusu bu turda kurulmadi; `ml_pack`
  Monitor tarafinda hala `None` (kod hazir ve testli).
- `M_fund` muhafazakardir (uc sart birden). Canli koşuda LAES/ATOM icin
  `M_fund=1.0` cikti; diger iki kapi yeterli oldu.

---

## [v9.x] — onceki surumler

Bkz. `git log`. Master Score v9 (30/30/20/20 additive + modifier),
Monte Carlo, Black-Litterman, Lopez de Prado Purged CV, Telegram + PWA.
