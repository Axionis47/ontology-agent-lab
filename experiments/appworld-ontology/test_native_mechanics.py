import pytest
"""Not-a-model integration check. No agent, model or application-effect API calls."""
import json
from core import configure_world
from contracts import runtime_code
from test_contracts import candidate


@pytest.mark.native
def test_function_ledger_survives_later_native_execution_exception():
    configure_world()
    from appworld import AppWorld
    with AppWorld.initializer(update_defaults=True,experiment_name='OWB01/mechanics-check',
                              load_ground_truth=False,random_seed=0):
        with AppWorld(task_id='22cc237_1') as world:
            installed=world.execute(runtime_code(candidate()))
            assert 'Error' not in installed and 'Traceback' not in installed
            result=world.execute("onto_records([{'type':'Record','properties':{'id':'one'}}]); raise ValueError('intentional instrumentation check')")
            assert 'intentional instrumentation check' in result
            captured=world.execute("print('LEDGER:' + json.dumps(_owb_function_calls))")
            packet=json.loads(next(line.removeprefix('LEDGER:') for line in captured.splitlines() if line.startswith('LEDGER:')))
            assert packet[0]['name']=='onto_records'
            assert packet[0]['result']==[{'id':'one'}]
