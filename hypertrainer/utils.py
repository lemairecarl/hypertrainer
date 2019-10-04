import io
import os
from enum import Enum
from functools import reduce
from itertools import chain
from pathlib import Path
from typing import Iterable

from ruamel.yaml import YAML

yaml = YAML()
SCRIPTS_PATH = []


def setup_scripts_path():
    global SCRIPTS_PATH

    path_var = os.environ.get('HYPERTRAINER_PATH')
    if path_var is None:
        SCRIPTS_PATH = []
        print('$HYPERTRAINER_PATH is not set. Use it like $PATH to tell HyperTrainer where to look for files.')
    else:
        SCRIPTS_PATH = path_var.split(':')


def resolve_path(path: str) -> Path:
    if not Path(path).exists():
        for p in SCRIPTS_PATH:
            resolved_path = Path(p) / path
            if resolved_path.exists():
                return resolved_path.absolute()
        raise FileNotFoundError('Could not find \'{}\'. Have you set $HYPERTRAINER_PATH correctly?'.format(path))
    else:
        return Path(path).absolute()


def get_item_at_path(obj, path, sep='.', default=KeyError):
    """Use this method like this: `get_item_with_path(obj, 'a.b.c')` to get the item `obj['a']['b']['c']`."""
    try:
        return reduce(lambda o, k: o[k], [obj] + path.split(sep))
    except (IndexError, KeyError):
        if default is KeyError:
            raise
        else:
            return default


def set_item_at_path(obj, path, value, sep='.'):
    """The setter alternative to `get_item_with_path()`."""
    path_tokens = path.split(sep)
    leaf_obj = reduce(lambda o, k: o[k], [obj] + path_tokens[:-1])
    leaf_obj[path_tokens[-1]] = value


def parse_columns(data):
    if data.strip() == '':
        return []
    data_lines = data.strip().split('\n')
    if data_lines == ['']:
        return []
    return [l.split() for l in data_lines]


def yaml_to_str(obj):
    with io.StringIO() as stream:
        yaml.dump(obj, stream)
        return stream.getvalue()


def join_dicts(dicts: Iterable[dict]):
    return dict(chain(*[list(x.items()) for x in dicts]))


class TaskStatus(Enum):
    Waiting = 'Waiting'
    Running = 'Running'
    Finished = 'Finished'
    Cancelled = 'Cancelled'
    Crashed = 'Crashed'
    Removed = 'Removed'  # on Moab: time exceeded
    Lost = 'Lost'
    Unknown = 'Unknown'

    def is_active(self):
        return self in {TaskStatus.Waiting, TaskStatus.Running, TaskStatus.Unknown}
