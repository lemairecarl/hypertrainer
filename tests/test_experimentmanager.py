import os
from pathlib import Path
from time import sleep

import pytest

# Trick for initializing a test database
from hypertrainer.utils import TaskStatus, yaml, deep_assert_equal, TestState

TestState.test_mode = True

from hypertrainer.experimentmanager import experiment_manager
from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.htplatform import HtPlatform
from hypertrainer.task import Task

scripts_path = Path(__file__).parent / 'scripts'


# Make sure we will work on a separate, empty test database
assert Task.select().count() == 0, 'Must work on empty test db'


def test_export_yaml():
    experiment_manager.create_tasks(
        config_file=str(scripts_path / 'test_hp.yaml'),
        platform='local')

    tmpfile = Path('/tmp/httest.yaml')
    if tmpfile.exists():
        tmpfile.unlink()

    experiment_manager.export_yaml(str(tmpfile))

    # TODO perform more checks


class TestLocal:
    def test_output_path(self):
        tasks = experiment_manager.create_tasks(
            config_file=str(scripts_path / 'test_simple.yaml'),
            platform='local')
        task = tasks[0]

        assert 'output_root' in task.config

        assert Path(task.output_root).exists()

        output_path = task.output_path

        assert Path(output_path).exists()


    def test_other_cwd(self):
        """Test that experiment_manager works independently from working dir"""

        old_cwd = os.getcwd()
        try:
            os.mkdir('/tmp/hypertrainer')  # TODO windows friendly?
        except FileExistsError:
            pass
        os.chdir('/tmp/hypertrainer')

        tasks = experiment_manager.create_tasks(
            config_file=str(scripts_path / 'test_simple.yaml'),
            platform='local')
        task = tasks[0]

        assert Path(task.project_path).exists()
        assert Path(task.script_file).exists()
        assert Path(task.output_root).exists()
        assert Path(task.output_path).exists()

        os.chdir(old_cwd)


    def test_submit(self):
        # 1. Launch task
        tasks = experiment_manager.create_tasks(
            config_file=str(scripts_path / 'test_hp.yaml'),
            platform='local')
        task_ids = [t.id for t in tasks]

        # 2. Check that the hp search configs were generated
        assert len(tasks) == 3

        # Wait task finished
        def check_finished():
            experiment_manager.update_tasks([ComputePlatformType.LOCAL])
            status = Task.get(Task.id == tasks[2].id).status
            return status == TaskStatus.Finished

        wait_true(check_finished, interval_secs=0.5)

        # 3. Check stuff on each task
        p_exp10_values, p_exp2_values, p_lin_values = set(), set(), set()
        orig_yaml = yaml.load(scripts_path / 'test_hp.yaml')
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


    def test_archive(self):
        # 1. Submit local task
        tasks = experiment_manager.create_tasks(
            config_file=str(scripts_path / 'test_hp.yaml'),
            platform='local')
        task_id = tasks[0].id

        # 2. Archive task
        experiment_manager.archive_tasks_by_id([task_id])

        # 3. Check that it still exists
        assert Task.select().where(Task.id == task_id).count() == 1

        # 4. Check that is_archived == True
        assert Task.get(Task.id == task_id).is_archived

        # 5. Check that it is absent from the non-archived list
        non_archived_tasks = experiment_manager.get_tasks(platform=ComputePlatformType.LOCAL)

        assert task_id not in [t.id for t in non_archived_tasks]

        # 6. Check that it is present in the archived list
        archived_tasks = experiment_manager.get_tasks(archived=True, platform=ComputePlatformType.LOCAL)
        assert task_id in [t.id for t in archived_tasks]


    def test_delete(self):
        def get_task_folder(task_id):
            return Path(Task.get(Task.id == task_id).output_path)

        # 1. Submit task
        tasks = experiment_manager.create_tasks(
            config_file=str(scripts_path / 'test_hp.yaml'),
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

    def test_cancel(self):
        tasks = experiment_manager.create_tasks(
            config_file=str(scripts_path / 'test_long.yaml'),
            platform='local')
        task_id = tasks[0].id

        experiment_manager.cancel_tasks_by_id([task_id])

        def check_cancelled():
            experiment_manager.update_tasks([ComputePlatformType.LOCAL])
            t = experiment_manager.get_tasks_by_id([task_id])[0]
            return t.status == TaskStatus.Cancelled

        wait_true(check_cancelled)


@pytest.fixture
def ht_platform():
    _ht_platform = HtPlatform(['localhost'])
    experiment_manager.platform_instances[ComputePlatformType.HT] = _ht_platform
    try:
        answers = _ht_platform.ping_workers()
    except (ConnectionError, ConnectionRefusedError):
        raise Exception('Could not connect to Redis. Make sure redis-server is running.')
    except TimeoutError:
        raise Exception('The ping timed out. A worker must listen queue \'localhost\'')
    assert answers == ['localhost']
    return _ht_platform


@pytest.fixture
def ht_platform_same_thread():
    _ht_platform = HtPlatform(['localhost'], same_thread=True)
    experiment_manager.platform_instances[ComputePlatformType.HT] = _ht_platform
    return _ht_platform


class TestRq:
    def test_submit(self, ht_platform):
        # Submit rq task
        tasks = experiment_manager.create_tasks(
            platform='ht',
            config_file=str(scripts_path / 'test_simple.yaml'))

        # Check that the task has status Waiting
        assert tasks[0].status == TaskStatus.Waiting

        sleep(0.2)  # FIXME this is too flaky
        task_id = tasks[0].id
        experiment_manager.update_tasks([ComputePlatformType.HT])
        assert experiment_manager.get_tasks_by_id([task_id])[0].status == TaskStatus.Running

        # Check that the task finishes successfully
        wait_task_finished(task_id, interval_secs=2, tries=6)

    @pytest.mark.xfail
    def test_submit_multiple(self, ht_platform):
        # Submit rq task
        tasks = experiment_manager.create_tasks(
            platform='ht',
            config_file=str(scripts_path / 'test_hp.yaml'))

        # Check that the task finishes successfully
        wait_task_finished(tasks[0].id, interval_secs=1, tries=8)

    def test_delete(self, ht_platform):
        # Submit task
        tasks = experiment_manager.create_tasks(
            platform='ht',
            config_file=str(scripts_path / 'test_simple.yaml'))
        task_id = tasks[0].id

        # Wait task finish
        wait_task_finished(task_id, interval_secs=2, tries=3)

        # Try deleting task (fails since not archived yet)
        with pytest.raises(RuntimeError):
            experiment_manager.delete_tasks_by_id([task_id])

        # Archive task
        experiment_manager.archive_tasks_by_id([task_id])
        task = Task.get(Task.id == task_id)
        assert task.is_archived

        # Check that the output path exists
        assert Path(task.output_path).exists()

        # Delete task
        experiment_manager.delete_tasks_by_id([task_id])

        # Check that task does not exist in DB
        assert Task.select().where(Task.id == task_id).count() == 0

        # Check that files on disk have been deleted
        wait_true(lambda: not Path(task.output_path).exists())

        # Check that the job does not exist in the worker's db
        info_dicts = ht_platform._get_info_dict_for_each_worker()
        assert len(info_dicts) == 1
        worker_db = info_dicts[0]
        assert task.job_id not in worker_db

    @pytest.mark.xfail
    def test_cancel(self, ht_platform):
        tasks = experiment_manager.create_tasks(
            config_file=str(scripts_path / 'test_long.yaml'),
            platform='ht')
        task_id = tasks[0].id

        # Check that the task is running
        def check_running():
            experiment_manager.update_tasks([ComputePlatformType.HT])
            t = experiment_manager.get_tasks_by_id([task_id])[0]
            return t.status == TaskStatus.Running
        wait_true(check_running)

        experiment_manager.cancel_tasks_by_id([task_id])

        # Check that the task is cancelled
        def check_cancelled():
            experiment_manager.update_tasks([ComputePlatformType.HT])
            t = experiment_manager.get_tasks_by_id([task_id])[0]
            return t.status == TaskStatus.Cancelled
        wait_true(check_cancelled)

    def test_acquire_one_gpu(self, monkeypatch, ht_platform_same_thread):
        monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '0,1')

        tasks = experiment_manager.create_tasks(
            config_file=str(scripts_path / 'test_gpu_1.yaml'),
            platform='ht')
        t1_id = tasks[0].id

        wait_task_finished(t1_id, interval_secs=1, tries=3)

        t1 = experiment_manager.get_tasks_by_id([t1_id])[0]
        experiment_manager.monitor(t1)

        assert t1.logs['out'].strip() == 'gpu_id=0'


def wait_true(fn, interval_secs=0.4, tries=6):
    for i in range(tries):
        if fn():
            return
        else:
            sleep(interval_secs)
    raise TimeoutError


def wait_task_finished(task_id, interval_secs=0.4, tries=6):
    def get_status():
        experiment_manager.update_tasks()
        return Task.get(Task.id == task_id).status

    for i in range(tries):
        status = get_status()
        if status == TaskStatus.Finished:
            return
        elif status in (TaskStatus.Running, TaskStatus.Waiting):
            sleep(interval_secs)
        else:
            experiment_manager.print_output(task_id)
            raise ChildProcessError(str(status))
    raise TimeoutError
