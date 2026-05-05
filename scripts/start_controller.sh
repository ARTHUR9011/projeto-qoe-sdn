#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v osken-manager >/dev/null 2>&1; then
    echo "Erro: osken-manager nao encontrado. Instale o OS-Ken antes de iniciar o controlador."
    exit 1
fi

echo "Iniciando controlador OS-Ken na porta 6633..."
exec osken-manager --ofp-tcp-listen-port 6633 controlador/simple_switch_13.py
