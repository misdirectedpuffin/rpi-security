#!/usr/bin/env python3

import argparse
import logging
import logging.handlers
import signal
import sys
import time
# from threading import Thread
import asyncio

import security
from security.camera import Camera
from security.network import Network
from security.util import exit_error, exit_clean, exception_handler


def parse_arguments():
    p = argparse.ArgumentParser(
        description='A simple security system to run on a Raspberry Pi.'
    )
    p.add_argument(
        '-c',
        '--config_file',
        help='Path to config file.',
        default='/etc/rpi-security.conf'
    )
    p.add_argument(
        '-s',
        '--data_file',
        help='Path to data file.',
        default='/var/lib/rpi-security/data.yaml'
    )
    p.add_argument(
        '-d',
        '--debug',
        help='To enable debug output to stdout',
        action='store_true',
        default=False
    )
    return p.parse_args()


def setup_logging(debug_mode, log_to_stdout):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    syslog_format = logging.Formatter(
        "%(filename)s:%(threadName)s %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    syslog_handler.setFormatter(syslog_format)

    if log_to_stdout:
        stdout_level = logging.DEBUG
        stdout_format = logging.Formatter(
            "%(asctime)s %(levelname)-7s %(filename)s:%(lineno)-12s %(threadName)-25s %(message)s", "%Y-%m-%d %H:%M:%S")
    else:
        stdout_level = logging.CRITICAL
        stdout_format = logging.Formatter("ERROR: %(message)s")

    if debug_mode:
        syslog_handler.setLevel(logging.DEBUG)
    else:
        syslog_handler.setLevel(logging.INFO)

    logger.addHandler(syslog_handler)
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(stdout_format)
    stdout_handler.setLevel(stdout_level)
    logger.addHandler(stdout_handler)
    return logger


if __name__ == "__main__":
    args = parse_arguments()
    logger = setup_logging(debug_mode=False, log_to_stdout=args.debug)

    try:
        network = Network()
        # camera = Camera()
        # if camera.debug_mode:
        #     logger.handlers[0].setLevel(logging.DEBUG)
    except Exception as exc:
        exit_error('Configuration error: {0}'.format(repr(exc)))

    else:
        loop = asyncio.get_event_loop()
        

