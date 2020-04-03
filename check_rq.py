from redis import Redis
from rq import Queue
import argparse

from hypertrainer.htplatform_worker import test_job
from hypertrainer.utils import config_context

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--queue', type=str, default='jobs')
    ap.add_argument('--msg', type=str, default='ping!')
    args = ap.parse_args()

    with config_context() as config:
        redis_port = config['ht_platform']['redis_port']
    redis_conn = Redis(port=redis_port)
    queue = Queue(name=args.queue, connection=redis_conn)
    job = queue.enqueue(test_job, args=(args.msg,))
