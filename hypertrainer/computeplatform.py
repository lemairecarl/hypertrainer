import os
import signal
import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from glob import glob
import tempfile

from hypertrainer.utils import TaskStatus, parse_columns, resolve_path, yaml


class ComputePlatform(ABC):
    @abstractmethod
    def submit(self, task, continu=False) -> str:
        """Submit a task and return the plaform specific task id.

        If continu=True, run script in already-existing output path.

        Note: since 'continue' is a keyword in Python, I had to choose something else.
        """
        pass

    @abstractmethod
    def monitor(self, task, keys=None):
        """Return a dict of logs.

        Example: {
            'out': '...',
            'err': '...',
            'metric_loss': '...'
        }
        """
        pass

    @abstractmethod
    def cancel(self, task):
        """Cancel a task."""
        pass

    @abstractmethod
    def get_statuses(self, job_ids) -> dict:
        """Return a dict mapping job ids to their statuses.

        Example: {
            '1234': TaskStatus.Running,
            '5678': TaskStatus.Waiting
        }
        """
        pass


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

    def submit(self, task, continu=False):
        job_path = self._make_job_path(task)
        config_file = job_path / 'config.yaml'
        if not continu:
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

    def monitor(self, task, keys=None):
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

    def get_statuses(self, job_ids) -> dict:
        statuses = {}
        for job_id in job_ids:
            p = self.processes.get(job_id)
            if p is None:
                statuses[job_id] = TaskStatus.Lost
                continue
            poll_result = p.poll()
            if poll_result is None:
                statuses[job_id] = TaskStatus.Running
            else:
                if p.returncode == 0:
                    statuses[job_id] = TaskStatus.Finished
                else:
                    statuses[job_id] = TaskStatus.Crashed
        return statuses

    def _make_job_path(self, task):
        return self.root_dir / str(task.id)


class HeliosPlatform(ComputePlatform):
    status_map = {
        'Defer': TaskStatus.Waiting,
        'Idle': TaskStatus.Waiting,
        'Running': TaskStatus.Running,
        'Canceling': TaskStatus.Cancelled,
        'Complete': TaskStatus.Finished,
        'Removed': TaskStatus.Removed
    }

    def __init__(self, server_user):
        self.server_user = server_user
        self.submission_template = Path('platform/helios/moab_template.sh').read_text()
        self.setup_template = Path('platform/helios/moab_setup.sh').read_text()

    def submit(self, task, continu=False):
        job_remote_dir = self._make_job_path(task)
        if continu:
            setup_script = self.replace_variables('cd $HYPERTRAINER_JOB_DIR && msub $HYPERTRAINER_NAME.sh', task)
        else:
            task.output_path = job_remote_dir
            setup_script = self.replace_variables(self.setup_template, task, submission=self.submission_template)
        completed_process = None
        try:
            completed_process = subprocess.run(['ssh', self.server_user],
                                               input=setup_script.encode(), stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
            completed_process.check_returncode()
        except subprocess.CalledProcessError:
            print(completed_process.stderr)
            raise  # FIXME handle error
        job_id = completed_process.stdout.decode('utf-8').strip()
        return job_id

    def monitor(self, task, keys=None):
        logs = {}
        with tempfile.TemporaryDirectory() as tmpdir:
            # Get all .txt, .log files in output path
            subprocess.run(['scp', self.server_user + ':' + self._make_job_path(task) + '/*.{log,txt}', tmpdir],
                           stderr=subprocess.DEVNULL)  # Ignore errors (e.g. if *.log doesn't exist)
            for f in glob(tmpdir + '/*'):
                p = Path(f)
                logs[p.stem] = p.read_text()
        return logs

    def get_statuses(self, job_ids):
        statuses = self._get_statuses(job_ids)  # Get statuses of active jobs
        ccodes = self._get_completion_codes()  # Get statuses for completed jobs

        for job_id in job_ids:
            if job_id in ccodes:
                # Job just completed
                if ccodes[job_id] == 0:
                    statuses[job_id] = TaskStatus.Finished
                else:
                    statuses[job_id] = TaskStatus.Crashed
            else:
                # Job still active (or lost)
                if job_id not in statuses:
                    statuses[job_id] = TaskStatus.Lost  # Job not found
        return statuses

    def _get_statuses(self, job_ids):
        job_ids_str = ','.join(job_ids)
        data = subprocess.run(['ssh', self.server_user, f'mdiag -j {job_ids_str} | grep $USER'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
        data_grid = parse_columns(data)
        statuses = {}
        for l in data_grid:
            job_id, status = l[0], l[1]
            statuses[job_id] = self.status_map[status]
        return statuses

    def _get_completion_codes(self):
        data = subprocess.run(['ssh', self.server_user, 'showq -u $USER -c | grep $USER'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
        data_grid = parse_columns(data)
        ccodes = {}
        for l in data_grid:
            job_id, ccode = l[0], l[2]
            if ccode == 'CNCLD(271)':
                ccode = 271
            else:
                ccode = int(ccode)
            ccodes[job_id] = ccode
        return ccodes

    def cancel(self, task):
        subprocess.run(['ssh', self.server_user, f'mjobctl -c {task.job_id}'])
        task.status = TaskStatus.Cancelled
        task.save()

    @staticmethod
    def _make_job_path(task):
        return '$HOME/hypertrainer/jobs/' + str(task.id)

    @staticmethod
    def replace_variables(input_text, task, **kwargs):
        key_value_map = [
            ('$HYPERTRAINER_SUBMISSION', kwargs.get('submission', '')),
            ('$HYPERTRAINER_NAME', task.name),
            ('$HYPERTRAINER_OUTFILE', task.output_path + '/out.txt'),
            ('$HYPERTRAINER_ERRFILE', task.output_path + '/err.txt'),
            ('$HYPERTRAINER_JOB_DIR', task.output_path),
            ('$HYPERTRAINER_SCRIPT', task.script_file),
            ('$HYPERTRAINER_CONFIGFILE', task.output_path + '/config.yaml'),
            ('$HYPERTRAINER_CONFIGDATA', task.dump_config())
        ]
        output = input_text
        for key, value in key_value_map:
            output = output.replace(key, value)
        return output


class SlurmPlatform(ComputePlatform):
    status_map = {
        'PD': TaskStatus.Waiting,
        'R': TaskStatus.Running,
        'CG': TaskStatus.Running,
        'CD': TaskStatus.Finished,
        'F': TaskStatus.Crashed,
        'CA': TaskStatus.Cancelled,
        'DL': TaskStatus.Removed,
        'TO': TaskStatus.Removed
    }

    def __init__(self, server_user):
        self.server_user = server_user
        self.user = server_user.split('@')[0]
        self.submission_template = Path('platform/slurm/slurm_template.sh')
        self.setup_template = Path('platform/slurm/slurm_setup.sh')

    def submit(self, task, continu=False):
        job_remote_dir = self._make_job_path(task)
        if continu:
            setup_script = self.replace_variables(
                'cd $HYPERTRAINER_JOB_DIR && sbatch --parsable $HYPERTRAINER_NAME.sh', task)
        else:
            task.output_path = job_remote_dir
            setup_script = self.replace_variables(self.setup_template.read_text(), task,
                                                  submission=self.submission_template.read_text())
        completed_process = None
        try:
            completed_process = subprocess.run(['ssh', self.server_user],
                                               input=setup_script.encode(), stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
            completed_process.check_returncode()
        except subprocess.CalledProcessError:
            print(completed_process.stderr)
            raise  # FIXME handle error
        job_id = completed_process.stdout.decode('utf-8').strip()
        return job_id

    def monitor(self, task, keys=None):
        logs = {}
        with tempfile.TemporaryDirectory() as tmpdir:
            # Get all .txt, .log files in output path
            subprocess.run(['scp', self.server_user + ':' + self._make_job_path(task) + '/*.{log,txt}', tmpdir],
                           stderr=subprocess.DEVNULL)  # Ignore errors (e.g. if *.log doesn't exist)
            for f in glob(tmpdir + '/*'):
                p = Path(f)
                logs[p.stem] = p.read_text()
        return logs

    def get_statuses(self, job_ids):
        statuses = self._get_statuses(job_ids)  # Get statuses of active jobs
        ccodes = self._get_completion_codes()  # Get statuses for completed jobs

        for job_id in job_ids:
            if job_id in ccodes:
                # Job just completed
                if ccodes[job_id] == 0:
                    statuses[job_id] = TaskStatus.Finished
                else:
                    statuses[job_id] = TaskStatus.Crashed
            else:
                # Job still active (or lost)
                if job_id not in statuses:
                    statuses[job_id] = TaskStatus.Lost  # Job not found
        return statuses

    def _get_statuses(self, job_ids):
        data = subprocess.run(['ssh', self.server_user, 'squeue -u $USER | grep $USER'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
        data_grid = parse_columns(data)
        statuses = {}
        for l in data_grid:
            job_id, status = l[0], l[4]
            if job_id not in job_ids:
                continue
            statuses[job_id] = self.status_map[status]
        return statuses

    def _get_completion_codes(self):
        data = subprocess.run(['ssh', self.server_user, 'sacct -o JobID,ExitCode -n -s CD,F,CA,DL,TO -S 010100'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
        data_grid = parse_columns(data)
        ccodes = {}
        for l in data_grid:
            job_id, ccode = l[0], l[1]
            if '.' in job_id:
                continue
            ccodes[job_id] = int(ccode.split(':')[0])
        return ccodes

    def cancel(self, task):
        subprocess.run(['ssh', self.server_user, f'scancel {task.job_id}'])
        task.status = TaskStatus.Cancelled
        task.save()

    def _make_job_path(self, task):
        return '/home/' + self.user + '/hypertrainer/output/' + str(task.id)

    @staticmethod
    def replace_variables(input_text, task, **kwargs):
        key_value_map = [
            ('$HYPERTRAINER_SUBMISSION', kwargs.get('submission', '')),
            ('$HYPERTRAINER_NAME', task.name),
            ('$HYPERTRAINER_OUTFILE', task.output_path + '/out.txt'),
            ('$HYPERTRAINER_ERRFILE', task.output_path + '/err.txt'),
            ('$HYPERTRAINER_JOB_DIR', task.output_path),
            ('$HYPERTRAINER_SCRIPT', task.script_file),
            ('$HYPERTRAINER_CONFIGFILE', task.output_path + '/config.yaml'),
            ('$HYPERTRAINER_CONFIGDATA', task.dump_config())
        ]
        output = input_text
        for key, value in key_value_map:
            output = output.replace(key, value)
        return output


class ComputePlatformType(Enum):
    LOCAL = 'local'
    HELIOS = 'helios'
    GRAHAM = 'graham'
    BELUGA = 'beluga'


# Instantiate ComputePlatform's if available
platform_instances = {
    ComputePlatformType.LOCAL: LocalPlatform()
}
if 'HELIOS' in os.environ:
    platform_instances[ComputePlatformType.HELIOS] = HeliosPlatform(server_user=os.environ['HELIOS'])
if 'GRAHAM' in os.environ:
    platform_instances[ComputePlatformType.GRAHAM] = SlurmPlatform(server_user=os.environ['GRAHAM'])
if 'BELUGA' in os.environ:
    platform_instances[ComputePlatformType.BELUGA] = SlurmPlatform(server_user=os.environ['BELUGA'])


def get_platform(p_type: ComputePlatformType):
    return platform_instances[p_type]


def list_platforms(as_str=False):
    """Lists available platforms.

    Use this instead of list(ComputePlatformType), as it would contain all *implemented* platforms, including those
    that are not available.
    """

    if as_str:
        return [p.value for p in platform_instances.keys()]
    else:
        return list(platform_instances.keys())


def get_python_env_command(script_file_local: Path, platform: str):
    env_config_file = script_file_local.parent / 'env.yaml'
    if not env_config_file.exists:
        return ['python']

    env_config = yaml.load(env_config_file)[platform]
    if env_config['conda']:
        if 'path' in env_config:
            return [env_config['conda_bin'], 'run', '-p', env_config['path'], 'python']
        else:
            return [env_config['conda_bin'], 'run', '-n', env_config['name'], 'python']
    else:
        return [env_config['path'] + '/bin/python']
