import os
from pathlib import Path
from time import time

import numpy as np
import pandas as pd
from peewee import CharField, IntegerField, FloatField

from hypertrainer.computeplatform import ComputePlatformType, get_platform
from hypertrainer.db import BaseModel, EnumField, YamlField, get_db
from hypertrainer.utils import TaskStatus, set_item_at_path, get_item_at_path, yaml_to_str, parse_columns


class Task(BaseModel):
    script_file = CharField()  # Relative to the scripts folder, that exists on all platforms TODO document this
    config = YamlField()
    job_id = CharField(default='')
    platform_type = EnumField(ComputePlatformType, default=ComputePlatformType.LOCAL)
    name = CharField(default='')
    status = EnumField(TaskStatus, default=TaskStatus.Unknown)
    cur_epoch = IntegerField(default=0)
    cur_iter = IntegerField(default=0)
    iter_per_epoch = IntegerField(default=0)
    epoch_duration = FloatField(default=0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.logs = {}
        self.metrics = {}
        self.total_time_remain = -1
        self.ep_time_remain = -1

    @property
    def platform(self):
        self.platform_type: ComputePlatformType  # because PyCharm is confused
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
        self.config: dict  # For helps pycharm inspection
        if 'training' not in self.config:
            self.config['training'] = {}  # FIXME generalize this (simply use output_path at config root?)
        set_item_at_path(self.config, 'training.output_path', path)
        self.save()

    def submit(self):
        self.job_id = self.platform.submit(self)
        self.save()

    def continu(self):
        self.job_id = self.platform.submit(self, continu=True)
        self.status = TaskStatus.Unknown
        self.save()

    def cancel(self):
        self.platform.cancel(self)
        self.save()

    def monitor(self):
        # Retrieve logs
        get_db().close()
        self.logs = self.platform.monitor(self)
        get_db().connect()

        # Interpret logs
        for name, log in self.logs.items():
            if name == 'progress':
                # Columns = epoch_idx, iter_idx, iter_per_epoch, unix_timestamp
                data = parse_columns(log)
                if data:
                    data = data if data[0][0].isdigit() else data[1:]  # Handle presence/absence of header
                    df = pd.DataFrame(data, columns=['ep_idx', 'iter_idx', 'iter_per_epoch', 'timestamp'])
                    df = df.astype(float).astype(int)
                    # Epochs
                    self.cur_epoch = int(df.tail(1).ep_idx)
                    epochs_times = df.groupby('ep_idx').min().timestamp.values
                    if len(epochs_times) > 1:
                        durations = epochs_times[1:] - epochs_times[:-1]
                        self.epoch_duration = np.mean(durations)  # TODO more weight to last epochs?
                        cur_ep_elapsed = time() - epochs_times[-1]
                        self.ep_time_remain = max(self.epoch_duration - cur_ep_elapsed, 0)
                        epochs_remaining = get_item_at_path(self.config, 'training.num_epochs') - self.cur_epoch - 1
                        self.total_time_remain = self.ep_time_remain + self.epoch_duration * epochs_remaining
                    # Iterations
                    self.cur_iter = int(df.tail(1).iter_idx)
                    self.iter_per_epoch = int(df.tail(1).iter_per_epoch)
                    self.save()

            elif name.startswith('metric_'):
                data = parse_columns(log)
                if data:
                    data = data if int(data[0][0]) == 0 else data[1:]  # Handle presence/absence of header
                    m_name = name.partition('_')[2]  # Example: 'd_j_trump'.partition('_') -> ('d', '_', 'j_trump')
                    if name.startswith('metric_classwise_'):
                        m_name = m_name.partition('_')[2]
                        data_arrays = {}
                        # Columns: epoch_idx, class_idx, value
                        df = pd.DataFrame(data, columns=['epoch_idx', 'class_idx', 'value'], dtype=float)
                        for class_idx, sub_df in df.groupby('class_idx'):
                            del sub_df['class_idx']
                            label = class_idx if type(class_idx) is str else str(int(class_idx))
                            data_arrays[label] = sub_df.values  # convert to numpy
                        self.metrics[m_name] = data_arrays
                    else:
                        # Columns: epoch_idx, value
                        data_array = np.array(data, dtype=np.float)
                        self.metrics[m_name] = data_array

        # Remove logs that have been interpreted
        for k in [k for k in self.logs.keys() if k.startswith('metric_') or k in {'progress'}]:
            del self.logs[k]

    def dump_config(self):
        return yaml_to_str(self.config)
