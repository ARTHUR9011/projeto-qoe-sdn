#!/usr/bin/env python3

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def run():
    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    info("*** Adicionando controlador remoto\n")
    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6633
    )

    info("*** Adicionando switches OpenFlow 1.3\n")
    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    s2 = net.addSwitch("s2", protocols="OpenFlow13")

    info("*** Adicionando hosts\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24")  # servidor DASH
    h2 = net.addHost("h2", ip="10.0.0.2/24")  # cliente principal
    h3 = net.addHost("h3", ip="10.0.0.3/24")  # concorrente
    h4 = net.addHost("h4", ip="10.0.0.4/24")  # concorrente

    info("*** Criando enlaces\n")
    net.addLink(h1, s1, bw=100)
    net.addLink(s1, s2, bw=2, delay="10ms")  # enlace gargalo
    net.addLink(s2, h2, bw=100)
    net.addLink(s2, h3, bw=100)
    net.addLink(s2, h4, bw=100)

    info("*** Iniciando rede\n")
    net.build()
    c0.start()
    s1.start([c0])
    s2.start([c0])

    info("*** Testando conectividade\n")
    net.pingAll()

    info("*** CLI do Mininet pronta\n")
    CLI(net)

    info("*** Encerrando rede\n")
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
