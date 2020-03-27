#!/usr/bin/env python
import argparse
import socket
from multiprocessing import Process
from typing import List

from redis import Redis
from rq import Connection, Worker
from rq.worker import StopRequested


# Preload libraries
# TODO import library_that_you_want_preloaded


class WorkerContext:
    def __init__(self, hostname, num_workers=1):
        self.hostname = hostname if hostname is not None else socket.gethostname()
        redis_port = 6380  # FIXME config
        self.redis_conn = Redis(port=redis_port)
        self.conn = Connection(self.redis_conn)

        self.worker_processes: List[Process] = []
        self.num_workers = num_workers

        print('Redis port:', redis_port)

    def __enter__(self):
        self.conn.__enter__()

        self.worker_processes.append(Process(target=work, args=(self.hostname,)))  # Worker specific queue
        self.worker_processes += [Process(target=work, args=('jobs',)) for _ in range(self.num_workers)]

        for w in self.worker_processes:
            w.start()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.__exit__(exc_type, exc_val, exc_tb)

        for w in self.worker_processes:
            w.terminate()

    def wait(self):
        for w in self.worker_processes:
            w.join()


def work(queue_name):
    # NOTE: Executed in a separate process. This affects print and logging.

    print('Working on queue', queue_name)
    w = Worker([queue_name])
    try:
        w.work()
    except StopRequested:
        print('StopRequested')
        pass


def start_worker(**kwargs):
    with WorkerContext(**kwargs) as c:
        c.wait()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--hostname', type=str)
    ap.add_argument('--workers', type=int, default=1)
    args = ap.parse_args()

    start_worker(hostname=args.hostname, num_workers=args.workers)
