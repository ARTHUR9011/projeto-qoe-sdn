#!/usr/bin/env bash
set -euo pipefail

echo "Limpando estado antigo do Mininet e processos auxiliares..."
sudo mn -c || true
sudo pkill -f 'python3 -m http.server 8000 --bind 10.0.0.1' || true
sudo pkill -f 'iperf3' || true
sudo pkill -f 'osken-manager' || true
sudo pkill -f 'ryu-manager' || true
echo "Limpeza concluida."
