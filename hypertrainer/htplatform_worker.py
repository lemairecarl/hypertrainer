import pickle
import subprocess
from pathlib import Path
from time import sleep

from rq import get_current_job

from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.localplatform import get_python_env_command
from hypertrainer.utils import yaml

ht_root = Path.home() / 'hypertrainer'  # FIXME config
local_db = ht_root / 'db.pkl'  # FIXME config


def run(
        task_uuid: str,
        script_file: Path,
        config_dump: str,
        output_root_path: Path,
        project_path: Path,
        resume: bool
        ):
    # Prepare the job
    output_path = output_root_path / task_uuid
    config_file = output_path / 'config.yaml'
    if not resume:
        # Setup task dir
        output_path.mkdir(parents=True, exist_ok=False)
        config = yaml.load(config_dump)
        config['training']['output_path'] = str(output_path)  # FIXME does not generalize!
        yaml.dump(config, config_file)
    python_env_command = get_python_env_command(project_path, ComputePlatformType.HT.value)
    stdout_path = output_path / 'out.txt'  # FIXME this ignores task.stdout_path
    stderr_path = output_path / 'err.txt'

    # Start the subprocess
    p = subprocess.Popen(python_env_command + [str(script_file), str(config_file)],
                         stdout=stdout_path.open(mode='w'),
                         stderr=stderr_path.open(mode='w'),
                         cwd=str(output_path),
                         universal_newlines=True)

    # Write into to local db
    job_id = get_current_job().id
    _update_job(job_id, {'output_path': str(output_path), 'pid': p.pid})

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
    # TODO
    return {}
    job_path = _get_job_path(task_id)
    logs = {}
    patterns = ('*.log', '*.txt')
    for pattern in patterns:
        for f in job_path.glob(pattern):
            p = Path(f)
            logs[p.stem] = p.read_text()
    return logs


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
