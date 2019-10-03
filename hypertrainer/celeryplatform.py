from celery import Celery

from hypertrainer.computeplatform import ComputePlatform


class CeleryPlatform(ComputePlatform):
    app = Celery('tasks', backend='rpc://', broker='amqp://localhost')

    def submit(self, task, continu=False) -> str:
        run.delay(task, continu)
        return 'celeryDummy'

    def fetch_logs(self, task, keys=None):
        return {}

    def cancel(self, task):
        pass

    def get_statuses(self, job_ids) -> dict:
        return {}


@CeleryPlatform.app.task
def run(task, continu=False):
    print(task.script_file)
    print(task.dump_config())
