# -*- coding: utf-8 -*-

import logging
import os
import time
from configparser import SafeConfigParser
from datetime import datetime
from queue import Queue
from threading import Event, Lock

import numpy as np
from PIL import Image

from picamera import PiCamera
from picamera.array import PiMotionAnalysis
from picamera.exc import PiCameraNotRecording

logger = logging.getLogger()

TIMESTAMP_FORMAT = '%Y-%m-%d-%H%M%S'


def queue_captured(func):
    """Decorator to put the captured images on a queue."""
    def wrapper(*args):
        """Wrapper to return the function"""
        queue = args[0].queue # self.queue
        captured = func(*args)
        for capture in captured:
            queue.put(captured)
        return captured

    return wrapper


def log(func):
    """Decorator to log exceptions."""
    def wrapper(*args):
        """Wrapper to return the function."""
        try:
            result = func(*args)
        except Exception as exc:
            logger.exception(
                'Exception raised in %s. Traceback: %s',
                func.__name__,
                str(exc)
            )
            return
        else:
            logger.info('%s: %s', func.__name__, result)
            return result


def pause_record(func):
    """Pause recording before a method and start afterward."""

    def wrapper(self):
        """Inner wrapper."""
        if self.camera.recording:
            self.camera.wait_recording(0.1)
        try:
            response = func(self)
        except Exception as exc:
            logger.error('Error in start_motion_detection: %s', exc)
        finally:
            self.camera.start_recording(
                os.devnull,
                format='h264',
                motion_output=self
            )
        return response

    return wrapper


def settle_time(func):
    """Check if `settle time` has been reached."""

    def wrapper(self):
        """Internal wrapper."""
        if (time.time() - self.motion_detection_started) < self.motion_settle_time:
            logger.debug('Ignoring initial motion due to settle time')
            return
        func(self)
    return wrapper


class MotionDetector(PiMotionAnalysis):
    """Extend PiMotionAnalysis with custom analysis method."""

    camera_trigger = Event()

    def __init__(self, camera, size=None):
        super(MotionDetector, self).__init__(camera, size)
        self.motion_magnitude = 60
        self.motion_vectors = 10
        self.motion_settle_time = 1
        self.motion_detection_started = 0

        self.camera.framerate = self.motion_framerate
        exposure_speed = self.camera.exposure_speed
        self.camera.shutter_speed = exposure_speed
        self.camera.awb_mode = 'off'
        self.camera.exposure_mode = 'off'

    @log
    @pause_record
    def start_motion_detection(self):
        """Begin motion detection."""
        logger.debug('Starting motion detection')
        self.set_motion_settings()
        self.motion_detection_started = time.time()

    @settle_time
    def analyse(self, a):
        """Motion detection algorithm taken from docs.

        https://picamera.readthedocs.io/en/release-1.10/api_array.html#picamera.array.PiMotionAnalysis
        """
        a = np.sqrt(
            np.square(a['x'].astype(np.float)) +
            np.square(a['y'].astype(np.float))
        ).clip(0, 255).astype(np.uint8)

        vector_count = (a > self.motion_magnitude).sum()
        if vector_count > self.motion_vectors:
            logger.info(
                'Motion detected. Vector count: %s. Threshold: %s',
                vector_count,
                self.motion_vectors
            )
            # Set flag=True. Notify all threads.
            self.camera_trigger.set()


class Camera(PiCamera):
    """A wrapper for the camera.

    Runs motion detection, provides a queue for photos, captues photos and GIFs.
    Default resolution is 1280x720. Original code has it as 1024x768.
    """

    def __init__(
            self,
            framerate=5,
            resolution=(1024, 768),  # auto set to 1280 x 720 if None
            temp_directory='/var/tmp',
            images_directory='/var/tmp'
    ):
        super(Camera, self).__init__(framerate=framerate, resolution=resolution)

        self.camera_mode = 'gif'.lower()
        self.photo_size = (1024, 768)
        self.gif_size = (1024, 768)
        self.motion_size = (1024, 768)
        self.motion_detection_setting = (60, 10)
        self.vflip = False
        self.hflip = False
        self.debug_mode = False
        self.pir_pin = 14
        self.capture_length = 3
        self.temp_directory = temp_directory
        self.images_directory = images_directory

        self.lock = Lock()
        self.queue = Queue()


    def create_image_path(self, timestamp, prefix='security', name=None, file_suffix='.jpg'):
        """Create the location on disk to store the captured image."""
        # timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        if prefix == name:
            prefix = None

        return os.path.join(
            self.images_directory,
            self._make_filename(
                timestamp,
                prefix=prefix,
                name=name,
                file_suffix=file_suffix
            )
        )

    def _make_filename(self, timestamp, prefix=None, name=None, file_suffix='.jpg'):
        """Return the correct filename.

        Args:
            timestamp (str): timestamp as a string.
            prefix (str): A prefix before the file name.
            name (str): The file name
        Returns:
            A filename with .jpg suffix.
        """
        parts = [part for part in (timestamp, prefix, name) if part is not None]
        return '-'.join(parts) + (file_suffix or '')

    @log
    def capture_image(self, timestamp, name=None):
        """Captures an image and saves it to disk."""
        image_path = self.create_image_path(timestamp, name=name)
        with self.lock:
            while self.recording:
                time.sleep(0.1)
            time.sleep(2)
            self.capture(image_path, use_video_port=False)
        return image_path

    def create_jpg_paths(self, path, capture_length=3):
        """Yield numbered paths.

        Args:
            path (str): The absolute file path to enumerate.
        Yield:
            (str): A numbered formatted string.
        """
        for i in range(capture_length * 3):
            yield '{path}-{count}'.format(path=path, count=i)

    def save_gif(self, first, rest, timestamp=None):
        """Create a gif from a series of images (jpg)

        Args:
            first (str): The path to the first image in the series.
            rest (list): A list of paths to the remaining images.
            timestamp (str): A string representing the current date and
                time.
        Returns: None
        """

        # Create a new path to store a .gif
        if timestamp is None:
            date_time = datetime.utcnow()

        timestamp = date_time.strftime(TIMESTAMP_FORMAT)
        gif_path = self.create_image_path(timestamp, file_suffix='.gif')

        first_jpg = Image.open(first)
        return first_jpg.save(
            gif_path,
            append_images=[Image.open(path) for path in rest],
            save_all=True,
            loop=0,
            duration=200
        )

    def capture_to_path(self, path):
        """Capture an image from the camera to the current path.

        Args:
            path (str): The path to capture to.

        Returns: None
        """
        while self.recording:
            time.sleep(0.1)
        self.capture(path)

    @log
    def create_gif(self, timestamp, capture_length=3):
        """Create a gif from a series of jpg files

        Args:
            timestamp (str): A string in the form `TIMESTAMP_FORMAT`
        """
        prepared_paths = [self.create_image_path(timestamp, name=i) for i in range(capture_length * 3)]
        paths = self.capture_sequence(prepared_paths)

        with self.lock:
            for path in paths:
                self.capture_to_path(path)

        # # Remove the unused jpg paths.
        # for jpeg in jpg_paths:
        #     os.remove(jpeg)

    @queue_captured
    def trigger_camera(self, timestamp, capture_length=3):
        """Capture image.

        Args:
            timestamp (str): Timestamp in format '%Y-%m-%d-%H%M%S'
        """
        if self.camera_mode == 'gif':
            captured = self.create_gif(timestamp)

        elif self.camera_mode == 'photo':
            for i in range(capture_length):
                captured = self.capture_image(timestamp, name=i)

        else:
            logger.error('Unsupported camera_mode: %s', self.camera_mode)
        return captured

    @log
    def end_recording(self):
        """Stop the camera from recording."""
        try:
            logger.debug('Stopping recording.')
            self.stop_recording()
        except PiCameraNotRecording as exc:
            logger.warning(str(exc))
            return


    def clear_queue(self):
        with self.queue.mutex:
            self.queue.queue.clear()

    def process_photos(self, network):
        """
        Monitors the captured_from_camera list for newly captured photos.
        When a new photos are present it will run arp_ping_macs to remove
        false positives and then send the photos via Telegram.
        After successfully sendind the photo it will also archive the photo
        and remove it from the list.
        """
        logger.info("thread running")
        while True:
            if not self.queue.empty():
                if network.state.current == 'armed':
                    logger.debug('Running arp_ping_macs before sending photos...')
                    network.arp_ping_macs()
                    time.sleep(2)
                    while True:
                        if network.state.current != 'armed':
                            self.clear_queue()
                            break
                        photo = self.queue.get()
                        if photo is None:
                            break
                        logger.debug('Processing the photo: {0}'.format(photo))
                        network.state.update_triggered(True)
                        network.telegram_send_message('Motioned detected')
                        if network.telegram_send_file(photo):
                            self.queue.task_done()
                else:
                    logger.debug('Stopping photo processing as state is now {0} and clearing queue'.format(
                        network.state.current))
                    self.queue.queue.clear()
            time.sleep(0.1)
