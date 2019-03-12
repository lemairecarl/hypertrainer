import os
import signal
import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from functools import reduce
from pathlib import Path

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
        """Return information about the task.
        
        Methods that override this method are expected to return the following dict:
        {
            'status': TaskStatus object
            'stdout': str containing the whole stdout
            'stderr': str containing the whole stderr
            'logs': {
                'log_filename.extension': str containing the whole log,
                ...(all other logs)...
            }
        }
        Keys can be a list of dict keys, for example: ['status'], in which case a partial dict is returned. If keys is
        None, the full dict is returned.
        """
        pass

    @abstractmethod
    def cancel(self, task):
        """Cancel a task."""
        pass

    @abstractmethod
    def get_statuses(self, job_ids) -> dict:
        pass

    @abstractmethod
    def get_completion_codes(self) -> dict:
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
        self.processes[p.pid] = p
        return str(p.pid)
    
    def monitor(self, task, keys=None) -> TaskState:
        if keys is not None and (len(keys) >= 2 or 'status' not in keys):
            raise NotImplementedError
        
        p = self.processes.get(int(task.job_id), None)  # type: subprocess.Popen
        if p is None:
            return TaskState(status=TaskStatus.Lost)

        poll_result = p.poll()
        if poll_result is None:
            status = TaskStatus.Running
        else:
            if p.returncode == 0:
                status = TaskStatus.Finished
            elif p.returncode < 0:
                # Negative value: terminated by a signal
                status = TaskStatus.Cancelled
            else:
                status = TaskStatus.Crashed
        return TaskState(status=status)

    def cancel(self, task):
        os.kill(int(task.job_id), signal.SIGTERM)

    def get_statuses(self, job_ids) -> dict:
        return {}  # FIXME

    def get_completion_codes(self) -> dict:
        return {}  # FIXME


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
        job_remote_dir = '$HOME/hypertrainer/jobs/' + str(task.id)
        task.output_path = job_remote_dir
        setup_script = self.replace_variables(self.setup_template, task, submission=self.submission_template)

        completed_process = subprocess.run(['ssh', self.server_user],
                                           input=setup_script.encode(), stdout=subprocess.PIPE)
        job_id = completed_process.stdout.decode('utf-8').strip()
        return job_id

    def monitor(self, task, keys=None):
        pass

    def get_statuses(self, job_ids):
        job_ids_str = ','.join(job_ids)
        data = subprocess.run(['ssh', self.server_user, f'mdiag -j {job_ids_str} | grep $USER'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
        data_grid = self.parse_columns(data)
        statuses = {}
        for l in data_grid:
            job_id, status = l[0], l[1]
            statuses[job_id] = self.status_map[status]
        return statuses

    def get_completion_codes(self):
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
    def parse_columns(data):
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
