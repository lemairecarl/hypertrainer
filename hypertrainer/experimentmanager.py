import os
import uuid
from pathlib import Path
from typing import Iterable, Optional, List

from tabulate import tabulate

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.hpsearch import generate as generate_hpsearch
from hypertrainer.htplatform import HtPlatform
from hypertrainer.localplatform import LocalPlatform
from hypertrainer.slurmplatform import SlurmPlatform
from hypertrainer.task import Task
from hypertrainer.utils import yaml


class ExperimentManager:
    _instantiated = False

    platform_instances = None

    def __init__(self):
        if ExperimentManager._instantiated:
            raise Exception('ExperimentManager should not be instantiated manually. Use experiment_manager.')
        ExperimentManager._instantiated = True

        # TODO initialize from config yaml instead of env vars
        # Instantiate ComputePlatform's if available
        self.platform_instances = {
            ComputePlatformType.LOCAL: LocalPlatform()
        }
        if 'HTPLATFORM_WORKERS' in os.environ:
            self.platform_instances[ComputePlatformType.HT] \
                = HtPlatform(os.environ['HTPLATFORM_WORKERS'].split(','))
        else:
            self.platform_instances[ComputePlatformType.HT] \
                = HtPlatform(['localhost'])  # FIXME
        if 'GRAHAM' in os.environ:
            self.platform_instances[ComputePlatformType.GRAHAM] \
                = SlurmPlatform(server_user=os.environ['GRAHAM'])
        if 'BELUGA' in os.environ:
            self.platform_instances[ComputePlatformType.BELUGA] \
                = SlurmPlatform(server_user=os.environ['BELUGA'])

    def get_tasks(self, platform: Optional[ComputePlatformType] = None,
                  proj: Optional[str] = None,
                  archived=False,
                  descending_order=True,
                  ) -> List[Task]:
        # TODO rename this function? Maybe get_filtered_tasks?
        p_list = [platform] if platform is not None else None
        self.update_tasks(platforms=p_list)  # TODO return tasks to avoid other db query?

        if platform is None:
            q = Task.select().where(Task.is_archived == archived)
        else:
            q = Task.select().where((Task.platform_type == platform) & (Task.is_archived == archived))

        if proj is not None:
            q = q.where(Task.project == proj)
        if descending_order:
            q = q.order_by(Task.id.desc())
        tasks = list(q)

        for t in tasks:
            self.monitor(t)
        return tasks

    def update_tasks(self, platforms: list = None):
        if platforms is None:
            platforms = self.list_platforms()
        for ptype in platforms:
            platform = self.platform_instances[ptype]
            tasks = list(Task.select().where(Task.platform_type == ptype))
            if len(tasks) == 0:
                continue
            platform.update_tasks(tasks)
            Task.bulk_update(tasks, Task.get_fields())  # FIXME updating all records everytime is heavy

    def create_tasks(self, platform: str, config_file: str, project: str = ''):
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
            self.submit_task(t)  # TODO submit in batch to server!
        return tasks

    def submit_task(self, task: Task):
        task.job_id = self.get_platform(task).submit(task)
        task.post_submit()

    def get_tasks_by_id(self, task_ids: List[int]):
        return list(Task.select().where(Task.id.in_(task_ids)))

    def resume_tasks(self, tasks: Iterable[Task]):
        for t in tasks:
            if not t.status.is_active():
                t.job_id = self.get_platform(t).submit(t, resume=True)  # TODO one bulk ssh command
                t.post_resume()

    def cancel_tasks(self, tasks: Iterable[Task]):
        for t in tasks:
            if t.status.is_active():
                self.get_platform(t).cancel(t)  # TODO one bulk ssh command
                t.post_cancel()

    def cancel_tasks_by_id(self, task_ids: List[int]):
        self.cancel_tasks(self.get_tasks_by_id(task_ids))

    def monitor(self, t: Task):
        # TODO rename this method 'update' or something?
        t.logs = self.get_platform(t).fetch_logs(t)
        t.interpret_logs()

    def archive_tasks_by_id(self, task_ids: List[int]):
        Task.update(is_archived=True).where(Task.id.in_(task_ids)).execute()

    def delete_tasks_by_id(self, task_ids: List[int]):
        """Delete all traces of the task.

        This method deletes the task from the server database and the worker database. It also deletes the output path.
        """

        if Task.select().where(Task.id.in_(task_ids) & (Task.is_archived == False)).count() > 0:
            raise RuntimeError('Only archived tasks can be deleted')

        # Ask the platform to delete each task (on the corresponding worker)
        for t in Task.select().where(Task.id.in_(task_ids)):
            self.get_platform(t).delete(t)

        # Delete the task from the server database
        Task.delete().where(Task.id.in_(task_ids)).execute()

    def list_projects(self):
        return [t.project for t in Task.select(Task.project).where(Task.project != '').distinct()]

    def get_platform(self, task: Task) -> ComputePlatform:
        try:
            return self.platform_instances[task.platform_type]
        except KeyError:
            raise Exception(f'The platform {task.platform_type} has not been initialized.')

    def list_platforms(self, as_str=False):
        """Lists available platforms.

        Use this instead of list(ComputePlatformType), as it would contain all *implemented* platforms, including those
        that are not available.
        """

        if as_str:
            return [p.value for p in self.platform_instances.keys()]
        else:
            return list(self.platform_instances.keys())

    def print_tasks(self, **kwargs):
        """Print tasks list"""
        tasks = self.get_tasks(descending_order=False, **kwargs)
        table = [[t.id,
                  #t.uuid,
                  t.job_id,
                  t.hostname,
                  t.platform_type.abbrev,
                  t.name,
                  t.status.abbrev] for t in tasks]
        headers = [
            'ID',
            #'UUID',
            'JobID',
            'Hostname',
            'Platf',
            'Name',
            'Stat'
        ]
        print(tabulate(table, headers=headers))


experiment_manager = ExperimentManager()
