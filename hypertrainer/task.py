from pathlib import Path

from ruamel.yaml import YAML
from peewee import CharField

from hypertrainer.computeplatform import TaskState, ComputePlatformType, get_platform
from hypertrainer.db import BaseModel, EnumField
from hypertrainer.utils import TaskStatus

yaml = YAML()


class Task(BaseModel):
    job_id = CharField()
    platform = EnumField(ComputePlatformType)
    script_file = CharField()
    config_file = CharField()
    name = CharField()

    def __init__(self, script_file: str, config_file: str, job_id=None, platform_type=ComputePlatformType.LOCAL,
                 name=None, **kwargs):
        super().__init__(**kwargs)

        self.job_id = job_id  # Platform specific ID
        self.platform_type = platform_type
        self.script_file = script_file
        self.config_file = config_file

        self.config_file_path = Path(config_file)
        self.config = yaml.load(self.config_file_path)  # FIXME not in model (should be instead of file path)
        self.name = name or self.config_file_path.stem

        self.current_state = None
        self.metrics = []
        self.best_epoch = None

    @property
    def platform(self):
        return get_platform(self.platform_type)

    @property
    def status_str(self):
        return self.current_state.status.value

    @property
    def is_running(self):
        return self.current_state.status == TaskStatus.Running

    @property
    def stdout_path(self):
        path = Path(self.config['output_path']) / 'out.txt'
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def stderr_path(self):
        path = Path(self.config['output_path']) / 'err.txt'
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def monitor(self):
        if self.job_id is None:
            self.current_state = TaskState(status=TaskStatus.Waiting)
        else:
            self.current_state = self.platform.monitor(self)

    def submit(self):
        self.job_id = self.platform.submit(self)
        self.save()

    def cancel(self):
        self.platform.cancel(self)
        # self.save()  # nothing to save

    def get_output(self):
        # TODO use self.platform
        # return stdout, stderr as strings
        return self.stdout_path.read_text(), self.stderr_path.read_text()
