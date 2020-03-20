import time
from pathlib import Path
from typing import List, Iterable, Dict

from redis import Redis
from rq import Queue
from rq.job import Job

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.utils import TaskStatus, get_python_env_command
from hypertrainer.htplatform_worker import run, get_jobs_info, get_logs, test_job, ping, raise_exception, delete_job


class HtPlatform(ComputePlatform):
    """The HT (HyperTrainer) Platform allows to send jobs to one or more Linux machines.

    Each participating worker consumes jobs from a global queue. There can be several workers per machine.
    """

    def __init__(self, worker_hostnames: List[str]):
        self.worker_hostnames = worker_hostnames

        redis_conn = Redis(port=6380)  # FIXME config
        self.jobs_queue = Queue(name='jobs', connection=redis_conn)
        self.worker_queues: Dict[str, Queue] = {h: Queue(name=h, connection=redis_conn) for h in self.worker_hostnames}

    def submit(self, task, resume=False):
        output_path = Path(task.output_root) / str(task.uuid)
        python_env_command = get_python_env_command(Path(task.project_path), ComputePlatformType.HT.value)
        job = self.jobs_queue.enqueue(run, job_timeout=-1, kwargs=dict(
            script_file=Path(task.script_file),
            output_path=output_path,
            python_env_command=python_env_command,
            config_dump=task.dump_config(),
            resume=resume))
        # At this point, we only know the rq job id. No pid since the job might have to wait.
        return job.id

    def fetch_logs(self, task, keys=None):
        if task.hostname == '':  # The job hasn't been consumed yet
            return {}
        rq_job = self.worker_queues[task.hostname].enqueue(get_logs, args=(task.job_id,), ttl=2, result_ttl=2)
        logs = wait_for_result(rq_job, timeout=2)
        return logs

    def cancel(self, task):
        raise NotImplementedError

    def update_tasks(self, tasks):
        # TODO only check requested ids

        for t in tasks:
            t.status = TaskStatus.Lost
        job_id_to_task = {t.job_id: t for t in tasks}
        found_jobs = 0

        info_dicts = self._get_info_dict_for_each_worker()
        for hostname, local_db in zip(self.worker_hostnames, info_dicts):
            for job_id in set(local_db.keys()).intersection(job_id_to_task.keys()):
                found_jobs += 1

                job_info = local_db[job_id]
                t = job_id_to_task[job_id]

                t.status = TaskStatus(job_info['status'])
                t.output_path = job_info['output_path']
                t.hostname = hostname

    def delete(self, task):
        self.worker_queues[task.hostname].enqueue(delete_job, args=(task.job_id, task.output_path), ttl=4)

    def _get_info_dict_for_each_worker(self):
        rq_jobs = [q.enqueue(get_jobs_info, ttl=2, result_ttl=2) for q in self.worker_queues.values()]
        results = wait_for_results(rq_jobs, wait_secs=1)
        return results

    def ping_workers(self):
        rq_jobs = [q.enqueue(ping, ttl=2, result_ttl=2, args=(h,)) for h, q in self.worker_queues.items()]
        results = wait_for_results(rq_jobs, wait_secs=1)
        return results

    def raise_exception_in_worker(self, exc_type, queue_name):
        self.worker_queues[queue_name].enqueue(raise_exception, ttl=2, result_ttl=2, args=(exc_type,))


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


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['test'])
    ap.add_argument('--queue', type=str, default='jobs')
    ap.add_argument('--msg', type=str, default='ping!')
    args = ap.parse_args()

    assert args.mode == 'test'

    redis_conn = Redis(port=6380)  # FIXME config
    queue = Queue(name=args.queue, connection=redis_conn)
    job = queue.enqueue(test_job, args=(args.msg,))
