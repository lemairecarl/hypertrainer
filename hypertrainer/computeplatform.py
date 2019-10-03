from abc import ABC, abstractmethod


class ComputePlatform(ABC):
    @abstractmethod
    def submit(self, task, continu=False) -> str:
        """Submit a task and return the plaform specific task id.

        If continu=True, run script in already-existing output path.

        Note: since 'continue' is a keyword in Python, I had to choose something else.
        """
        pass

    @abstractmethod
    def fetch_logs(self, task, keys=None):
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
