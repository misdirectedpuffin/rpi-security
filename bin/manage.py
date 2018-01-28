#!/usr/bin/env python3

import argparse
import logging
import logging.handlers
import signal
import sys
import time
from threading import Thread

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
        network = Network(args.config_file, args.data_file)
        camera = Camera(
            network.photo_size,
            network.gif_size,
            network.motion_size,
            network.camera_vflip,
            network.camera_hflip,
            network.motion_detection_setting,
            network.camera_capture_length,
            network.camera_mode
        )
        if network.debug_mode:
            logger.handlers[0].setLevel(logging.DEBUG)
    except Exception as exc:
        exit_error('Configuration error: {0}'.format(repr(exc)))

    sys.excepthook = exception_handler

    # Start the threads
    telegram_bot_thread = Thread(
        name='telegram_bot',
        target=security.threads.telegram_bot,
        args=(security, camera)
    )
    telegram_bot_thread.daemon = True
    telegram_bot_thread.start()

    monitor_alarm_state_thread = Thread(
        name='monitor_alarm_state',
        target=security.threads.monitor_alarm_state,
        args=(security, camera)
    )
    monitor_alarm_state_thread.daemon = True
    monitor_alarm_state_thread.start()

    capture_packets_thread = Thread(
        name='capture_packets',
        target=security.threads.capture_packets,
        args=(security,)
    )
    capture_packets_thread.daemon = True
    capture_packets_thread.start()

    process_photos_thread = Thread(
        name='process_photos',
        target=security.threads.process_photos,
        args=(security, camera)
    )
    process_photos_thread.daemon = True
    process_photos_thread.start()
    signal.signal(signal.SIGTERM, exit_clean)
    try:
        logger.info("rpi-security running")
        network.telegram_send_message('rpi-security running')
        while True:
            time.sleep(100)
    except KeyboardInterrupt:
        exit_clean()
