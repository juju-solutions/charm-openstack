import sys
from unittest import mock

import pytest

from nagios_plugin3 import CriticalError, UnknownError

sys.path.append("files/nagios/plugins")

from check_openstack_interface import check, _parse_arguments  # noqa: E402


def check_raises(exp_error, exp_count, *args, **kwargs):

    def sep_join(interfaces):
        assert exp_count == len(interfaces), "Unexpected number of interfaces"
        return ",".join(interfaces)

    with mock.patch("check_openstack_interface.SEPARATOR") as mock_sep:
        mock_sep.join.side_effect = sep_join
        if exp_error:
            with pytest.raises(exp_error):
                check(*args, **kwargs)
        else:
            check(*args, **kwargs)


@pytest.mark.parametrize("networks,ids,kwargs,exp_error,exp_count", [
    ([("1", "ACTIVE")], set(), {"check_all": True}, None, 1),
    ([("1", "ACTIVE"), ("2", "DOWN")], set(),
     {"skip": {"2"}, "check_all": True}, None, 1),
    ([("1", "ACTIVE"), ("2", "DOWN")], set(), {"check_all": True},
     CriticalError, 1),
    ([("1", "ACTIVE"), ("2", "TEST")], set(),
     {"check_all": True}, UnknownError, 1),
    ([("1", "ACTIVE"), ("2", "TEST")], {"1"}, {}, None, 1),
    ([("1", "ACTIVE"), ("2", "TEST")], set(),
     {"skip": {"2"}, "check_all": True}, None, 1),
    ([("1", "ACTIVE"), ("2", "DOWN")], {"1"}, {}, None, 1),
    ([("1", "ACTIVE"), ("2", "DOWN")], {"1", "2"}, {}, CriticalError, 1),
    ([("1", "DOWN"), ("2", "DOWN")], {"1", "2"}, {}, CriticalError, 2),
    ([("1", "ACTIVE"), ("2", "DOWN")], {"3"}, {}, CriticalError, 1)
])
def test_check_network(networks, ids, kwargs, exp_error, exp_count,
                       credentials, add_interface):
    """Test NRPE check for OpenStack networks."""
    for net_id, status in networks:
        add_interface("network", interface_id=net_id, status=status)

    check_raises(exp_error, exp_count, credentials, "network", ids, **kwargs)


@pytest.mark.parametrize("subnets,ids,exp_error,exp_count", [
    (["1"], {"1"}, None, 1),
    (["1", "2"], {"2"}, None, 1),
    (["1", "2", "3"], {"4"}, CriticalError, 1),
    (["1", "2", "3"], {"1", "2", "3"}, None, 3)
])
def test_check_subnet(subnets, ids, exp_error, exp_count, credentials,
                      add_interface):
    """Test NRPE check for OpenStack subnets (without 'status')."""
    for subnet_id in subnets:
        add_interface("subnet", interface_id=subnet_id)

    check_raises(exp_error, exp_count, credentials, "subnet", ids)


@pytest.mark.parametrize("ports,skip,select,exp_error,exp_count", [
    ([("1", {"status": "ACTIVE"})], {}, {}, None, 1),
    ([("1", {"status": "ACTIVE"}), ("2", {"status": "DOWN"})], {"2"}, {},
     None, 1),
    ([("1", {"status": "ACTIVE", "network_id": "ext"}),
      ("2", {"status": "DOWN", "network_id": "int"})], {},
     {"network_id": "int"}, CriticalError, 1),
    ([("1", {"status": "ACTIVE", "network_id": "ext"}),
      ("2", {"status": "DOWN", "network_id": "int"})], {},
     {"network_id": "ext"}, None, 1),
    ([("1", {"status": "DOWN"})], {}, {"tenant_id": "test"}, None, 0),
    ([("1", {"status": "DOWN", "tenant_id": "test"})], {},
     {"tenant_id": "test"}, CriticalError, 1),
    ([("1", {"status": "DOWN", "tenant_id": "test", "network_id": "ext"})], {},
     {"tenant_id": "test", "network_id": "int"}, None, 0),
    ([("1", {"status": "DOWN", "tenant_id": "test", "network_id": "ext"})], {},
     {"tenant_id": "test", "network_id": "ext"}, CriticalError, 1),
    ([("1", {"status": "DOWN", "tenant_id": "test", "network_id": "ext"})], {},
     {"tenant_id": "test", "network_id": "ext"}, CriticalError, 1),
    ([(str(i), {"status": "ACTIVE", "network_id": "ext"}) for i in range(10)],
     {}, {"network_id": "ext"}, None, 10),
])
def test_check_port(ports, skip, select, exp_error, exp_count, credentials,
                    add_interface):
    """Test NRPE check for OpenStack ports (apply skip-id and select)."""
    for port_id, kwargs in ports:
        add_interface("port", interface_id=port_id, **kwargs)

    check_raises(exp_error, exp_count, credentials, "port", {}, skip=skip,
                 select=select, check_all=True)


@pytest.mark.parametrize("args,exp_output", [
    (["--all"], (set(), set(), dict(), True)),
    (["--id", "1", "--id", "2"], ({"1", "2"}, set(), dict(), False)),
    (["-i", "1", "-i", "2"], ({"1", "2"}, set(), dict(), False)),
    (["--all", "--skip-id", "2"], (set(), {"2"}, dict(), True)),
    (["--all", "--skip-id", "2", "--skip-id", "3"],
     (set(), {"2", "3"}, dict(), True)),
    (["--all", "--skip-id", "2", "--select", "a=b"],
     (set(), {"2"}, {"a": "b"}, True))
])
def test_parse_arguments(args, exp_output, monkeypatch, credentials_cnf):
    """Test configuration of argparse.parser"""
    monkeypatch.setattr(sys, "argv",
                        ["", "network", "-c", credentials_cnf, *args])
    output = _parse_arguments()

    assert exp_output == output[2:]


@pytest.mark.parametrize("interface,args", [
    ("network", ["-i", "1", "--all"]),
    ("network", ["-i", "1", "--skip-id", "1"]),
    ("network", ["-i", "1", "--select", "a=b"]),
    ("wrong-interface", ["-i", "1"]),
    ("security-group", ["--all"]),
    ("subnet", ["--all"]),
    ("network", ["--skip-id", "1"])
])
def test_parse_arguments_error(interface, args, monkeypatch, credentials_cnf):
    """Test configuration of argparse.parser raise error"""
    monkeypatch.setattr(sys, "argv",
                        ["", interface, "-c", credentials_cnf, *args])

    with pytest.raises(SystemExit):
        _parse_arguments()
