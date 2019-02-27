import os
import signal
import subprocess
from abc import ABC, abstractmethod

from hypertrainer.utils import TaskStatus


class ComputePlatform(ABC):
    name = NotImplemented  # This must be overridden
    
    @abstractmethod
    def submit(self, task):
        """Submit a task and return the plaform specific task id."""
        pass
    
    @abstractmethod
    def monitor(self, task, keys=None):
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


class LocalPlatform(ComputePlatform):
    name = 'local'
    
    def __init__(self):
        self.processes = {}
    
    def submit(self, task):
        p = subprocess.Popen(['python', str(task.script_file_path), str(task.config_file_path)],
                             stdout=task.stdout_path.open(mode='w'),
                             stderr=task.stderr_path.open(mode='w'),
                             cwd=os.path.dirname(os.path.realpath(__file__)),
                             universal_newlines=True)
        self.processes[p.pid] = p
        return str(p.pid)
    
    def monitor(self, task, keys=None):
        if keys is not None and (len(keys) >= 2 or 'status' not in keys):
            raise NotImplementedError
        
        p = self.processes[int(task.job_id)]  # type: subprocess.Popen
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
        return {'status': status}

    def cancel(self, task):
        os.kill(int(task.job_id), signal.SIGTERM)
