import io
import sys
from enum import Enum
from functools import reduce
from itertools import chain
from pathlib import Path
from typing import Iterable, List
from uuid import UUID

from ruamel.yaml import YAML, StringIO


class TestState:
    test_mode = False
    data = None


yaml = YAML()
yaml.representer.add_representer(UUID, lambda dumper, uuid: dumper.represent_data(str(uuid)))
yaml.representer.add_multi_representer(Enum, lambda dumper, enum: dumper.represent_data(str(enum)))
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
    # with io.StringIO() as stream:
    stream = StringIO()
    yaml.dump(obj, stream)
    return stream.getvalue()


def print_yaml(obj):
    yaml.dump(obj, sys.stdout)


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
    RunFailed = 'RunFailed'
    Removed = 'Removed'  # on Moab: time exceeded
    Lost = 'Lost'
    Unknown = 'Unknown'

    status_abbrev = {
        'Waiting': 'Wait',
        'Running': 'Runn',
        'Finished': 'Fini',
        'Cancelled': 'Canc',
        'Crashed': 'Cras',
        'RunFailed': 'RuFa',
        'Removed': 'Remo',
        'Lost': 'Lost',
        'Unknown': 'Unkn'
    }

    @property
    def abbrev(self):
        return self.status_abbrev[self.value]

    @property
    def active_states(self):
        return {TaskStatus.Waiting, TaskStatus.Running, TaskStatus.Unknown}

    def is_active(self):
        return self in self.active_states

    def __str__(self):
        return self.value


def get_python_env_command(project_path: Path, platform: str) -> List[str]:
    """Get the command to use to invoke python.

    The default is 'python', but this can be configured to use a conda env.
    """

    # TODO move this in common file (it's used by htplatform_worker.py)
    default_interpreter = ['python']

    env_config_file = project_path / 'env.yaml'
    if not env_config_file.exists():
        return default_interpreter

    env_configs = yaml.load(env_config_file)
    if env_configs is None or platform not in env_configs:
        return default_interpreter

    env_config = env_configs[platform]
    if env_config['conda']:
        if 'path' in env_config:
            return [env_config['conda_bin'], 'run', '-p', env_config['path'], 'python']
        else:
            return [env_config['conda_bin'], 'run', '-n', env_config['name'], 'python']
    else:
        return [env_config['path'] + '/bin/python']
