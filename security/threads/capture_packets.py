# -*- coding: utf-8 -*-

# import logging

# from scapy.all import conf as scapy_conf
# from scapy.all import sniff

# import _thread

# scapy_conf.promisc=0
# scapy_conf.sniff_promisc=0


# logger = logging.getLogger()


# def capture_packets(network):
#     """
#     This function uses scapy to sniff packets for our MAC addresses and updates
#     the alarm state when packets are detected.
#     """
#     logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

#     def update_time(packet):
#         packet_mac = set(network.mac_addresses) & set([packet[0].addr2, packet[0].addr3])
#         packet_mac_str = list(packet_mac)[0]
#         network.state.update_last_mac(packet_mac_str)
#         logger.debug('Packet detected from {0}'.format(packet_mac_str))

#     def calculate_filter(mac_addresses):
#         mac_string = ' or '.join(mac_addresses)
#         filter_text = (
#             '((wlan addr2 ({0}) or wlan addr3 ({0})) '
#             'and type mgt subtype probe-req) '
#             'or (wlan addr1 {1} '
#             'and wlan addr3 ({0}))'
#         )
#         return filter_text.format(mac_string, network.my_mac_address)

#     while True:
#         logger.info("thread running")
#         try:
#             sniff(iface=network.network_interface, store=0, prn=update_time, filter=calculate_filter(network.mac_addresses))
#         except Exception as e:
#             logger.error('Scapy failed to sniff packets with error {0}'.format(repr(e)))
#             _thread.interrupt_main()
