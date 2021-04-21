from unittest import mock
from unittest.mock import MagicMock

import pytest

from reactive import openstack
from charms.layer.nagios import NAGIOS_PLUGINS_DIR
from charms.reactive import clear_flag, is_flag_set
from charmhelpers.contrib.charmsupport import nrpe
from charmhelpers.core.hookenv import config


@mock.patch("reactive.openstack.update_nrpe_config")
def test_initial_nrpe_config(mock_update_nrpe_config):
    clear_flag("nrpe-external-master.initial-config")
    openstack.initial_nrpe_config()
    assert is_flag_set("nrpe-external-master.initial-config")
    mock_update_nrpe_config.assert_called_once()


@mock.patch("reactive.openstack.update_nrpe_config")
def test_initial_nrpe_config_failed(mock_update_nrpe_config):
    def raise_error():
        raise Exception("test error")
    mock_update_nrpe_config.side_effect = raise_error
    clear_flag("nrpe-external-master.initial-config")

    with pytest.raises(Exception):
        openstack.initial_nrpe_config()
    assert not is_flag_set("nrpe-external-master.initial-config")
    mock_update_nrpe_config.assert_called_once()


@mock.patch("nrpe_helpers.write_nagios_openstack_cnf")
def test_update_nrpe_config(mock_write_nagios_openstack_cnf, kv):
    nrpe.NRPE.return_value = mock_nrpe_setup = MagicMock()
    NAGIOS_PLUGINS_DIR.__fspath__.return_value = "/test/"
    config.return_value = mock_config = MagicMock()

    # no NRPE checks were added / deleted
    mock_config.changed.return_value = False
    mock_config.get.side_effect = {}.get
    openstack.update_nrpe_config()
    mock_nrpe_setup.add_check.assert_not_called()
    mock_nrpe_setup.remove_check.assert_called_once_with(
        shortname="openstack_loadbalancers", description="",
        check_cmd="/test/check_openstack_loadbalancer.py "
                  "-c /etc/nagios/openstack.cnf"
    )
    mock_write_nagios_openstack_cnf.assert_called_once_with()
    mock_nrpe_setup.reset_mock()
    mock_config.reset_mock()

    # add NRPE check for kubernetes subnet
    mock_config.changed.return_value = True
    mock_config.get.side_effect = {"subnet-id": "1234"}.get
    openstack.update_nrpe_config()
    mock_nrpe_setup.add_check.assert_called_once_with(
        shortname="kubernetes_subnet",
        description="Check subnets: 1234 (skip: )",
        check_cmd="/test/check_openstack_interface.py subnet "
                  "-c /etc/nagios/openstack.cnf --id 1234"
    )
    assert mock_nrpe_setup.remove_check.call_count == 7 + 1
    mock_nrpe_setup.reset_mock()
    mock_config.reset_mock()

    # add NRPE check for servers
    mock_config.changed.return_value = True
    mock_config.get.side_effect = {"nrpe-server-ids": "1,2,3"}.get
    openstack.update_nrpe_config()
    mock_nrpe_setup.add_check.assert_called_once_with(
        shortname="openstack_servers",
        description="Check servers: 1,2,3 (skip: )",
        check_cmd="/test/check_openstack_interface.py server "
                  "-c /etc/nagios/openstack.cnf --id 1 --id 2 --id 3"
    )
    assert mock_nrpe_setup.remove_check.call_count == 7 + 1
    mock_nrpe_setup.reset_mock()
    mock_config.reset_mock()

    # add NRPE check for servers with skip-ids
    mock_config.changed.return_value = True
    mock_config.get.side_effect = {
        "nrpe-server-ids": "all", "nrpe-skip-server-ids": "1,2"}.get
    openstack.update_nrpe_config()
    mock_nrpe_setup.add_check.assert_called_with(
        shortname="openstack_servers",
        description="Check servers: all (skip: 1,2)",
        check_cmd="/test/check_openstack_interface.py server "
                  "-c /etc/nagios/openstack.cnf --all --skip-id 1 --skip-id 2"
    )
    assert mock_nrpe_setup.remove_check.call_count == 7 + 1
    mock_nrpe_setup.reset_mock()
    mock_config.reset_mock()

    # raise a ValueError while adding NRPE check
    mock_config.changed.return_value = True
    mock_config.get.side_effect = {
        "nrpe-server-ids": "1,2", "nrpe-skip-server-ids": "1"}.get
    with pytest.raises(ValueError):
        openstack.update_nrpe_config()

    mock_config.get.side_effect = {"subnet-id": "all"}.get

    with pytest.raises(ValueError):
        openstack.update_nrpe_config()

    mock_nrpe_setup.reset_mock()
    mock_config.reset_mock()

    # add NRPE check for loadbalancers
    kv().getrange.return_value = {"lb_1": None}
    mock_config.changed.return_value = False
    mock_config.get.side_effect = {}.get
    openstack.update_nrpe_config()
    mock_nrpe_setup.add_check.assert_called_once_with(
        shortname="openstack_loadbalancers",
        description="Check loadbalancers: lb_1",
        check_cmd="/test/check_openstack_loadbalancer.py "
                  "-c /etc/nagios/openstack.cnf --name lb_1"
    )
    mock_nrpe_setup.remove_check.assert_not_called()
    mock_nrpe_setup.reset_mock()

    kv().getrange.return_value = {"lb_1": None, "lb_2": None}
    openstack.update_nrpe_config()
    mock_nrpe_setup.add_check.assert_called_once_with(
        shortname="openstack_loadbalancers",
        description="Check loadbalancers: lb_1,lb_2",
        check_cmd="/test/check_openstack_loadbalancer.py "
                  "-c /etc/nagios/openstack.cnf --name lb_1 --name lb_2"
    )

    mock_nrpe_setup.remove_check.assert_not_called()
    mock_nrpe_setup.reset_mock()


@mock.patch("nrpe_helpers.remove_nagios_openstack_cnf")
def test_remove_nrpe_config(mock_remove_nagios_openstack_cnf, kv):
    nrpe.NRPE.return_value = mock_nrpe_setup = MagicMock()
    NAGIOS_PLUGINS_DIR.__fspath__.return_value = "/test/"
    config.return_value = mock_config = MagicMock()

    # no NRPE checks were removed
    mock_config.get.side_effect = {}.get
    openstack.remove_nrpe_config()
    mock_nrpe_setup.remove_check.assert_called_once_with(
        shortname="openstack_loadbalancers", description="",
        check_cmd="/test/check_openstack_loadbalancer.py "
                  "-c /etc/nagios/openstack.cnf"
    )
    mock_remove_nagios_openstack_cnf.assert_called_once_with()
    mock_remove_nagios_openstack_cnf.reset_mock()
    mock_nrpe_setup.reset_mock()

    # remove NRPE check for kubernetes network
    mock_config.get.side_effect = {"nrpe-server-ids": "1,2,3"}.get
    openstack.remove_nrpe_config()
    mock_nrpe_setup.remove_check.assert_has_calls([
        mock.call(shortname="openstack_servers", description="",
                  check_cmd="/test/check_openstack_interface.py server "
                            "-c /etc/nagios/openstack.cnf "
                            "--id 1 --id 2 --id 3"),
        mock.call(shortname="openstack_loadbalancers", description="",
                  check_cmd="/test/check_openstack_loadbalancer.py "
                            "-c /etc/nagios/openstack.cnf"),
    ])
    mock_remove_nagios_openstack_cnf.assert_called_once_with()
    mock_remove_nagios_openstack_cnf.reset_mock()
    mock_nrpe_setup.reset_mock()
