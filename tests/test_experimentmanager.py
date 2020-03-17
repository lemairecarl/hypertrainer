from pathlib import Path
from time import sleep

import pytest

from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.db import init_db
from hypertrainer.experimentmanager import experiment_manager
from hypertrainer.htplatform import HtPlatform
from hypertrainer.task import Task
from hypertrainer.utils import TaskStatus, yaml
from hypertrainer.utils import deep_assert_equal
from worker import WorkerContext

SCRIPTS_PATH = '/home/carl/source/hypertrainer/tests/scripts'  # FIXME


def test_init_db():
    init_db()  # TODO side effect... put in fixture?
    Task.delete().execute()  # FIXME

    assert Task.select().count() == 0


def test_local_output_path():
    tasks = experiment_manager.create_tasks(
        config_file=SCRIPTS_PATH + '/simple.yaml',
        platform='local')
    task = tasks[0]

    assert 'output_root' in task.config

    assert Path(task.output_root).exists()

    output_path = task.output_path

    assert Path(output_path).exists()


def test_submit_local():
    # 1. Launch task
    tasks = experiment_manager.create_tasks(
        config_file=SCRIPTS_PATH + '/test_submit.yaml',
        platform='local')
    task_ids = [t.id for t in tasks]

    # 2. Check that the hp search configs were generated
    assert len(tasks) == 3

    # Wait task finished
    def check_finished():
        experiment_manager.update_tasks()
        status = Task.get(Task.id == tasks[2].id).status
        return status == TaskStatus.Finished
    wait_true(check_finished, interval_secs=2)

    # 3. Check stuff on each task
    p_exp10_values, p_exp2_values, p_lin_values = set(), set(), set()
    orig_yaml = yaml.load(Path(SCRIPTS_PATH) / 'test_submit.yaml')
    for t in Task.select().where(Task.id.in_(task_ids)):  # type: Task
        # Check that yaml has been written correctly
        # NOTE: THIS FAILS IN DEBUG MODE
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


def test_archive_task():
    from hypertrainer.experimentmanager import experiment_manager
    from hypertrainer.task import Task

    # 1. Submit local task
    tasks = experiment_manager.create_tasks(
        config_file=SCRIPTS_PATH + '/test_submit.yaml',
        platform='local')
    task_id = tasks[0].id

    # 2. Archive task
    experiment_manager.archive_tasks_by_id([task_id])

    # 3. Check that it still exists
    assert Task.select().where(Task.id == task_id).count() == 1

    # 4. Check that is_archived == True
    assert Task.get(Task.id == task_id).is_archived

    # 5. Check that it is absent from the non-archived list
    non_archived_tasks = experiment_manager.get_tasks()

    assert task_id not in [t.id for t in non_archived_tasks]

    # 6. Check that it is present in the archived list
    archived_tasks = experiment_manager.get_tasks(archived=True)
    assert task_id in [t.id for t in archived_tasks]


def test_delete_local_task():
    from hypertrainer.experimentmanager import experiment_manager
    from hypertrainer.task import Task

    def get_task_folder(task_id):
        return Path(Task.get(Task.id == task_id).output_path)

    # 1. Submit task
    tasks = experiment_manager.create_tasks(
        config_file=SCRIPTS_PATH + '/test_submit.yaml',
        platform='local')
    task_id = tasks[0].id
    # 1.1 Wait that the folder exist on disk
    wait_true(lambda: get_task_folder(task_id).exists())
    task_folder = get_task_folder(task_id)
    # 2. Try deleting task (fails since not archived yet)
    with pytest.raises(RuntimeError):
        experiment_manager.delete_tasks_by_id([task_id])
    # 3. Archive task
    experiment_manager.archive_tasks_by_id([task_id])
    assert Task.get(Task.id == task_id).is_archived
    # 4. Delete task
    experiment_manager.delete_tasks_by_id([task_id])
    # 5. Check that task does not exist in DB
    assert Task.select().where(Task.id == task_id).count() == 0
    # 6. Check that files on disk have been deleted
    wait_true(lambda: not task_folder.exists())


def test_submit_rq_task():
    with WorkerContext(hostname='localhost'):

        ht_platform = HtPlatform(['localhost'])
        experiment_manager.platform_instances[ComputePlatformType.HT] = ht_platform  #FIXME
        try:
            answers = ht_platform.ping_workers()
        except TimeoutError:
            raise AssertionError('The ping timed out. A worker must listen queue \'localhost\'')
        assert answers == ['localhost']

        # 1. Submit rq task
        tasks = experiment_manager.create_tasks(
            config_file=SCRIPTS_PATH + '/test_submit.yaml',
            platform='htPlatform')
        task_id = tasks[0].id

        # 2. Check that the task finishes successfully
        def check_finished():
            experiment_manager.update_tasks()
            status = Task.get(Task.id == task_id).status
            return status == TaskStatus.Finished
        wait_true(check_finished, interval_secs=2)

# @pytest.mark.xfail
# def test_delete_rq_task(client):
#     # 1. Submit task
#     # 2. Archive task
#     # 3. Make sure task is archived
#     # 4. Delete task
#     # 5. Check that task does not exist in DB
#     # 6. Check that files on disk have been deleted
#     raise NotImplementedError


def wait_true(fn, interval_secs=1, tries=4):
    for i in range(tries):
        if fn():
            return
        else:
            sleep(interval_secs)
    raise TimeoutError
