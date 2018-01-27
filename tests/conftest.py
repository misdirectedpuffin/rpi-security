import pytest

from rpisec.rpis_camera import Camera

@pytest.fixture(scope="session")
def picamera():
    """Return an instance of the camera."""
    return Camera()
