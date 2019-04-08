from time import sleep
from pathlib import Path

from ruamel.yaml import YAML


def test_empty_db(client):
    """Test blank database."""

    rv = client.get('/')
    assert b'No tasks to show' in rv.data


def test_submit(client):
    # Note: client has to be passed to this test to setup the flask app correctly

    # Need to be in a flask app context before importing those:
    from hypertrainer.experimentmanager import experiment_manager
    from hypertrainer.task import Task
    from hypertrainer.utils import TaskStatus

    yaml = YAML()

    # 1. Launch task
    experiment_manager.submit(script_file='test.py', config_file='test.yaml', platform='local')

    # 2. Wait for it to finish, then get tasks
    sleep(2)
    tasks = experiment_manager.get_all_tasks(do_update=True)
    assert len(tasks) == 3, 'There should be 3 tasks'

    # 3. Check stuff on each task
    p_exp10_values, p_exp2_values, p_lin_values = set(), set(), set()
    orig_yaml = yaml.load(Path('test.yaml'))
    for t in tasks:  # type: Task
        # Check that yaml has been written correctly
        deep_assert_equal(t.config, orig_yaml, exclude_keys=['output_path', 'is_child', 'dummy_param_exp10',
                                                             'dummy_param_exp2', 'dummy_param_lin'])

        # Check output
        t.monitor()
        assert t.logs['err'].strip() == 'printing to stderr'
        assert t.logs['out'].strip() == 'printing to stdout'

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


def deep_assert_equal(a, b, exclude_keys):
    """For asserting partial equality between yaml config objects"""

    if isinstance(a, dict):
        keys = set(a.keys()).union(set(b.keys()))
        for k in keys:
            if k in exclude_keys:
                continue
            else:
                assert k in a
                assert k in b
            deep_assert_equal(a[k], b[k], exclude_keys)
    elif isinstance(a, list):
        assert len(a) == len(b)
        for i in range(len(a)):
            deep_assert_equal(a[i], b[i], exclude_keys)
    else:
        assert a == b
