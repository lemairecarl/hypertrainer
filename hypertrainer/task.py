from pathlib import Path

import pandas as pd
from dataclasses import dataclass
from ruamel.yaml import YAML

from hypertrainer.computeplatform import ComputePlatformType, get_platform

yaml = YAML()


class Task:
    def __init__(self, script_file_path: Path, config_file_path: Path):
        self.metrics = []
        self.best_epoch = None
        self.task_id = None
        self.job_id = None  # Platform specific ID
        self.platform_type: ComputePlatformType = ComputePlatformType.LOCAL

        self.script_file_path: Path = script_file_path
        self.config_file_path: Path = config_file_path
        self.config = yaml.load(config_file_path)
        self.name = self.config_file_path.stem

    @property
    def platform(self):
        return get_platform(self.platform_type)

    @property
    def status_str(self):
        # TODO more efficient
        return self.platform.monitor(self)['status'].value

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

    def submit(self):
        self.job_id = self.platform.submit(self)
        self.task_id = self.platform_type.value + '_' + self.job_id

    def cancel(self):
        self.platform.cancel(self)

    def get_output(self):
        # TODO use self.platform
        # return stdout, stderr as strings
        return self.stdout_path.read_text(), self.stderr_path.read_text()
