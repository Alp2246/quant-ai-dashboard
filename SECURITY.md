# Security Policy

## Reporting a vulnerability

Please **do not** open public issues for security problems.

Open a [GitHub Security Advisory](https://github.com/Alp2246/quant-ai-dashboard/security/advisories/new) or contact the repository owner privately.

## Secrets

Never commit:

- `.env`, `TELEGRAM_BOT_TOKEN`, API keys
- SSH private keys, Tailscale keys
- Personal `telegram.json` / chat IDs in public forks

Use `.env.example` as a template only.

## Dependencies

Keep `venv` updated: `pip install -U -r requirements.txt`
