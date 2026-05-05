#!/usr/bin/env python3
"""Topologia base da Etapa 1 para streaming DASH em Mininet."""

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController


def criar_rede():
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )

    info("*** Adicionando controlador remoto c0 em 127.0.0.1:6633\n")
    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6633,
    )

    info("*** Adicionando hosts\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")

    info("*** Adicionando switch s1 com OpenFlow 1.3\n")
    s1 = net.addSwitch("s1", protocols="OpenFlow13", failMode="secure")

    info("*** Criando enlaces TCLink de 100 Mbps\n")
    for host in (h1, h2, h3, h4):
        net.addLink(host, s1, bw=100)

    return net, c0, s1


def executar_topologia():
    net, c0, s1 = criar_rede()

    try:
        info("*** Iniciando rede\n")
        net.build()
        c0.start()
        s1.start([c0])

        info("*** Testando conectividade inicial com pingAll\n")
        net.pingAll()

        info("*** Rede pronta. Use os comandos no CLI do Mininet.\n")
        CLI(net)
    finally:
        info("*** Encerrando rede\n")
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    executar_topologia()
