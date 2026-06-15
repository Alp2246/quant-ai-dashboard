"""
ingestion - cig veri toplayicilar.

Her modul async def poll(ctx: TaskContext) -> None imzasini saglar.
orchestrator bu fonksiyonu her tick'te cagirir.

Adim 2+ icin planlanan moduller:
    sec_edgar.py        - SEC EDGAR 8-K/Form 4/13D EFTS canli tarayici
    reddit.py           - r/wallstreetbets, r/stocks mention velocity
    polygon_options.py  - unusual options activity
    stocktwits.py       - trending tickers
    google_trends.py    - arama hacmi spike
    mofcom_cn.py        - Cin ihracat kontrol duyurulari
    sam_gov.py          - ABD federal sozlesme odulleri
    uspto.py            - patent grants
"""
