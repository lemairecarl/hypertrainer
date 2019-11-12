import os
import signal
import subprocess
from pathlib import Path

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.utils import resolve_path, TaskStatus, yaml


class LocalPlatform(ComputePlatform):
    root_dir: Path = None

    def __init__(self):
        self.setup_output_path()

        self.processes = {}

    @staticmethod
    def setup_output_path():
        # Setup root output dir
        p = os.environ.get('HYPERTRAINER_OUTPUT')
        if p is None:
            LocalPlatform.root_dir = Path.home() / 'hypertrainer' / 'output'
            print('Using root output dir: {}\nYou can configure this with $HYPERTRAINER_OUTPUT.'
                  .format(LocalPlatform.root_dir))
        else:
            LocalPlatform.root_dir = Path(p)
        LocalPlatform.root_dir.mkdir(parents=True, exist_ok=True)

    def submit(self, task, resume=False):
        job_path = self._make_job_path(task)
        config_file = job_path / 'config.yaml'
        if not resume:
            # Setup task dir
            job_path.mkdir(parents=True, exist_ok=False)
            task.output_path = str(job_path)
            config_file.write_text(task.dump_config())
        # Launch process
        script_file_local = resolve_path(task.script_file)
        python_env_command = get_python_env_command(script_file_local, task.platform_type.value)  # default: ['python']
        print('Using env:', python_env_command)

        p = subprocess.Popen(python_env_command + [str(script_file_local), str(config_file)],
                             stdout=task.stdout_path.open(mode='w'),
                             stderr=task.stderr_path.open(mode='w'),
                             cwd=task.output_path,
                             universal_newlines=True)
        job_id = str(p.pid)
        self.processes[job_id] = p
        return job_id

    def fetch_logs(self, task, keys=None):
        job_path = self._make_job_path(task)
        logs = {}
        patterns = ('*.log', '*.txt')
        for pattern in patterns:
            for f in job_path.glob(pattern):
                p = Path(f)
                logs[p.stem] = p.read_text()
        return logs

    def cancel(self, task):
        os.kill(int(task.job_id), signal.SIGTERM)
        task.status = TaskStatus.Cancelled
        task.save()

    def update_tasks(self, tasks):
        for t in tasks:
            p = self.processes.get(t.job_id)
            if p is None:
                t.status = TaskStatus.Lost
                continue
            poll_result = p.poll()
            if poll_result is None:
                t.status = TaskStatus.Running
            else:
                if p.returncode == 0:
                    t.status = TaskStatus.Finished
                else:
                    t.status = TaskStatus.Crashed

    def _make_job_path(self, task):
        return self.root_dir / str(task.id)


def get_python_env_command(script_file_local: Path, platform: str):
    default_interpreter = ['python']

    env_config_file = script_file_local.parent / 'env.yaml'
    if not env_config_file.exists():
        return default_interpreter

    env_configs = yaml.load(env_config_file)
    if env_configs is None or platform not in env_configs:
        return default_interpreter

    env_config = env_configs[platform]
    if env_config['conda']:
        if 'path' in env_config:
            return [env_config['conda_bin'], 'run', '-p', env_config['path'], 'python']
        else:
            return [env_config['conda_bin'], 'run', '-n', env_config['name'], 'python']
    else:
        return [env_config['path'] + '/bin/python']