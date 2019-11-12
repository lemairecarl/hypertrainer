import subprocess
import tempfile
from glob import glob
from pathlib import Path

from hypertrainer.computeplatform import ComputePlatform
from hypertrainer.utils import TaskStatus, parse_columns


class SlurmPlatform(ComputePlatform):
    status_map = {
        'PD': TaskStatus.Waiting,
        'R': TaskStatus.Running,
        'CG': TaskStatus.Running,
        'CD': TaskStatus.Finished,
        'F': TaskStatus.Crashed,
        'CA': TaskStatus.Cancelled,
        'DL': TaskStatus.Removed,
        'TO': TaskStatus.Removed
    }

    def __init__(self, server_user):
        self.server_user = server_user
        self.user = server_user.split('@')[0]
        self.submission_template = Path('platform/slurm/slurm_template.sh')
        self.setup_template = Path('platform/slurm/slurm_setup.sh')

    def submit(self, task, resume=False):
        job_remote_dir = self._make_job_path(task)
        if resume:
            setup_script = self.replace_variables(
                'cd $HYPERTRAINER_JOB_DIR && sbatch --parsable $HYPERTRAINER_NAME.sh', task)
        else:
            task.output_path = job_remote_dir
            setup_script = self.replace_variables(self.setup_template.read_text(), task,
                                                  submission=self.submission_template.read_text())
        completed_process = None
        try:
            completed_process = subprocess.run(['ssh', self.server_user],
                                               input=setup_script.encode(), stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
            completed_process.check_returncode()
        except subprocess.CalledProcessError:
            print(completed_process.stderr)
            raise  # FIXME handle error
        job_id = completed_process.stdout.decode('utf-8').strip()
        return job_id

    def fetch_logs(self, task, keys=None):
        logs = {}
        with tempfile.TemporaryDirectory() as tmpdir:
            # Get all .txt, .log files in output path
            subprocess.run(['scp', self.server_user + ':' + self._make_job_path(task) + '/*.{log,txt}', tmpdir],
                           stderr=subprocess.DEVNULL)  # Ignore errors (e.g. if *.log doesn't exist)
            for f in glob(tmpdir + '/*'):
                p = Path(f)
                logs[p.stem] = p.read_text()
        return logs

    def update_tasks(self, tasks):
        job_ids = [t.job_id for t in tasks]
        statuses = self._get_statuses(job_ids)  # Get statuses of active jobs
        ccodes = self._get_completion_codes()  # Get statuses for completed jobs

        for t in tasks:
            if t.job_id in ccodes:
                # Job just completed
                if ccodes[t.job_id] == 0:
                    t.status = TaskStatus.Finished
                else:
                    t.status = TaskStatus.Crashed
            else:
                # Job still active (or lost)
                if t.job_id not in statuses:
                    t.status = TaskStatus.Lost  # Job not found

    def _get_statuses(self, job_ids):
        data = subprocess.run(['ssh', self.server_user, 'squeue -u $USER | grep $USER'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
        data_grid = parse_columns(data)
        statuses = {}
        for l in data_grid:
            job_id, status = l[0], l[4]
            if job_id not in job_ids:
                continue
            statuses[job_id] = self.status_map[status]
        return statuses

    def _get_completion_codes(self):
        data = subprocess.run(['ssh', self.server_user, 'sacct -o JobID,ExitCode -n -s CD,F,CA,DL,TO -S 010100'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
        data_grid = parse_columns(data)
        ccodes = {}
        for l in data_grid:
            job_id, ccode = l[0], l[1]
            if '.' in job_id:
                continue
            ccodes[job_id] = int(ccode.split(':')[0])
        return ccodes

    def cancel(self, task):
        subprocess.run(['ssh', self.server_user, f'scancel {task.job_id}'])
        task.status = TaskStatus.Cancelled
        task.save()

    def _make_job_path(self, task):
        return '/home/' + self.user + '/hypertrainer/output/' + str(task.id)

    @staticmethod
    def replace_variables(input_text, task, **kwargs):
        key_value_map = [
            ('$HYPERTRAINER_SUBMISSION', kwargs.get('submission', '')),
            ('$HYPERTRAINER_NAME', task.name),
            ('$HYPERTRAINER_OUTFILE', task.output_path + '/out.txt'),
            ('$HYPERTRAINER_ERRFILE', task.output_path + '/err.txt'),
            ('$HYPERTRAINER_JOB_DIR', task.output_path),
            ('$HYPERTRAINER_SCRIPT', task.script_file),
            ('$HYPERTRAINER_CONFIGFILE', task.output_path + '/config.yaml'),
            ('$HYPERTRAINER_CONFIGDATA', task.dump_config())
        ]
        output = input_text
        for key, value in key_value_map:
            output = output.replace(key, value)
        return output