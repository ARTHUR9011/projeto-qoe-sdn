# QoE em Streaming de Vídeo com Controle via SDN

**Construção do ambiente experimental, caracterização da degradação da Qualidade de Experiência e mitigação dinâmica com OpenFlow**

Unipampa · Engenharia de Software · Programabilidade de infraestrutura de redes

**Arthur Provenzi Parizotto · Rafael Lopes**
Prof. Marcelo Caggiani Luizelli — Alegrete, 2026

---

## 1. O problema

**Vídeo DASH é baixado em segmentos de 4 segundos — e a rede nem sempre colabora**

- No streaming **DASH**, o player baixa o vídeo em pequenos segmentos. Se um segmento demora **mais de 4 s** para chegar, a reprodução trava: é o **rebuffering**.
- Banda limitada, atraso, jitter, perda de pacotes e **tráfego concorrente** degradam a Qualidade de Experiência (QoE) do usuário.
- **Pergunta do projeto:** uma rede programável (SDN) consegue *detectar* essa degradação e *reagir sozinha* para proteger o vídeo?

---

## 2. Visão geral — três etapas

**Construir, degradar, controlar**

| Etapa | O que faz |
|---|---|
| **Etapa 1 — Construir o ambiente** | Topologia emulada no Mininet com switch OpenFlow, controlador SDN e servidor de vídeo DASH. Baseline de latência, perda e throughput. |
| **Etapa 2 — Degradar e medir** | Cenários adversos com `tc/netem/tbf` e tráfego concorrente com `iperf3`. A QoE é medida pelo tempo de download de um segmento. |
| **Etapa 3 — Controlar via SDN** | Controlador monitora a rede, detecta tráfego elevado e instala regras OpenFlow que bloqueiam os fluxos concorrentes, preservando o vídeo. |

---

## 3. Ambiente experimental

**Tudo roda emulado em uma única máquina Linux**

| Ferramenta | Papel |
|---|---|
| **Mininet** | emula hosts, switches e enlaces virtuais |
| **Open vSwitch** | switch virtual compatível com OpenFlow 1.3 |
| **OS-Ken / Ryu** | controlador SDN que programa os switches |
| **FFmpeg** | gera o vídeo e o segmenta no formato DASH |
| **http.server** | servidor HTTP do Python entrega os segmentos |
| **curl -w** | mede tempo, vazão e código HTTP do download |
| **iperf3** | gera tráfego UDP concorrente ao vídeo |
| **tc / netem / tbf** | aplica banda limitada, atraso, jitter e perda |

---

## 4. Etapa 1 — Ambiente base

**Um servidor DASH, três clientes, um switch OpenFlow**

```text
                    h2  cliente principal
                     |
h1 servidor ---- s1 ---- h3  cliente
   DASH              |
                    h4  cliente

controlador c0 (OS-Ken) programa o s1 via OpenFlow 1.3
```

Resultados do baseline:

| Métrica | Resultado |
|---|---|
| Perda no `pingall` | **0%** (12/12) |
| RTT médio entre hosts | **~0,07 ms** |
| Throughput com iperf3 | **~88 Mbit/s** |
| Manifesto DASH | **HTTP 200** |

---

## 5. Etapa 2 — Metodologia

**A QoE vira número: tempo para baixar um segmento**

- As degradações são aplicadas com **tc** na interface de saída do servidor (**h1-eth0**) — é por ali que todo o vídeo passa.
- O cliente **h2** baixa sempre o mesmo segmento de 518 KB e o **curl** registra tempo, velocidade e código HTTP.
- Como cada segmento tem 4 s de vídeo: **buffering estimado = max(0, tempo de download − 4 s)**.

```bash
h2 curl -o chunk.m4s \
   -w "tempo=%{time_total} velocidade=%{speed_download} http=%{http_code}" \
   http://10.0.0.1:8000/chunk-stream0-00001.m4s
```

---

## 6. Etapa 2 — Resultados

**Nem toda degradação pesa igual**

Tempo de download do segmento DASH por cenário (limite do segmento: 4 s):

| Cenário | Tempo (s) | Buffering estimado (s) |
|---|---:|---:|
| Tráfego concorrente | 0,05 | 0 |
| Baseline | 0,07 | 0 |
| Perda 2% | 0,20 | 0 |
| Banda 2 Mbit/s | 2,94 | 0 |
| Atraso/jitter 100±30 ms | **10,94** | **6,94** |
| Combinado | **39,08** | **35,08** |

- O cenário **combinado** (banda + atraso + perda + concorrência) foi **553× mais lento** que o baseline.
- Tráfego concorrente sozinho **não degradou nada** — sem um gargalo compartilhado, não há disputa. Isso motiva a topologia da Etapa 3.

---

## 7. Etapa 3 — Nova topologia

**Um gargalo de verdade: 2 Mbit/s entre os switches**

```text
h1 servidor ---- s1 == gargalo 2 Mbit/s · 10 ms == s2 ---- h2  cliente principal
   DASH                                               ---- h3  concorrente
                                                      ---- h4  concorrente
```

- Todo o tráfego — vídeo e concorrente — disputa o **mesmo enlace de 2 Mbit/s**.
- O **iperf3** injeta fluxos UDP de 40 Mbit/s de h1 para h3 e h4, sufocando o download do vídeo em h2.
- Sem intervenção, o segmento que levava 0,07 s passa a levar **mais de 60 s**.

---

## 8. Etapa 3 — Controlador QoE

**Detectar, mitigar, rearmar — em ciclo**

1. **Monitorar** — pede estatísticas de porta aos switches a cada **2 s** e calcula a taxa em Mbit/s pela diferença de bytes.
2. **Detectar** — taxa acima do limiar (**1,5 Mbit/s** no gargalo) é interpretada como degradação da QoE.
3. **Mitigar** — instala regras OpenFlow de **drop** (prioridade 300) para o UDP concorrente h1→h3 e h1→h4, por 60 s.
4. **Rearmar** — quando as regras expiram, a detecção **rearma**: se o tráfego voltar, a mitigação é reaplicada.

Log real do controlador:

```text
Degradacao detectada: dpid=1, porta=1, taxa=65.60 Mbit/s
Mitigacao aplicada no dpid=1: bloqueio dinamico de fluxos UDP concorrentes h1->h3 e h1->h4.
Mitigacao aplicada no dpid=2: bloqueio dinamico de fluxos UDP concorrentes h1->h3 e h1->h4.
Regras de mitigacao expiraram: deteccao rearmada.
```

---

## 9. Etapa 3 — Resultado

**O mesmo download, 24× mais rápido**

Tempo de download do segmento sob tráfego concorrente:

| Cenário | Tempo (s) | Buffering estimado (s) | Vazão (Mbit/s) |
|---|---:|---:|---:|
| Sem controle SDN | 61,17 | 57,17 | 0,07 |
| **Com controle SDN** | **2,51** | **0** | **1,65** |

- **−95,9%** no tempo de download.
- **Buffering eliminado** com o controle ativo.

---

## 10. Conclusão

**A rede programável saiu da análise passiva para a reação automática**

- A QoE do streaming DASH é **sensível às condições da rede** — e métricas simples (tempo de download, vazão, buffering estimado) bastam para caracterizá-la.
- Um controlador SDN consegue **detectar degradação e mitigá-la sozinho**, instalando regras OpenFlow dinamicamente.
- **Trabalhos futuros:** priorização por filas OpenFlow, reroteamento em topologias com múltiplos caminhos e telemetria no plano de dados com P4.

Reprodução:

```bash
git clone https://github.com/ARTHUR9011/projeto-qoe-sdn.git
make demo               # roda as 3 etapas automaticamente
make show-demo-results  # resumo dos resultados
```
