from pathlib import Path
import sys

from flask import (
    Blueprint, render_template, request
)

sys.path.append("..")  # FIXME
from hypertrainer.experimentmanager import experiment_manager as em

bp = Blueprint('dashboard', __name__)


@bp.route('/', methods=['GET', 'POST'])
def main(msg='Ready.'):
    action = request.args.get('action')
    if action == 'submit':
        msg = submit()
    elif action == 'kill':
        msg = kill()
    elif action is None:
        pass
    else:
        msg = 'ERROR: Unrecognized action.'
    return render_template('index.html', tasks=em.tasks.values(), msg=msg)


@bp.route('/monitor/<task_id>')
def monitor(task_id):
    task = em.tasks[task_id]
    stdout, stderr = task.get_output()
    return render_template('monitor.html', task=task, stdout=stdout, stderr=stderr)


def submit():
    script_path = request.form['script']
    config_path = request.form['config']
    em.submit(script_path=Path(script_path), config_file_path=Path(config_path))
    return 'Launching "{}" with "{}".'.format(script_path, config_path)


def kill():
    task_id = request.args.get('task_id')
    em.cancel_from_id(task_id)
    return 'Cancelling task {}.'.format(task_id)