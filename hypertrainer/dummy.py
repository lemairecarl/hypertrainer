"""
Prints a file to stdout, sleeps for some time and exits.
"""

import argparse
from pathlib import Path
from time import sleep

from ruamel.yaml import YAML

yaml = YAML()

ap = argparse.ArgumentParser()
ap.add_argument('file')
args = ap.parse_args()

config = yaml.load(Path(args.file))
out_filepath = Path(config['output_path']) / 'out.txt'
err_filepath = Path(config['output_path']) / 'err.txt'


print('Input YAML config follows:')
print(Path(args.file).read_text())

n_iter = config.get('n_iter', 20)
secs_per_iter = config.get('secs_per_iter', 1)
die_after = config.get('die_after', -1)
print('\nStarting iterations!')
for i in range(n_iter):
    if i == die_after:
        raise RuntimeError('Goodbye cruel world')
    print('Iter {}/{}'.format(i, n_iter), flush=True)
    sleep(secs_per_iter)
print('Done.')
