#!/usr/bin/env python3

# Copyright (C) 2021 Canonical Ltd.

# Authors:
#   Robert Gildein <robert.gildein@canonical.com>


import argparse
import os
from configparser import ConfigParser

import openstack
from nagios_plugin3 import try_check, CriticalError, WarnError, UnknownError


SEPARATOR = ","
HEALTHY = 0
WARNING = 1
CRITICAL = 2
LB_STATE = {
    ("ONLINE", "ACTIVE"): HEALTHY,
    ("ONLINE", "DELETED"): CRITICAL,
    ("ONLINE", "ERROR"): CRITICAL,
    ("ONLINE", "PENDING_CREATE"): WARNING,
    ("ONLINE", "PENDING_UPDATE"): WARNING,
    ("ONLINE", "PENDING_DELETE"): WARNING,
    ("DRAINING", "ACTIVE"): WARNING,
    ("DRAINING", "DELETED"): CRITICAL,
    ("DRAINING", "ERROR"): CRITICAL,
    ("DRAINING", "PENDING_CREATE"): CRITICAL,
    ("DRAINING", "PENDING_UPDATE"): CRITICAL,
    ("DRAINING", "PENDING_DELETE"): CRITICAL,
    ("OFFLINE", "ACTIVE"): HEALTHY,
    ("OFFLINE", "DELETED"): CRITICAL,
    ("OFFLINE", "ERROR"): CRITICAL,
    ("OFFLINE", "PENDING_CREATE"): WARNING,
    ("OFFLINE", "PENDING_UPDATE"): WARNING,
    ("OFFLINE", "PENDING_DELETE"): WARNING,
    ("DEGRADED", "ACTIVE"): CRITICAL,
    ("DEGRADED", "DELETED"): CRITICAL,
    ("DEGRADED", "ERROR"): CRITICAL,
    ("DEGRADED", "PENDING_CREATE"): CRITICAL,
    ("DEGRADED", "PENDING_UPDATE"): CRITICAL,
    ("DEGRADED", "PENDING_DELETE"): CRITICAL,
    ("ERROR", "ACTIVE"): CRITICAL,
    ("ERROR", "DELETED"): CRITICAL,
    ("ERROR", "ERROR"): CRITICAL,
    ("ERROR", "PENDING_CREATE"): CRITICAL,
    ("ERROR", "PENDING_UPDATE"): CRITICAL,
    ("ERROR", "PENDING_DELETE"): CRITICAL,
    ("NO_MONITOR", "ACTIVE"): CRITICAL,
    ("NO_MONITOR", "DELETED"): CRITICAL,
    ("NO_MONITOR", "ERROR"): CRITICAL,
    ("NO_MONITOR", "PENDING_CREATE"): CRITICAL,
    ("NO_MONITOR", "PENDING_UPDATE"): CRITICAL,
    ("NO_MONITOR", "PENDING_DELETE"): CRITICAL,
}


def _parse_arguments():
    """Parse the check arguments and credentials to OpenStack.
    :returns: credentials, set IDs,
    :rtype: Tuple[configparser.ConfigParser, set]
    """
    credentials = ConfigParser()
    parser = argparse.ArgumentParser("check_openstack_loadbalancer")
    parser.add_argument(
        "-c", "--credential", required=True, type=argparse.FileType("r"),
        help="path to OpenStack credential cnf file")
    parser.add_argument(
        "-n", "--name", required=True, action="append", type=str,
        help="check specific name (can be used multiple times)")
    args = parser.parse_args()
    credentials.read_file(args.credential)

    return credentials, set(args.name)


def _healthy(lb):
    """Check if load balancer is healthy."""
    return LB_STATE.get(
        (lb.operating_status, lb.provisioning_status)) == HEALTHY


def _warning(lb):
    """Check if load balancer is in warning state."""
    return LB_STATE.get(
        (lb.operating_status, lb.provisioning_status)) == WARNING


def _unhealthy(lb):
    """Check if load balancer is unhealthy."""
    return LB_STATE.get(
        (lb.operating_status, lb.provisioning_status)) == CRITICAL


def _check_output(critical, notfound, warning, unknown, healthy):
    """Process check output."""
    total = len(healthy.union(critical, notfound, warning, unknown))
    error = None
    message = "OK: healthy LBs [{}] ({}/{})".format(
        SEPARATOR.join(healthy), len(healthy), total)

    if unknown:
        error = UnknownError
        message = "UNKNOWN: LBs [{}] ({}/{}){}{}".format(
            SEPARATOR.join(unknown), len(unknown), total, os.linesep, message)

    if warning:
        error = WarnError
        message = "WARNING: LBs [{}] ({}/{}){}{}".format(
            SEPARATOR.join(warning), len(warning), total, os.linesep, message)

    if notfound.union(critical):
        error = CriticalError
        msg_notfound = "LBs not found [{}] ({}/{})".format(
            SEPARATOR.join(notfound), len(notfound), total)
        msg_critical = "critical [{}] ({}/{})".format(
            SEPARATOR.join(critical), len(critical), total)
        message = "CRITICAL: {}, {}{}{}".format(
            msg_notfound, msg_critical, os.linesep, message)

    if error:
        raise error(message)

    print(message)


def check(credentials, names):
    """Check OpenStack loadbalancer.

    :param credentials: OpenStack credentials
    :type credentials: configparser.ConfigParser
    :param names: OpenStack loadbalancer names that will be checked
    :type names: Set[str]
    :raise nagios_plugin3.CriticalError: if loadbalancer not found
    :raise nagios_plugin3.CriticalError: if loadbalancer is in critical state
    :raise nagios_plugin3.WarnError: if loadbalancer is in warning state
    :raise nagios_plugin3.UnknownError: if loadbalancer is in unknown state
    """
    critical, notfound, warning, unknown, healthy = (set(), set(), set(),
                                                     set(), set())
    connection = openstack.connect(**credentials["openstack"])
    for name in names:
        lb = connection.load_balancer.find_load_balancer(name_or_id=name)
        if lb is None:  # LB was not found
            notfound.add(name)
            continue

        lb_name = "{}[{},{}]".format(name, lb.operating_status,
                                     lb.provisioning_status)

        if _healthy(lb):  # LB is in healthy state
            healthy.add(lb_name)
        elif _warning(lb):  # LB is in warning state
            warning.add(lb_name)
        elif _unhealthy(lb):  # LB is in unhealthy state
            critical.add(lb_name)
        else:  # LB is in unknown state
            unknown.add(lb_name)

    _check_output(critical, notfound, warning, unknown, healthy)


def main():
    credentials, names = _parse_arguments()
    try_check(check, credentials, names)


if __name__ == "__main__":
    main()
