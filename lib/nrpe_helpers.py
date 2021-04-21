import collections
import os

from charmhelpers.core import hookenv
from charmhelpers.core.templating import render
from charms.layer.nagios import (
    NAGIOS_PLUGINS_DIR,
    install_nagios_plugin_from_file,
    remove_nagios_plugin,
)
from charms.layer.openstack import (
    get_all_loadbalancer,
    get_creds_env,
    get_user_credentials,
)


# NOTE (rgildein): This namedtuple is used to define NRPE check. Composed of:
#                  name - NRPE check shortname
#                  interface - OpenStack interface to be check
#                  config - option name defined in config.yaml
#                  config_skip - option name define in config.yaml
#                  all - if the option in config.yaml can be `all`
NrpeCheck = collections.namedtuple(
    "NRPE_CHECK", "name interface config config_skip all")

NRPE_CHECKS = [
    # check , OpenStack interface, check_all allowed, skip ids
    NrpeCheck("kubernetes_subnet", "subnet", "subnet-id", None, False),
    NrpeCheck("kubernetes_network", "network", "floating-network-id",
              None, False),
    NrpeCheck("openstack_networks", "network", "nrpe-network-ids",
              "nrpe-skip-network-ids", True),
    NrpeCheck("openstack_subnets", "subnet", "nrpe-subnet-ids", None, False),
    NrpeCheck("openstack_ports", "port", "nrpe-port-ids", "nrpe-skip-port-ids",
              True),
    NrpeCheck("openstack_floating_ips", "floating-ip", "nrpe-floating-ip-ids",
              "nrpe-skip-floating-ip-ids", True),
    NrpeCheck("openstack_servers", "server", "nrpe-server-ids",
              "nrpe-skip-server-ids", True),
    NrpeCheck("openstack_security_groups", "security-group",
              "nrpe-security-group-ids", None, False),
]
NRPE_OPENSTACK_INTERFACE = "check_openstack_interface.py"
NRPE_OPENSTACK_LOADBALANCER = "check_openstack_loadbalancer.py"
NRPE_CONFIG_FLAGS_CHANGED = [
    *["config.changed.{}".format(c.config) for c in NRPE_CHECKS],
    *["config.changed.{}".format(c.config_skip) for c in NRPE_CHECKS
      if c.config_skip],
    "loadbalancers.changed",
]
OPENSTACK_NAGIOS_CREDENTIAL_FILE = "/etc/nagios/openstack.cnf"


def write_nagios_openstack_cnf():
    """Create a OpenStack configuration file with nagios user credentials."""
    creds = get_user_credentials()
    env = get_creds_env(creds)
    render("nagios-openstack.cnf", OPENSTACK_NAGIOS_CREDENTIAL_FILE, env,
           owner="nagios", group="nagios", perms=0o640)
    return OPENSTACK_NAGIOS_CREDENTIAL_FILE


def remove_nagios_openstack_cnf():
    """Remove a OpenStack configuration file with nagios user credentials."""
    if os.path.exists(OPENSTACK_NAGIOS_CREDENTIAL_FILE):
        os.remove(OPENSTACK_NAGIOS_CREDENTIAL_FILE)


def create_nrpe_check_cmd(check):
    """Crete cmd command for checking OpenStack IDs.

    :param check: Definition NRPE check for OpenStack interface
    :type check: nrpe_helpers.NrpeCheck
    :returns: NRPE check CMD
    :rtype: string
    :raise ValueError: if the IDs is set to "all" and is not supported
                       if skip IDs are set, but without IDs set to "all"
    """
    config = hookenv.config()
    value_ids = config.get(check.config) or ""
    value_skip_ids = config.get(check.config_skip) or ""
    ids = [i for i in value_ids.split(",") if i]  # remove empty string
    skip_ids = [i for i in value_skip_ids.split(",") if i]
    script = os.path.join(NAGIOS_PLUGINS_DIR, NRPE_OPENSTACK_INTERFACE)
    cmd = "{} {} -c {}".format(
        script, check.interface, OPENSTACK_NAGIOS_CREDENTIAL_FILE)

    if "all" in ids:
        if not check.all:
            raise ValueError("value \"all\" is not supported with "
                             "\"{}\"".format(check.config))
        cmd += " --all"
        cmd += "".join([" --skip-id {}".format(i) for i in skip_ids])
    elif skip_ids:
        raise ValueError("\"{}\" option is not allowed with \"{}\" option "
                         "not set to \"all\"".format(check.config_skip,
                                                     check.config))
    else:
        cmd += "".join([" --id {}".format(i) for i in ids])

    return cmd


def _add_nrpe_check(nrpe_setup, name, description, cmd):
    """
    Help function to add NRPE check.

    :param nrpe_setup: NPRE object management checks
    :type nrpe_setup: charmhelpers.contrib.charmsupport.nrpe.NRPE
    :param name: short name of NRPE check
    :type name: str
    :param description: description of NRPE check
    :type description: str
    :param cmd: CMD of NRPE check
    :type cmd: str
    """
    nrpe_setup.add_check(
        shortname=name, description=description, check_cmd=cmd)
    hookenv.log("NRPE check {} was added.".format(name), level=hookenv.DEBUG)


def _remove_nrpe_check(nrpe_setup, name, cmd):
    """
    Help function to remove NRPE check.

    :param nrpe_setup: NPRE object management checks
    :type nrpe_setup: charmhelpers.contrib.charmsupport.nrpe.NRPE
    :param name: short name of NRPE check
    :type name: str
    :param cmd: CMD of NRPE check
    :type cmd: str
    """
    try:
        nrpe_setup.remove_check(shortname=name, description="", check_cmd=cmd)
        hookenv.log("NRPE check {} was removed.".format(name),
                    level=hookenv.DEBUG)
    except FileNotFoundError:
        hookenv.log("NRPE check {} was not found.".format(name),
                    level=hookenv.DEBUG)


def update_openstack_interface_check(nrpe_setup, initialized):
    """Update NRPE checks for OpenStack interfaces.

    :param nrpe_setup: NPRE object management checks
    :type nrpe_setup: charmhelpers.contrib.charmsupport.nrpe.NRPE
    :param initialized: flag if checks are initialized for the first time
    :type initialized: bool
    """
    config = hookenv.config()
    install_nagios_plugin_from_file(
        "files/nagios/plugins/check_openstack_interface.py",
        NRPE_OPENSTACK_INTERFACE)

    for check in NRPE_CHECKS:
        cmd = create_nrpe_check_cmd(check)
        if (config.get(check.config) and (config.changed(check.config) or
                                          config.changed(check.config_skip) or
                                          initialized)):
            description = "Check {}s: {} (skip: {})".format(
                check.interface, config.get(check.config) or "",
                config.get(check.config_skip) or "")
            _add_nrpe_check(nrpe_setup, check.name, description, cmd)
        elif not config.get(check.config) and config.changed(check.config):
            _remove_nrpe_check(nrpe_setup, check.name, cmd)

    nrpe_setup.write()


def remove_openstack_interface_check(nrpe_setup):
    """Remove NRPE checks for OpenStack interfaces.

    :param nrpe_setup: NPRE object management checks
    :type nrpe_setup: charmhelpers.contrib.charmsupport.nrpe.NRPE
    """
    config = hookenv.config()
    for check in NRPE_CHECKS:
        if config.get(check.config):
            cmd = create_nrpe_check_cmd(check)
            _remove_nrpe_check(nrpe_setup, check.name, cmd)

    nrpe_setup.write()
    remove_nagios_plugin(NRPE_OPENSTACK_INTERFACE)


def update_openstack_loadbalancer_check(nrpe_setup):
    """Update NRPE check for OpenStack loadbalancers.

    :param nrpe_setup: NRPE object management checks
    :type nrpe_setup: charmhelpers.contrib.charmsupport.nrpe.NRPE
    """
    install_nagios_plugin_from_file(
        "files/nagios/plugins/check_openstack_loadbalancer.py",
        NRPE_OPENSTACK_LOADBALANCER)

    script = os.path.join(NAGIOS_PLUGINS_DIR, NRPE_OPENSTACK_LOADBALANCER)
    cmd = "{} -c {}".format(script, OPENSTACK_NAGIOS_CREDENTIAL_FILE)

    lbs = get_all_loadbalancer()
    if not lbs:
        _remove_nrpe_check(nrpe_setup, "openstack_loadbalancers", cmd)
    else:
        cmd += "".join([" --name {}".format(lb_name) for lb_name in lbs])
        description = "Check loadbalancers: {}".format(",".join(lbs))
        _add_nrpe_check(nrpe_setup, "openstack_loadbalancers", description,
                        cmd)

    nrpe_setup.write()


def remove_openstack_loadbalancer_check(nrpe_setup):
    """Remove NRPE check for OpenStack loadbalancers.

    :param nrpe_setup: NRPE object management checks
    :type nrpe_setup: charmhelpers.contrib.charmsupport.nrpe.NRPE
    """
    script = os.path.join(NAGIOS_PLUGINS_DIR, NRPE_OPENSTACK_LOADBALANCER)
    cmd = "{} -c {}".format(script, OPENSTACK_NAGIOS_CREDENTIAL_FILE)

    _remove_nrpe_check(nrpe_setup, "openstack_loadbalancers", cmd)

    nrpe_setup.write()
    remove_nagios_plugin(NRPE_OPENSTACK_INTERFACE)
