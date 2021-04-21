#!/usr/bin/env python3

# Copyright (C) 2021 Canonical Ltd.

# Authors:
#   Robert Gildein <robert.gildein@canonical.com>

import argparse
from configparser import ConfigParser

import openstack
from nagios_plugin3 import try_check, UnknownError, CriticalError

SEPARATOR = ","
ACTIVE = "ACTIVE"
DOWN = "DOWN"
VALID_STATUS = [ACTIVE, DOWN]
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
    parser.add_argument("interface", type=str, help="interface name")
    parser.add_argument("-c", "--credential", required=True,
                        type=argparse.FileType("r"),
                        help="path to OpenStack credential cnf file")
    parser.add_argument("--all", action="store_true", help="check all")
    parser.add_argument("-i", "--id", action="append", type=str, default=[],
                        help="check specific id (can be used multiple times)")
    parser.add_argument("--skip-id", action="append", type=str, default=[],
                        help="skip specific id (can be used multiple times)")
    parser.add_argument("--select", action="append", type=str, default=[],
                        help="use `--select` together with `--all` "
                             "(e.g. --select subnet=<id>) "
                             "(can be used multiple times)")
    args = parser.parse_args()

    if args.interface not in INTERFACE:
        parser.error("`{}` interface is not supported".format(args.interface))

    if args.all and args.interface in INTERFACE_BY_EXISTENCE:
        parser.error("flag `--all` is not supported with "
                     "interface {}".format(args.interface))
    if args.all and args.id:
        parser.error("`--all` and `--id` can't be given together")
    elif not args.all and not args.id:
        parser.error("at least one of '--all/--id' parameters must be entered")
    elif not args.all and args.skip_id:
        parser.error("`--skip-id` must be used with `--all`")
    elif not args.all and args.select:
        parser.error("`--select` must be used with `--all`")

    credentials.read_file(args.credential)

    return (credentials, args.interface, set(args.id), set(args.skip_id),
            dict(arg.split("=", 1) for arg in args.select), args.all)


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
    down, unknown, notfound = [], [], []

    for id_ in ids:
        interface = interfaces.get(id_)

        if not interface:
            notfound.append(id_)
        elif hasattr(interface, "status"):
            if interface.status == DOWN:
                down.append(id_)
            elif interface.status not in VALID_STATUS:
                unknown.append(id_)

    if notfound:
        raise CriticalError("{}s \"{}\" not found ({}/{})".format(
            name, SEPARATOR.join(notfound), len(notfound), len(ids)))

    if unknown:
        raise UnknownError("{}s \"{}\" have unknown status ({}/{})".format(
            name, SEPARATOR.join(unknown), len(unknown), len(ids)))

    if down:
        raise CriticalError("{}s \"{}\" are DOWN ({}/{})".format(
            name, SEPARATOR.join(down), len(down), len(ids)))


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
    print("OK - All {}s passed. ({}/{}) IDs: {}".format(
        name, len(ids), len(interfaces), SEPARATOR.join(ids)))


def main():
    args = _parse_arguments()
    try_check(check, *args)


if __name__ == "__main__":
    main()
