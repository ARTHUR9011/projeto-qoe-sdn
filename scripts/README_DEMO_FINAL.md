# Demo final automatizada — Projeto QoE/SDN

## Comando recomendado para a aula

```bash
cd ~/projeto-qoe-sdn
make clean
make permissions
make demo
make show-demo-results
```

O alvo `make demo` roda a versao de apresentacao: Etapa 1, Etapa 2 e Etapa 3 com controle SDN. Ele pula a medicao ao vivo sem controle na Etapa 3 para evitar travar a apresentacao.

## Para rodar tambem o cenario sem controle da Etapa 3

```bash
make demo-full
```

Nesse modo, a Etapa 3A usa um limite de tempo curto. Se aparecer `exitcode=28`, isso significa timeout: o download sem controle nao terminou dentro da janela da demo.

## Arquivos gerados

Os resultados ficam em:

```bash
resultados/demo_final/
```

Os mais importantes sao:

```bash
resultados/demo_final/resumo.txt
resultados/demo_final/resumo.csv
resultados/demo_final/etapa3/com_controle/logs_decisao_filtrados.txt
resultados/demo_final/etapa3/com_controle/flows_s1.txt
resultados/demo_final/etapa3/com_controle/flows_s2.txt
```

## O que foi corrigido nesta versao

- O iperf3 da Etapa 1 reinicia o servidor a cada cliente, evitando `server is busy running a test`.
- A Etapa 2 usa parametros de degradacao que demonstram piora da QoE sem gerar arquivo vazio por timeout.
- A Etapa 3 usa link h1-s1 com mais banda e gargalo apenas entre s1-s2, deixando a regra OpenFlow de drop aliviar o gargalo de verdade.
- O download com controle so inicia depois que o log `Mitigacao aplicada` aparece.
- O resumo nao calcula porcentagem enganosa quando o cenario sem controle termina em timeout.
