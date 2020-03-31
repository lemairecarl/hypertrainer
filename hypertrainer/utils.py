import contextlib
import fcntl
import os
import sys
import time
from enum import Enum
from functools import reduce
from itertools import chain
from pathlib import Path
from typing import Iterable, List, Dict
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
    RunFailed = 'RunFailed'  # Error occured while trying to start
    Removed = 'Removed'  # on Moab: time exceeded
    Lost = 'Lost'  # Officially lost and inactive; will not be updated
    Unknown = 'Unknown'  # Temporarily (or not) unknown. E.g. trying to contact worker

    @property
    def abbrev(self):
        return self.value[:4]

    @property
    def is_active(self):
        return self in self.active_states()

    @staticmethod
    def active_states():
        return {TaskStatus.Waiting, TaskStatus.Running, TaskStatus.Unknown}

    def __str__(self):
        return self.value


def get_python_env_command(project_path: Path, platform: str) -> List[str]:
    """Get the command to use to invoke python.

    The default is 'python', but this can be configured to use a conda env.
    """

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


class LockedError(Exception):
    pass


class PidFile(object):
    """Adapted from github.com/trbs/pid"""

    def __init__(self, path: Path):
        self.path: Path = path
        self.pidfile = None

    def try_acquire(self):
        try:
            self.__enter__()
            return True
        except LockedError:
            return False

    def release(self):
        return self.__exit__()

    def __enter__(self):
        self.pidfile = self.path.open("a+")
        try:
            fcntl.flock(self.pidfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise LockedError
        self.pidfile.seek(0)
        self.pidfile.truncate()
        self.pidfile.write(str(os.getpid()))
        self.pidfile.flush()
        self.pidfile.seek(0)
        return self

    def __exit__(self, exc_type=None, exc_value=None, exc_tb=None):
        try:
            self.pidfile.close()
        except IOError as err:
            # ok if file was just closed elsewhere
            if err.errno != 9:
                raise
        self.pidfile = None
        self.path.unlink()

    @property
    def is_locked(self):
        return self.pidfile is not None


class GpuLock(PidFile):
    def __init__(self, gpu_id):
        self.gpu_id = gpu_id
        self.path = hypertrainer_home / f'gpu_{gpu_id}.lock'
        super().__init__(self.path)


class GpuLockManager:
    def __init__(self):
        self.locks: Dict[str, GpuLock] = {}

        cuda_visible_devices_var = os.environ.get('CUDA_VISIBLE_DEVICES', None)
        if cuda_visible_devices_var not in ('', None):
            visible_devices = cuda_visible_devices_var.split(',')
            self.locks = [GpuLock(gpu_id) for gpu_id in visible_devices]

    def num_free_gpus(self) -> int:
        return sum(1 for lock in self.locks if not lock.is_locked)

    def acquire_one_gpu(self) -> GpuLock:
        """Wait for a gpu to be available, acquire it and return the GpuLock

        The GpuLock must be released when the job is done."""

        if len(self.locks) < 1:
            raise Exception('GpuLockManager: There are no visible GPUs.')

        while True:
            for gpu_lock in self.locks:
                if gpu_lock.try_acquire():
                    return gpu_lock
            print('GpuLockManager: waiting for a GPU...')
            time.sleep(2)


def get_config_file() -> Path:
    config_path = hypertrainer_home / 'config.yaml'
    if not config_path.exists():
        default_config_path = Path(__file__).parent / 'default_config.yaml'
        config_path.write_text(default_config_path.read_text())
    return config_path


@contextlib.contextmanager
def config_context():
    config_file_path = get_config_file()
    file_initialized = config_file_path.exists()
    with config_file_path.open('r+') as f:
        config = yaml.load(f) if file_initialized else {}
        yield config
        f.seek(0)
        f.truncate()
        yaml.dump(config, f)
