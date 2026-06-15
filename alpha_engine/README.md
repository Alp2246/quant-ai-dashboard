# QuantAI Alpha Engine

Async, minute-tick **early-warning system** for deep-tech equities. Ingests SEC EDGAR, Form 4 insider purchases, Google News, and Reddit RSS; normalizes signals with **cohort-aware z-scores** (MEGA / MID / SMALL cap); fires **ALPHA EVENTs** when multiple sources spike together; pushes rich **Telegram alerts** (Turkish formatting, English docs).

> **Goal:** Catch catalysts (AXTI-style export news, NVTS OEM deals, Form 4 insider buys) **hours to days before** price discovery — not after.

---

## How it works

```
Sources                Analytics                    Output
─────────              ──────────                   ──────
SEC 8-K      ──┐
Form 4       ──┼──► Signal Bus ──► Cohort z-score ──► Composite score ──► Telegram
Google News  ──┤         ▲              + decay
Reddit RSS   ──┘         └── cooldown ──┘
```

**ALPHA EVENT** = same ticker, **2+ independent sources** above z-threshold (configurable), composite ≥ trigger.

| Severity | Typical trigger |
|----------|-----------------|
| 🚨 KRITIK | SEC filing, insider buy, 3+ sources, extreme sentiment |
| ⚡ YUKSEK | Corroborated 2-source anomaly |

---

## Quick start

```bash
cd alpha_engine
cp .env.example .env   # Windows: copy .env.example .env
```

Minimum `.env`:

```env
SEC_USER_AGENT=YourName your@email.com
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

```bash
python main.py --health    # config check
python main.py --once      # single tick
python main.py --tick 60   # production loop
```

Use project venv from repo root:

```powershell
..\venv\Scripts\python.exe main.py --tick 60
```

---

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `Z_TRIGGER` | 3.0 | Per-source z-score threshold |
| `MIN_SIGNALS_FOR_ALPHA` | 3 | Min sources (engine may use 2 for SMALL) |
| `ALERT_COOLDOWN_MIN` | 60 | Suppress duplicate Telegram spam |
| `MASTER_SCORE_INTERVAL_MIN` | 240 | Run `score_job.py` every N minutes |

See `config.py` and `.env.example`.

---

## Folder layout

```
alpha_engine/
├── main.py              # asyncio orchestrator
├── config.py            # settings + logging
├── src/
│   ├── ingestion/       # SEC, Form4, Reddit, Google News, Polygon
│   ├── analytics/       # engine, sentiment, alpha_notify
│   ├── notifiers/       # telegram_push
│   └── jobs/            # master_score_poll
└── data/state/          # signals, cooldowns (gitignored)
```

---

## Integration with dashboard

- Dashboard tab **🚨 Early Warning** reads `data/state/signals.jsonl`
- `score_job.py` (repo root) sends **KRITIK ALIM / GUCLU AL** Telegram from Master Score
- Unified labels: `verdict_rules.py` at repo root

---

## Disclaimer

Educational/research only. Not financial advice.
