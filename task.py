from pathlib import Path

import pandas as pd
from dataclasses import dataclass
from ruamel_yaml import YAML

from utils import get_item_at_path

yaml = YAML()


class Task:
    def __init__(self, name: str, config):
        self.name = name
        self.config = config
        self.metrics = []
        self.best_epoch = None
        self.get_metrics()

    @staticmethod
    def from_config_file(config_file_path):
        config_file_path = Path(config_file_path)
        config_data = yaml.load(config_file_path)
        return Task(config_file_path.stem, config_data)
    
    def get_metrics(self):
        # TODO train + val
        output_path = Path(get_item_at_path(self.config, 'training.output_path'))
    
        # Loss
        losses = pd.read_csv(output_path / 'trn_losses_values.log', sep=' ', header=None, names=['ep', 'val'])
        self.metrics.append(
            Metric(name='Loss', type='line', data=losses.values)
        )
        best_epoch = losses['val'].idxmin()
        assert losses['ep'][best_epoch] == best_epoch
        self.best_epoch = best_epoch
    
        # Classwise final score
        all_scores = pd.read_csv(output_path / 'trn_classes_score.log', sep=' ', header=None, names=['ep', 'id', 'val'])
        scores = all_scores[all_scores['ep'] == best_epoch].copy()
        scores['metric'], scores['class_idx'] = scores['id'].str.split('_', 1).str
        for name, val in scores.groupby('metric'):
            self.metrics.append(
                Metric(name=name, type='bar', data=val['val'].values)
            )


@dataclass
class Metric:
    name: str
    type: str
    data: object
