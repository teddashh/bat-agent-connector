"""A10 / B02: historical observations preserve creation evidence after host removal."""
import time

import pytest

from bat_agent_connector import confinement
from bat_agent_connector.inventory import Inventory
from bat_agent_connector.task_journal import Journal


@pytest.mark.parametrize('legacy', [False, True])
async def test_removed_host_keeps_history_without_claiming_current_confinement(fleet_factory, tmp_path, legacy):
    fleet = fleet_factory()
    journal = Journal(tmp_path / 'history.db')
    inventory = Inventory(journal, fleet.config)
    creation = confinement.snapshot('claude', {'permissionMode': 'acceptEdits'},
                                   account={'status': 'verified', 'protected_roots': ['/fixture/protected']})
    row = {'session_id': 'historical', 'loaded': True}
    if not legacy:
        row.update(confinement=creation, current_verification={'status': 'verified'})
    try:
        inventory._record_success('h1', time.time(), [row], 'fixture')
        fleet.config.hosts.pop('h1')
        result = inventory.session_document('h1', 'historical')['session']
        assert result['scope_status'] == 'outside_current_config'
        assert result['current_verification']['status'] == 'unknown'
        if not legacy:
            assert result['confinement'] == creation
            assert result['current_verification']['host_check']['reason'] == 'host_not_configured'
        assert inventory.observation.history('session', 'h1/historical')['events']
    finally:
        await inventory.close()
        await fleet.close()
        journal.close()
