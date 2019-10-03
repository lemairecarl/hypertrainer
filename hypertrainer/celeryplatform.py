import os
import subprocess
from pathlib import Path

from celery import Celery, Task as CeleryTask

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.localplatform import get_python_env_command
from hypertrainer.utils import TaskStatus, resolve_path, setup_scripts_path

app = Celery('hypertrainer.celeryplatform', backend='rpc://', broker='amqp://localhost')


class CeleryPlatform(ComputePlatform):
    _root_dir: Path = None
    local_processes = {}

    def __init__(self):
        self.processes = {}

    def submit(self, task, continu=False):
        task_info = run.s(task.id, task.script_file, task.dump_config(), task.output_path,
                          continu).apply_async(queue='jobs').get(timeout=2)
        job_id = task_info['job_id']
        self.processes[job_id] = task_info
        return job_id

    def fetch_logs(self, task, keys=None):
        return {}

    def cancel(self, task):
        pass

    def get_statuses(self, job_ids) -> dict:
        statuses = {'': TaskStatus.Unknown, 'celeryDummy': TaskStatus.Unknown}
        for j in job_ids:
            statuses[j] = TaskStatus.Unknown
        for p in self.processes.values():
            status_str = get_status.s(p['job_id']).apply_async(queue=p['hostname']).get(timeout=2)  # TODO async group
            statuses[p['job_id']] = TaskStatus(status_str)
        return statuses

    @staticmethod
    def get_root_dir():
        if CeleryPlatform._root_dir is None:
            CeleryPlatform.setup_output_path()
        return CeleryPlatform._root_dir

    @staticmethod
    def setup_output_path():
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
        continu: bool
        ):
    setup_scripts_path()  # FIXME
    job_path = CeleryPlatform.get_root_dir() / str(task_id)  # Gets the job path on the worker
    config_file = job_path / 'config.yaml'
    if not continu:
        # Setup task dir
        job_path.mkdir(parents=True, exist_ok=False)
        output_path = str(job_path)
        # FIXME modify config to set output_path!
        config_file.write_text(config_dump)
    # Launch process
    script_file_local = resolve_path(script_filename)
    python_env_command = get_python_env_command(script_file_local, ComputePlatformType.CELERY.value)
    print('Using env:', python_env_command)
    stdout_path = Path(job_path) / 'out.txt'  # FIXME this ignores task.stdout_path
    stderr_path = Path(job_path) / 'err.txt'

    p = subprocess.Popen(python_env_command + [str(script_file_local), str(config_file)],
                         stdout=stdout_path.open(mode='w'),
                         stderr=stderr_path.open(mode='w'),
                         cwd=output_path,
                         universal_newlines=True)

    job_id = _celery_task.request.id
    CeleryPlatform.local_processes[job_id] = p
    return {
        'job_id': job_id,
        'task_id': task_id,
        'hostname': _celery_task.request.hostname[7:],  # FIXME !!! FIXME need to save in DB? or on disk?
        'pid': p.pid,
        'output_path': output_path
    }


@app.task
def get_status(job_id):
    print(job_id)
    raise NotImplementedError
    return TaskStatus.Running.value
