import os
from pathlib import Path

from ruamel.yaml import YAML
from peewee import CharField, IntegerField

from hypertrainer.computeplatform import ComputePlatformType, get_platform
from hypertrainer.db import BaseModel, EnumField, YamlField
from hypertrainer.utils import TaskStatus, set_item_at_path, get_item_at_path, yaml_to_str

yaml = YAML()


# Setup scripts dir
SCRIPTS_DIR = os.environ.get('HYPERTRAINER_SCRIPTS')
if SCRIPTS_DIR is None:
    SCRIPTS_DIR = Path.home() / 'hypertrainer' / 'scripts'
    print('Using root scripts dir: {}\nYou can configure this with $HYPERTRAINER_SCRIPTS.'.format(SCRIPTS_DIR))
else:
    SCRIPTS_DIR = Path(SCRIPTS_DIR)
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)



class Task(BaseModel):
    job_id = CharField()
    platform_type = EnumField(ComputePlatformType)
    script_file = CharField()  # Relative to the scripts folder, that exists on all platforms TODO document this
    config = YamlField()
    name = CharField()
    status = EnumField(TaskStatus)
    cur_epoch = IntegerField()
    cur_iter = IntegerField()

    def __init__(self, script_file: str, config, job_id='', platform_type=ComputePlatformType.LOCAL,
                 name=None, status=TaskStatus.Unknown, cur_epoch=0, cur_iter=0, **kwargs):
        super().__init__(**kwargs)

        self.job_id = job_id  # Platform specific ID
        self.platform_type = platform_type
        self.script_file = script_file
        self.status = status
        self.cur_epoch = cur_epoch
        self.cur_iter = cur_iter

        if type(config) is str:
            config_file_path = self.resolve_path(config)
            self.config = yaml.load(config_file_path)
            self.name = config_file_path.stem
            self.save()  # insert in database
        else:
            self.config = config
            self.name = name

        self.logs = {}

    @property
    def platform(self):
        return get_platform(self.platform_type)

    @property
    def is_running(self):
        return self.status == TaskStatus.Running

    @property
    def stdout_path(self):
        return Path(self.output_path) / 'out.txt'

    @property
    def stderr_path(self):
        return Path(self.output_path) / 'err.txt'

    @property
    def output_path(self) -> str:
        return get_item_at_path(self.config, 'training.output_path')

    @output_path.setter
    def output_path(self, path: str):
        set_item_at_path(self.config, 'training.output_path', path)
        self.save()

    def submit(self):
        self.job_id = self.platform.submit(self)
        self.save()

    def cancel(self):
        self.platform.cancel(self)
        self.save()

    def monitor(self):
        self.logs = self.platform.monitor(self)

        # Update cur_epoch
        if 'epochs' in self.logs:
            lines = self.logs['epochs'].strip().split('\n')
            if len(lines) > 0:
                ep_idx, timestamp = lines[-1].split()
                self.cur_epoch = int(ep_idx)
                self.save()

    def dump_config(self):
        return yaml_to_str(self.config, yaml)

    @staticmethod
    def resolve_path(path: str) -> Path:
        if not Path(path).exists():
            resolved_path = SCRIPTS_DIR / path
            if not resolved_path.exists():
                raise FileNotFoundError('Could not find {}'.format(path))
            return resolved_path
        else:
            return Path(path)
