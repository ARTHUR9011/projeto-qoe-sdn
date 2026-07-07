#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v osken-manager >/dev/null 2>&1; then
    echo "Erro: osken-manager nao encontrado. Instale o OS-Ken antes de iniciar o controlador."
    exit 1
fi

# Uso:
#   ./scripts/start_controller.sh                         # controlador simples
#   ./scripts/start_controller.sh qoe                     # controlador QoE
#   CONTROLLER_APP=controlador/qoe_controller_13.py ./scripts/start_controller.sh
#   ./scripts/start_controller.sh controlador/qoe_controller_13.py
ARG="${1:-}"
if [[ -n "${CONTROLLER_APP:-}" ]]; then
    APP="$CONTROLLER_APP"
elif [[ "$ARG" == "qoe" ]]; then
    APP="controlador/qoe_controller_13.py"
elif [[ -n "$ARG" ]]; then
    APP="$ARG"
else
    APP="controlador/simple_switch_13.py"
fi

if [[ ! -f "$APP" ]]; then
    echo "Erro: controlador nao encontrado: $APP"
    exit 1
fi

echo "Iniciando controlador OS-Ken na porta 6633: $APP"
exec osken-manager --ofp-tcp-listen-port 6633 "$APP"
