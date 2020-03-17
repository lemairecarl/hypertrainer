from abc import ABC, abstractmethod


class ComputePlatform(ABC):
    @abstractmethod
    def submit(self, task, resume=False) -> str:
        """Setup and submit a task and return the plaform specific task id.

        If task.output_path is not already set, this method must set it (and
        make sure the dir is created).
        If resume=True, run script in already-existing output path.
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
        """Cancel a task.

        Returns nothing.
        """
        pass

    @abstractmethod
    def update_tasks(self, tasks):
        """Request the platform to update the specified tasks.

        The main purpose of this method is to update the tasks' status. However, other fields of the tasks may
        also be updated.

        Returns nothing.
        """
        pass
