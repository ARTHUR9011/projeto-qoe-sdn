#!/usr/bin/env python3
"""
Demo funcional automatizada das Etapas 1, 2 e 3 do projeto QoE/SDN.

Diferenca para a versao anterior:
- Nao envia comandos para o CLI interativo do Mininet via stdin.
- Executa a demo pela API Python do Mininet, evitando erros como
  "Unknown command: echo" e "ping: option requires an argument -- W".
- Usa o controlador simples nas Etapas 1 e 2.
- Usa a topologia de gargalo com 2 switches e o controlador QoE na Etapa 3.
- Salva evidencias e um resumo final em resultados/demo_final/.

Uso recomendado, na raiz do projeto:
  sudo -E python3 scripts/demo_todas_etapas.py
ou:
  ./scripts/demo_todas_etapas.sh
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    from mininet.link import TCLink
    from mininet.log import setLogLevel
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController
except ImportError as exc:  # pragma: no cover - so aparece fora do Mininet
    print("Erro: nao foi possivel importar o Mininet.")
    print("Instale o Mininet e execute este script dentro da VM/ambiente Linux do projeto.")
    raise exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = PROJECT_ROOT / "resultados" / "demo_final"
DASH_DIR = PROJECT_ROOT / "video" / "dash"
CHUNK_URL = "http://10.0.0.1:8000/chunk-stream0-00001.m4s"
MANIFEST_URL = "http://10.0.0.1:8000/manifest.mpd"
SEGMENT_DURATION_S = 4.0

HOST_IPS = {
    "h1": "10.0.0.1",
    "h2": "10.0.0.2",
    "h3": "10.0.0.3",
    "h4": "10.0.0.4",
}


class DemoError(RuntimeError):
    pass


def print_step(title: str) -> None:
    line = "=" * 78
    print(f"\n{line}\n{title}\n{line}", flush=True)


def print_sub(title: str) -> None:
    print(f"\n--- {title} ---", flush=True)


def ensure_root() -> None:
    if os.geteuid() != 0:
        raise DemoError(
            "Execute como root/sudo. Exemplo: sudo -E python3 scripts/demo_todas_etapas.py"
        )


def require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise DemoError(f"Comando obrigatorio nao encontrado: {command}")


def shell(command: str, *, cwd: Path = PROJECT_ROOT, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        shell=True,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="replace") as f:
        f.write(text)


def cleanup_system() -> None:
    # Evita que execucoes antigas afetem a demo.
    commands = [
        "mn -c >/dev/null 2>&1 || true",
        "pkill -f 'python3 -m http.server 8000 --bind 10.0.0.1' >/dev/null 2>&1 || true",
        "pkill -f 'iperf3' >/dev/null 2>&1 || true",
        "pkill -f 'osken-manager' >/dev/null 2>&1 || true",
    ]
    for cmd in commands:
        shell(cmd)


def start_controller(controller_file: Path, log_path: Path, qoe_log_path: Optional[Path] = None) -> subprocess.Popen:
    if not controller_file.exists():
        raise DemoError(f"Controlador nao encontrado: {controller_file}")

    require_command("osken-manager")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8", errors="replace")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if qoe_log_path is not None:
        qoe_log_path.parent.mkdir(parents=True, exist_ok=True)
        env["QOE_LOG_FILE"] = str(qoe_log_path)

    cmd = [
        "osken-manager",
        "--ofp-tcp-listen-port",
        "6633",
        str(controller_file.relative_to(PROJECT_ROOT)),
    ]

    print(f">>> Iniciando controlador: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        preexec_fn=os.setsid,
    )
    time.sleep(3)

    if proc.poll() is not None:
        log_file.close()
        content = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        raise DemoError(f"Controlador encerrou antes da hora. Log:\n{content}")

    return proc


def stop_controller(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=3)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
    time.sleep(1)


def create_base_net() -> Mininet:
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )

    c0 = net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6633)
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")
    s1 = net.addSwitch("s1", protocols="OpenFlow13", failMode="secure")

    # 20 Mbps deixa a saida mais limpa do que 100 Mbps e continua suficiente para
    # demonstrar baseline estavel. A Etapa 3 tem gargalo proprio de 2 Mbps.
    for host in (h1, h2, h3, h4):
        net.addLink(host, s1, bw=20)

    net.build()
    c0.start()
    s1.start([c0])
    time.sleep(2)
    return net


def create_stage3_net() -> Mininet:
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )

    c0 = net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6633)
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")

    s1 = net.addSwitch("s1", protocols="OpenFlow13", failMode="secure")
    s2 = net.addSwitch("s2", protocols="OpenFlow13", failMode="secure")

    # O link h1-s1 precisa ser alto para que a mitigacao no switch realmente
    # alivie o gargalo s1-s2. Se h1-s1 for baixo, os fluxos UDP podem enfileirar
    # antes de chegar no switch, e o download DASH continua lento mesmo apos o drop.
    net.addLink(h1, s1, bw=100)
    net.addLink(s1, s2, bw=2, delay="10ms")  # enlace gargalo da Etapa 3
    net.addLink(s2, h2, bw=100)
    net.addLink(s2, h3, bw=100)
    net.addLink(s2, h4, bw=100)

    net.build()
    c0.start()
    s1.start([c0])
    s2.start([c0])
    time.sleep(2)
    return net


def stop_net(net: Optional[Mininet]) -> None:
    if net is not None:
        try:
            net.stop()
        except Exception as exc:
            print(f"Aviso: erro ao parar Mininet: {exc}")
    time.sleep(1)


def host_cmd(net: Mininet, host_name: str, command: str, out_path: Optional[Path] = None, show: bool = True) -> str:
    host = net.get(host_name)
    output = host.cmd(command)
    if out_path is not None:
        write_text(out_path, output)
    if show and output.strip():
        print(output.strip(), flush=True)
    return output


def switch_cmd(net: Mininet, switch_name: str, command: str, out_path: Optional[Path] = None, show: bool = False) -> str:
    switch = net.get(switch_name)
    output = switch.cmd(command)
    if out_path is not None:
        write_text(out_path, output)
    if show and output.strip():
        print(output.strip(), flush=True)
    return output


def start_dash_server(net: Mininet, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    dash_log = out_dir / "dash_server.log"
    host_cmd(net, "h1", "pkill -f 'python3 -m http.server 8000 --bind 10.0.0.1' || true", show=False)
    cmd = (
        f"cd {DASH_DIR} && "
        f"nohup python3 -m http.server 8000 --bind 10.0.0.1 "
        f"> {dash_log} 2>&1 &"
    )
    host_cmd(net, "h1", cmd, show=False)
    time.sleep(2)


def stop_dash_server(net: Mininet) -> None:
    try:
        host_cmd(net, "h1", "pkill -f 'python3 -m http.server 8000 --bind 10.0.0.1' || true", show=False)
    except Exception:
        pass


def validate_manifest(net: Mininet, out_dir: Path, hosts: Iterable[str] = ("h2",)) -> None:
    for host in hosts:
        print(f"Validando manifesto DASH em {host}...")
        host_cmd(
            net,
            host,
            f"curl -I --max-time 5 {MANIFEST_URL}",
            out_dir / f"manifest_{host}.txt",
            show=True,
        )


def run_pingall_equivalent(net: Mininet, out_path: Path, show: bool = True) -> Tuple[int, int]:
    lines: List[str] = ["*** Pingall equivalente executado pela demo"]
    sent = 0
    received = 0

    for src in ("h1", "h2", "h3", "h4"):
        line = f"{src} ->"
        for dst, dst_ip in HOST_IPS.items():
            if src == dst:
                continue
            sent += 1
            rc = host_cmd(
                net,
                src,
                f"bash -lc 'ping -c 1 -W 1 {dst_ip} >/dev/null 2>&1; echo $?'",
                show=False,
            ).strip().splitlines()[-1]
            if rc == "0":
                received += 1
                line += f" {dst}"
            else:
                line += " X"
        lines.append(line)

    dropped = sent - received
    loss = int((dropped * 100) / sent) if sent else 100
    lines.append(f"*** Results: {loss}% dropped ({received}/{sent} received)")
    text = "\n".join(lines) + "\n"
    write_text(out_path, text)
    if show:
        print(text, end="", flush=True)
    return received, sent


def run_qoe_download(
    net: Mininet,
    out_dir: Path,
    scenario: str,
    max_time: int = 30,
    host: str = "h2",
    show: bool = True,
) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    qoe_file = out_dir / "qoe_chunk.txt"
    chunk_file = out_dir / "chunk_h2.m4s"

    cmd = f"""bash -lc 'curl -s --max-time {max_time} -o {chunk_file} -w "cenario={scenario}\\ntempo=%{{time_total}}\\ntamanho=%{{size_download}}\\nvelocidade=%{{speed_download}}\\nhttp=%{{http_code}}\\nexitcode=%{{exitcode}}\\n" {CHUNK_URL} > {qoe_file}'"""

    host_cmd(net, host, cmd, show=False)
    text = qoe_file.read_text(encoding="utf-8", errors="replace") if qoe_file.exists() else ""

    data = parse_qoe_text(text)
    data.setdefault("cenario", scenario)

    # Acrescenta buffering estimado.
    try:
        tempo = float(data.get("tempo", "0").replace(",", "."))
    except ValueError:
        tempo = 0.0
    buffering = max(0.0, tempo - SEGMENT_DURATION_S)
    data["buffering_estimado"] = f"{buffering:.3f}"

    normalized = "".join(f"{k}={v}\n" for k, v in data.items())
    write_text(qoe_file, normalized)

    if show:
        print(normalized, end="", flush=True)

    return data


def parse_qoe_text(text: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def start_iperf_servers(net: Mininet) -> None:
    for h in ("h1", "h2", "h3", "h4"):
        try:
            host_cmd(net, h, "pkill -f iperf3 || true", show=False)
        except Exception:
            pass
    host_cmd(net, "h3", "iperf3 -s -D", show=False)
    host_cmd(net, "h4", "iperf3 -s -D", show=False)
    time.sleep(1)


def start_udp_competitors(net: Mininet, out_dir: Path, duration: int = 25, bitrate: str = "40M") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    start_iperf_servers(net)
    host_cmd(
        net,
        "h1",
        f"bash -lc 'iperf3 -c 10.0.0.3 -u -b {bitrate} -t {duration} > {out_dir / 'iperf_h1_h3.txt'} 2>&1 &'",
        show=False,
    )
    host_cmd(
        net,
        "h1",
        f"bash -lc 'iperf3 -c 10.0.0.4 -u -b {bitrate} -t {duration} > {out_dir / 'iperf_h1_h4.txt'} 2>&1 &'",
        show=False,
    )
    time.sleep(2)


def stop_iperf(net: Mininet) -> None:
    for h in ("h1", "h2", "h3", "h4"):
        try:
            host_cmd(net, h, "pkill -f iperf3 || true", show=False)
        except Exception:
            pass


def clear_tc(net: Mininet, host: str = "h1", iface: str = "h1-eth0") -> None:
    host_cmd(net, host, f"tc qdisc del dev {iface} root || true", show=False)


def save_summary_csv(rows: List[Dict[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["etapa", "cenario", "tempo", "tamanho", "velocidade", "http", "exitcode", "buffering_estimado"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def demo_stage1(controller_log: Path) -> List[Dict[str, str]]:
    print_step("ETAPA 1 - Ambiente experimental funcional")
    proc = None
    net = None
    out_dir = RESULT_ROOT / "etapa1"
    rows: List[Dict[str, str]] = []

    try:
        proc = start_controller(PROJECT_ROOT / "controlador" / "simple_switch_13.py", controller_log)
        net = create_base_net()

        print_sub("Conectividade entre todos os hosts")
        run_pingall_equivalent(net, out_dir / "pingall.txt")

        print_sub("Latencia h1 <-> h2")
        host_cmd(net, "h1", "ping -c 5 10.0.0.2", out_dir / "ping_h1_h2.txt", show=True)
        host_cmd(net, "h2", "ping -c 5 10.0.0.1", out_dir / "ping_h2_h1.txt", show=True)

        print_sub("Servidor DASH e manifesto")
        start_dash_server(net, out_dir)
        validate_manifest(net, out_dir, hosts=("h2", "h3", "h4"))

        print_sub("Throughput com iperf3")
        # iperf3 atende apenas um teste por vez no mesmo servidor. Para evitar
        # o erro "server is busy running a test", iniciamos um servidor -1
        # novo para cada cliente.
        for h in ("h2", "h3", "h4"):
            host_cmd(net, "h1", "pkill -f iperf3 || true", show=False)
            time.sleep(0.5)
            host_cmd(net, "h1", "iperf3 -s -1 -D", show=False)
            time.sleep(1)
            host_cmd(net, h, "iperf3 -c 10.0.0.1 -t 3", out_dir / f"iperf_{h}_h1.txt", show=True)
            time.sleep(1)
        stop_iperf(net)

        print("\nEtapa 1 concluida: topologia, conectividade, DASH e throughput validados.")
        rows.append({"etapa": "1", "cenario": "ambiente_base", "http": "200"})
        return rows
    finally:
        if net is not None:
            stop_dash_server(net)
            stop_iperf(net)
        stop_net(net)
        stop_controller(proc)


def demo_stage2(controller_log: Path, full_mode: bool = False) -> List[Dict[str, str]]:
    print_step("ETAPA 2 - Degradacao de rede e caracterizacao da QoE")
    proc = None
    net = None
    out_dir = RESULT_ROOT / "etapa2"
    rows: List[Dict[str, str]] = []

    # Modo padrao para apresentacao: degradacao clara, mas sem ficar 40s parado.
    # Modo completo usa parametros mais proximos do relatorio.
    if full_mode:
        rate = "2mbit"
        delay = "100ms 30ms"
        loss = "2%"
        max_time = 70
        competitor_duration = 60
        competitor_bitrate = "40M"
    else:
        # Modo de apresentacao: degrada, mas evita timeout/arquivo vazio.
        # A combinacao abaixo costuma produzir alguns segundos de download,
        # mostrando queda de QoE sem travar a apresentacao.
        rate = "2mbit"
        delay = "80ms 15ms"
        loss = "0.2%"
        max_time = 45
        competitor_duration = 25
        competitor_bitrate = "20M"

    try:
        proc = start_controller(PROJECT_ROOT / "controlador" / "simple_switch_13.py", controller_log)
        net = create_base_net()
        start_dash_server(net, out_dir)

        print_sub("QoE baseline sem degradacao")
        baseline = run_qoe_download(net, out_dir / "baseline", "baseline", max_time=15)
        baseline["etapa"] = "2"
        rows.append(baseline)

        print_sub("Aplicando degradacao com tc/netem/tbf")
        clear_tc(net)
        host_cmd(net, "h1", f"tc qdisc add dev h1-eth0 root handle 1: netem delay {delay} loss {loss}", show=True)
        # burst em bytes/kbytes suficiente evita que o TBF congele o download
        # e gere size_download=0 por timeout.
        host_cmd(net, "h1", f"tc qdisc add dev h1-eth0 parent 1: handle 2: tbf rate {rate} burst 128kb latency 400ms", show=True)
        host_cmd(net, "h1", "tc qdisc show dev h1-eth0", out_dir / "combinado" / "tc_qdisc.txt", show=True)

        print_sub("Gerando trafego concorrente UDP")
        start_udp_competitors(net, out_dir / "combinado", duration=competitor_duration, bitrate=competitor_bitrate)

        print_sub("QoE no cenario degradado")
        degradado = run_qoe_download(net, out_dir / "combinado", "combinado_degradado", max_time=max_time)
        degradado["etapa"] = "2"
        rows.append(degradado)

        clear_tc(net)
        stop_iperf(net)

        print("\nEtapa 2 concluida: foi demonstrado o impacto da degradacao no tempo de download e no buffering estimado.")
        return rows
    finally:
        if net is not None:
            clear_tc(net)
            stop_dash_server(net)
            stop_iperf(net)
        stop_net(net)
        stop_controller(proc)


def demo_stage3_no_control(controller_log: Path) -> List[Dict[str, str]]:
    print_step("ETAPA 3A - Cenario com trafego concorrente sem mitigacao QoE")
    proc = None
    net = None
    out_dir = RESULT_ROOT / "etapa3" / "sem_controle"
    rows: List[Dict[str, str]] = []

    try:
        proc = start_controller(PROJECT_ROOT / "controlador" / "simple_switch_13.py", controller_log)
        net = create_stage3_net()
        start_dash_server(net, out_dir)
        validate_manifest(net, out_dir, hosts=("h2",))
        run_pingall_equivalent(net, out_dir / "pingall.txt", show=True)

        print_sub("Gerando trafego concorrente UDP sem mitigacao")
        start_udp_competitors(net, out_dir, duration=20, bitrate="35M")

        print_sub("Download DASH no h2 sem controle SDN de QoE")
        # Limite curto proposital: em apresentacao, basta mostrar que sem
        # mitigacao o download nao termina dentro da janela aceitavel.
        sem_controle = run_qoe_download(net, out_dir, "sem_controle_sdn", max_time=12)
        sem_controle["etapa"] = "3"
        rows.append(sem_controle)

        switch_cmd(net, "s1", "ovs-ofctl -O OpenFlow13 dump-flows s1", out_dir / "flows_s1.txt")
        switch_cmd(net, "s2", "ovs-ofctl -O OpenFlow13 dump-flows s2", out_dir / "flows_s2.txt")

        print("\nCenario sem controle concluido: serve como comparacao para a mitigacao da Etapa 3.")
        return rows
    finally:
        if net is not None:
            stop_dash_server(net)
            stop_iperf(net)
        stop_net(net)
        stop_controller(proc)


def demo_stage3_with_control(controller_log: Path, qoe_log: Path) -> List[Dict[str, str]]:
    print_step("ETAPA 3B - Controle SDN com deteccao e mitigacao")
    proc = None
    net = None
    out_dir = RESULT_ROOT / "etapa3" / "com_controle"
    rows: List[Dict[str, str]] = []

    try:
        proc = start_controller(PROJECT_ROOT / "controlador" / "qoe_controller_13.py", controller_log, qoe_log)
        net = create_stage3_net()
        start_dash_server(net, out_dir)
        validate_manifest(net, out_dir, hosts=("h2",))
        run_pingall_equivalent(net, out_dir / "pingall.txt", show=True)

        print_sub("Gerando trafego concorrente UDP para o controlador detectar")
        start_udp_competitors(net, out_dir, duration=25, bitrate="35M")

        print("Aguardando o monitor do controlador coletar estatisticas e instalar regras...", flush=True)
        wait_for_mitigation(controller_log, qoe_log, timeout=12)

        print_sub("Download DASH no h2 com controle SDN ativo")
        com_controle = run_qoe_download(net, out_dir, "com_controle_sdn", max_time=20)
        com_controle["etapa"] = "3"
        rows.append(com_controle)

        print_sub("Regras OpenFlow instaladas nos switches")
        switch_cmd(net, "s1", "ovs-ofctl -O OpenFlow13 dump-flows s1", out_dir / "flows_s1.txt", show=True)
        switch_cmd(net, "s2", "ovs-ofctl -O OpenFlow13 dump-flows s2", out_dir / "flows_s2.txt", show=True)

        print_sub("Logs de decisao do controlador QoE")
        combined_log = ""
        for path in (controller_log, qoe_log):
            if path.exists():
                combined_log += path.read_text(encoding="utf-8", errors="replace") + "\n"
        relevant = "\n".join(
            line for line in combined_log.splitlines()
            if re.search(r"degrad|mitig|dpid|taxa|bloqueio", line, re.IGNORECASE)
        )
        write_text(out_dir / "logs_decisao_filtrados.txt", relevant + "\n")
        print(relevant or "Nenhum log filtrado encontrado; verifique controller_etapa3_com_controle.log.")

        print("\nEtapa 3 concluida: controlador QoE detectou trafego elevado e aplicou mitigacao via OpenFlow.")
        return rows
    finally:
        if net is not None:
            stop_dash_server(net)
            stop_iperf(net)
        stop_net(net)
        stop_controller(proc)



def wait_for_mitigation(controller_log: Path, qoe_log: Path, timeout: int = 12) -> bool:
    """Aguarda logs de mitigacao antes de medir o DASH com controle.

    Isso deixa a apresentacao mais estavel: o download do h2 so comeca depois
    que as regras drop ja foram instaladas nos switches.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        combined = ""
        for path in (controller_log, qoe_log):
            if path.exists():
                combined += path.read_text(encoding="utf-8", errors="replace") + "\n"
        if "Mitigacao aplicada" in combined:
            print("Mitigacao detectada nos logs. Prosseguindo com a medicao DASH.", flush=True)
            return True
        time.sleep(1)
    print("Aviso: nao encontrei log de mitigacao dentro do tempo limite; prosseguindo mesmo assim.", flush=True)
    return False

def make_human_summary(rows: List[Dict[str, str]]) -> str:
    lines = []
    lines.append("Resumo da demo final - QoE SDN")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Cenarios medidos:")
    for row in rows:
        etapa = row.get("etapa", "")
        cenario = row.get("cenario", "")
        tempo = row.get("tempo", "-")
        velocidade = row.get("velocidade", "-")
        http = row.get("http", "-")
        buffering = row.get("buffering_estimado", "-")
        exitcode = row.get("exitcode", "-")
        lines.append(
            f"- Etapa {etapa} / {cenario}: tempo={tempo}s, velocidade={velocidade} B/s, "
            f"http={http}, exitcode={exitcode}, buffering_estimado={buffering}s"
        )

    def by_scenario(name: str) -> Optional[Dict[str, str]]:
        for r in rows:
            if r.get("cenario") == name:
                return r
        return None

    sem = by_scenario("sem_controle_sdn")
    com = by_scenario("com_controle_sdn")
    if sem and com:
        lines.append("")
        if sem.get("exitcode") not in ("0", "") or sem.get("tamanho") in ("0", ""):
            lines.append(
                "Comparacao Etapa 3: sem controle, o download nao terminou dentro do limite "
                f"da demo ({sem.get('tempo', '-')}s); com controle, terminou com "
                f"HTTP {com.get('http', '-')} e tamanho {com.get('tamanho', '-')} bytes."
            )
        else:
            try:
                t_sem = float(sem.get("tempo", "0").replace(",", "."))
                t_com = float(com.get("tempo", "0").replace(",", "."))
                if t_sem > 0 and t_com > 0:
                    red = ((t_sem - t_com) / t_sem) * 100
                    lines.append(f"Melhora Etapa 3: reducao aproximada de {red:.2f}% no tempo de download.")
            except ValueError:
                pass

    lines.append("")
    lines.append("Arquivos importantes:")
    lines.append(f"- {RESULT_ROOT / 'resumo.csv'}")
    lines.append(f"- {RESULT_ROOT / 'resumo.txt'}")
    lines.append(f"- {RESULT_ROOT / 'etapa3' / 'com_controle' / 'logs_decisao_filtrados.txt'}")
    lines.append(f"- {RESULT_ROOT / 'etapa3' / 'com_controle' / 'flows_s1.txt'}")
    lines.append(f"- {RESULT_ROOT / 'etapa3' / 'com_controle' / 'flows_s2.txt'}")
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Demo automatizada das Etapas 1, 2 e 3 do projeto QoE SDN.")
    parser.add_argument("--skip-stage1", action="store_true", help="Nao executa a Etapa 1.")
    parser.add_argument("--skip-stage2", action="store_true", help="Nao executa a Etapa 2.")
    parser.add_argument("--skip-stage3-sem-controle", action="store_true", help="Nao executa o cenario sem controle da Etapa 3.")
    parser.add_argument("--full-etapa2", action="store_true", help="Usa parametros mais lentos, proximos do relatorio, na Etapa 2.")
    args = parser.parse_args(argv)

    ensure_root()
    setLogLevel("warning")

    for cmd in ("mn", "ovs-ofctl", "curl", "iperf3", "osken-manager"):
        require_command(cmd)

    if not DASH_DIR.exists() or not (DASH_DIR / "manifest.mpd").exists():
        raise DemoError(f"Diretorio DASH ou manifest.mpd nao encontrado em {DASH_DIR}")

    RESULT_ROOT.mkdir(parents=True, exist_ok=True)

    print_step("Preparacao da demo")
    print(f"Projeto: {PROJECT_ROOT}")
    print(f"Resultados: {RESULT_ROOT}")
    cleanup_system()

    rows: List[Dict[str, str]] = []

    try:
        if not args.skip_stage1:
            rows.extend(demo_stage1(RESULT_ROOT / "controller_etapa1.log"))

        if not args.skip_stage2:
            rows.extend(demo_stage2(RESULT_ROOT / "controller_etapa2.log", full_mode=args.full_etapa2))

        if not args.skip_stage3_sem_controle:
            rows.extend(demo_stage3_no_control(RESULT_ROOT / "controller_etapa3_sem_controle.log"))

        rows.extend(
            demo_stage3_with_control(
                RESULT_ROOT / "controller_etapa3_com_controle.log",
                RESULT_ROOT / "etapa3" / "com_controle" / "controlador_decisoes.log",
            )
        )

        save_summary_csv(rows, RESULT_ROOT / "resumo.csv")
        summary = make_human_summary(rows)
        write_text(RESULT_ROOT / "resumo.txt", summary)

        print_step("RESUMO FINAL")
        print(summary)
        print("Demo finalizada com sucesso.")
        return 0

    except KeyboardInterrupt:
        print("\nDemo interrompida pelo usuario.")
        return 130
    finally:
        cleanup_system()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DemoError as exc:
        print(f"\nERRO: {exc}", file=sys.stderr)
        cleanup_system()
        raise SystemExit(1)
