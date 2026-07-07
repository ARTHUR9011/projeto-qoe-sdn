#!/usr/bin/env bash
# Wrapper seguro para a demo final.
# Rode da raiz do projeto:
#   ./scripts/demo_todas_etapas.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E python3 scripts/demo_todas_etapas.py "$@"
else
  exec python3 scripts/demo_todas_etapas.py "$@"
fi
