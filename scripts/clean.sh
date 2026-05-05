#!/bin/bash
set -e

echo "Limpando estado antigo do Mininet e processos auxiliares..."
sudo mn -c
sudo pkill -f "python3 -m http.server 8000 --bind 10.0.0.1" || true
sudo pkill -f "iperf3 -s" || true
echo "Limpeza concluida."
