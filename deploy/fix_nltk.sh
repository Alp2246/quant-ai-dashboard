#!/bin/bash
set -e
PD=/home/ubuntu/quant-dashboard
mkdir -p "$PD/.cache/nltk_data"
export NLTK_DATA="$PD/.cache/nltk_data"
"$PD/venv/bin/python" << 'PY'
import nltk
d = "/home/ubuntu/quant-dashboard/.cache/nltk_data"
for pkg in ("vader_lexicon", "punkt", "stopwords"):
    nltk.download(pkg, download_dir=d, quiet=True)
print("NLTK OK")
PY
sudo systemctl daemon-reload
sudo systemctl restart streamlit
sleep 5
systemctl is-active streamlit
