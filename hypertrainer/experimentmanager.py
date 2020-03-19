import os
import shutil
import uuid
from pathlib import Path
from typing import Iterable, Optional, List

from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.hpsearch import generate as generate_hpsearch
from hypertrainer.htplatform import HtPlatform
from hypertrainer.localplatform import LocalPlatform
from hypertrainer.slurmplatform import SlurmPlatform
from hypertrainer.task import Task
from hypertrainer.utils import yaml


class ExperimentManager:
    platform_instances = None

    @staticmethod
    def init():
        # TODO initialize from config yaml instead of env vars
        # Instantiate ComputePlatform's if available
        ExperimentManager.platform_instances = {
            ComputePlatformType.LOCAL: LocalPlatform()
        }
        if 'HTPLATFORM_WORKERS' in os.environ:
            ExperimentManager.platform_instances[ComputePlatformType.HT] \
                = HtPlatform(os.environ['HTPLATFORM_WORKERS'].split(','))
        else:
            ExperimentManager.platform_instances[ComputePlatformType.HT] \
                = HtPlatform(['localhost'])  # FIXME
        if 'GRAHAM' in os.environ:
            ExperimentManager.platform_instances[ComputePlatformType.GRAHAM] \
                = SlurmPlatform(server_user=os.environ['GRAHAM'])
        if 'BELUGA' in os.environ:
            ExperimentManager.platform_instances[ComputePlatformType.BELUGA] \
                = SlurmPlatform(server_user=os.environ['BELUGA'])

    @staticmethod
    def get_tasks(platform: Optional[ComputePlatformType] = None,
                  proj: Optional[str] = None,
                  archived=False) -> List[Task]:
        # TODO rename this function? Maybe get_filtered_tasks?
        p_list = [platform] if platform is not None else None
        ExperimentManager.update_tasks(platforms=p_list)  # TODO return tasks to avoid other db query?

        if platform is None:
            q = Task.select().where(Task.is_archived == archived)
        else:
            q = Task.select().where((Task.platform_type == platform) & (Task.is_archived == archived))

        if proj is not None:
            q = q.where(Task.project == proj)
        q = q.order_by(Task.id.desc())
        tasks = list(q)

        for t in tasks:
            ExperimentManager.monitor(t)
        return tasks

    @staticmethod
    def update_tasks(platforms: list = None):
        if platforms is None:
            platforms = ExperimentManager.list_platforms()
        for ptype in platforms:
            platform = ExperimentManager.platform_instances[ptype]
            tasks = list(Task.select().where(Task.platform_type == ptype))
            if len(tasks) == 0:
                continue
            platform.update_tasks(tasks)
            Task.bulk_update(tasks, Task.get_fields())  # FIXME updating all records everytime is heavy

    @staticmethod
    def create_tasks(platform: str, config_file: str, project: str = ''):
        # Load yaml config
        config_file_path = Path(config_file)
        yaml_config = yaml.load(config_file_path)
        yaml_config = {} if yaml_config is None else yaml_config  # handle empty config file
        name = config_file_path.stem
        # Handle hpsearch
        if 'hpsearch' in yaml_config:
            configs = generate_hpsearch(yaml_config, name)
        else:
            configs = {name: yaml_config}
        # Make tasks
        tasks = []
        ptype = ComputePlatformType(platform)
        for name, config in configs.items():
            t = Task(uuid=uuid.uuid4(),
                     project_path=str(config_file_path.parent.absolute()),
                     config=config,
                     name=name,
                     platform_type=ptype,
                     project=project)
            t.save()  # insert in database
            tasks.append(t)
        # Submit tasks
        for t in tasks:
            ExperimentManager.submit_task(t)  # TODO submit in batch to server!
        return tasks

    @staticmethod
    def submit_task(task: Task):
        task.job_id = ExperimentManager.get_platform(task).submit(task)
        task.post_submit()

    @staticmethod
    def get_tasks_by_id(task_ids: list):
        return list(Task.select().where(Task.id.in_(task_ids)))

    @staticmethod
    def resume_tasks(tasks: Iterable[Task]):
        for t in tasks:
            if not t.status.is_active():
                t.job_id = ExperimentManager.get_platform(t).submit(t, resume=True)  # TODO one bulk ssh command
                t.post_resume()

    @staticmethod
    def cancel_tasks(tasks: Iterable[Task]):
        for t in tasks:
            if t.status.is_active():
                ExperimentManager.get_platform(t).cancel(t)  # TODO one bulk ssh command
                t.post_cancel()

    @staticmethod
    def monitor(t: Task):
        # TODO rename this method 'update' or something?
        t.logs = ExperimentManager.get_platform(t).fetch_logs(t)
        t.interpret_logs()

    @staticmethod
    def archive_tasks_by_id(task_ids: list):
        Task.update(is_archived=True).where(Task.id.in_(task_ids)).execute()

    @staticmethod
    def delete_tasks_by_id(task_ids: list):
        if Task.select().where(Task.id.in_(task_ids) & (Task.is_archived == False)).count() > 0:
            raise RuntimeError('Only archived tasks can be deleted')
        for t in Task.select().where(Task.id.in_(task_ids)):
            print('Deleting', t.output_path)
            shutil.rmtree(t.output_path,
                          onerror=lambda function, path, excinfo: print('ERROR', function, path, excinfo))
        Task.delete().where(Task.id.in_(task_ids)).execute()

    @staticmethod
    def list_projects():
        return [t.project for t in Task.select(Task.project).where(Task.project != '').distinct()]

    @staticmethod
    def get_platform(task: Task):
        try:
            return ExperimentManager.platform_instances[task.platform_type]
        except KeyError:
            raise Exception(f'The platform {task.platform_type} has not been initialized.')

    @staticmethod
    def list_platforms(as_str=False):
        """Lists available platforms.

        Use this instead of list(ComputePlatformType), as it would contain all *implemented* platforms, including those
        that are not available.
        """

        if as_str:
            return [p.value for p in ExperimentManager.platform_instances.keys()]
        else:
            return list(ExperimentManager.platform_instances.keys())


experiment_manager = ExperimentManager()  # FIXME do not instantiate, it is just a namespace
experiment_manager.init()
