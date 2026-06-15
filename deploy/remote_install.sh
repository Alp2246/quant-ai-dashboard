#!/usr/bin/env bash
set -euo pipefail
if ! swapon --show 2>/dev/null | grep -q swapfile; then
  sudo fallocate -l 2G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q swapfile /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi
free -h
cd ~/quant-dashboard
chmod +x deploy/bootstrap.sh
export DEBIAN_FRONTEND=noninteractive
bash deploy/bootstrap.sh 2>&1 | tee /tmp/bootstrap.log
