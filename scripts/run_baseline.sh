#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="$PROJECT_ROOT/resultados"
DASH_DIR="$PROJECT_ROOT/video/dash"

HOSTS=(h1 h2 h3 h4)

if [ "$EUID" -eq 0 ]; then
    SUDO=()
else
    SUDO=(sudo)
fi

host_pid() {
    local host="$1"
    pgrep -f "mininet:$host" | head -n 1
}

require_command() {
    local command="$1"
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Erro: comando '$command' nao encontrado."
        exit 1
    fi
}

require_mininet_hosts() {
    local host pid
    for host in "${HOSTS[@]}"; do
        pid="$(host_pid "$host")"
        if [ -z "$pid" ]; then
            echo "Erro: host $host nao encontrado. Inicie a topologia com 'make topology' antes do baseline."
            exit 1
        fi
    done
}

run_host() {
    local host="$1"
    shift
    local pid command
    pid="$(host_pid "$host")"
    command="$*"

    if [ -z "$pid" ]; then
        echo "Erro: host $host nao encontrado."
        exit 1
    fi

    "${SUDO[@]}" mnexec -a "$pid" bash -lc "$command"
}

host_ip() {
    case "$1" in
        h1) echo "10.0.0.1" ;;
        h2) echo "10.0.0.2" ;;
        h3) echo "10.0.0.3" ;;
        h4) echo "10.0.0.4" ;;
        *) return 1 ;;
    esac
}

run_pingall_equivalent() {
    local src dst dst_ip sent received dropped loss line
    sent=0
    received=0

    echo "*** Pingall equivalente executado via mnexec"
    for src in "${HOSTS[@]}"; do
        line="$src ->"
        for dst in "${HOSTS[@]}"; do
            if [ "$src" = "$dst" ]; then
                continue
            fi

            dst_ip="$(host_ip "$dst")"
            sent=$((sent + 1))
            if run_host "$src" "ping -c 1 -W 1 $dst_ip >/dev/null 2>&1"; then
                received=$((received + 1))
                line="$line $dst"
            else
                line="$line X"
            fi
        done
        echo "$line"
    done

    dropped=$((sent - received))
    loss=$((dropped * 100 / sent))
    echo "*** Results: $loss% dropped ($received/$sent received)"
}

require_command pgrep
require_command mnexec
require_mininet_hosts

mkdir -p "$RESULTS_DIR"

echo "Coletando conectividade base..."
run_pingall_equivalent > "$RESULTS_DIR/pingall.txt"
run_host h1 "ping -c 10 10.0.0.2" > "$RESULTS_DIR/ping_h1_h2.txt"
run_host h2 "ping -c 10 10.0.0.1" > "$RESULTS_DIR/ping_h2_h1.txt"

echo "Iniciando servidor DASH no h1..."
DASH_DIR_QUOTED="$(printf "%q" "$DASH_DIR")"
run_host h1 "pkill -f '[p]ython3 -m http.server 8000 --bind 10.0.0.1' >/dev/null 2>&1 || true"
run_host h1 "cd $DASH_DIR_QUOTED && nohup python3 -m http.server 8000 --bind 10.0.0.1 >/tmp/qoe_dash_server.log 2>&1 &"
sleep 1

echo "Validando manifesto DASH..."
run_host h2 "curl -I --max-time 5 http://10.0.0.1:8000/manifest.mpd" > "$RESULTS_DIR/dash_h2_header.txt"
run_host h3 "curl -I --max-time 5 http://10.0.0.1:8000/manifest.mpd" > "$RESULTS_DIR/dash_h3_header.txt"
run_host h4 "curl -I --max-time 5 http://10.0.0.1:8000/manifest.mpd" > "$RESULTS_DIR/dash_h4_header.txt"

echo "Executando testes iperf3..."
run_host h1 "pkill -f '[i]perf3 -s' >/dev/null 2>&1 || true"
run_host h1 "iperf3 -s -D"
sleep 1

run_host h2 "iperf3 -c 10.0.0.1 -t 10" > "$RESULTS_DIR/iperf_h2_h1.txt"
run_host h3 "iperf3 -c 10.0.0.1 -t 10" > "$RESULTS_DIR/iperf_h3_h1.txt"
run_host h4 "iperf3 -c 10.0.0.1 -t 10" > "$RESULTS_DIR/iperf_h4_h1.txt"

echo "Baseline concluido. Resultados salvos em $RESULTS_DIR."
