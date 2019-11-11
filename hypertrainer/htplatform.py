import os
import time
from pathlib import Path
from typing import List

from redis import Redis
from rq import Queue

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.utils import TaskStatus
from hypertrainer.htplatform_worker import run, get_jobs_info


class HtPlatform(ComputePlatform):
    """The HT (HyperTrainer) Platform allows to send jobs to one or more Linux machines.

    Each participating worker (can be several workers per machine) consumes jobs from a global queue.
    """

    _root_dir: Path = None

    def __init__(self, worker_hostnames: List[str]):
        self.worker_hostnames = worker_hostnames

        redis_conn = Redis(port=6380)  # FIXME config
        self.jobs_queue = Queue(name='jobs', connection=redis_conn)
        self.worker_queues = {h: Queue(name=h, connection=redis_conn) for h in self.worker_hostnames}

    def submit(self, task, resume=False):
        job = self.jobs_queue.enqueue(run, job_timeout=-1, args=(
            task.id, task.script_file, task.dump_config(), task.output_path, resume))
        # At this point, we only know the rq job id. No pid since the job might have to wait.
        return job.id

    def fetch_logs(self, task, keys=None):
        return {}

    def cancel(self, task):
        pass

    def update_tasks(self, tasks):
        # TODO do not modify database here!!!
        # TODO only check requested ids
        # TODO handle continue on different host
        # TODO check for pending jobs -- need a result backend for this (e.g. redis)

        for t in tasks:
            t.status = TaskStatus.Unknown
        job_id_to_task = {t.job_id: t for t in tasks}

        info_dicts = self.get_info_dict_for_each_worker()  # TODO catch timeout
        for hostname, local_db in zip(self.worker_hostnames, info_dicts):
            for job_id in set(local_db.keys()).intersection(job_id_to_task.keys()):
                job_info = local_db[job_id]
                t = job_id_to_task[job_id]

                t.status = TaskStatus(job_info['status'])
                t.output_path = job_info['output_path']
                t.hostname = hostname

    @staticmethod
    def get_root_dir():
        if HtPlatform._root_dir is None:
            HtPlatform.setup_output_path()
        return HtPlatform._root_dir

    @staticmethod
    def setup_output_path():
        # FIXME cannot store in memory
        # Setup root output dir
        p = os.environ.get('HYPERTRAINER_OUTPUT')
        if p is None:
            HtPlatform._root_dir = Path.home() / 'hypertrainer' / 'output'
            print('Using root output dir: {}\nYou can configure this with $HYPERTRAINER_OUTPUT.'
                  .format(HtPlatform._root_dir))
        else:
            HtPlatform._root_dir = Path(p)
        HtPlatform._root_dir.mkdir(parents=True, exist_ok=True)

    def get_info_dict_for_each_worker(self):
        results = [q.enqueue(get_jobs_info).result for q in self.worker_queues]

        time.sleep(1)  # FIXME config
        if any(r is None for r in results):
            raise TimeoutError

        return results
