# Projeto QoE SDN — Etapa 1

## Objetivo

Construir um ambiente experimental funcional e reproduzível para streaming de vídeo DASH em Mininet, usando um controlador SDN com OpenFlow e coleta inicial de métricas de rede. Esta etapa estabelece a base do projeto "Melhoria da QoE em Streaming de Vídeo com Mininet, SDN e P4".

## Escopo da Etapa 1

Esta entrega cobre apenas o cenário base, sem degradação artificial. Portanto, esta etapa não implementa `tc/netem`, mitigação dinâmica via controlador, P4 ou gráficos comparativos de degradação.

## Fundamentação resumida

SDN separa o plano de controle do plano de dados: o controlador decide a lógica de encaminhamento, enquanto os switches executam as regras instaladas. O OpenFlow permite que o controlador programe tabelas de fluxo nos switches. O Mininet emula hosts, switches, enlaces e topologias customizadas em Linux, com suporte nativo a OpenFlow. P4 está relacionado à programabilidade do plano de dados e pode ser usado como extensão futura, mas não faz parte da Etapa 1.

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
- VLC opcional para validação visual

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

Teste o DASH:

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
- respostas `HTTP/1.0 200 OK` para `manifest.mpd`;
- `Content-Type` do manifesto como `application/dash+xml`;
- throughput estável nos testes `iperf3`;
- ausência de degradação significativa.

## Resultados obtidos

Os resultados abaixo vêm dos arquivos já presentes em `resultados/`:

- `h1 -> h2`: 10 pacotes enviados, 10 recebidos, 0% perda, RTT médio 0,123 ms.
- `h2 -> h1`: 10 pacotes enviados, 10 recebidos, 0% perda, RTT médio 0,078 ms.
- `h2 -> h1` com `iperf3`: receiver aproximadamente 70,3 Mbits/sec.
- `h3 -> h1` com `iperf3`: receiver aproximadamente 72,9 Mbits/sec.
- `h4 -> h1` com `iperf3`: receiver aproximadamente 68,9 Mbits/sec.
- `h2`, `h3` e `h4` acessaram `manifest.mpd` com `HTTP/1.0 200 OK`, `Content-Type application/dash+xml` e `Content-Length 2201`.

O arquivo `resultados/pingall.txt` é gerado ao executar `make baseline` em ambiente Linux/Mininet.

## Organização do repositório

- `controlador/`: controlador SDN L2 com aprendizado de MAC e OpenFlow 1.3.
- `topologia/`: topologia Mininet com um servidor, três clientes e um switch.
- `scripts/`: automação para iniciar controlador, topologia, servidor DASH, baseline e limpeza.
- `video/`: vídeo de teste e segmentos DASH.
- `resultados/`: medições iniciais de ping, iperf3 e validação HTTP do DASH.
- `relatorio/`: relatório LaTeX da Etapa 1.

## Próximas etapas

A Etapa 2 deve introduzir degradação controlada com `tc/netem` ou `tbf`, tráfego concorrente com `iperf3` e correlação entre métricas de rede e QoE. Essas funcionalidades não foram implementadas nesta etapa.
