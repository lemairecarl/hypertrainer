import pytest


def test_archive_task(client):
    from hypertrainer.experimentmanager import experiment_manager
    from hypertrainer.task import Task

    # 1. Submit local task
    tasks = experiment_manager.create_tasks(script_file='script_test_submit.py', config_file='test_submit.yaml',
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


@pytest.mark.xfail
def test_delete_task(client):
    # 1. Submit rq task
    # 2. Archive task
    # 3. Make sure task is archived
    # 4. Delete task
    # 5. Check that task does not exist in DB
    # 6. Check that files on disk have been deleted
    raise NotImplementedError


@pytest.mark.xfail
def test_submit_rq_task(client):
    raise NotImplementedError
