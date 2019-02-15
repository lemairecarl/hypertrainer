import time
import os
from pathlib import Path
from collections import namedtuple

import numpy as np
from ruamel_yaml import YAML
import visdom

from utils import get_item_at_path

yaml = YAML()

CONFIGS_PATH = Path(os.environ['EM_CONFIGS_PATH'])

Run = namedtuple('Run', ['name', 'metrics'])
Metric = namedtuple('Metric', ['name', 'data'])


class Server(object):
    def __init__(self):
        self.vis = visdom.Visdom()
    
    @staticmethod
    def get_metrics(output_path: Path):
        # TODO train + val
        metrics = []
        
        # Loss
        losses = np.loadtxt(str(output_path / 'trn_losses_values.log'), delimiter=' ')
        metrics.append(
            Metric('Loss', losses)
        )
        
        # TODO other metrics
        return metrics
    
    def get_runs(self):
        """
        
        :return: a list of Run objects.
        """
        
        # Iterate on yaml files
        runs = []
        for config_file_path in CONFIGS_PATH.glob('*.yaml'):
            config_file_path = Path(config_file_path)
            config_data = yaml.load(config_file_path)
            output_path = Path(get_item_at_path(config_data, 'training.output_path'))
            runs.append(
                Run(config_file_path.stem, self.get_metrics(output_path))
            )
        return runs
    
    def main_loop(self):
        while True:
            for r in self.get_runs():
                for m in r.metrics:
                    self.vis.line(Y=m.data[:, 1], X=m.data[:, 0], win=m.name, env=r.name, opts=dict(title=m.name))
            
            time.sleep(60)
    
    
if __name__ == '__main__':
    s = Server()
    s.main_loop()
