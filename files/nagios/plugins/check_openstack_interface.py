#!/usr/bin/env python3

# Copyright (C) 2021 Canonical Ltd.

# Authors:
#   Robert Gildein <robert.gildein@canonical.com>

import argparse
import os
from configparser import ConfigParser

import openstack
from nagios_plugin3 import try_check, UnknownError, CriticalError

SEPARATOR = ","
ACTIVE = "ACTIVE"
DOWN = "DOWN"
INTERFACE = {
    "network": "network.networks",
    "floating-ip": "network.ips",
    "server": "compute.servers",
    "port": "network.ports",
    "security-group": "network.security_groups",
    "subnet": "network.subnets",
}
INTERFACE_BY_EXISTENCE = ["security-group", "subnet"]


def _rgetattr(obj, *attrs):
    if len(attrs) == 0:
        return obj

    return _rgetattr(getattr(obj, attrs[0]), *attrs[1:])


def _parse_arguments():
    """Parse the check arguments and connect to OpenStack.

    :returns: credentials, interface name, set IDs,
              set IDs to skip, values to filter when using `--all`
              and check all flag
    :rtype: Tuple[configparser.ConfigParser, str, set, set, dict, bool]
    """
    credentials = ConfigParser()
    parser = argparse.ArgumentParser("check_openstack_interface")
    parser.add_argument("interface", type=str, choices=INTERFACE.keys(),
                        help="interface name")
    parser.add_argument("-c", "--credential", required=True,
                        type=lambda path: credentials.read_file(
                            argparse.FileType("r")(path)),
                        help="path to OpenStack credential cnf file")
    group = parser.add_mutually_exclusive_group(required=True)
    # section for argument -i/--id
    group.add_argument("-i", "--id", action="append", type=str, default=[],
                       help="check specific id (can be used multiple times)")

    # section for argument --all
    group.add_argument("--all", action="store_true", help="check all")
    parser.add_argument("--skip-id", action="append", type=str, default=[],
                        help="skip specific id (can be used multiple times)")

    parser.add_argument("--select", action="append", type=str, default=[],
                        help="use `--select` together with `--all` "
                             "(e.g. --select subnet=<id>) "
                             "(can be used multiple times)")

    args = parser.parse_args()

    if args.all and args.interface in INTERFACE_BY_EXISTENCE:
        parser.error("flag `--all` is not supported with "
                     "interface {}".format(args.interface))
    elif not args.all and args.skip_id:
        parser.error("`--skip-id` must be used with `--all`")
    elif not args.all and args.select:
        parser.error("`--select` must be used with `--all`")

    return (credentials, args.interface, set(args.id), set(args.skip_id),
            dict(arg.split("=", 1) for arg in args.select), args.all)


def _check_output(interface, critical, notfound, unknown, healthy):
    """Process check output."""
    total = len(healthy.union(critical, notfound, unknown))
    error = None
    message = "OK: healthy {}s [{}] ({}/{})".format(
        interface, SEPARATOR.join(healthy), len(healthy), total)

    if unknown:
        error = UnknownError
        message = "UNKNOWN: {}s [{}] ({}/{}){}{}".format(
            interface, SEPARATOR.join(unknown), len(unknown), total,
            os.linesep, message)

    if notfound.union(critical):
        error = CriticalError
        msg_notfound = "{}s not found [{}] ({}/{})".format(
            interface, SEPARATOR.join(notfound), len(notfound), total)
        msg_critical = "unhealthy {}s [{}] ({}/{})".format(
            interface, SEPARATOR.join(critical), len(critical), total)
        message = "CRITICAL: {}, {}{}{}".format(
            msg_notfound, msg_critical, os.linesep, message)

    if error:
        raise error(message)

    print(message)


def _check_interface(name, interfaces, ids):
    """Check OpenStack interface existence.

    :param name: OpenStack interface name
    :type name: str
    :param interfaces: dictionary of OpenStack interfaces
    :type interfaces: Dict[str, Any]
    :param ids: list of OpenStack interface IDs/names that will be checked
    :type ids: Set[str]
    :raise nagios_plugin3.CriticalError: if interface not found
    :raise nagios_plugin3.UnknownError: if interface status is not valid
    :raise nagios_plugin3.CriticalError: if interface status is DOWN
    """
    critical, notfound, unknown, healthy = set(), set(), set(), set()

    for id_ in ids:
        interface = interfaces.get(id_)

        if not interface:
            notfound.add(id_)
        elif hasattr(interface, "status"):
            if interface.status == ACTIVE:
                healthy.add(id_)
            elif interface.status == DOWN:
                critical.add(id_)
            else:
                unknown.add(id_)
        else:
            healthy.add(id_)

    _check_output(name, critical, notfound, unknown, healthy)


def _interface_filter(interface, skip, select):
    """Apply `--skip` and `--select` parameter to interface.

    :param interface: OpenStack interface, e.g. network, port, ...
    :type: Any
    :param skip: OpenStack interface IDs that will be skipped [None]
    :type skip: Set[str]
    :param select: values for OpenStack interfaces filtering [None]
    :type select: Dict[str, str]
    :returns: a Boolean value to identify whether this interface is used
    :rtype: bool
    """
    if interface.id in (skip or {}):
        return False

    for key, value in (select or {}).items():
        if getattr(interface, key, None) != value:
            return False

    return True


def check(credentials, name, ids, skip=None, select=None, check_all=False):
    """Check OpenStack interface.

    :param credentials: OpenStack credentials
    :type credentials: configparser.ConfigParser
    :param name: OpenStack interface name
    :type name: str
    :param ids: OpenStack interface IDs that will be check
    :type ids: Set[str]
    :param skip: OpenStack interface IDs that will be skipped [None]
    :type skip: Set[str]
    :param select: values for OpenStack interfaces filtering [None]
    :type select: Dict[str, str]
    :param check_all: flag to checking all OpenStack interfaces [False]
    :type check_all: bool
    :raise nagios_plugin3.CriticalError: if interface not found
    :raise nagios_plugin3.UnknownError: if interface status is not valid
    :raise nagios_plugin3.CriticalError: if interface status is DOWN
    """
    connection = openstack.connect(**credentials["openstack"])
    interfaces = {i.id: i for i in _rgetattr(connection,
                                             *INTERFACE[name].split("."))()}
    if check_all:
        ids = {i.id for i in interfaces.values()
               if _interface_filter(i, skip, select)}

    _check_interface(name, interfaces, ids)


def main():
    args = _parse_arguments()
    try_check(check, *args)


if __name__ == "__main__":
    main()
