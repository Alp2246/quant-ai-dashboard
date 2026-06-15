# Sharing the Dashboard (English)

## Local use

```powershell
.\run.bat
# http://localhost:8501
```

## Internet sharing (friends, demos)

```powershell
.\paylasim_baslat.bat
```

Share: `https://YOUR-NODE.tailXXXX.ts.net`

**Requirements:**

- PC stays on; do not close the launcher window
- [Tailscale](https://tailscale.com/download) installed and logged in
- Funnel enabled in [Tailscale admin ACL](https://login.tailscale.com/admin/acls)

**Visitors do not need Tailscale.**

### HTTPS error on your own PC?

If you run Tailscale locally, MagicDNS may break your own Funnel URL. Use `http://localhost:8501` locally; friends use the HTTPS link.

## Cloud (24/7 without your PC)

See [deploy/ORACLE_KURULUM.md](../deploy/ORACLE_KURULUM.md) — Oracle Free Tier + `app_lite.py` + Alpha Engine.

## Mobile

- PWA: sidebar → Phone App section  
- APK build: [APK_OLUSTURMA.md](../APK_OLUSTURMA.md)

## Telegram alerts

Configure `alpha_engine/.env` — see [alpha_engine/README.md](../alpha_engine/README.md).
