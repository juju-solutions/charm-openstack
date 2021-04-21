import pytest

import nrpe_helpers

from charmhelpers.core.hookenv import config


@pytest.mark.parametrize("ids,skip_ids,check_all,exp_cmd", [
    ("1,2", "", False, "--id 1 --id 2"),
    ("all", "1,2", True, "--all --skip-id 1 --skip-id 2"),
    ("all", "1,2", True, "--all --skip-id 1 --skip-id 2"),
])
def test_create_nrpe_check_cmd(ids, skip_ids, check_all, exp_cmd):
    """Test creating cmd for NRPE check."""
    config.return_value = {
        "nrpe_check_cmd-ids": ids, "nrpe_check_cmd-skip-ids": skip_ids,
    }
    check = nrpe_helpers.NrpeCheck("test", "test", "nrpe_check_cmd-ids",
                                   "nrpe_check_cmd-skip-ids", check_all)

    cmd = nrpe_helpers.create_nrpe_check_cmd(check)

    assert exp_cmd in cmd


@pytest.mark.parametrize("ids,skip_ids,check_all", [
    ("all", "", False),
    ("1,2", "1", True),
])
def test_create_nrpe_check_cmd_error(ids, skip_ids, check_all):
    """Test creating cmd for NRPE check."""
    config.return_value = {
        "nrpe_check_cmd-ids": ids, "nrpe_check_cmd-skip-ids": skip_ids,
    }
    check = nrpe_helpers.NrpeCheck("test", "test", "nrpe_check_cmd-ids",
                                   "nrpe_check_cmd-skip-ids", check_all)

    with pytest.raises(ValueError):
        nrpe_helpers.create_nrpe_check_cmd(check)
