import argparse
from copy import deepcopy
from functools import reduce
from pathlib import Path

import numpy as np
from ruamel_yaml import YAML

ap = argparse.ArgumentParser()
ap.add_argument('input_file', type=str, help='Path to yaml file')
ap.add_argument('-s', '--hp-search', action='store_true')
args = ap.parse_args()


def get_item_with_path(obj, path, sep='.'):
    return reduce(lambda o, k: o[k], [obj] + path.split(sep))


def set_item_with_path(obj, path, value, sep='.'):
    path_tokens = path.split(sep)
    leaf_obj = reduce(lambda o, k: o[k], [obj] + path_tokens[:-1])
    leaf_obj[path_tokens[-1]] = value


def generate_random_value(p):
    v = np.random.uniform(p['lo'], p['hi'])
    if 'exponent_base' in p:
        v = p['exponent_base'] ** v
    return v


def make_child_config(yaml_data):
    child = deepcopy(yaml_data)
    child['hpsearch']['is_child'] = True
    return child


def generate_hpsearch():
    yaml = YAML()
    parent_file_path = Path(args.input_file)
    parent_yaml = yaml.load(parent_file_path)
    hpsearch_config = parent_yaml['hpsearch']
    
    if hpsearch_config['is_child']:
        raise RuntimeError('This YAML config is itself a child config for an hyperparameter search.')
    
    assert hpsearch_config['type'] == 'random_uniform'
    
    description = hpsearch_config['desc'] if 'desc' in hpsearch_config else 'hpsearch'
    
    for trial_idx in range(hpsearch_config['n_trials']):
        child_yaml = make_child_config(parent_yaml)
        for p in hpsearch_config['params']:
            value = generate_random_value(p)
            set_item_with_path(child_yaml, p['param'], value)
        child_file_path = parent_file_path.with_name(
            parent_file_path.stem + '_{}_{}.yaml'.format(description, trial_idx))
        yaml.dump(child_yaml, child_file_path)


if __name__ == '__main__':
    if args.hp_search:
        generate_hpsearch()
