import subprocess
from pathlib import Path
from time import sleep
import pickle

from rq import get_current_job

from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.localplatform import get_python_env_command
from hypertrainer.utils import resolve_path, setup_scripts_path, yaml

ht_root = Path.home() / 'hypertrainer'  # FIXME config
ht_output_path = ht_root / 'output'
local_db = ht_root / 'db.pkl'  # FIXME config


def run(
        task_id: int,
        script_filename: str,
        config_dump: str,
        output_path: str,
        resume: bool
        ):
    # Prepare the job
    setup_scripts_path()  # FIXME do not run this each time
    job_path = _get_job_path(task_id)  # Gets the job path on the worker
    config_file = job_path / 'config.yaml'
    if not resume:
        # Setup task dir
        job_path.mkdir(parents=True, exist_ok=False)
        output_path = str(job_path)
        config = yaml.load(config_dump)
        config['training']['output_path'] = output_path  # FIXME does not generalize!
        yaml.dump(config, config_file)
    script_file_local = resolve_path(script_filename)
    python_env_command = get_python_env_command(script_file_local, ComputePlatformType.HT.value)
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
    job_id = get_current_job().id
    _update_job(job_id, {'output_path': output_path, 'pid': p.pid})

    # Monitor the job
    monitor_interval = 2  # TODO config?
    while True:
        poll_result = p.poll()
        if poll_result is None:
            _update_job(job_id, {'status': 'Running'})
        else:
            if p.returncode == 0:
                print('Finished successfully')
                _update_job(job_id, {'status': 'Finished'})
            else:
                print('Crashed!')
                _update_job(job_id, {'status': 'Crashed'})
            break  # End the rq job
        sleep(monitor_interval)


def get_logs(task_id):
    job_path = _get_job_path(task_id)
    logs = {}
    patterns = ('*.log', '*.txt')
    for pattern in patterns:
        for f in job_path.glob(pattern):
            p = Path(f)
            logs[p.stem] = p.read_text()
    return logs


def _get_job_path(task_id):
    return ht_output_path / str(task_id)


def get_jobs_info():
    return _get_db_contents()


def _check_init_db():
    if not local_db.exists():
        with local_db.open('wb') as f:
            pickle.dump({}, f)


def _update_job(job_id: str, data: dict):
    _check_init_db()
    with local_db.open('rb') as f:
        db = pickle.load(f)
    if job_id not in db:
        db[job_id] = {}
    db[job_id].update(data)
    with local_db.open('wb') as f:
        pickle.dump(db, f)


def _get_db_contents():
    _check_init_db()
    with local_db.open('rb') as f:
        db = pickle.load(f)
    return db


def test_job(msg: str):
    """Prints a message. For testing purposes."""
    print(msg)
