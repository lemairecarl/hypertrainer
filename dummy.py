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
ap.add_argument('--sleep-secs', type=int, default=10)
args = ap.parse_args()

config = yaml.load(Path(args.file))
out_filepath = Path(config['output_path']) / 'out.txt'
err_filepath = Path(config['output_path']) / 'err.txt'
out_filepath.parent.mkdir(parents=True, exist_ok=True)
err_filepath.parent.mkdir(parents=True, exist_ok=True)

with out_filepath.open('w', newline=os.linesep) as stdout, err_filepath.open('w', newline=os.linesep) as stderr:
    print(Path(args.file).read_text(), file=stdout, flush=True)
    
    print('Sleepin {} secs'.format(args.sleep_secs), file=stderr, flush=True)
    sleep(args.sleep_secs)
    print('Done sleepin', file=stderr, flush=True)
