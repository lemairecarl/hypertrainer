import io
from enum import Enum
from functools import reduce

from ruamel.yaml import YAML

yaml = YAML()


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


class TaskStatus(Enum):
    Waiting = 'Waiting'
    Running = 'Running'
    Finished = 'Finished'
    Cancelled = 'Cancelled'
    Crashed = 'Crashed'
    Lost = 'Lost'
    Unknown = 'Unknown'

    def is_active(self):
        return self in {TaskStatus.Waiting, TaskStatus.Running, TaskStatus.Unknown}
