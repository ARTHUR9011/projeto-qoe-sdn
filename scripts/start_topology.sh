#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Iniciando topologia Mininet da Etapa 1..."
exec sudo python3 topologia/topologia_qoe.py
