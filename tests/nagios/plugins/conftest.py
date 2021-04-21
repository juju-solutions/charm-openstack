from configparser import ConfigParser
from unittest.mock import MagicMock

import openstack
import pytest

INTERFACES = {}


class FakeOpenStackInterface:
    def __init__(self, interface_type, interface_id, status=None, **kwargs):
        self._interface_type = interface_type
        self._id = interface_id
        if status is not None:
            self.status = status
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return "{}-{}".format(self._interface_type, self._id)

    @property
    def type(self):
        return self._interface_type


def get_id(name):
    return name.split("-")[-1]


@pytest.fixture
def credentials():
    yield {"openstack": {"auth_url": "127.0.0.1"}}


@pytest.fixture
def credentials_cnf(tmpdir, credentials):
    config = ConfigParser()
    config.read_dict(credentials)
    path = tmpdir.join("test.cnf")
    with open(path, "w") as file:
        config.write(file)

    yield path.strpath


@pytest.fixture(autouse=True)
def mock_openstack(monkeypatch):
    global INTERFACES
    fake_connection = MagicMock()
    fake_connection.network.networks.side_effect = lambda: [
        net for net in INTERFACES.values() if net.type == "network"]
    fake_connection.network.subnets.side_effect = lambda: [
        subnet for subnet in INTERFACES.values() if subnet.type == "subnet"]
    fake_connection.network.ports.side_effect = lambda: [
        port for port in INTERFACES.values() if port.type == "port"]

    monkeypatch.setattr(openstack, "connect", lambda auth_url: fake_connection)

    yield fake_connection

    INTERFACES.clear()


@pytest.fixture
def add_interface():
    def _add_interface(interface, interface_id, **kwargs):
        global INTERFACES
        INTERFACES.update({
            interface_id: FakeOpenStackInterface(interface, interface_id,
                                                 **kwargs)
        })

    yield _add_interface


@pytest.fixture
def remove_interface():
    def _remove_interface(interface_id):
        global INTERFACES
        del INTERFACES[interface_id]

    yield _remove_interface
