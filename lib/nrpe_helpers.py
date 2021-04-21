import collections
import os

from charmhelpers.core import hookenv
from charmhelpers.core.templating import render
from charms.layer.nagios import NAGIOS_PLUGINS_DIR
from charms.layer.openstack import get_creds_env, get_user_credentials


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
NRPE_CONFIG_FLAGS_CHANGED = [
    *["config.changed.{}".format(c.config) for c in NRPE_CHECKS],
    *["config.changed.{}".format(c.config_skip) for c in NRPE_CHECKS
      if c.config_skip]
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
