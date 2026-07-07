#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Uso:
#   ./scripts/start_topology.sh          # Etapa 1/2
#   ./scripts/start_topology.sh etapa3   # topologia com 2 switches e gargalo
#   TOPOLOGY_APP=topologia/topologia_qoe_etapa3.py ./scripts/start_topology.sh
ARG="${1:-}"
if [[ -n "${TOPOLOGY_APP:-}" ]]; then
    APP="$TOPOLOGY_APP"
elif [[ "$ARG" == "etapa3" ]]; then
    APP="topologia/topologia_qoe_etapa3.py"
else
    APP="topologia/topologia_qoe.py"
fi

if [[ ! -f "$APP" ]]; then
    echo "Erro: topologia nao encontrada: $APP"
    exit 1
fi

echo "Iniciando topologia Mininet: $APP"
exec sudo python3 "$APP"
