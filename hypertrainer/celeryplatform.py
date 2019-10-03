from celery import Celery

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.utils import TaskStatus

app = Celery('hypertrainer.celeryplatform', backend='rpc://', broker='amqp://localhost')


class CeleryPlatform(ComputePlatform):
    def submit(self, task, continu=False) -> str:
        run.delay(task.script_file, task.dump_config())
        return 'celeryDummy'

    def fetch_logs(self, task, keys=None):
        return {}

    def cancel(self, task):
        pass

    def get_statuses(self, job_ids) -> dict:
        return {'': TaskStatus.Unknown, 'celeryDummy': TaskStatus.Unknown}


@app.task
def run(script, task_config):
    print(script)
    print(task_config)
