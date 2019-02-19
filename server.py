import time
import os
from pathlib import Path
from collections import defaultdict

import visdom

from task import Task
from utils import get_item_at_path, make_info_tables


CONFIGS_PATH = Path(os.environ['EM_CONFIGS_PATH'])
INFO_FIELDS = ['global.model_name', 'training.output_path', 'training.num_epochs']


class Server(object):
    def __init__(self):
        self.vis = visdom.Visdom()
        self.tasks = []
        
        if not self.vis.check_connection():
            raise RuntimeError('A visdom server must be running. Please run `visdom` in a terminal.')
    
    def refresh_tasks(self):
        """
        TODO documentation
        :return: a list of Task objects.
        """
        
        self.tasks.clear()
        # Iterate on yaml files
        for config_file_path in CONFIGS_PATH.glob('*.yaml'):
            self.tasks.append(Task.from_config_file(config_file_path))
        
        self.add_suffixes_to_parent_configs()
    
    def show_task_info(self, task):
        info = [(field_path, get_item_at_path(task.config, field_path)) for field_path in INFO_FIELDS]
        hp_params = [x['param'] for x in task.config['hpsearch']['params']]
        hpinfo = [(field_path, get_item_at_path(task.config, field_path)) for field_path in hp_params]
        if not get_item_at_path(task.config, 'hpsearch.is_child', default=False):
            hpinfo.insert(0, ('(Parent config)', ''))
        all_info = {'Info': info, 'Hyperparameter search': hpinfo}
        self.vis.text(make_info_tables(all_info), win='info', env=task.name)
    
    def plot_task_metrics(self, task):
        for m in task.metrics:
            if m.type == 'line':
                self.vis.line(Y=m.data[:, 1], X=m.data[:, 0],
                              win=m.name, env=task.name, opts=dict(title=m.name))
            elif m.type == 'bar':
                rn = [str(i) for i in range(len(m.data))]
                title = m.name.capitalize() + ' for epoch ' + str(task.best_epoch)
                self.vis.bar(m.data,
                             win=m.name, env=task.name, opts=dict(title=title, rownames=rn))
    
    def main_loop(self):
        print('Experiment Manager Server is running.')
        while True:
            self.refresh_tasks()
            for task in self.tasks:
                self.show_task_info(task)
                self.plot_task_metrics(task)
            
            time.sleep(2 * 60)
            
    def add_suffixes_to_parent_configs(self):
        # needed because of how the visdom UI works
        prefix_map = defaultdict(lambda: (999, None))
        for task in self.tasks:
            name_tokens = task.name.split('_')
            if len(name_tokens) < prefix_map[name_tokens[0]][0]:
                prefix_map[name_tokens[0]] = (len(name_tokens), task)
        for n, task in prefix_map.values():
            task.name += '_main'


if __name__ == '__main__':
    s = Server()
    s.main_loop()
