import os
import subprocess
from pathlib import Path
from time import sleep
from typing import List
import pickle

from celery import Celery, Task as CeleryTask, group as Group

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.localplatform import get_python_env_command
from hypertrainer.task import Task
from hypertrainer.utils import TaskStatus, resolve_path, setup_scripts_path

app = Celery('hypertrainer.celeryplatform', backend='redis://localhost:6380', broker='amqp://localhost')
local_db = Path.home() / 'hypertrainer' / 'db.pkl'


class CeleryPlatform(ComputePlatform):
    _root_dir: Path = None

    def __init__(self, worker_hostnames: List[str]):
        self.worker_hostnames = worker_hostnames

    def submit(self, task, resume=False):
        async_result = run.s(task.id, task.script_file, task.dump_config(), task.output_path, resume).apply_async(
                             queue='jobs')
        job_id = async_result.id
        async_result.forget()  # The function returns nothing
        # At this point, we only know the celery task id. No pid since the job might have to wait.
        return job_id

    def fetch_logs(self, task, keys=None):
        return {}

    def cancel(self, task):
        pass

    def get_statuses(self, job_ids) -> dict:
        # TODO get celery status
        # FIXME handle queued state (differentiate between Lost and Waiting)

        # TODO only check requested ids
        req_statuses = {}

        # TODO check that process is still running?
        # TODO handle continue on different host
        status_dicts_g = Group([get_local_statuses.signature(queue=h) for h in self.worker_hostnames])
        status_dicts = status_dicts_g.apply_async().get(timeout=2)
        for hostname, status_dict in zip(self.worker_hostnames, status_dicts):
            for job_id, status_str in status_dict.items():
                req_statuses[job_id] = TaskStatus(status_str)
            # Set hostname TODO do it only once!
            Task.update({Task.hostname: hostname}).where(Task.job_id.in_(status_dict.keys()))

        # Check for pending jobs
        for job_id in job_ids:
            async_result = run.AsyncResult(job_id)
            if async_result.status == 'PENDING':
                req_statuses[job_id] = TaskStatus.Waiting

        # TODO SUCCESS, FAILURE
        return req_statuses

    @staticmethod
    def get_root_dir():
        if CeleryPlatform._root_dir is None:
            CeleryPlatform.setup_output_path()
        return CeleryPlatform._root_dir

    @staticmethod
    def setup_output_path():
        # FIXME cannot store in memory
        # Setup root output dir
        p = os.environ.get('HYPERTRAINER_OUTPUT')
        if p is None:
            CeleryPlatform._root_dir = Path.home() / 'hypertrainer' / 'output'
            print('Using root output dir: {}\nYou can configure this with $HYPERTRAINER_OUTPUT.'
                  .format(CeleryPlatform._root_dir))
        else:
            CeleryPlatform._root_dir = Path(p)
        CeleryPlatform._root_dir.mkdir(parents=True, exist_ok=True)


@app.task(bind=True)
def run(_celery_task: CeleryTask,
        task_id: int,
        script_filename: str,
        config_dump: str,
        output_path: str,
        resume: bool
        ):
    # Prepare the job
    setup_scripts_path()  # FIXME do not run this each time
    job_path = CeleryPlatform.get_root_dir() / str(task_id)  # Gets the job path on the worker
    config_file = job_path / 'config.yaml'
    if not resume:
        # Setup task dir
        job_path.mkdir(parents=True, exist_ok=False)
        output_path = str(job_path)
        # FIXME modify config to set output_path!
        config_file.write_text(config_dump)
    script_file_local = resolve_path(script_filename)
    python_env_command = get_python_env_command(script_file_local, ComputePlatformType.CELERY.value)
    print('Using env:', python_env_command)
    stdout_path = Path(job_path) / 'out.txt'  # FIXME this ignores task.stdout_path
    stderr_path = Path(job_path) / 'err.txt'

    # Start the subprocess
    p = subprocess.Popen(python_env_command + [str(script_file_local), str(config_file)],
                         stdout=stdout_path.open(mode='w'),
                         stderr=stderr_path.open(mode='w'),
                         cwd=output_path,
                         universal_newlines=True)

    hostname = strip_username_from_hostname(_celery_task.request.hostname)
    job_id = _celery_task.request.id
    update_job(job_id, 'Running')  # TODO check that it is really running
    # FIXME write pid, output_path to a file?

    # Monitor the job
    monitor_interval = 2  # TODO config
    while True:
        poll_result = p.poll()
        if poll_result is None:
            update_job(job_id, 'Running')
        else:
            if p.returncode == 0:
                print('Finished successfully')
                update_job(job_id, 'Finished')
            else:
                print('Crashed!')
                update_job(job_id, 'Crashed')
            break  # End the celery task
        sleep(monitor_interval)


@app.task
def get_local_statuses():
    return get_db_contents()


def check_init_db():
    if not local_db.exists():
        with local_db.open('wb') as f:
            pickle.dump({}, f)


def update_job(job_id: str, status: str):
    check_init_db()
    with local_db.open('rb') as f:
        db = pickle.load(f)
    db[job_id] = status
    with local_db.open('wb') as f:
        pickle.dump(db, f)


def get_db_contents():
    check_init_db()
    with local_db.open('rb') as f:
        db = pickle.load(f)
    return db


def strip_username_from_hostname(hostname):
    return hostname.split('@')[1]
