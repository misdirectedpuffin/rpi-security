# -*- coding: utf-8 -*-

import logging
import os
import sys
import time
import _thread

import yaml
from netaddr import IPNetworkInterface
from scapy.all import ARP, Ether, srp, sniff
from scapy.all import conf as scapy_conf
from telegram import Bot as TelegramBot

from netifaces import ifaddresses

from .exit_clean import exit_error
from .security.state import State

scapy_conf.promisc = 0
scapy_conf.sniff_promisc = 0

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
logger = logging.getLogger()


class Network(object):
    """Reads and processed configuration, checks system settings."""

    def __init__(self, interface='mon0', user_mac_address=None):
        self.interface = interface
        self._mac_addresses = None
        self._user_mac_address = None
        self._interface_mac_addr = None
        self._is_monitor_mode = None
        self._network_address = None
        self._check_system()
        self.state = State(self)

    def _arp_ping(self, mac_address):
        result = False
        # Send and recieve packets.
        ether = Ether(dst=mac_address)/ARP(pdst=self.network_address)
        answered, unanswered = srp(ether, timeout=1, verbose=False)
        if any(answered):
            for reply in answered:
                if reply[1].hwsrc == mac_address:
                    if not isinstance(result, list):
                        result = []
                    result.append(str(reply[1].psrc))
                    result = ', '.join(result)
        return result

    def arp_ping_macs(self, mac_address, repeat=4):
        """Performs an ARP scan of a destination MAC address

        Determines if the MAC addresses are present on the network.
        """
        while repeat > 0:
            for mac_address in self.mac_addresses:
                result = self._arp_ping(mac_address)
                if result:
                    logger.debug(
                        'MAC %s responded to ARP ping with address %s',
                        mac_address,
                        result
                    )
                    break
                else:
                    logger.debug(
                        'MAC %s did not respond to ARP ping',
                        mac_address
                    )
            if repeat > 1:
                time.sleep(2)
            repeat -= 1

    def _check_system(self):
        if not os.geteuid() == 0:
            exit_error('{0} must be run as root'.format(sys.argv[0]))

        if not self.is_monitor_mode():
            message = (
                'Monitor mode is not enabled for interface {0} '
                'or interface does not exist'
            )
            raise Exception(message.format(self.network_interface))

        # self._set_interface_mac_addr()
        # self._set_network_address()

    @property
    def mac_addresses(self):
        if self._mac_addresses is None:
            self._mac_addresses = self.config.mac_addresses.lower().split(',')
        return self._mac_addresses

    @property
    def user_mac_address(self):
        if self._user_mac_address is None:
            self._user_mac_address = 'xx:ee:ii:ii:ee:ff:uu:99:ee:78'
        return self._user_mac_address

    @property
    def is_valid(self):
        path = '/sys/class/net/{0}/type'.format(self.interface)
        try:
            with open(path, 'r') as type_file:
                content = type_file.read()
        except FileNotFoundError as exc:
            logger.exception(exc)
        else:
            return content.startswith('80')

    @property
    def is_operational(self):
        """Check that the interface is not 'down'."""
        path = '/sys/class/net/{0}/operstate'.format(self.interface)
        try:
            with open(path, 'r') as operdata:
                content = operdata.read()
        except FileNotFoundError as exc:
            logger.exception(exc)
        else:
            return content.startswith('down')

    @property
    def is_monitor_mode(self):
        """
        Returns True if an interface is in monitor mode
        """
        if self._is_monitor_mode is None:
            self._is_monitor_mode = all([
                self.is_operational,
                self.is_valid
            ])
        return self._is_monitor_mode

    @property
    def interface_mac_addr(self):
        """
        Gets the MAC address of an interface
        """
        if self._interface_mac_addr is None:
            try:
                interface_path = '/sys/class/net/{0}/address'.format(
                    self.network_interface)

                with open(interface_path, 'r') as f:
                    self._interface_mac_addr = f.read().strip()
            except FileNotFoundError:
                raise Exception('Interface {0} does not exist'.format(self.network_interface))
            except Exception:
                raise Exception('Unable to get MAC address for interface {0}'.format(self.network_interface))
        return self._interface_mac_addr


    @property
    def network_address(self):
        """
        Finds the corresponding normal interface for a monitor interface and
        then calculates the subnet address of this interface
        """
        if self._network_address is None:
            for interface in os.listdir('/sys/class/net'):
                if interface in ['lo', self.interface]:
                    continue
                try:
                    with open('/sys/class/net/{0}/address'.format(interface), 'r') as f:
                        interface_mac_address = f.read().strip()
                except:
                    pass
                else:
                    if interface_mac_address == self.interface_mac_addr:
                        interface_details = ifaddresses(interface)
                        my_network = IPNetworkInterface(
                            '{0}/{1}'.format(
                                interface_details[2][0]['addr'],
                                interface_details[2][0]['netmask']
                            )
                        )
                        network_address = my_network.cidr
                        logger.debug(
                            'Calculated network %s from interface %s',
                            network_address,
                            interface
                        )
                        self.network_address = str(network_address)
            if not hasattr(self, 'network_address'):
                message = 'Unable to get network address for interface {0}'.format(
                    self.interface
                )
                raise Exception(message)

    def capture_packets(self):
        """
        This function uses scapy to sniff packets for our MAC addresses and updates
        the alarm state when packets are detected.
        """
        logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
        while True:
            logger.info("Capturing packets")
            try:
                sniff(
                    iface=self.interface,
                    store=0,
                    prn=self.update_time,
                    filter=self.calculate_filter(self.mac_addresses)
                )
            except Exception as e:
                logger.error(
                    'Scapy failed to sniff packets with error {0}'.format(repr(e)))
                _thread.interrupt_main()

    def update_time(self, packet):
        packet_mac = set(self.mac_addresses) & \
            set([
                packet[0].addr2,
                packet[0].addr3
            ])
        packet_mac_str = list(packet_mac)[0]
        self.state.update_last_mac(packet_mac_str) # store in db?
        logger.debug('Packet detected from {0}'.format(packet_mac_str))

    def calculate_filter(self):
        mac_string = ' or '.join(self.mac_addresses)
        filter_text = (
            '((wlan addr2 ({0}) or wlan addr3 ({0})) '
            'and type mgt subtype probe-req) '
            'or (wlan addr1 {1} '
            'and wlan addr3 ({0}))'
        )
        return filter_text.format(mac_string, self.user_mac_address)

    def monitor_alarm_state(self, camera):
        """
        This function monitors and updates the alarm state, starts/stops motion detection when
        state is armed and takes photos when motion detection is triggered.
        """
        logger.info("thread running")
        while True:
            time.sleep(0.1)
            self.state.check()
            if self.state.current == 'armed':
                while not camera.lock.locked():
                    camera.start_motion_detection()
                    self.state.check()
                    if self.state.current is not 'armed':
                        break
                    if camera.motion_detector.camera_trigger.is_set():
                        camera.stop_motion_detection()
                        camera.trigger_camera()
                        camera.motion_detector.camera_trigger.clear()
                else:
                    camera.stop_motion_detection()
            else:
                camera.stop_motion_detection()
