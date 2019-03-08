# FIXME move this code in dashboard.py?
from hypertrainer.computeplatform import ComputePlatformType
from hypertrainer.task import Task


class ExperimentManager:
    @staticmethod
    def get_all_tasks():
        all_tasks = list(Task.select())
        for t in all_tasks:
            t.monitor()
        return all_tasks

    @staticmethod
    def submit(platform: str, script_file: str, config_file: str):
        t = Task(script_file, config_file, platform_type=ComputePlatformType(platform))
        t.submit()

    @staticmethod
    def cancel_from_id(task_id):
        t = Task.get(Task.id == task_id)
        t.cancel()


experiment_manager = ExperimentManager()
