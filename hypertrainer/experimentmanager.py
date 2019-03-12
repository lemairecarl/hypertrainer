# FIXME move this code in dashboard.py?
from hypertrainer.computeplatform import ComputePlatformType, get_platform, TaskState
from hypertrainer.task import Task
from hypertrainer.utils import TaskStatus


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
        for ptype in current_platforms:
            platform = get_platform(ptype)
            tasks = Task.select().where(Task.platform_type == ptype)
            job_ids = [t.job_id for t in tasks]
            statuses = platform.get_statuses(job_ids)
            ccodes = platform.get_completion_codes()  # TODO merge two calls into one get_statuses?
            for t in tasks:
                if t.status.is_active():
                    if t.job_id in ccodes:
                        # Job just completed
                        if ccodes[t.job_id] == 0:
                            t.status = TaskStatus.Finished
                        else:
                            t.status = TaskStatus.Crashed
                    else:
                        # Job still active (or lost)
                        if t.job_id in statuses:
                            t.status = statuses[t.job_id]
                        else:
                            t.status = TaskStatus.Lost  # Job not found
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
