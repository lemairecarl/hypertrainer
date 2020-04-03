import subprocess

from hypertrainer.utils import config_context

with config_context() as config:
    redis_port = config['ht_platform']['redis_port']

subprocess.run(['redis-server', '--port', str(redis_port)])
