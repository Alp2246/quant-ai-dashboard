#!/usr/bin/env bash
# ============================================================================
# bootstrap.sh - QuantAI dashboard + Alpha Engine kurulumu (Ubuntu ARM/x86)
#
# Calistirma:
#   bash deploy/bootstrap.sh
#
# Tek seferlik (~10 dakika). Sonradan tekrar calistirmak guvenli.
# ============================================================================
set -euo pipefail

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*" >&2; }

PROJECT_DIR="${PROJECT_DIR:-$HOME/quant-dashboard}"
ENGINE_DIR="$PROJECT_DIR/alpha_engine"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_USER="$(whoami)"

cd "$HOME"

# ============================================================================
# 0) Pre-flight check
# ============================================================================
log "==> Pre-flight kontrolu"
if [[ ! -d "$PROJECT_DIR" ]]; then
    err "$PROJECT_DIR bulunamadi. Dosyalari PC'den kopyalaman gerek:"
    err "  PowerShell: scp -i <key> -r quant-dashboard ubuntu@<IP>:~/"
    exit 1
fi

ARCH=$(uname -m)
log "Mimari: $ARCH"
log "Kullanici: $SERVICE_USER"
log "Proje yolu: $PROJECT_DIR"

# ============================================================================
# 1) System packages
# ============================================================================
log "==> Sistem paketleri guncellemesi"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 python3-venv python3-pip python3-dev \
    build-essential libffi-dev libssl-dev \
    curl wget git unzip \
    rsync htop tmux jq \
    iptables-persistent
ok "Sistem paketleri kuruldu"

# Python versiyon kontrol
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log "Python versiyonu: $PY_VERSION"
if [[ "$PY_VERSION" < "3.10" ]]; then
    err "Python 3.10+ lazim. Mevcut: $PY_VERSION"
    exit 1
fi

# ============================================================================
# 2) Python virtual env
# ============================================================================
log "==> Python venv olusturma"
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip setuptools wheel -q

log "==> requirements.txt kurulumu (dashboard)"
pip install -r "$PROJECT_DIR/requirements.txt" -q

if [[ -f "$ENGINE_DIR/requirements.txt" ]]; then
    log "==> requirements.txt kurulumu (alpha_engine)"
    pip install -r "$ENGINE_DIR/requirements.txt" -q
fi
ok "Python paketleri kuruldu"

# ============================================================================
# 3) .env kontrolu
# ============================================================================
log "==> .env dosyasi kontrolu"
ENGINE_ENV="$ENGINE_DIR/.env"
if [[ ! -f "$ENGINE_ENV" ]]; then
    if [[ -f "$ENGINE_DIR/.env.example" ]]; then
        cp "$ENGINE_DIR/.env.example" "$ENGINE_ENV"
        warn ".env dosyasi olusturuldu (ornek): $ENGINE_ENV"
        warn "Telegram token ve diger sirleri eklemeyi UNUTMA:"
        warn "  nano $ENGINE_ENV"
    else
        warn ".env.example yok, manuel olustur: $ENGINE_ENV"
    fi
else
    ok ".env mevcut"
fi

# ============================================================================
# 4) Tailscale
# ============================================================================
log "==> Tailscale kurulumu"
if ! command -v tailscale &> /dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
    ok "Tailscale kuruldu"
else
    ok "Tailscale zaten kurulu"
fi

# Tailscale up - hostname'i 'abozer' yap ki Funnel URL'i aynı kalsın
log "==> Tailscale baslatma (hostname=abozer)"
if ! tailscale status &> /dev/null || [[ "$(tailscale status --json | jq -r '.BackendState' 2>/dev/null)" != "Running" ]]; then
    warn "Tailscale baglanti gerekli - link gosteriliyor..."
    warn "Bu linki TARAYICIDA ac ve gir:"
    sudo tailscale up --hostname=abozer --accept-routes --ssh
else
    log "Tailscale zaten baglanmis"
    TS_HOSTNAME=$(tailscale status --json | jq -r '.Self.HostName' 2>/dev/null || echo "unknown")
    log "Mevcut hostname: $TS_HOSTNAME"
    if [[ "$TS_HOSTNAME" != "abozer" ]]; then
        warn "Hostname 'abozer' degil. Manuel set et:"
        warn "  sudo tailscale set --hostname=abozer"
    fi
fi
ok "Tailscale OK"

# ============================================================================
# 5) systemd service'leri
# ============================================================================
log "==> systemd unit dosyalari kurma"
SVC_DIR="$PROJECT_DIR/deploy/systemd"

if [[ ! -d "$SVC_DIR" ]]; then
    err "Systemd unit klasoru bulunamadi: $SVC_DIR"
    err "Repo'yu tekrar kopyala"
    exit 1
fi

# Template'leri kopyala, kullaniciya ozelle
for svc in streamlit.service alpha-engine.service; do
    src="$SVC_DIR/$svc"
    dst="/etc/systemd/system/$svc"
    if [[ ! -f "$src" ]]; then
        warn "$src yok, atlandi"
        continue
    fi
    sudo sed -e "s|__USER__|$SERVICE_USER|g" \
              -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
              -e "s|__VENV_DIR__|$VENV_DIR|g" \
              "$src" | sudo tee "$dst" > /dev/null
    sudo chmod 644 "$dst"
    ok "$svc -> $dst"
done

sudo systemctl daemon-reload

log "==> Servisleri enable et + baslat"
for svc in streamlit alpha-engine; do
    sudo systemctl enable "$svc" 2>/dev/null || true
    sudo systemctl restart "$svc"
    sleep 1
    if sudo systemctl is-active --quiet "$svc"; then
        ok "$svc calisiyor"
    else
        warn "$svc baslayamadi - kontrol: sudo journalctl -u $svc -n 30"
    fi
done

# ============================================================================
# 6) Tailscale Funnel
# ============================================================================
log "==> Tailscale Funnel ayarliyor (port 8501)"
sleep 3   # Streamlit'in baslamasini bekle

# Onceki funnel varsa kapat
sudo tailscale funnel reset 2>/dev/null || true
sleep 1

# 8501 portunu funnel ile aciliyoruz (PUBLIC HTTPS)
if sudo tailscale funnel --bg 8501 2>&1 | tee /tmp/funnel.log; then
    ok "Funnel acildi - PUBLIC HTTPS"
else
    warn "Funnel acmada hata - manuel dene: sudo tailscale funnel 8501"
fi

# ============================================================================
# 7) Firewall (UFW)
# ============================================================================
log "==> UFW firewall ayari"
if command -v ufw &> /dev/null; then
    sudo ufw --force enable 2>/dev/null || true
    sudo ufw allow OpenSSH 2>/dev/null || true
    # Tailscale arayuzu zaten guvenli, ek port acmaya gerek yok
    ok "UFW: SSH acik, geri kalan Tailscale uzerinden"
fi

# ============================================================================
# Ozet
# ============================================================================
echo ""
echo "============================================================"
echo "  KURULUM TAMAMLANDI"
echo "============================================================"
echo ""
tailscale status 2>/dev/null | head -5 || true
echo ""
echo "PUBLIC URL: https://abozer.tail4ea368.ts.net"
echo ""
echo "Servisler:"
sudo systemctl is-active streamlit alpha-engine 2>/dev/null || true
echo ""
echo "Loglar:"
echo "  sudo journalctl -fu streamlit"
echo "  sudo journalctl -fu alpha-engine"
echo ""
echo "Yeniden baslatma:"
echo "  sudo systemctl restart streamlit alpha-engine"
echo ""
echo "Telegram bot 1-2 dakika icinde basligi gondermeli."
echo "============================================================"
