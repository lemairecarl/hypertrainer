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
from hypertrainer.utils import TaskStatus, resolve_path, setup_scripts_path, yaml

app = Celery('hypertrainer.celeryplatform', backend='rpc://', broker='amqp://localhost:5672')
local_db = Path.home() / 'hypertrainer' / 'db.pkl'


class HtPlatform(ComputePlatform):
    """The HT (HyperTrainer) Platform allows to send jobs to one or more Linux machines.

    Each participating worker (can be several workers per machine) consumes jobs from a global queue.
    """

    _root_dir: Path = None

    def __init__(self, worker_hostnames: List[str]):
        self.worker_hostnames = worker_hostnames

    def submit(self, task, resume=False):
        async_result = run.s(task.id, task.script_file, task.dump_config(), task.output_path, resume).apply_async(
                             queue='jobs')
        job_id = async_result.id
        # At this point, we only know the celery task id. No pid since the job might have to wait.
        return job_id

    def fetch_logs(self, task, keys=None):
        return {}

    def cancel(self, task):
        pass

    def update_tasks(self, tasks):
        # TODO do not modify database here!!!
        # TODO only check requested ids
        # TODO handle continue on different host
        # TODO check for pending jobs -- need a result backend for this (e.g. redis)

        for t in tasks:
            t.status = TaskStatus.Unknown
        job_id_to_task = {t.job_id: t for t in tasks}

        info_dicts_g = Group([get_jobs_info.signature(queue=h) for h in self.worker_hostnames])
        info_dicts = info_dicts_g.apply_async().get(timeout=5)  # TODO catch celery.exceptions.TimeoutError
        for hostname, local_db in zip(self.worker_hostnames, info_dicts):
            for job_id in set(local_db.keys()).intersection(job_id_to_task.keys()):
                job_info = local_db[job_id]
                t = job_id_to_task[job_id]

                t.status = TaskStatus(job_info['status'])
                t.output_path = job_info['output_path']
                t.hostname = hostname

    @staticmethod
    def get_root_dir():
        if HtPlatform._root_dir is None:
            HtPlatform.setup_output_path()
        return HtPlatform._root_dir

    @staticmethod
    def setup_output_path():
        # FIXME cannot store in memory
        # Setup root output dir
        p = os.environ.get('HYPERTRAINER_OUTPUT')
        if p is None:
            HtPlatform._root_dir = Path.home() / 'hypertrainer' / 'output'
            print('Using root output dir: {}\nYou can configure this with $HYPERTRAINER_OUTPUT.'
                  .format(HtPlatform._root_dir))
        else:
            HtPlatform._root_dir = Path(p)
        HtPlatform._root_dir.mkdir(parents=True, exist_ok=True)


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
    job_path = HtPlatform.get_root_dir() / str(task_id)  # Gets the job path on the worker
    config_file = job_path / 'config.yaml'
    if not resume:
        # Setup task dir
        job_path.mkdir(parents=True, exist_ok=False)
        output_path = str(job_path)
        config = yaml.load(config_dump)
        config['training']['output_path'] = output_path  # FIXME does not generalize!
        yaml.dump(config, config_file)
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

    # Write into to local db
    job_id = _celery_task.request.id
    update_job(job_id, {'output_path': output_path, 'pid': p.pid})

    # Monitor the job
    monitor_interval = 2  # TODO config
    while True:
        poll_result = p.poll()
        if poll_result is None:
            update_job(job_id, {'status': 'Running'})
        else:
            if p.returncode == 0:
                print('Finished successfully')
                update_job(job_id, {'status': 'Finished'})
            else:
                print('Crashed!')
                update_job(job_id, {'status': 'Crashed'})
            break  # End the celery task
        sleep(monitor_interval)


@app.task
def get_jobs_info():
    return get_db_contents()


def check_init_db():
    if not local_db.exists():
        with local_db.open('wb') as f:
            pickle.dump({}, f)


def update_job(job_id: str, data: dict):
    # TODO use a sqlite db
    check_init_db()
    with local_db.open('rb') as f:
        db = pickle.load(f)
    if job_id not in db:
        db[job_id] = {}
    db[job_id].update(data)
    with local_db.open('wb') as f:
        pickle.dump(db, f)


def get_db_contents():
    check_init_db()
    with local_db.open('rb') as f:
        db = pickle.load(f)
    return db


def strip_username_from_hostname(hostname):
    return hostname.split('@')[1]
