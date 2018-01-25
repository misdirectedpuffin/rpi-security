"""Unit tests related to security class."""
import yaml

import pytest
from rpisec import RpisSecurity


def test_read_data_file(tmpdir):
    """It reads a data file from disk."""
    with tmpdir.as_cwd():
        with open('test.yaml', mode='wb') as tmp_stream:
            mock_data = {'foo': 'bar'}
            yaml.dump(mock_data, tmp_stream)
            pi_security = RpisSecurity('/foo.txt', 'test.yaml')
            print(pi_security._read_data_file())
            # assert pi_security._read_data_file() == 
