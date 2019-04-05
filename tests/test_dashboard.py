import os
import tempfile
from time import sleep


def test_empty_db(client):
    """Start with a blank database."""

    rv = client.get('/')
    assert b'No tasks to show' in rv.data


def test_submit(client):
    from hypertrainer.experimentmanager import experiment_manager
    from hypertrainer.task import Task
    from hypertrainer.utils import TaskStatus

    # 1. Launch task
    experiment_manager.submit(script_file='test.py', config_file='test.yaml', platform='local')

    # 2. Wait for it to finish, then get tasks
    sleep(2)
    tasks = experiment_manager.get_all_tasks(do_update=True)
    assert len(tasks) == 3, 'There should be 3 tasks'

    # 3. Check stuff on each task
    p_exp10_values, p_exp2_values, p_lin_values = set(), set(), set()
    for t in tasks:  # type: Task
        # TODO check that yaml matches original

        # Check status
        assert t.status == TaskStatus.Finished, 'Status must be: Finished'

        # Check hyperparam search
        p_exp10 = t.config['training']['dummy_param_exp10']
        p_exp2 = t.config['training']['dummy_param_exp2']
        p_lin = t.config['training']['dummy_param_lin']

        assert p_exp10 not in p_exp10_values, 'Hyperparam value must be unique'
        assert p_exp2 not in p_exp2_values, 'Hyperparam value must be unique'
        assert p_lin not in p_lin_values, 'Hyperparam value must be unique'
        p_exp10_values.add(p_exp10)
        p_exp2_values.add(p_exp2)
        p_lin_values.add(p_lin)

        assert 10 ** -2 <= p_exp10 <= 10 ** 2, 'Hyperparameter values must be in range'
        assert 2 ** -2 <= p_exp2 <= 2 ** 2, 'Hyperparameter values must be in range'
        assert -2 <= p_lin <= 2, 'Hyperparameter values must be in range'

        # Check output
        t.monitor()
        assert t.logs['out'].strip() == 'printing to stdout'
        assert t.logs['err'].strip() == 'printing to stderr'


# def deep_equal(a, b, exclude_keys):
#     if issubclass(a, dict) or isinstance(a, list):
#         for k in a:
#             if k in exclude_keys:
#                 continue
#             deep_equal(a[k], b[k], exclude_keys)
#     else:
#         if a != b:
#             return False
#     return True
#
#
# yaml = YAML()
#     input_yaml = yaml.load(Path(sys.argv[1]))
#     orig_yaml = yaml.load(Path('test.yaml'))
#     assert deep_equal(input_yaml, orig_yaml, exclude_keys=['output_path', 'is_child', 'dummy_param_exp10',
#                                                            'dummy_param_exp2', 'dummy_param_lin'])
