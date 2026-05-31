# 📚 Ogrenme Kaynaklari — Quant AI Dashboard icin

Bu liste, projeyi anlamak ve gelistirmek icin onerilen kaynaklardir.
**Sira:** once Python temeli → veri → finans → ML → dashboard.

---

## 1) Python Temeli (baslangic)

| Kaynak | Tur | Neden |
|--------|-----|-------|
| *Automate the Boring Stuff with Python* — Al Sweigart | Kitap (ucretsiz web) | Pratik, hizli baslangic |
| *Python Crash Course* — Eric Matthes | Kitap | Temiz OOP + proje |
| freeCodeCamp Python (YouTube) | Video | Ucretsiz, Turkce altyazi |
| docs.python.org/3/tutorial | Dokumantasyon | Resmi referans |

**Ogren:** degiskenler, fonksiyonlar, siniflar, dosya okuma, `pip`, sanal ortam (`venv`).

---

## 2) Veri Bilimi (pandas, numpy)

| Kaynak | Tur |
|--------|-----|
| *Python for Data Analysis* — Wes McKinney | Kitap (pandas yazari) |
| Kaggle "Python" + "Pandas" micro-courses | Ucretsiz interaktif |
| pandas.pydata.org/docs | Dokumantasyon |

**Ogren:** DataFrame, filtreleme, `groupby`, zaman serisi (`resample`).

---

## 3) Kantitatif Finans (Quant)

| Kaynak | Tur | Konu |
|--------|-----|------|
| *Advances in Financial Machine Learning* — Marcos Lopez de Prado | Kitap | ML + finans (ileri) |
| *Algorithmic Trading* — Ernest Chan | Kitap | Strateji, backtest |
| *Quantitative Trading* — Ernest Chan | Kitap | Basit quant giris |
| Investopedia (RSI, MACD, CFAR benzeri) | Web | Teknik analiz |
| yfinance dokumantasyonu | Web | Hisse verisi cekme |

**Ogren:** getiri, volatilite, RSI, MACD, overfitting, backtest tuzaklari.

---

## 4) Makine Ogrenmesi

| Kaynak | Tur |
|--------|-----|
| *Hands-On Machine Learning* — Aurelien Geron | Kitap |
| scikit-learn.org/stable/user_guide.html | Dokumantasyon |
| Kaggle "Intro to Machine Learning" | Ucretsiz kurs |

**Ogren:** train/test split, classification, `RandomForest`, `XGBoost`, feature importance.

---

## 5) NLP / Sentiment

| Kaynak | Tur |
|--------|-----|
| *Natural Language Processing with Python* — Bird, Klein, Loper | Kitap (NLTK) |
| TextBlob dokumantasyonu | Web |
| NewsAPI dokumantasyonu | Web (opsiyonel API) |

**Ogren:** tokenization, polarity, haber → skor pipeline.

---

## 6) Dashboard / Gorsellestirme

| Kaynak | Tur |
|--------|-----|
| docs.streamlit.io | Dokumantasyon |
| plotly.com/python | Grafik kutuphanesi |
| *Interactive Dashboards with Streamlit* (cok sayida blog) | Web |

---

## 7) Bu Projeyi Anlamak Icin Okuma Sirasi

```
1. config.py          → sabitler, esikler
2. technical_indicators.py → RSI, MACD nasil hesaplanir
3. data_fetcher.py    → yfinance ile veri
4. sentiment_analysis.py → haber + TextBlob
5. ml_model.py        → ozellikler + model + AL/BEKLE/SAT
6. alerts.py          → alim firsati kurallari
7. app.py             → Streamlit arayuzu
```

---

## 8) Ucretsiz API Anahtarlari (opsiyonel)

| Servis | Ucretsiz limit | Kayit |
|--------|----------------|-------|
| NewsAPI | 100 istek/gun | newsapi.org |
| Alpha Vantage | 25 istek/gun | alphavantage.co |
| OpenAI | ucretli | platform.openai.com |

`.env` dosyasina `NEWS_API_KEY=...` yaz.

---

## 9) Senin Bilgisayarinda (Ryzen 9 + 32 GB RAM)

- Python 3.12 yeterli
- XGBoost CPU'da hizli calisir
- GPU gerekmez (bu proje icin)
- MATLAB: radar/FPGA isleri icin (ayri proje)
- Vivado: FPGA (ayri proje)

---

## 10) Sonraki Adimlar (projeyi gelistir)

- [ ] Gercek backtest modulu ekle
- [ ] Portfoy optimizasyonu (Markowitz)
- [ ] Telegram/Discord uyari botu
- [ ] PostgreSQL ile veri arsivi
- [ ] LSTM / Transformer fiyat tahmini (ileri seviye)
