import csv
import uuid
from pathlib import Path
from typing import Iterable, Optional, List

from tabulate import tabulate
from termcolor import colored

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.db import init_db
from hypertrainer.hpsearch import generate as generate_hpsearch
from hypertrainer.htplatform import HtPlatform, ConnectionError
from hypertrainer.localplatform import LocalPlatform
from hypertrainer.task import Task
from hypertrainer.utils import yaml, print_yaml, TaskStatus, TestState


class ExperimentManager:
    _instantiated = False

    platform_instances = None

    def __init__(self):
        if ExperimentManager._instantiated:
            raise Exception('ExperimentManager should not be instantiated manually. Use experiment_manager.')
        ExperimentManager._instantiated = True

        init_db()

        self.platform_instances = {
            ComputePlatformType.LOCAL: LocalPlatform()
        }
        if not TestState.test_mode:
            try:
                ht_platform = HtPlatform()
                self.platform_instances[ComputePlatformType.HT] = ht_platform
            except ConnectionError:
                print('WARNING: Could not instantiate HtPlatform. Is redis-server running?')

    def get_tasks(self, platform: Optional[ComputePlatformType] = None,
                  proj: Optional[str] = None,
                  archived=False,
                  descending_order=True,
                  ) -> List[Task]:
        # TODO rename this function? Maybe get_filtered_tasks?

        # Update the records (e.g. status)
        p_list = [platform] if platform is not None else None
        self.update_tasks(platforms=p_list)  # TODO return tasks to avoid other db query?

        # Get the records
        if platform is None:
            q = Task.select().where(Task.is_archived == archived)
        else:
            q = Task.select().where((Task.platform_type == platform) & (Task.is_archived == archived))
        if proj is not None:
            q = q.where(Task.project == proj)
        if descending_order:
            q = q.order_by(Task.id.desc())
        tasks = list(q)

        # Get the logs
        for t in tasks:
            try:
                self.monitor(t)
            except TimeoutError:
                t.logs = {'err': 'Timed out'}
        return tasks

    def update_tasks(self, platforms: list = None):
        if platforms is None:
            platforms = self.list_platforms()
        for ptype in platforms:
            platform = self.platform_instances[ptype]
            tasks = list(Task.select().where((Task.platform_type == ptype)
                                             & (Task.status.in_(TaskStatus.active_states()))))
            if len(tasks) == 0:
                continue
            platform.update_tasks(tasks)
            Task.bulk_update(tasks, Task.get_fields())  # FIXME updating all records everytime is heavy

    def create_tasks(self, platform: str, config_file: str, project: str = ''):
        """Create and submit tasks to the specified platform according to the config yaml file"""

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
                     project=project,
                     status=TaskStatus.Waiting)
            t.save()  # insert in database
            tasks.append(t)
        # Submit tasks
        for t in tasks:
            self._submit_task(t)  # TODO submit in batch to server!
        return tasks

    def _submit_task(self, task: Task):
        task.job_id = self.get_platform(task).submit(task)
        task.post_submit()

    def get_tasks_by_id(self, task_ids: List[int]):
        """Get the tasks records from the db"""

        return list(Task.select().where(Task.id.in_(task_ids)))

    def resume_tasks(self, tasks: Iterable[Task]):
        """Resume the non-active tasks.

        Resume the tasks from where they left off, if possible.
        """
        for t in tasks:
            if not t.status.is_active:
                t.job_id = self.get_platform(t).submit(t, resume=True)  # TODO one bulk ssh command
                t.post_resume()

    def resume_tasks_by_id(self, task_ids: List[int]):
        """Resume the non-active tasks.

        Resume the tasks from where they left off, if possible.
        """
        self.resume_tasks(self.get_tasks_by_id(task_ids))

    def cancel_tasks(self, tasks: Iterable[Task]):
        """Cancel the tasks

        Stop the execution of the tasks.
        """
        for t in tasks:
            if t.status.is_active:
                self.get_platform(t).cancel(t)  # TODO one bulk ssh command
                t.post_cancel()

    def cancel_tasks_by_id(self, task_ids: List[int]):
        """Cancel the tasks

        Stop the execution of the tasks.
        """
        self.cancel_tasks(self.get_tasks_by_id(task_ids))

    def monitor(self, t: Task):
        # TODO rename this method 'update' or something?
        t.logs = self.get_platform(t).fetch_logs(t)
        t.interpret_logs()

    def archive_tasks_by_id(self, task_ids: List[int]):
        """Archive the tasks

        Remove the tasks from the main list, but keep all their data (in db and on disk)
        """

        Task.update(is_archived=True).where(Task.id.in_(task_ids)).execute()

    def delete_tasks_by_id(self, task_ids: List[int]):
        """Delete all traces of the tasks

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
        """Print a table of the non-archived tasks"""

        tasks = self.get_tasks(descending_order=False, **kwargs)
        table = [[t.id,
                  str(t.uuid).split('-')[0],  # Only show the first part of the UUID
                  t.platform_type.abbrev,
                  t.hostname,
                  t.name,
                  t.status.abbrev] for t in tasks]
        headers = [
            'ID',
            'UUID',
            'Platf',
            'Hostname',
            'Name',
            'Stat'
        ]
        print(tabulate(table, headers=headers))

    def print_task_config(self, task_id):
        """Print the task's config yaml"""

        t = self.get_tasks_by_id([task_id])[0]
        print_yaml(t.config)

    def print_output(self, task_id):
        """Print the task's out and err logs"""

        task = self.get_tasks_by_id([task_id])[0]
        self.monitor(task)
        logs = task.logs

        print(colored('--- Begin log `out` ---', attrs=['bold']))
        print(logs.get('out', '`out` log does not exist'))
        print(colored('--- End log `out` -----', attrs=['bold']))
        print(colored('--- Begin log `err` ---', attrs=['bold']))
        print(logs.get('err', '`err` log does not exist'))
        print(colored('--- End log `err` -----', attrs=['bold']))

    def export_csv(self, filename):
        """Export the Task database as csv"""

        filepath = Path(filename)
        if filepath.exists():
            raise FileExistsError

        with filepath.open('w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)

            # Write header
            field_names = next(Task.select().dicts().iterator()).keys()
            csv_writer.writerow(field_names)

            # Write data
            for task_tuple in Task.select().tuples().iterator():
                csv_writer.writerow(task_tuple)

    def export_yaml(self, filename):
        """Export the Task database as yaml"""

        filepath = Path(filename)
        if filepath.exists():
            raise FileExistsError

        task_dicts = list(Task.select().dicts())  # TODO write on the fly instead?

        with filepath.open('w') as f:
            yaml.dump(task_dicts, f)


experiment_manager = ExperimentManager()
