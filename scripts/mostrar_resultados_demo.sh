#!/usr/bin/env bash
# Mostra rapidamente os resultados gerados pela demo final.

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

RESULT_DIR="resultados/demo_final"

echo "===== RESUMO DA DEMO ====="
if [[ -f "$RESULT_DIR/resumo.txt" ]]; then
  cat "$RESULT_DIR/resumo.txt"
else
  echo "Resumo ainda nao encontrado. Rode: ./scripts/demo_todas_etapas.sh"
fi

echo
echo "===== LOGS DE DECISAO DA ETAPA 3 ====="
if [[ -f "$RESULT_DIR/etapa3/com_controle/logs_decisao_filtrados.txt" ]]; then
  cat "$RESULT_DIR/etapa3/com_controle/logs_decisao_filtrados.txt"
else
  echo "Logs filtrados ainda nao encontrados."
fi

echo
echo "===== REGRAS OPENFLOW COM CONTROLE - S1 ====="
if [[ -f "$RESULT_DIR/etapa3/com_controle/flows_s1.txt" ]]; then
  grep -Ei "udp|10.0.0.3|10.0.0.4|priority=300|drop|actions" "$RESULT_DIR/etapa3/com_controle/flows_s1.txt" || cat "$RESULT_DIR/etapa3/com_controle/flows_s1.txt"
else
  echo "Arquivo flows_s1.txt nao encontrado."
fi

echo
echo "===== REGRAS OPENFLOW COM CONTROLE - S2 ====="
if [[ -f "$RESULT_DIR/etapa3/com_controle/flows_s2.txt" ]]; then
  grep -Ei "udp|10.0.0.3|10.0.0.4|priority=300|drop|actions" "$RESULT_DIR/etapa3/com_controle/flows_s2.txt" || cat "$RESULT_DIR/etapa3/com_controle/flows_s2.txt"
else
  echo "Arquivo flows_s2.txt nao encontrado."
fi
