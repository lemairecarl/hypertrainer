import os
import time
from pathlib import Path
from typing import List, Iterable

from redis import Redis
from rq import Queue
from rq.job import Job

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.utils import TaskStatus
from hypertrainer.htplatform_worker import run, get_jobs_info, get_logs


class HtPlatform(ComputePlatform):
    """The HT (HyperTrainer) Platform allows to send jobs to one or more Linux machines.

    Each participating worker consumes jobs from a global queue. There can be several workers per machine.
    """

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
        rq_job = self.worker_queues[task.hostname].enqueue(get_logs, args=(task.id,), ttl=1, result_ttl=2)
        logs = wait_for_result(rq_job, timeout=2)
        return logs

    def cancel(self, task):
        pass

    def update_tasks(self, tasks):
        # TODO only check requested ids

        for t in tasks:
            t.status = TaskStatus.Unknown
        job_id_to_task = {t.job_id: t for t in tasks}

        info_dicts = self._get_info_dict_for_each_worker()
        for hostname, local_db in zip(self.worker_hostnames, info_dicts):
            for job_id in set(local_db.keys()).intersection(job_id_to_task.keys()):
                job_info = local_db[job_id]
                t = job_id_to_task[job_id]

                t.status = TaskStatus(job_info['status'])
                t.output_path = job_info['output_path']
                t.hostname = hostname

    def _get_info_dict_for_each_worker(self):
        rq_jobs = [q.enqueue(get_jobs_info, ttl=1, result_ttl=1) for q in self.worker_queues.values()]
        results = wait_for_results(rq_jobs, wait_secs=1)
        return results


def wait_for_result(rq_job: Job, timeout):
    time.sleep(timeout)
    if rq_job.result is None:
        raise TimeoutError
    return rq_job.result


def wait_for_results(rq_jobs: Iterable[Job], wait_secs):
    time.sleep(wait_secs)
    results = [j.result for j in rq_jobs]
    if any(r is None for r in results):
        raise TimeoutError
    return results
