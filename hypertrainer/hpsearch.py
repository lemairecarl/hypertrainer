import argparse
from copy import deepcopy
from pathlib import Path

import numpy as np
from ruamel.yaml import YAML

from hypertrainer.utils import set_item_at_path

yaml = YAML()

ap = argparse.ArgumentParser()
ap.add_argument('input_file', type=str, help='Path to yaml file')
args = ap.parse_args()


def generate_random_value(p):
    # TODO documentation
    v = np.random.uniform(p['lo'], p['hi'])
    if 'exponent_base' in p:
        v = p['exponent_base'] ** v
    return v


def make_child_config(yaml_data):
    # TODO documentation
    child = deepcopy(yaml_data)
    child['hpsearch'].insert(0, 'is_child', True, comment='This YAML was generated using the config below')
    return child


def generate(parent_yaml, parent_name):
    """Generate child YAML configs as a dict {name: yaml_object}"""

    # TODO documentation
    hpsearch_config = parent_yaml['hpsearch']
    
    if hpsearch_config.get('is_child', False):
        raise RuntimeError('This YAML is itself a child config generated for an hyperparameter search.')
    
    assert hpsearch_config['type'] == 'random_uniform'
    
    description = hpsearch_config['desc'] if 'desc' in hpsearch_config else 'hpsearch'
    child_configs = {}

    for trial_idx in range(hpsearch_config['n_trials']):
        child_yaml = make_child_config(parent_yaml)
        for p in hpsearch_config['params']:
            value = generate_random_value(p)
            set_item_at_path(child_yaml, p['param'], value)
        name = parent_name + '_{}_{}'.format(description, trial_idx)
        child_configs[name] = child_yaml

    return child_configs


def write_to_file(child_configs, parent_file_path):
    for name, child_yaml in child_configs.items():
        child_file_path = parent_file_path.with_name(name + '.yaml')
        yaml.dump(child_yaml, child_file_path)


if __name__ == '__main__':
    parent_file_path = Path(args.input_file)
    parent_yaml = yaml.load(parent_file_path)
    child_configs = generate(parent_yaml, parent_file_path.stem)
    write_to_file(child_configs, parent_file_path)
