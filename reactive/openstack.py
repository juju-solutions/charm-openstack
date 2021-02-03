from distutils.util import strtobool
from charmhelpers.core import hookenv
from charmhelpers.contrib.charmsupport import nrpe
from charms.reactive import (
    hook,
    when,
    when_all,
    when_any,
    when_not,
    is_flag_set,
    toggle_flag,
    clear_flag,
    set_flag,
)

from charms.reactive.relations import endpoint_from_name

import nrpe_helpers

from charms import layer


@when_all('snap.installed.openstackclients')
def set_app_ver():
    version = layer.snap.get_installed_version('openstackclients')
    hookenv.application_version_set(version)


@when_any('config.changed.credentials',
          'config.changed.auth-url',
          'config.changed.username',
          'config.changed.password',
          'config.changed.project-name',
          'config.changed.user-domain-name',
          'config.changed.project-domain-name',
          'config.changed.region',
          'config.changed.endpoint-tls-ca')
def update_creds():
    clear_flag('charm.openstack.creds.set')


@hook('upgrade-charm')
def upgrade_charm():
    # when the charm is upgraded, recheck the creds in case anything
    # has changed or we want to handle any of the fields differently
    clear_flag('charm.openstack.creds.set')


@hook('pre-series-upgrade')
def pre_series_upgrade():
    layer.status.blocked('Series upgrade in progress')


@when_not('charm.openstack.creds.set')
def get_creds():
    toggle_flag('charm.openstack.creds.set', layer.openstack.get_credentials())


@when_all('snap.installed.openstackclients',
          'charm.openstack.creds.set')
@when_not('endpoint.clients.requests-pending')
@when_not('upgrade.series.in-progress')
def no_requests():
    layer.status.active('Ready')


@when_all('snap.installed.openstackclients',
          'charm.openstack.creds.set',
          'endpoint.clients.joined')
@when_any('endpoint.clients.requests-pending',
          'config.changed')
@when_not('upgrade.series.in-progress')
def handle_requests():
    layer.status.maintenance('Granting integration requests')
    clients = endpoint_from_name('clients')
    config_change = is_flag_set('config.changed')
    config = hookenv.config()
    has_octavia = layer.openstack.detect_octavia()
    try:
        manage_security_groups = strtobool(config['manage-security-groups'])
        # use bool() to force True / False instead of 1 / 0
        manage_security_groups = bool(manage_security_groups)
    except ValueError:
        layer.status.blocked('Invalid value for manage-security-groups config')
        return
    except AttributeError:
        # in case manage_security_groups is already bool
        manage_security_groups = config['manage-security-groups']
    requests = clients.all_requests if config_change else clients.new_requests
    for request in requests:
        layer.status.maintenance(
            'Granting request for {}'.format(request.unit_name))
        creds = layer.openstack.get_user_credentials()
        request.set_credentials(**creds)
        request.set_lbaas_config(config['subnet-id'],
                                 config['floating-network-id'],
                                 config['lb-method'],
                                 manage_security_groups,
                                 has_octavia)

        def _or_none(val):
            if val in (None, '', 'null'):
                return None
            else:
                return val
        request.set_block_storage_config(
            _or_none(config.get('bs-version')),
            _or_none(config.get('trust-device-path')),
            _or_none(config.get('ignore-volume-az')))
        layer.openstack.log('Finished request for {}', request.unit_name)
    clients.mark_completed()


@when_all('charm.openstack.creds.set',
          'credentials.connected')
@when_not('upgrade.series.in-progress')
def write_credentials():
    credentials = endpoint_from_name('credentials')
    reformatted_creds = layer.openstack.get_creds_and_reformat()
    credentials.expose_credentials(reformatted_creds)


@when_all('charm.openstack.creds.set',
          'endpoint.loadbalancer.joined')
@when_not('upgrade.series.in-progress')
def create_or_update_loadbalancers():
    layer.status.maintenance('Managing load balancers')
    lb_clients = endpoint_from_name('loadbalancer')
    try:
        for request in lb_clients.requests:
            if not request.members:
                continue
            lb = layer.openstack.manage_loadbalancer(request.application_name,
                                                     request.members)
            request.set_address_port(lb.fip or lb.address, lb.port)
    except layer.openstack.OpenStackError as e:
        layer.status.blocked(str(e))


@hook('stop')
def cleanup():
    # TODO: Also clean up removed LBs as they go away
    layer.openstack.cleanup()


@when("nrpe-external-master.available")
@when_not("nrpe-external-master.initial-config")
def initial_nrpe_config():
    set_flag("nrpe-external-master.initial-config")
    update_nrpe_config()


@when("nrpe-external-master.available")
@when_any("config.changed.nagios_context",
          "config.changed.nagios_servicegroups",
          "nrpe-external-master.reconfigure",
          *nrpe_helpers.NRPE_CONFIG_FLAGS_CHANGED)
def update_nrpe_config():
    """Set up all NRPE checks."""
    config = hookenv.config()
    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    layer.openstack.write_nagios_openstack_cnf()
    layer.nagios.install_nagios_plugin_from_file(
        "files/nagios/plugins/check_openstack_interface.py",
        nrpe_helpers.NRPE_OPENSTACK_INTERFACE)

    for check in nrpe_helpers.NRPE_CHECKS:
        cmd = layer.openstack.create_nrpe_check_cmd(check)
        if ((config.changed(check.config) or config.changed(check.config_skip))
                and config.get(check.config)):
            nrpe_setup.add_check(
                shortname=check.name,
                description="Check {}s: {}".format(check.interface,
                                                   config.get(check.config)),
                check_cmd=cmd)
            hookenv.log("NRPE check {} was added".format(check.name),
                        level=hookenv.DEBUG)
        elif config.changed(check.config) and not config.get(check.config):
            nrpe_setup.remove_check(shortname=check.name, description="",
                                    check_cmd=cmd)
            hookenv.log("NRPE check {} was removed".format(check.name),
                        level=hookenv.DEBUG)

    nrpe_setup.write()
    hookenv.log("NRPE checks were updated.", level=hookenv.DEBUG)


@when_not("nrpe-external-master.available")
@when("nrpe-external-master.initial-config")
def remove_nrpe_config():
    """Remove all NRPE checks and related scripts."""
    config = hookenv.config()
    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname)

    for check in nrpe_helpers.NRPE_CHECKS:
        cmd = layer.openstack.create_nrpe_check_cmd(check)

        if config.get(check.config):
            nrpe_setup.remove_check(
                shortname=check.name,
                description="",
                chech_cmd=cmd
            )
            hookenv.log("NRPE check {} was removed".format(check.name),
                        level=hookenv.DEBUG)

    nrpe_setup.write()
    layer.nagios.remove_nagios_plugin(nrpe_helpers.NRPE_OPENSTACK_INTERFACE)
    layer.openstack.remove_nagios_openstack_cnf()
    hookenv.log("NRPE checks was removed.", level=hookenv.DEBUG)
