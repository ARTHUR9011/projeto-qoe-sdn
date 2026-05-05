from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


def criar_topologia():
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

    info("*** Adicionando hosts\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")

    info("*** Adicionando switch OpenFlow\n")
    s1 = net.addSwitch("s1", protocols="OpenFlow13")

    info("*** Criando enlaces\n")
    net.addLink(h1, s1, bw=100)
    net.addLink(h2, s1, bw=100)
    net.addLink(h3, s1, bw=100)
    net.addLink(h4, s1, bw=100)

    info("*** Iniciando rede\n")
    net.build()
    c0.start()
    s1.start([c0])

    info("*** Testando conectividade\n")
    net.pingAll()

    info("*** Rede pronta. Use os comandos no terminal do Mininet.\n")
    CLI(net)

    info("*** Encerrando rede\n")
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    criar_topologia()
