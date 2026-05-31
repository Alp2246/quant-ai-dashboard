# Quant AI Dashboard

ABD hisseleri (**WOLF, IONQ, RGTI, ATOM, LAES**) icin:
- Gecmis fiyat (yfinance)
- Haber sentiment (TextBlob + RSS + yfinance news)
- ML sinyali (XGBoost / scikit-learn)
- Streamlit dashboard

> **Uyari:** Egitim amaclidir. Yatirim tavsiyesi degildir.

## Proje Yapisi

```
quant-dashboard/
├── app.py                    # Streamlit ana uygulama
├── config.py                 # Ayarlar, esikler, ticker listesi
├── data_fetcher.py           # yfinance veri cekme
├── technical_indicators.py   # RSI, MACD
├── sentiment_analysis.py     # Haber + NLP skor
├── ml_model.py               # ML tahmin + AL/BEKLE/SAT
├── alerts.py                 # 15 dk alim firsati mantigi
├── requirements.txt
├── .env.example              # Opsiyonel API anahtarlari
├── run.bat                   # Tek tik baslat
├── setup.ps1                 # Ilk kurulum
├── OGRENME_KITAPLARI.md      # Kitap ve kaynak listesi
└── data/                     # Cache (otomatik)
```

## Kurulum (ilk kez)

```powershell
cd C:\fpga_work\quant-dashboard
.\setup.ps1
```

## Calistirma

```powershell
.\run.bat
```

veya:

```powershell
.\venv\Scripts\activate
streamlit run app.py
```

Tarayici: **http://localhost:8501**

## Ozellikler

| Ozellik | Aciklama |
|---------|----------|
| 5 yillik fiyat grafigi | Plotly interaktif |
| Yillik getiri % | Bar chart |
| RSI + MACD | Teknik panel |
| Haber sentiment | -1 .. +1 skor |
| AI Oneri | AL / BEKLE / SAT |
| Alim uyarisi | Yuksek sentiment + teknik + ML |
| 15 dk yenileme | Otomatik (sidebar) |

## Opsiyonel: NewsAPI

1. https://newsapi.org kayit ol
2. `.env` dosyasi olustur:
   ```
   NEWS_API_KEY=senin_anahtarin
   ```

## Sorun Giderme

| Sorun | Cozum |
|-------|-------|
| `python bulunamadi` | `setup.ps1` tekrar calistir veya PATH'e Python ekle |
| TextBlob hatasi | `python -m textblob.download_corpora` |
| Veri bos | Internet + borsa saatleri; sembolleri kontrol et |
| Streamlit acilmiyor | `pip install streamlit` |
