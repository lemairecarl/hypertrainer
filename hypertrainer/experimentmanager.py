from typing import Union

from ruamel.yaml import YAML

from hypertrainer.computeplatform import ComputePlatformType, get_platform
from hypertrainer.task import Task
from hypertrainer.db import get_db
from hypertrainer.hpsearch import generate as generate_hpsearch

yaml = YAML()


class ExperimentManager:
    @staticmethod
    def get_all_tasks():
        # NOTE: statuses are not updated here; they are requested asynchronously by the dashboard
        all_tasks = list(Task.select())
        return all_tasks

    @staticmethod
    def get_tasks(platform: ComputePlatformType):
        ExperimentManager.update_statuses(platforms=[platform])  # TODO return tasks to avoid other db query?
        tasks = Task.select().where(Task.platform_type == platform)
        for t in tasks:
            t.monitor()
        return tasks

    @staticmethod
    def update_statuses(platforms: Union[str, list] = 'all'):
        if platforms == 'all':
            platforms = [ComputePlatformType.LOCAL, ComputePlatformType.HELIOS]  # FIXME dynamic
        for ptype in platforms:
            platform = get_platform(ptype)
            tasks = Task.select().where(Task.platform_type == ptype)
            job_ids = [t.job_id for t in tasks]
            get_db().close()  # Close db since the following may take time
            statuses = platform.get_statuses(job_ids)
            for t in tasks:
                if t.status.is_active():
                    t.status = statuses[t.job_id]
                    t.save()

    @staticmethod
    def submit(platform: str, script_file: str, config_file: str):
        # Load yaml config
        config_file_path = Task.resolve_path(config_file)
        yaml_config = yaml.load(config_file_path)
        name = config_file_path.stem
        # Handle hpsearch
        if 'hpsearch' in yaml_config:
            configs = generate_hpsearch(yaml_config, name)
        else:
            configs = {name: yaml_config}
        # Make tasks
        tasks = []
        for name, config in configs.items():
            t = Task(script_file=script_file, config=config, name=name, platform_type=ComputePlatformType(platform))
            t.save()  # insert in database
            tasks.append(t)
        # Submit tasks
        for t in tasks:
            get_db().close()  # avoid deadlock
            t.submit()  # FIXME submit all at once!

    @staticmethod
    def cancel_from_id(task_id):
        if type(task_id) is str:
            t = Task.get(Task.id == task_id)
            if t.status.is_active():
                t.cancel()
        else:
            assert type(task_id) is list
            tasks = Task.select().where(Task.id.in_(task_id))
            for t in tasks:
                if t.status.is_active():
                    get_db().close()  # avoid deadlock
                    t.cancel()  # TODO one bulk ssh command

    @staticmethod
    def delete_from_id(task_id):
        if type(task_id) is str:
            t = Task.get(Task.id == task_id)  # type: Task
            t.delete_instance()
        else:
            assert type(task_id) is list
            Task.delete().where(Task.id.in_(task_id)).execute()


experiment_manager = ExperimentManager()
