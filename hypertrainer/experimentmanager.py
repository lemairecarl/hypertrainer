# FIXME move this code in dashboard.py?
from hypertrainer.computeplatform import ComputePlatformType, get_platform, TaskState
from hypertrainer.task import Task


class ExperimentManager:
    @staticmethod
    def get_all_tasks():
        # FIXME more efficient db usage
        ExperimentManager.update_statuses()
        all_tasks = list(Task.select())
        return all_tasks

    @staticmethod
    def update_statuses():
        current_platforms = [ComputePlatformType.LOCAL, ComputePlatformType.HELIOS]  # FIXME dynamic
        for p in current_platforms:
            tasks = Task.select().where(Task.platform_type == p)
            job_ids = [t.job_id for t in tasks]
            statuses = get_platform(p).get_all_statuses(job_ids)
            for job_id, status in statuses.items():
                t = tasks.where(Task.job_id == job_id)
                if len(t) == 0:
                    continue
                t = t[0]  # type: Task
                if t.status.is_active():
                    t.status = status
                    t.save()

    @staticmethod
    def submit(platform: str, script_file: str, config_file: str):
        t = Task(script_file, config_file, platform_type=ComputePlatformType(platform))
        t.submit()

    @staticmethod
    def cancel_from_id(task_id):
        t = Task.get(Task.id == task_id)
        t.cancel()


experiment_manager = ExperimentManager()
