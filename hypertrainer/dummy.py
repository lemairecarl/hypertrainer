"""
Prints a file to stdout, sleeps for some time and exits.
"""

from pathlib import Path
import os
from time import sleep
import argparse

from ruamel_yaml import YAML

yaml = YAML()

ap = argparse.ArgumentParser()
ap.add_argument('file')
args = ap.parse_args()

config = yaml.load(Path(args.file))
out_filepath = Path(config['output_path']) / 'out.txt'
err_filepath = Path(config['output_path']) / 'err.txt'
out_filepath.parent.mkdir(parents=True, exist_ok=True)
err_filepath.parent.mkdir(parents=True, exist_ok=True)

with out_filepath.open('w', newline=os.linesep) as stdout, err_filepath.open('w', newline=os.linesep) as stderr:
    print('Input YAML config follows:', file=stdout)
    print(Path(args.file).read_text(), file=stdout)
    
    n_iter = config.get('n_iter', 30)
    secs_per_iter = config.get('secs_per_iter', 1)
    die_after = config.get('die_after', -1)
    for i in range(n_iter):
        if i == die_after:
            raise RuntimeError('Adieu monde cruel')
        print('Iter {}/{}'.format(i, n_iter), file=stderr, flush=True)
        sleep(secs_per_iter)
    print('Done.', file=stderr)
