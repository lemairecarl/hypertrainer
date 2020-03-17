#!/usr/bin/env python
import argparse
import socket
from multiprocessing import Process
from typing import Optional, Tuple

from redis import Redis
from rq import Connection, Worker


# Preload libraries
# TODO import library_that_you_want_preloaded


class WorkerContext:
    def __init__(self, hostname):
        self.hostname = hostname if hostname is not None else socket.gethostname()
        redis_port = 6380  # FIXME config
        self.redis_conn = Redis(port=redis_port)
        self.conn = Connection(self.redis_conn)
        self.worker_proc_pair: Optional[Tuple[Process]] = None

        print('Redis port:', redis_port)

    def __enter__(self):
        self.conn.__enter__()

        specific_queue_worker = Process(target=work, args=(self.hostname,))
        jobs_queue_worker = Process(target=work, args=('jobs',))

        specific_queue_worker.start()
        jobs_queue_worker.start()

        self.worker_proc_pair = specific_queue_worker, jobs_queue_worker

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.__exit__(exc_type, exc_val, exc_tb)

        specific_queue_worker, jobs_queue_worker = self.worker_proc_pair
        specific_queue_worker.terminate()
        jobs_queue_worker.terminate()

    def wait(self):
        specific_queue_worker, jobs_queue_worker = self.worker_proc_pair
        specific_queue_worker.join()
        jobs_queue_worker.join()


def work(queue_name):
    print('Working on queue', queue_name)
    w = Worker([queue_name], exc_handler=lambda *args: print(*args))
    w.work()


def start_worker(hostname=None):
    with WorkerContext(hostname=hostname) as c:
        c.wait()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--hostname', type=str)
    args = ap.parse_args()

    start_worker(hostname=args.hostname)
