#!/usr/bin/env python
import argparse
import socket
from multiprocessing import Process

from redis import Redis
from rq import Connection, Worker


# Preload libraries
# TODO import library_that_you_want_preloaded


def work(queue_name):
    print('Working on queue', queue_name)
    w = Worker([queue_name], exc_handler=lambda *args: print(*args))
    w.work()


def start_worker(hostname=None):
    hostname = hostname if hostname is not None else socket.gethostname()
    redis_port = 6380  # FIXME config
    print('Redis port:', redis_port)
    redis_conn = Redis(port=redis_port)
    with Connection(redis_conn):
        specific_queue_worker = Process(target=work, args=(hostname,))
        jobs_queue_worker = Process(target=work, args=('jobs',))

        specific_queue_worker.start()
        jobs_queue_worker.start()

        specific_queue_worker.join()
        jobs_queue_worker.join()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--hostname', type=str)
    args = ap.parse_args()

    start_worker(hostname=args.hostname)
