# Projeto QoE SDN - Etapa 1

## Objetivo

Construir um ambiente experimental funcional e reproduzível para streaming de vídeo DASH em Mininet, usando controlador SDN, OpenFlow e coleta inicial de métricas de rede. Esta etapa estabelece a base do projeto "Melhoria da QoE em Streaming de Vídeo com Mininet, SDN e P4".

## Escopo da Etapa 1

Esta entrega cobre somente o cenário base. O projeto nesta etapa valida a topologia, o controlador SDN, o acesso HTTP ao manifesto DASH e as métricas iniciais de conectividade, latência, perda e throughput.

Não foram aplicados atraso, perda, jitter ou limitação artificial de banda. Também não foram implementados mitigação dinâmica, degradação com `tc/netem`, comparação entre cenários degradados ou P4. P4 é citado apenas como possível extensão futura.

## Fundamentação resumida

SDN separa o plano de controle do plano de dados. O controlador decide a lógica de encaminhamento, enquanto os switches executam as regras instaladas. O OpenFlow permite que o controlador programe tabelas de fluxo nos switches. O Mininet emula hosts, switches, enlaces e topologias customizadas em Linux, com suporte a OpenFlow.

## Topologia

- `h1`: servidor DASH, IP `10.0.0.1/24`
- `h2`: cliente 1, IP `10.0.0.2/24`
- `h3`: cliente 2, IP `10.0.0.3/24`
- `h4`: cliente 3, IP `10.0.0.4/24`
- `s1`: switch OpenFlow 1.3
- `c0`: controlador SDN remoto em `127.0.0.1:6633`

```text
          h2
           |
h1 ---- s1 ---- h3
           |
          h4
```

O controlador `c0` controla o switch `s1` por OpenFlow.

## Requisitos

- Linux
- Mininet
- Open vSwitch
- Python 3
- OS-Ken ou Ryu
- iperf3
- curl
- ffmpeg, apenas se for gerar novamente o vídeo DASH

O VLC não é necessário para reproduzir os resultados documentados nesta etapa. A validação registrada foi feita por acesso HTTP ao manifesto `manifest.mpd`.

Em Ubuntu, uma instalação típica é:

```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch python3 python3-pip iperf3 curl ffmpeg make
pip3 install os-ken
```

## Como executar

Prepare as permissões dos scripts:

```bash
make permissions
```

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

Comando equivalente:

```bash
h1 bash -c "cd video/dash && python3 -m http.server 8000 --bind 10.0.0.1" &
```

Teste a conectividade:

```bash
pingall
```

Teste o DASH por HTTP:

```bash
h2 curl -I http://10.0.0.1:8000/manifest.mpd
h3 curl -I http://10.0.0.1:8000/manifest.mpd
h4 curl -I http://10.0.0.1:8000/manifest.mpd
```

Teste o throughput:

```bash
h1 iperf3 -s -D
h2 iperf3 -c 10.0.0.1 -t 10
h3 iperf3 -c 10.0.0.1 -t 10
h4 iperf3 -c 10.0.0.1 -t 10
```

Para salvar automaticamente os resultados, mantenha o controlador e a topologia em execução e rode em um terceiro terminal:

```bash
make baseline
```

Esse alvo usa `mnexec` para executar comandos nos hosts do Mininet e salva os arquivos em `resultados/`.

## Resultados esperados

No cenário base espera-se:

- `pingall` com `0% dropped`;
- respostas `HTTP/1.0 200 OK` para o manifesto DASH `manifest.mpd`;
- `Content-Type` do manifesto como `application/dash+xml`;
- throughput estável nos testes `iperf3`;
- ausência de degradação significativa.

## Resultados obtidos

Os resultados iniciais foram coletados no cenário base, sem aplicação de atraso, perda, jitter ou limitação artificial de banda.

### Conectividade

O teste `pingall` apresentou:

- Perda: `0% dropped`
- Resultado: `12/12 received` (12 pacotes recebidos de 12 enviados)

### Latência e perda

| Teste | Pacotes transmitidos | Pacotes recebidos | Perda | RTT min | RTT médio | RTT max | RTT mdev |
|---|---:|---:|---:|---:|---:|---:|---:|
| h1 -> h2 | 10 | 10 | 0% | 0.051 ms | 0.065 ms | 0.092 ms | 0.010 ms |
| h2 -> h1 | 10 | 10 | 0% | 0.052 ms | 0.074 ms | 0.133 ms | 0.023 ms |

### Throughput

| Fluxo | Intervalo sender | Sender | Intervalo receiver | Receiver | Retransmissões |
|---|---:|---:|---:|---:|---:|
| h2 -> h1 | 0.00-10.00 sec | 89.0 Mbits/sec | 0.00-10.01 sec | 88.4 Mbits/sec | 0 |
| h3 -> h1 | 0.00-10.00 sec | 88.4 Mbits/sec | 0.00-10.02 sec | 87.9 Mbits/sec | 0 |
| h4 -> h1 | 0.00-10.00 sec | 89.0 Mbits/sec | 0.00-10.02 sec | 88.5 Mbits/sec | 0 |

### Validação DASH

Os clientes `h2`, `h3` e `h4` acessaram o manifesto DASH `manifest.mpd` no servidor `h1` por HTTP.

| Cliente | Código HTTP | Servidor | Content-Type | Content-Length | Last-Modified |
|---|---|---|---|---:|---|
| h2 | HTTP/1.0 200 OK | SimpleHTTP/0.6 Python/3.12.3 | application/dash+xml | 2201 | Tue, 05 May 2026 02:15:01 GMT |
| h3 | HTTP/1.0 200 OK | SimpleHTTP/0.6 Python/3.12.3 | application/dash+xml | 2201 | Tue, 05 May 2026 02:15:01 GMT |
| h4 | HTTP/1.0 200 OK | SimpleHTTP/0.6 Python/3.12.3 | application/dash+xml | 2201 | Tue, 05 May 2026 02:15:01 GMT |

## Organização do repositório

- `controlador/`: controlador SDN L2 com aprendizado de MAC e OpenFlow 1.3.
- `topologia/`: topologia Mininet com um servidor, três clientes e um switch.
- `scripts/`: automação para iniciar controlador, topologia, servidor DASH, baseline e limpeza.
- `video/`: vídeo de teste e segmentos DASH.
- `resultados/`: medições iniciais de ping, iperf3 e validação HTTP do DASH.
- `relatorio/`: relatório LaTeX da Etapa 1.
