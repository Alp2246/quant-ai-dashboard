# Changelog

Bu dosya surum bazinda NEYIN neden degistigini tutar. Her madde bir
OLCUME dayanir — "iyilestirdik" demez, once/sonra sayisini yazar.

---

## [v11.0] — 2026-10-11 — Trend Kurali + 10 Yillik Pencere (ufuk uyumu)

### Neden bu surum var

Soru: "Programin dedigini yapsaydik neden zarar ediyorduk?" — 11.10.2026
tarihinde olcumle cevaplandi. Uc ayri katmanli neden bulundu:

1. **Gercek sinyaller (May–Agu 2026, takip edilse -%28,2):** toplamsal
   skor anlati/hype'i zirvede AL sinyaline ceviriyordu. Bu v10.0 kapilari
   ile COZULMUSTU (LAES 94.5 -> 42.0; o paketlerin 6'si bugun engellenir).
2. **Backtest kuralinin seciciligi yok denecek kadar az:** sinyal gunlerinin
   5g getirisi +%2.26 vs ayni hisselerde rastgele gun +%1.25 — kural bilgi
   tasimiyordu. 304 islemde win %35.5 < kira noktasi %36.6; islem basi
   beklenti -%0.22 (toplam -%66.6). Maliyet (30bp x 304 = %0.9) ve
   "zirve alimi" (sinyal oncesi 20g ort. +%2.6) suclu DEGIL.
3. **Ufuk uyusmazligi (asil katil):** getirinin AYLARCA biriktigi volatil
   evrende (SMCI al-tut +%1743, IONQ +%269) eski salinim kurali pozisyonu
   ortalama 5–6 gunde kapatiyordu. Cikistan sonra hisseler ort. 20g +%9.2 /
   60g +%28.3 gitmeye devam ediyordu. Cikis kuralini (SAT %77, ort. -%2.3)
   tamamen kaldirmak kayiplari BUYUTTU (-%110) — sorun cikis degil,
   5 gunluk islem ufkunun tezin ufkuyla celismesiydi.

### Olculmus sonuc (ayni 10 hisse / 10 yil verisi, tek oturum)

| | ONCE (salinim, TP 3xATR, 20g) | SONRA (trend, TP 6xATR, 60g) |
|---|---|---|
| Islem | 304 | 102 |
| Islem toplam getiri | -%66.6 | **+%442.5** |
| Bilesik | -%94.0 | **+%191.6** |
| POET | -%74.6 | **+%531.7** (al-tut +%12.4) |
| NVTS | -%44.8 | +%32.4 (alpha +%48.1) |

Dürüst not: win rate hâlâ ~%37 — kural cok islem kaybeder ama artik
kazananlari kesmez. RGTI/LAES/ATOM gibi deger kaybeden isimlerde bile
al-tut'un onune gecti.

### Eklenen/Degisen

- **`backtest.generate_signals` v11.0 TREND kurali:** AL = RSI 50 yukari
  kesisimi AND MACD hist > 0 AND Close > SMA200. SAT sinyali YOK — cikis
  yapısaldir (SL 2xATR / TP 6xATR / TIME 60g / END).
- **Eski kural arsivlendi:** `_generate_signals_swing_v10` (geri donus tek
  satir).
- **`atr_tp_mult` varsayilani 3.0 -> 6.0**; `BACKTEST_HOLDING_DAYS`
  20 -> 60 (`config.py`).
- **`PURGED_CV_HORIZON_DAYS` is motorundan AYRILDI** (sabit 20): yoksa
  ML etiket ufku sessizce 60 gune kayardi.
- **`BACKTEST_LOOKBACK_YEARS` 2.0 -> 10.0**; **`HISTORY_PERIOD` 5y -> 10y**
  (10y backtestin verisi eksik kaliyordu, sessizce 5y'ye kirpiliyordu).
- **`test_backtest_trend.py`** — 6 regresyon testi (SAT yok / rejim
  filtresi / TP=6xATR sabiti).
- **QA S4 senaryosu guncellendi:** "ATOM GAA bonus >= 15" beklentisi
  v10.0'in bilincli PR_ONLY kırpmasiyla celisiyordu; tespit + kırpma +
  baglayici-kanit-varken-kirpilma yok seklinde 3 kontrole bölündü (13/13).

### Bilincli olarak YAPILMAYANLAR / acik riskler

- **Edge iddiasi hâlâ YOK** — bu kurallar da canli paranın gerçek kopyası
  degildir; ileriye donuk paper trading ile olculmeli.
- v10.0 kapilari (master score hatti) bu kural degisikliginden
  ETkilENMEZ; backtest sekmesi ve reality check yeni kurali kullanir.
- SMA200 filtresi tek basina win rate'i duzeltMEdi (%35.5 -> %35.8);
  asil fark TP/TIME ufku genislemesiyle geldi.

---

## [v11.1] — 2026-10-11 — Ilere Donuk Olcum + Sinyal Akisi Onari

### Neden

Kullanici Ocak 2026'da 10–50k USD gercek para yatiracak (2030/2035/2040
ufku). v11.0 kuralinin edge'i geriye donuk testte degil GEREK ZAMANDA
olculmeli; ayrica veri akisinda iki bayatlik vardi.

### Yapilan

- **`paper_trading.py`** — v11.0 kuralinin canli olcum defteri. Her kosuda
  acik pozisyonlari yonetir (SL 2xATR / TP 6xATR / TIME 60 bar), sinyal
  veren hisseye sanal giris acar, her olayi `data/paper_trades.jsonl`ye
  yazar. Ocak'a kadar 2-3 ay out-of-sample veri toplanir; `summarize()`
  win rate/expectancy raporlar.
- **Gunluk otomasyon** (00:47 Europe/Istanbul, ABD kapanisi sonrasi):
  score_job + reality_check --export + paper_trading. Ilk kosum 11.10.2026
  basarili (3/3 adim OK, bildirim gitti). SMCI 37.7 DIKKAT + push kapida
  bastirildi — huni canli calisiyor.
- **`reality_snapshot.json` bayatligi kapatildi** — 71 gunluk bayatligin
  nedeni crash degil, export adiminin hic ZAMANLANMAMIS olmasiydi. Gunluk
  otomasyona eklendi; ilk taze export 11.10.2026.
- **`UZUN_VADE_RAPORU.md`** — Ocak girisi icin aday tablosu (kapili skor +
  sector_tam 10y bantlari + moonshot). O gunun gercegi: 10 hissenin 10'unda
  da M_overfit=0.7 (kisa gecmisli spekulatif evrende ML modelleri guven
  vermiyor) ve cogunluk fiyat SMA20/50 altinda — Ocak'a kadar takip
  kriteri: HAM skor yuksek + kapi acilirsa (fiyat>SMA50, model CV>%55)
  aday sayilir.
- **Genel temizlik (11.10.2026)** — 125 .py derleme taramasi: 0 bozuk;
  32 cekirdek modul import testi: 0 hata; app.py modul duzeyi calisti.
  ~870 MB olü agirlik kaldirildi: `build/` (359MB PyInstaller ara urunu),
  `tools/android-sdk` + JDK/node/git/gh yukleyicileri (APK deneme
  toolchain'i, `_download_*.py` ile geri indirilebilir), Mayis kalintisi
  `_build.log`/`_streamlit.err.log`. tools/'ta yalniz aktif tunnel
  araclari kaldi (cloudflared, tailscale msi).

### Bilincli risk / dürüst not

"Maximum verimde olan hisseyi yakalamak" garantisi YOKTUR. Sistem
olasilik siralar; Bessembinder gercegi: spekulatif hisselerin cogunlugu
S&P'yi yenemez. Gercek para, paper defterinde olumlu expectancy gorulene
kadar beklemelidir.

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
