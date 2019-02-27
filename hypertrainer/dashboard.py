from pathlib import Path
import sys

from flask import (
    Blueprint, render_template, request, flash, redirect, url_for
)

from hypertrainer.experimentmanager import experiment_manager as em

bp = Blueprint('dashboard', __name__)


@bp.route('/', methods=['GET', 'POST'])
def index():
    action = request.args.get('action')
    if action == 'submit':
        return submit()
    elif action == 'kill':
        return kill()
    elif action is None:
        pass
    else:
        flash('ERROR: Unrecognized action!', 'error')
    return render_template('index.html', tasks=em.tasks.values())


@bp.route('/monitor/<task_id>')
def monitor(task_id):
    task = em.tasks[task_id]
    stdout, stderr = task.get_output()
    return render_template('monitor.html', task=task, stdout=stdout, stderr=stderr)


def submit():
    script_path = request.form['script']
    config_path = request.form['config']
    em.submit(script_path=Path(script_path), config_file_path=Path(config_path))
    flash('Submitted "{}" with "{}".'.format(script_path, config_path), 'success')
    return redirect(url_for('index'))


def kill():
    task_id = request.args.get('task_id')
    em.cancel_from_id(task_id)
    flash('Cancelled task {}.'.format(task_id))
    return redirect(url_for('index'))
