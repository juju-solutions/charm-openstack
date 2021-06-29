import logging

import pytest


log = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test):
    """Build and deploy openstack-integrator in bundle"""
    openstack_integrator = await ops_test.build_charm(".")
    bundle = ops_test.render_bundle(
        "tests/data/bundle.yaml", master_charm=openstack_integrator, series="focal"
    )
    await ops_test.model.deploy(bundle, trust=True)
    await ops_test.model.wait_for_idle(wait_for_active=True, timeout=60 * 60)


async def test_status_messages(ops_test):
    """Validate that the status messages are correct."""
    expected_messages = {
        "kubernetes-master": "Kubernetes master running.",
        "kubernetes-worker": "Kubernetes worker running.",
        "openstack-integrator": "Ready",
    }
    for app, message in expected_messages.items():
        for unit in ops_test.model.applications[app].units:
            assert unit.workload_status_message == message
