#!/usr/bin/env python3

import os
import time
import logging
from pathlib import Path

from operator import attrgetter

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib import hub
from os_ken.lib.packet import packet
from os_ken.lib.packet import ethernet
from os_ken.lib.packet import ether_types


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = os.environ.get(
    "QOE_LOG_FILE",
    str(PROJECT_ROOT / "resultados" / "etapa3" / "logs" / "controlador_decisoes.log"),
)

# Duracao das regras de drop instaladas na mitigacao. O mesmo valor e usado
# para rearmar a deteccao quando as regras expiram nos switches.
MITIGACAO_TIMEOUT_S = 60


class QoEController13(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(QoEController13, self).__init__(*args, **kwargs)

        self.mac_to_port = {}
        self.datapaths = {}
        self.last_port_stats = {}
        self.mitigacao_ativa = False
        self.mitigacao_expira_em = 0.0

        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s"
        )

        self.logger.info("Controlador QoE iniciado.")
        logging.info("Controlador QoE iniciado.")

        self.monitor_thread = hub.spawn(self._monitor)

    def registrar_decisao(self, mensagem):
        self.logger.info(mensagem)
        logging.info(mensagem)
        print("[QoE-SDN]", mensagem)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(datapath, 0, match, actions)
        self.registrar_decisao(
            f"Switch conectado: dpid={datapath.id}. Regra table-miss instalada."
        )

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout
        )

        datapath.send_msg(mod)

    def drop_flow(self, datapath, match, priority=300, hard_timeout=60):
        parser = datapath.ofproto_parser
        actions = []
        self.add_flow(
            datapath=datapath,
            priority=priority,
            match=match,
            actions=actions,
            hard_timeout=hard_timeout
        )

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.datapaths[datapath.id] = datapath
                self.registrar_decisao(f"Datapath registrado para monitoramento: dpid={datapath.id}")
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                del self.datapaths[datapath.id]
                self.registrar_decisao(f"Datapath removido do monitoramento: dpid={datapath.id}")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src

        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(
                in_port=in_port,
                eth_src=src,
                eth_dst=dst
            )

            self.add_flow(
                datapath=datapath,
                priority=10,
                match=match,
                actions=actions,
                idle_timeout=30
            )

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )

        datapath.send_msg(out)

    def _monitor(self):
        while True:
            for datapath in list(self.datapaths.values()):
                self._request_stats(datapath)
            hub.sleep(2)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        datapath = ev.msg.datapath
        dpid = datapath.id
        now = time.time()

        # Rearma a deteccao quando as regras de drop ja expiraram nos switches,
        # permitindo nova mitigacao se o trafego concorrente retornar.
        if self.mitigacao_ativa and now >= self.mitigacao_expira_em:
            self.mitigacao_ativa = False
            self.registrar_decisao(
                "Regras de mitigacao expiraram: deteccao rearmada."
            )

        for stat in sorted(ev.msg.body, key=attrgetter("port_no")):
            port_no = stat.port_no

            if port_no > 1000:
                continue

            key = (dpid, port_no)
            tx_bytes = stat.tx_bytes
            rx_bytes = stat.rx_bytes
            total_bytes = tx_bytes + rx_bytes

            if key in self.last_port_stats:
                last_time, last_total = self.last_port_stats[key]
                delta_time = now - last_time
                delta_bytes = total_bytes - last_total

                if delta_time > 0 and delta_bytes >= 0:
                    rate_mbps = (delta_bytes * 8) / delta_time / 1_000_000

                    if rate_mbps >= 1.5 and not self.mitigacao_ativa:
                        self.registrar_decisao(
                            f"Degradacao detectada: dpid={dpid}, porta={port_no}, taxa={rate_mbps:.2f} Mbit/s"
                        )
                        self.aplicar_mitigacao()

            self.last_port_stats[key] = (now, total_bytes)

    def aplicar_mitigacao(self):
        self.mitigacao_ativa = True
        self.mitigacao_expira_em = time.time() + MITIGACAO_TIMEOUT_S

        for dpid, datapath in self.datapaths.items():
            parser = datapath.ofproto_parser

            # Bloqueia fluxos UDP concorrentes do servidor h1 para h3 e h4.
            # Esses fluxos representam trafego iperf3 usado para degradar o streaming.
            match_h1_h3_udp = parser.OFPMatch(
                eth_type=0x0800,
                ip_proto=17,
                ipv4_src="10.0.0.1",
                ipv4_dst="10.0.0.3"
            )

            match_h1_h4_udp = parser.OFPMatch(
                eth_type=0x0800,
                ip_proto=17,
                ipv4_src="10.0.0.1",
                ipv4_dst="10.0.0.4"
            )

            self.drop_flow(datapath, match_h1_h3_udp, priority=300, hard_timeout=MITIGACAO_TIMEOUT_S)
            self.drop_flow(datapath, match_h1_h4_udp, priority=300, hard_timeout=MITIGACAO_TIMEOUT_S)

            self.registrar_decisao(
                f"Mitigacao aplicada no dpid={dpid}: bloqueio dinamico de fluxos UDP concorrentes h1->h3 e h1->h4."
            )
