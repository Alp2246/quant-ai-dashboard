# Referans Kutuphaneler ve Kaynaklar

Bu dashboard'da kullanilan ve gelecekte entegre edilebilecek acik kaynak araclar.

## 1. Finansal ML / Quant (Mevcut + Gelistirme)

### Su an kullaniliyor
- **yfinance** — fiyat + temel veri + haber. Hong Kong / Shanghai borsalari icin
  `0981.HK`, `1347.HK` formatini destekler. Bazi durumlarda yetersiz kalabilir;
  alternatifler: `akshare`, `investpy`, `eodhd`.
- **scikit-learn** + **XGBoost** — yon tahmini siniflandirma.
- **Prophet (Meta)** — 6 ay ve 10 yil zaman serisi tahmini, %80 guven araligi.
- **statsmodels** — Bollinger bands, regresyon araclari.

### Onerilen Genisleme
- **AI4Finance-Foundation/FinRL** ([github](https://github.com/AI4Finance-Foundation/FinRL))  
  Reinforcement learning ile alim-satim. PPO/A2C/DDPG ajanlari ile dinamik
  strateji ogrenmesi. Bu projeye eklenirse `backtest.py`'deki sabit kurali
  (RSI<40 + MACD>signal) RL ajaniyla degistirebiliriz.

- **mrjbq7/ta-lib** ([github](https://github.com/mrjbq7/ta-lib))  
  200+ indikator (RSI, MACD, Bollinger, Stochastic, ADX, Ichimoku). C
  kutuphanesi gerektirir; Python `TA-Lib` paketi onun wrapper'i. Pure-python
  alternatif: `ta` paketi (zaten requirements.txt'de). Bollinger Bands su an
  `technical_indicators.py` icine eklenmis durumda.

- **Backtrader / Vectorbt / Zipline** — sektorel altin standart backtest
  motorlari. Su an basit kendi backtest motorumuz var; ileride
  `vectorbt`'a tasinabilir (cok daha hizli vector tabanli).

## 2. Sentiment Analizi

### Su an kullaniliyor
- **TextBlob** — basit polarite (-1..+1).
- **NLTK** — tokenizer, brown corpus.
- **feedparser** — Reddit RSS, Google News RSS.

### Onerilen Genisleme
- **TheBigStockMarket/Stock-Sentiment-Analysis** — haber basliklarini NLP ile
  analiz edip fiyat tahmini yapan akademik proje. Bizim modulun pipeline'ina
  ek model olarak eklenebilir.
- **FinBERT** ([yiyanghkust/finbert-tone](https://huggingface.co/yiyanghkust/finbert-tone))  
  Finans-spesifik BERT modeli. TextBlob'tan cok daha dogru. `transformers`
  paketiyle entegre edilebilir; ~500MB model agirligi.
- **PRAW** (Python Reddit API Wrapper) — anahtarli daha derin Reddit erisimi.
  Su an RSS kullaniyoruz (anahtarsiz).
- **snscrape** — Twitter/X arsiv tarama (rate limit'siz alternatif).

## 3. UI / Dashboard

### Su an kullaniliyor
- **Streamlit** + **Plotly** + plotly.express.

### Referans Projeler
- **Streamlit-Financial-Dashboard** — galerilerde 30+ Streamlit dashboard ornegi.
- **Fin-Analyzer** — bilanco/gelir tablosu karsilastirma araci.

## 4. Cinli Hisseler / Global Borsalar

yfinance dogrudan calismazsa:
- **akshare** ([github.com/akfamily/akshare](https://github.com/akfamily/akshare)) —
  cok kuvvetli Cin pazar verisi (A-share, H-share, Shenzhen). Anahtarsiz.
- **investpy** ([github.com/alvarobartt/investpy](https://github.com/alvarobartt/investpy)) —
  investing.com verisi (zaman zaman blokli olabilir).
- **EOD Historical Data API** — paralı ama global tum borsalar.

## 5. Risk / Portfoy Yonetimi

### Su an
- Sharpe Ratio, Maximum Drawdown, Calmar Ratio (backtest.py).
- ATR tabanli dinamik Stop-Loss / Take-Profit.
- 10y bust/stable/10x/100x risk dagilim heuristik'i.

### Onerilen
- **PyPortfolioOpt** — Markowitz, Black-Litterman portfoy optimizasyonu.
- **Riskfolio-Lib** — gelismis risk modelleri (CVaR, EVaR, OmegaRatio).
- **Empyrical** (Quantopian) — getiri istatistikleri (Sortino, Omega vb.).

## 6. Veri Saglama / Cache

- **DuckDB** — yerel parquet uzerinde SQL; uzun gecmis veri saklamak icin.
- **APScheduler** — 15-dakikalik refresh icin cron-benzeri.
- **Redis** — Streamlit cache_data yerine paylasilan cache (multi-user).

## 7. Bu Projedeki Modul Esmesi

```
data_fetcher.py          -> yfinance + currency + fallback
technical_indicators.py  -> ta benzeri (RSI/MACD/ATR/Bollinger/SMA-20-50-200)
fundamentals.py          -> yfinance .info -> 5-bilesenli Fundamental Score
radar_watchlist.py       -> Durability (6 boyut, R&D + gross margin moat dahil)
forecasting.py           -> Prophet (6 ay + 10 yil)
backtest.py              -> kural tabanli + Sharpe/MaxDD/Calmar
master_score.py          -> Teknik 40 / Haber 20 / Reddit 20 / Temel 20
sentiment_analysis.py    -> TextBlob + Google RSS + NewsAPI + Reddit RSS
reddit_sentiment.py      -> r/stocks, r/investing, r/QuantumComputing,
                            r/semiconductors, r/wallstreetbets
critical_news.py         -> 80+ anahtar term (InP, GaAs, SiC, supply chain,
                            Cin-ABD tekno savasi, EUV, sanctions)
milestones.py            -> statik DB + haberden regex cimbiz
dca_calculator.py        -> aylik DCA + 10 yil up/central/down projeksiyon
risk_distribution.py     -> bust / 10x / 100x heuristik dagilim
notifications.py         -> plyer toast + alerts.log
app.py                   -> Streamlit (9 sekme)
```

## 8. Kullanilan Veri Kaynaklari Ozeti

| Kaynak | Tip | Anahtar | Limit |
|--------|-----|---------|-------|
| yfinance | OHLCV, news, info | yok | adil kullanim |
| Google News RSS | haber | yok | yok |
| Reddit RSS | sosyal medya | yok | ~60 req/dk |
| NewsAPI | haber (opsiyonel) | NEWS_API_KEY | ucretsiz 100/gun |
| OpenAI (opsiyonel) | sentiment LLM | OPENAI_API_KEY | kullanima gore |

## 9. Sonraki Adim Onerileri

- **FinRL ajan**: `train_model()`'i RL ile degistir.
- **FinBERT**: TextBlob yerine finans-spesifik BERT.
- **Vectorbt**: backtest'i 100x hizlandir, parametre taramasi yap.
- **akshare**: Cin A-share verisi.
- **PyPortfolioOpt**: 5 hisseyi optimal agirliklarla bul (Sharpe maksimize).
