from unittest.mock import patch

import charms.unit_test

from charms.unit_test import patch_fixture


charms.unit_test.patch_reactive()
charms.unit_test.patch_module('subprocess')
charms.unit_test.patch_module('urllib.request')
charms.unit_test.patch_module('charms.leadership')
patch('time.sleep').start()


log_err = patch_fixture('charms.layer.openstack.log_err')
_load_creds = patch_fixture('charms.layer.openstack._load_creds')
detect_octavia = patch_fixture('charms.layer.openstack.detect_octavia')
_run_with_creds = patch_fixture('charms.layer.openstack._run_with_creds')
_openstack = patch_fixture('charms.layer.openstack._openstack')
_neutron = patch_fixture('charms.layer.openstack._neutron')
LoadBalancerClient = patch_fixture('charms.layer.openstack.LoadBalancerClient')
OctaviaLBClient = patch_fixture('charms.layer.openstack.OctaviaLBClient')
NeutronLBClient = patch_fixture('charms.layer.openstack.NeutronLBClient')
_default_subnet = patch_fixture('charms.layer.openstack._default_subnet')
kv = patch_fixture('charms.layer.openstack.kv')
config = patch_fixture('charms.layer.openstack.config')
get_port_sec_enabled = patch_fixture('charms.layer.openstack.BaseLBImpl'
                                     '.get_port_sec_enabled',
                                     patch_opts={'return_value': True},
                                     fixture_opts={'autouse': True})
_normalize_creds = patch_fixture('charms.layer.openstack._normalize_creds')
_save_creds = patch_fixture('charms.layer.openstack._save_creds')
_determine_version = patch_fixture('charms.layer.openstack._determine_version')
