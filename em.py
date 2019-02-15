import argparse
from copy import deepcopy
from pathlib import Path

import numpy as np
from ruamel_yaml import YAML

from utils import set_item_at_path

ap = argparse.ArgumentParser()
ap.add_argument('input_file', type=str, help='Path to yaml file')
ap.add_argument('-s', '--hp-search', action='store_true')
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


def generate_hpsearch():
    # TODO documentation
    yaml = YAML()
    parent_file_path = Path(args.input_file)
    parent_yaml = yaml.load(parent_file_path)
    hpsearch_config = parent_yaml['hpsearch']
    
    if hpsearch_config.get('is_child', False):
        raise RuntimeError('This YAML is itself a child config generated for an hyperparameter search.')
    
    assert hpsearch_config['type'] == 'random_uniform'
    
    description = hpsearch_config['desc'] if 'desc' in hpsearch_config else 'hpsearch'
    
    for trial_idx in range(hpsearch_config['n_trials']):
        child_yaml = make_child_config(parent_yaml)
        for p in hpsearch_config['params']:
            value = generate_random_value(p)
            set_item_at_path(child_yaml, p['param'], value)
        child_file_path = parent_file_path.with_name(
            parent_file_path.stem + '_{}_{}.yaml'.format(description, trial_idx))
        yaml.dump(child_yaml, child_file_path)


if __name__ == '__main__':
    if args.hp_search:
        generate_hpsearch()
