import io
from enum import Enum
from functools import reduce
from itertools import chain
from pathlib import Path
from typing import Iterable

from ruamel.yaml import YAML

yaml = YAML()


hypertrainer_home = Path.home() / 'hypertrainer'


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


def deep_assert_equal(a, b, exclude_keys):
    """For asserting partial equality between yaml config objects"""

    if isinstance(a, dict):
        keys = set(a.keys()).union(set(b.keys()))
        for k in keys:
            if k in exclude_keys:
                continue
            else:
                assert k in a
                assert k in b
            deep_assert_equal(a[k], b[k], exclude_keys)
    elif isinstance(a, list):
        assert len(a) == len(b)
        for i in range(len(a)):
            deep_assert_equal(a[i], b[i], exclude_keys)
    else:
        assert a == b


class TaskStatus(Enum):
    Waiting = 'Waiting'
    Running = 'Running'
    Finished = 'Finished'
    Cancelled = 'Cancelled'
    Crashed = 'Crashed'
    Removed = 'Removed'  # on Moab: time exceeded
    Lost = 'Lost'
    Unknown = 'Unknown'

    @property
    def abbrev(self):
        return self.value[:4]

    @property
    def active_states(self):
        return {TaskStatus.Waiting, TaskStatus.Running, TaskStatus.Unknown}

    def is_active(self):
        return self in self.active_states
