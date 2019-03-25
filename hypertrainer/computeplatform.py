import os
import signal
import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from glob import glob
import tempfile

from dataclasses import dataclass

from hypertrainer.utils import TaskStatus


@dataclass
class TaskState:
    status: TaskStatus


class ComputePlatform(ABC):
    @abstractmethod
    def submit(self, task) -> str:
        """Submit a task and return the plaform specific task id."""
        pass
    
    @abstractmethod
    def monitor(self, task, keys=None) -> TaskState:
        """Return a dict of logs.

        Example: {
            'stdout': '...',
            'stderr': '...',
            'trn_classes_score': '...',
            ...
        }
        """
        pass

    @abstractmethod
    def cancel(self, task):
        """Cancel a task."""
        pass

    @abstractmethod
    def get_statuses(self, job_ids) -> dict:
        pass


class LocalPlatform(ComputePlatform):
    def __init__(self):
        self.processes = {}
    
    def submit(self, task):
        p = subprocess.Popen(['python', task.script_file, task.config_file],
                             stdout=task.stdout_path.open(mode='w'),
                             stderr=task.stderr_path.open(mode='w'),
                             cwd=os.path.dirname(os.path.realpath(__file__)),
                             universal_newlines=True)
        job_id = str(p.pid)
        self.processes[job_id] = p
        return job_id
    
    def monitor(self, task, keys=None) -> TaskState:
        raise NotImplementedError

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


class HeliosPlatform(ComputePlatform):
    status_map = {
        'Defer': TaskStatus.Waiting,
        'Idle': TaskStatus.Waiting,
        'Running': TaskStatus.Running,
        'Canceling': TaskStatus.Cancelled,
        'Complete': TaskStatus.Finished
    }

    def __init__(self, server_user='lemc2220@helios.calculquebec.ca'):
        self.server_user = server_user
        self.submission_template = Path('sample/moab_template.sh').read_text()
        self.setup_template = Path('sample/moab_setup.sh').read_text()

    def submit(self, task):
        job_remote_dir = self._make_job_path(task)
        task.output_path = job_remote_dir
        setup_script = self.replace_variables(self.setup_template, task, submission=self.submission_template)

        completed_process = subprocess.run(['ssh', self.server_user],
                                           input=setup_script.encode(), stdout=subprocess.PIPE)
        job_id = completed_process.stdout.decode('utf-8').strip()
        return job_id

    def monitor(self, task, keys=None):
        logs = {}
        with tempfile.TemporaryDirectory() as tmpdir:
            # Get all .txt, .log files in output path
            subprocess.run(['scp', self.server_user + ':' + self._make_job_path(task) + '/*.{log,txt}', tmpdir])
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
        data_grid = self.parse_columns(data)
        statuses = {}
        for l in data_grid:
            job_id, status = l[0], l[1]
            statuses[job_id] = self.status_map[status]
        return statuses

    def _get_completion_codes(self):
        data = subprocess.run(['ssh', self.server_user, f'showq -u $USER -c | grep $USER'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
        data_grid = self.parse_columns(data)
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
    def parse_columns(data):
        if data.strip() == '':
            return []
        data_lines = data.strip().split('\n')
        return [l.split() for l in data_lines]

    @staticmethod
    def replace_variables(input_text, task, **kwargs):
        key_value_map = [
            ('$HYPERTRAINER_SUBMISSION', kwargs.get('submission', '')),
            ('$HYPERTRAINER_NAME', task.name),
            ('$HYPERTRAINER_OUTFILE', task.output_path + '/out.txt'),
            ('$HYPERTRAINER_ERRFILE', task.output_path + '/err.txt'),
            ('$HYPERTRAINER_JOB_DIR', task.output_path),
            ('$HYPERTRAINER_SCRIPT', f'$HOME/hypertrainer/{task.script_file}'),
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


platform_instances = {
    ComputePlatformType.LOCAL: LocalPlatform(),
    ComputePlatformType.HELIOS: HeliosPlatform()
}


def get_platform(p_type: ComputePlatformType):
    return platform_instances[p_type]
