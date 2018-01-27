import pytest


def test_create_image_path(picamera):
    """It returns the expected image path."""
    assert picamera.create_image_path('2018-01-27T00:00:00') == \
        '/var/tmp/2018-01-27T00:00:00-security.jpg'


@pytest.mark.parametrize('timestamp, prefix, name, suffix, expected', [
    ('2018-01-27T00:00:00', None, None, '.jpg', '2018-01-27T00:00:00.jpg'),
    ('2018-01-27T00:00:00', 'foo-prefix', None,
     '.jpg', '2018-01-27T00:00:00-foo-prefix.jpg'),
    ('2018-01-27T00:00:00', 'foo-prefix', 'foo-name',
     '.jpg', '2018-01-27T00:00:00-foo-prefix-foo-name.jpg'),
    ('2018-01-27T00:00:00', 'foo-prefix', 'foo-name',
     None, '2018-01-27T00:00:00-foo-prefix-foo-name'),
])
def test_make_filename(picamera, timestamp, prefix, name, suffix, expected):
    assert picamera._make_filename(
        timestamp,
        prefix=prefix,
        name=name,
        file_suffix=suffix
    ) == expected


@pytest.mark.xfail
def test_capture_image():
    assert 1 == 2


def test_create_jpg_paths(picamera):
    """It returns the expected file paths."""
    assert list(picamera.create_jpg_paths('/test/path')) == [
        '/test/path-0',
        '/test/path-1',
        '/test/path-2',
        '/test/path-3',
        '/test/path-4',
        '/test/path-5',
        '/test/path-6',
        '/test/path-7',
        '/test/path-8',
    ]


@pytest.mark.xfail
def test_save_gif():
    """It saves a .gif to the expected location."""
    assert 1 == 2


@pytest.mark.xfail
def test_capture_to_path():
    """It """
    assert 1 == 2


@pytest.mark.xfail
def test_create_gif():
    assert 1 == 2
