import contextlib
import os
import pickle
import shutil
import subprocess
from pathlib import Path
from time import sleep
from typing import List

from rq import get_current_job

from hypertrainer.utils import yaml, hypertrainer_home, GpuLockManager

local_db = hypertrainer_home / 'db.pkl'  # FIXME config


def run(
        script_file: Path,
        output_path: Path,
        config_dump: str,
        python_env_command: List[str],
        resume: bool
        ):
    gpu_lock = None
    try:
        # Prepare the job
        config_file = output_path / 'config.yaml'
        config = yaml.load(config_dump)
        if not resume:
            # Setup task dir
            output_path.mkdir(parents=True, exist_ok=False)
            config = yaml.load(config_dump)
            yaml.dump(config, config_file)
        stdout_path = output_path / 'out.txt'  # FIXME this ignores task.stdout_path
        stderr_path = output_path / 'err.txt'

        # Manage GPU dependency
        env_vars = os.environ
        if 'num_gpus' in config:
            num_required_gpus = config['num_gpus']
            if num_required_gpus > 1:
                raise NotImplementedError
            gpu_lock = GpuLockManager().acquire_one_gpu()
            env_vars = os.environ.copy()
            env_vars['CUDA_VISIBLE_DEVICES'] = gpu_lock.gpu_id

        # Start the subprocess
        p = subprocess.Popen(python_env_command + [str(script_file), str(config_file)],
                             stdout=stdout_path.open(mode='w'),
                             stderr=stderr_path.open(mode='w'),
                             cwd=str(output_path),
                             universal_newlines=True,
                             env=env_vars)

        # Write into to local db
        job_id = get_current_job().id
        _update_job(job_id, {'pid': p.pid})

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

    except Exception:
        job_id = get_current_job().id
        _update_job(job_id, {'status': 'RunFailed'})
        raise
    finally:
        # Release the GPU lock if needed
        if gpu_lock is not None:
            gpu_lock.release()


def get_logs(output_path: str):
    logs = {}
    patterns = ('*.log', '*.txt')
    for pattern in patterns:
        for matched_file_path in Path(output_path).glob(pattern):
            log_name = matched_file_path.stem
            logs[log_name] = matched_file_path.read_text()
    return logs


def delete_job(job_id: str, output_path: str):
    _delete_job(job_id)
    print('Deleting', output_path)
    shutil.rmtree(output_path,
                  onerror=lambda function, path, excinfo: print('ERROR', function, path, excinfo))


def ping(msg):
    return msg


def raise_exception(exc_type):
    raise exc_type


def get_jobs_info():
    with local_db_context() as db:
        jobs_info = db
    return jobs_info


def _check_init_db():
    if not local_db.exists():
        with local_db.open('wb') as f:
            pickle.dump({}, f)


@contextlib.contextmanager
def local_db_context():
    _check_init_db()
    with local_db.open('r+b') as f:
        db = pickle.load(f)
        yield db
        f.seek(0)
        f.truncate()
        pickle.dump(db, f)


def _update_job(job_id: str, data: dict):
    with local_db_context() as db:
        if job_id not in db:
            db[job_id] = {}
        db[job_id].update(data)


def _delete_job(job_id: str):
    with local_db_context() as db:
        del db[job_id]


def test_job(msg: str):
    """Prints a message. For testing purposes."""
    print(msg)
