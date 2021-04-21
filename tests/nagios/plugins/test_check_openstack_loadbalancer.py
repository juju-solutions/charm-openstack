import collections
import sys

import pytest

from nagios_plugin3 import CriticalError, WarnError

sys.path.append("files/nagios/plugins")

from check_openstack_loadbalancer import (  # noqa: E402
    check, _healthy, _warning)  # noqa: E402


FakeLB = collections.namedtuple("FakeLB",
                                "provisioning_status operating_status")


@pytest.mark.parametrize("lbs,names,exp_error", [
    ({"lb_1": FakeLB("ACTIVE", "ONLINE")}, ["lb_1", "lb_2"], CriticalError),
    ({"lb_1": FakeLB("ACTIVE", "ONLINE"),
      "lb_2": FakeLB("ACTIVE", "ONLINE")}, ["lb_1", "lb_2"], None),
    ({"lb_1": FakeLB("ACTIVE", "ONLINE"),
      "lb_2": FakeLB("ACTIVE", "ONLINE")}, ["lb_1"], None),
    ({"lb_1": FakeLB("PENDING_UPDATE", "OFFLINE"),
      "lb_2": FakeLB("ACTIVE", "ONLINE")}, ["lb_1"], WarnError),
    ({"lb_1": FakeLB("DELETED", "OFFLINE"),
      "lb_2": FakeLB("ACTIVE", "ONLINE")}, ["lb_1", "lb_2"], CriticalError),
    ({"lb_1": FakeLB("ACTIVE", "ONLINE"),
      "lb_2": FakeLB("ERROR", "ERROR")}, ["lb_1", "lb_2"], CriticalError),
    ({}, ["lb_1", "lb_2"], CriticalError),
])
def test_check(lbs, names, exp_error, loadbalancers, credentials):
    """Test NRPE check for OpenStack load balancer."""
    loadbalancers.update(lbs)
    if exp_error:
        with pytest.raises(exp_error):
            check(credentials, names)
    else:
        check(credentials, names)


@pytest.mark.parametrize("lb, exp_return", [
    (FakeLB("ACTIVE", "ONLINE"), True),
    (FakeLB("DELETED", "ONLINE"), False),
    (FakeLB("ERROR", "ERROR"), False),
    (FakeLB("ACTIVE", "ERROR"), False),
])
def test_healthy(lb, exp_return):
    """Test function to check whether the loadbalancer is healthy."""
    assert _healthy(lb) == exp_return


@pytest.mark.parametrize("lb, exp_return", [
    (FakeLB("ACTIVE", "ONLINE"), False),
    (FakeLB("PENDING_CREATE", "ONLINE"), True),
    (FakeLB("PENDING_UPDATE", "ONLINE"), True),
    (FakeLB("PENDING_DELETE", "ONLINE"), True),
    (FakeLB("PENDING_DELETE", "OFFLINE"), True),
    (FakeLB("ERROR", "ERROR"), False),
    (FakeLB("ACTIVE", "ERROR"), False),
])
def test_warning(lb, exp_return):
    """Test function to check whether the loadbalancer is in warning state."""
    assert _warning(lb) == exp_return
