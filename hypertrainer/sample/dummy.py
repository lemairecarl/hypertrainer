"""
Prints a file to stdout, sleeps for some time and exits.
"""

import argparse
from pathlib import Path
from random import random
from time import sleep, time

from ruamel.yaml import YAML

yaml = YAML()

ap = argparse.ArgumentParser()
ap.add_argument('file')
args = ap.parse_args()

config = yaml.load(Path(args.file))
output_path = Path(config['training']['output_path'])
iterations_log = output_path / 'progress.log'
loss_log = output_path / 'metric_loss.log'

print('Input YAML config follows:')
print(Path(args.file).read_text())

n_epochs = config['training'].get('num_epochs', 1)
n_iter = config.get('n_iter', 20)
secs_per_iter = config.get('secs_per_iter', 1)
die_after = config.get('die_after', -1)
print('\nStarting iterations!')

with iterations_log.open('a', buffering=1) as iter_log_file, loss_log.open('a', buffering=1) as loss_file:
    for ep_idx in range(n_epochs):
        for i in range(n_iter):
            iter_log_file.write('{}\t{}\t{}\t{}\n'.format(ep_idx, i, n_iter, time()))

            if i == die_after:
                raise RuntimeError('Goodbye cruel world')
            print('Iter {}/{}'.format(i, n_iter), flush=True)
            sleep(secs_per_iter)

        loss_file.write('{}\t{}\n'.format(ep_idx, random()))

print('Done.')
