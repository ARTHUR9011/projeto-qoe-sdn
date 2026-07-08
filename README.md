# Projeto QoE SDN

## Objetivo

Avaliar como condições adversas de rede afetam a Qualidade de Experiência (QoE) em streaming de vídeo DASH e demonstrar que um mecanismo de controle programável via SDN pode mitigar o impacto de fluxos concorrentes. O ambiente usa Mininet, Open vSwitch, OpenFlow 1.3 e controlador OS-Ken/Ryu.

O projeto está organizado em três etapas:

- **Etapa 1** — ambiente experimental base: topologia Mininet, controlador SDN, servidor DASH e coleta inicial de métricas (conectividade, latência, perda, throughput).
- **Etapa 2** — caracterização da degradação da QoE: cenários adversos com `tc/netem/tbf` (banda, atraso/jitter, perda) e tráfego concorrente com `iperf3`.
- **Etapa 3** — controle via SDN: controlador que monitora estatísticas OpenFlow, detecta tráfego elevado e instala regras dinâmicas de drop para bloquear fluxos UDP concorrentes, preservando o streaming.

P4 não foi implementado; é citado apenas como extensão futura.

## Topologias

### Etapa 1 e 2 — `topologia/topologia_qoe.py`

- `h1`: servidor DASH, IP `10.0.0.1/24`
- `h2`: cliente principal, IP `10.0.0.2/24`
- `h3`: cliente / concorrente, IP `10.0.0.3/24`
- `h4`: cliente / concorrente, IP `10.0.0.4/24`
- `s1`: switch OpenFlow 1.3
- `c0`: controlador SDN remoto em `127.0.0.1:6633`

```text
          h2
           |
h1 ---- s1 ---- h3
           |
          h4
```

### Etapa 3 — `topologia/topologia_qoe_etapa3.py`

Dois switches com enlace gargalo de 2 Mbit/s e 10 ms entre eles, para que o tráfego concorrente realmente dispute recursos com o vídeo:

```text
h1 (servidor DASH) -- s1 ==[gargalo 2 Mbit/s]== s2 -- h2 (cliente principal)
                                                   -- h3 (concorrente)
                                                   -- h4 (concorrente)
```

## Controladores

- `controlador/simple_switch_13.py`: switch L2 com aprendizado de MAC (Etapas 1 e 2).
- `controlador/qoe_controller_13.py`: controlador QoE da Etapa 3. Solicita estatísticas de porta a cada 2 s, estima a taxa em Mbit/s e, ao ultrapassar o limiar de 1,5 Mbit/s, instala regras de drop (prioridade 300, `hard_timeout` de 60 s) para os fluxos UDP `h1->h3` e `h1->h4`. Quando as regras expiram, a detecção é rearmada automaticamente e uma nova mitigação pode ser aplicada se o tráfego concorrente retornar. As decisões são registradas em `resultados/etapa3/logs/controlador_decisoes.log`.

## Requisitos

- Linux
- Mininet
- Open vSwitch
- Python 3
- OS-Ken ou Ryu
- iperf3
- curl
- ffmpeg, apenas se for gerar novamente o vídeo DASH

O VLC não é necessário: a QoE é medida pelo download de um segmento DASH com `curl -w` (tempo, tamanho, velocidade e código HTTP).

Em Ubuntu, uma instalação típica é:

```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch python3 python3-pip iperf3 curl ffmpeg make
pip3 install os-ken
```

## Demo automatizada (recomendado)

A forma mais simples de reproduzir as três etapas é a demo automatizada, que usa a API Python do Mininet e salva as evidências em `resultados/demo_final/`:

```bash
make clean
make permissions
make demo               # Etapas 1, 2 e 3 com controle SDN
make show-demo-results  # exibe o resumo dos resultados
```

Para incluir também a medição ao vivo do cenário sem controle da Etapa 3:

```bash
make demo-full
```

Detalhes em `scripts/README_DEMO_FINAL.md`.

## Execução manual

### Etapa 1 — ambiente base

Terminal 1:

```bash
make controller
```

Terminal 2:

```bash
make topology
```

Dentro do CLI do Mininet, inicie o servidor DASH no `h1`:

```bash
h1 bash scripts/start_dash_server.sh &
```

Valide conectividade, DASH e throughput:

```bash
pingall
h2 curl -I http://10.0.0.1:8000/manifest.mpd
h1 iperf3 -s -D
h2 iperf3 -c 10.0.0.1 -t 10
```

Para salvar automaticamente os resultados do baseline, com controlador e topologia ativos, rode em um terceiro terminal:

```bash
make baseline
```

### Etapa 2 — degradação e QoE

Com o ambiente da Etapa 1 ativo, aplique as degradações na saída do servidor (`h1-eth0`) e meça a QoE. Exemplos:

```bash
# limitação de banda
h1 bash -c 'tc qdisc add dev h1-eth0 root tbf rate 2mbit burst 32kbit latency 400ms'

# atraso e jitter
h1 bash -c 'tc qdisc add dev h1-eth0 root netem delay 100ms 30ms distribution normal'

# perda de pacotes
h1 bash -c 'tc qdisc add dev h1-eth0 root netem loss 2%'

# medição de QoE (tempo de download de um segmento DASH)
h2 bash scripts/measure_qoe_etapa3.sh resultados/etapa2/<cenario>
```

O buffering estimado é `max(0, tempo_de_download - 4)`, pois os segmentos DASH têm 4 segundos.

### Etapa 3 — controle via SDN

Terminal 1 (controlador QoE):

```bash
make controller-qoe
```

Terminal 2 (topologia com gargalo):

```bash
make topology-etapa3
```

No CLI do Mininet, inicie o servidor DASH, gere tráfego concorrente com `iperf3` UDP de `h1` para `h3`/`h4` e meça o download do segmento em `h2` com e sem o controlador QoE. Os logs de decisão do controlador comprovam a detecção e a mitigação.

## Resultados principais

- **Etapa 1**: `pingall` com 0% de perda, RTT médio < 0,1 ms, throughput ~88 Mbit/s e manifesto DASH acessível com `HTTP 200`.
- **Etapa 2**: o cenário combinado (banda 2 Mbit/s + atraso/jitter + perda 2% + tráfego concorrente) elevou o tempo de download do segmento de 0,07 s para 39,08 s, com buffering estimado de 35,08 s.
- **Etapa 3**: com o controlador QoE, o tempo de download sob tráfego concorrente caiu de 61,17 s para 2,51 s (redução de ~95,9%), eliminando o buffering estimado.

## Organização do repositório

- `controlador/`: controladores SDN (switch L2 e controlador QoE com mitigação dinâmica).
- `topologia/`: topologias Mininet das Etapas 1/2 e da Etapa 3 (gargalo).
- `scripts/`: automação (controlador, topologia, servidor DASH, baseline, medição de QoE, demo das três etapas e limpeza).
- `video/`: vídeo de teste e segmentos DASH.
- `resultados/`: evidências das medições (baseline, cenários da Etapa 2, Etapa 3 e demo final).
- `relatorio/figuras/`: figuras usadas no relatório.
