# -*- coding: utf-8 -*-

import logging
import os
import sys
import time
from configparser import SafeConfigParser

import yaml
from netaddr import IPNetworkInterface
from scapy.all import ARP, Ether, srp
from telegram import Bot as TelegramBot

from netifaces import ifaddresses

from .exit_clean import exit_error
from .security.state import State

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)



logger = logging.getLogger()


class NetworkInterface(object):
    """Reads and processed configuration, checks system settings."""
    default_config = {
        'camera_save_path': '/var/tmp',
        'network_interface': 'mon0',
        'packet_timeout': '700',
        'debug_mode': 'False',
        'pir_pin': '14',
        'camera_vflip': 'False',
        'camera_hflip': 'False',
        'photo_size': '1024x768',
        'gif_size': '1024x768',
        'motion_size': '1024x768',
        'motion_detection_setting': '60x10',
        'camera_mode': 'gif',
        'camera_capture_length': '3'
    }

    def __init__(self, config_file, data_file, interface='wlan0'):
        self.config_file = config_file
        self.data_file = data_file
        # self.network_interface = network_interface
        self.saved_data = self._read_data_file()
        self.interface = interface

        self._interface_mac_addr = None
        self._is_monitor_mode = None
        self._network_address = None
        self._parse_config_file()
        self._check_system()
        self.state = State(self)

        try:
            self.bot = TelegramBot(token=self.telegram_bot_token)
        except Exception as exc:
            raise Exception('Failed to connect to Telegram with error: {0}'.format(repr(exc)))

        logger.debug('Initialised: {0}'.format(vars(self)))

    def _read_data_file(self):
        """Reads a data file from disk."""
        result = None
        try:
            with open(self.data_file, 'r') as stream:
                result = yaml.load(stream) or {}
        except Exception as exc:
            logger.error('Failed to read data file {0}: {1}'.format(self.data_file, repr(exc)))
        else:
            logger.debug('Data file read: {0}'.format(self.data_file))
        return result

    def _parse_config_file(self):
        def _str2bool(v):
            return v.lower() in ("yes", "true", "t", "1")

        cfg = SafeConfigParser(defaults=self.default_config)
        cfg.read(self.config_file)

        for k, v in cfg.items('main'):
            setattr(self, k, v)

        self.debug_mode = _str2bool(self.debug_mode)
        self.camera_vflip = _str2bool(self.camera_vflip)
        self.camera_hflip = _str2bool(self.camera_hflip)
        self.pir_pin = int(self.pir_pin)
        self.photo_size = tuple([int(x) for x in self.photo_size.split('x')])
        self.gif_size = tuple([int(x) for x in self.gif_size.split('x')])
        self.motion_size = tuple([int(x) for x in self.motion_size.split('x')])
        self.motion_detection_setting = tuple([int(x) for x in self.motion_detection_setting.split('x')])
        self.camera_capture_length = int(self.camera_capture_length)
        self.camera_mode = self.camera_mode.lower()
        self.packet_timeout = int(self.packet_timeout)
        self.mac_addresses = self.mac_addresses.lower().split(',')

    def _arp_ping(self, mac_address):
        result = False
        answered, unanswered = srp(
            Ether(
                dst=mac_address
                )/ARP(pdst=self.network_address),
                timeout=1,
                verbose=False
        )
        if len(answered) > 0:
            for reply in answered:
                if reply[1].hwsrc == mac_address:
                    if type(result) is not list:
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

