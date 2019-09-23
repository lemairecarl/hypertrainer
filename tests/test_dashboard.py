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
    experiment_manager.submit(script_file='script_test_submit.py', config_file='test_submit.yaml', platform='local')

    # 2. Wait for it to finish, then get tasks
    sleep(2)
    tasks = experiment_manager.get_all_tasks(do_update=True)
    assert len(tasks) == 3

    # 3. Check stuff on each task
    p_exp10_values, p_exp2_values, p_lin_values = set(), set(), set()
    orig_yaml = yaml.load(Path('scripts/test_submit.yaml'))
    for t in tasks:  # type: Task
        # Check that yaml has been written correctly
        deep_assert_equal(t.config, orig_yaml, exclude_keys=['output_path', 'is_child', 'dummy_param_exp10',
                                                             'dummy_param_exp2', 'dummy_param_lin'])

        # Check output
        experiment_manager.monitor(t)
        assert t.logs['err'].strip() == 'printing to stderr'
        assert t.logs['out'].strip() == 'printing to stdout'

        # Check status
        assert t.status == TaskStatus.Finished

        # Check hyperparam search
        p_exp10 = t.config['training']['dummy_param_exp10']
        p_exp2 = t.config['training']['dummy_param_exp2']
        p_lin = t.config['training']['dummy_param_lin']

        # Hyperparam value must be unique
        assert p_exp10 not in p_exp10_values
        assert p_exp2 not in p_exp2_values
        assert p_lin not in p_lin_values
        p_exp10_values.add(p_exp10)
        p_exp2_values.add(p_exp2)
        p_lin_values.add(p_lin)

        # Hyperparameter values must be in range
        assert 10 ** -2 <= p_exp10 <= 10 ** 2
        assert 2 ** -2 <= p_exp2 <= 2 ** 2
        assert -2 <= p_lin <= 2


def test_continue(client):
    # Note: client has to be passed to this test to setup the flask app correctly

    # Need to be in a flask app context before importing those:
    from hypertrainer.experimentmanager import experiment_manager
    from hypertrainer.task import Task
    from hypertrainer.utils import TaskStatus

    experiment_manager.submit(script_file='script_test_continue.py', config_file='test_continue.yaml', platform='local')
    sleep(1)

    tasks = experiment_manager.get_all_tasks(do_update=True)
    assert len(tasks) == 1
    t = tasks[0]  # type: Task
    assert t.status == TaskStatus.Finished

    t.continu()
    sleep(1)

    tasks = experiment_manager.get_all_tasks(do_update=True)
    assert len(tasks) == 1
    t = tasks[0]  # type: Task
    assert t.status == TaskStatus.Finished
    # Check that there is exactly two X; one for initial submission, one for continue
    assert (Path(t.output_path) / 'i_was_here.txt').read_text().strip() == 'XX'


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
