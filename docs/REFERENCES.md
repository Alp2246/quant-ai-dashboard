# References & Acknowledgments

QuantAI implements **published concepts** from quantitative finance, machine learning, and software engineering.  
**No proprietary source code** from commercial broker apps (e.g. Midas, Robinhood, TradingView) was copied. All Python code in this repository is original work by the contributors, licensed under [MIT](../LICENSE).

---

## Academic & industry references

| Concept | Used in | Reference |
|---------|---------|-----------|
| Multi-factor equity scoring | `master_score.py` | Fama, E. F., & French, K. R. (1993). *Common risk factors in the returns on stocks and bonds.* Journal of Financial Economics. |
| Meta-labeling, purged CV, MDA-style dynamic coefficient | `ml_model.py`, `purged_cv.py`, `research_agent.py` | López de Prado, M. (2018). *Advances in Financial Machine Learning.* Wiley. |
| Binomial confidence interval for ML probability | `master_score.py` | Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *JASA.* |
| Black-Litterman portfolio blending | `black_litterman.py` | Black, F., & Litterman, R. (1992). Global portfolio optimization. *Financial Analysts Journal.* |
| Monte Carlo / GBM risk paths | `risk_distribution.py` | Standard geometric Brownian motion (textbook quant finance) |
| Qualitative overlay / scuttlebutt-style milestones | `visionary_goals.py`, `engineering_notes.py` | Fisher, P. (1958). *Common Stocks and Uncommon Profits* (qualitative research tradition) |
| Cohort-normalized anomaly detection | `alpha_engine/src/analytics/engine.py` | Standard z-score / baseline normalization (statistics); design inspired by market-microstructure “unusual activity” practice |
| Sentiment polarity | `sentiment_analysis.py` | Bird, S., Klein, E., & Loper, E. *NLTK*; Loria, S. *TextBlob* |
| Technical indicators (RSI, MACD) | `technical_indicators.py` | Wilder, J. W. (1978) RSI; Appel, G. MACD — via `ta` / standard definitions |

Full formulas: [Math_Specs.md](../Math_Specs.md)

---

## Open-source libraries

| Library | License | Use |
|---------|---------|-----|
| [Python](https://python.org) | PSF | Runtime |
| [Streamlit](https://streamlit.io) | Apache 2.0 | Dashboard UI |
| [pandas](https://pandas.pydata.org) | BSD | Data frames |
| [NumPy](https://numpy.org) | BSD | Numerics |
| [scikit-learn](https://scikit-learn.org) | BSD | ML |
| [XGBoost](https://xgboost.ai) | Apache 2.0 | ML |
| [Plotly](https://plotly.com) | MIT | Charts |
| [yfinance](https://github.com/ranaroussi/yfinance) | Apache 2.0 | Market data (unofficial Yahoo API) |
| [TextBlob](https://textblob.readthedocs.io) | MIT | Sentiment |
| [NLTK](https://nltk.org) | Apache 2.0 | NLP |
| [Prophet](https://facebook.github.io/prophet/) | MIT | Forecasting |
| [feedparser](https://feedparser.readthedocs.io) | BSD | RSS |
| [Tailscale](https://tailscale.com) | Proprietary client | Secure sharing (optional) |

See `requirements.txt` and `alpha_engine/requirements.txt` for versions.

---

## Data sources & terms of use

| Source | Access | Notes |
|--------|--------|-------|
| [SEC EDGAR](https://www.sec.gov/edgar) | Public | Requires honest `SEC_USER_AGENT` (name + email) |
| Google News RSS | Public feeds | Respect rate limits |
| Reddit RSS | Public | Respect rate limits |
| Yahoo Finance (via yfinance) | Unofficial API | Subject to Yahoo terms; not for commercial redistribution |
| Polygon.io | API key (optional) | Subject to Polygon license |

Users are responsible for complying with each provider’s terms.

---

## Trademarks

**QuantAI** is an independent open-source project.  
**Midas**, **Yahoo Finance**, **TradingView**, **Telegram**, **Oracle**, **Tailscale**, ticker symbols, and company names are trademarks of their respective owners.  
No endorsement or affiliation is implied.

---

## How to cite this project

```bibtex
@software{quantai_dashboard,
  author = {Alp2246 and QuantAI Contributors},
  title = {QuantAI Dashboard: Multi-Source Alpha for Deep-Tech Equities},
  year = {2026},
  url = {https://github.com/Alp2246/quant-ai-dashboard},
  license = {MIT}
}
```

Or use GitHub’s **Cite this repository** button ([CITATION.cff](../CITATION.cff)).

---

## Contributing & IP

By contributing, you agree that your contributions are licensed under the project MIT License. Do not submit proprietary code from employers or third-party apps without permission.

See [docs/LEGAL.md](LEGAL.md) for full IP / disclaimer text.
