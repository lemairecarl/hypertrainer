#!/usr/bin/env python
import socket
from multiprocessing import Process

from redis import Redis
from rq import Connection, Worker

# Preload libraries
# TODO import library_that_you_want_preloaded


def work(queue_name):
    w = Worker([queue_name])
    w.work()


if __name__ == '__main__':
    hostname = socket.gethostname()
    print('Hostname:', hostname)

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
