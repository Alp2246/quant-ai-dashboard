"""
ticker_map - ticker <-> CIK eslestirme.

SEC EDGAR filtreleme ticker degil CIK ister. Bu modul SEC'in
company_tickers.json dosyasini indirir ve onbellekler.

Cache: data/state/ticker_cik.json (24 saat gecerli)
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

LOG = logging.getLogger(__name__)
SEC_URL = "https://www.sec.gov/files/company_tickers.json"
CACHE_TTL = 86400  # 24h


async def load_ticker_to_cik(cache_path: Path, user_agent: str) -> dict[str, str]:
    """
    Returns: { "AXTI": "0000895456", "IONQ": "0001824920", ... }
    CIK 10 haneye zero-padded gelir (SEC EDGAR formati).
    """
    if cache_path.is_file():
        age = time.time() - cache_path.stat().st_mtime
        if age < CACHE_TTL:
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception as exc:
                LOG.warning("ticker_cik cache okunamadi: %s", exc)

    from .http_client import get_http_client
    client = get_http_client()
    try:
        raw = await client.get_json(
            SEC_URL,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )
    except Exception as exc:
        LOG.error("ticker_cik indirilemedi: %s", exc)
        if cache_path.is_file():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        return {}

    out: dict[str, str] = {}
    if isinstance(raw, dict):
        for v in raw.values():
            ticker = (v.get("ticker") or "").upper()
            cik = v.get("cik_str")
            if ticker and cik is not None:
                out[ticker] = str(int(cik)).zfill(10)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(out), encoding="utf-8")
    LOG.info("ticker_cik haritasi yuklendi: %d entry", len(out))
    return out
