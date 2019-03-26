from flask import (
    Blueprint, render_template, request, flash, redirect, url_for, jsonify
)

from hypertrainer.computeplatform import ComputePlatformType
from hypertrainer.task import Task
from hypertrainer.experimentmanager import experiment_manager as em
from hypertrainer.utils import get_item_at_path

bp = Blueprint('dashboard', __name__)


@bp.route('/', methods=['GET', 'POST'])
def index():
    action = request.args.get('action')
    if action == 'submit':
        return submit()
    elif action == 'kill':
        return kill()
    elif action == 'bulk':
        # Bulk action on selected tasks
        task_ids = [k.split('-')[1] for k, v in request.form.items() if k.startswith('check-') and v]
        if request.form['action'] == 'Cancel':
            em.cancel_from_id(task_ids)
            flash('Cancelled tasks {}.'.format(', '.join(task_ids)))
        elif request.form['action'] == 'Delete':
            em.delete_from_id(task_ids)
    elif action is None:
        pass
    else:
        flash('ERROR: Unrecognized action!', 'error')
    platforms = [p.value for p in ComputePlatformType]
    return render_template('index.html', tasks=em.get_all_tasks(), platforms=platforms)


@bp.route('/monitor/<task_id>')
def monitor(task_id):
    task = Task.get(Task.id == task_id)
    task.monitor()
    if 'out' in task.logs:
        selected_log = 'out'
    else:
        selected_log = next(iter(task.logs.keys()))
    return render_template('monitor.html', task=task, selected_log=selected_log)


@bp.route('/enum')
def enum_platforms():
    return jsonify([p.value for p in ComputePlatformType])
    # return jsonify(['local'])


@bp.route('/update/<platform>')
def update(platform):
    tasks = em.get_tasks(ComputePlatformType(platform))
    data = {}
    for t in tasks:
        data[t.id] = {
            'status': t.status.value,
            'epoch': t.cur_epoch,
            'total_epochs': get_item_at_path(t.config, 'training.num_epochs', default=None),
            'iter': t.cur_iter,
            'iter_per_epoch': t.iter_per_epoch
        }
    return jsonify(data)


def submit():
    platform = request.form['platform']
    script_file = request.form['script']
    config_file = request.form['config']
    em.submit(platform, script_file, config_file)
    flash('Submitted "{}" with "{}" on {}.'.format(script_file, config_file, platform), 'success')
    return redirect(url_for('index'))


def kill():
    task_id = request.args.get('task_id')
    em.cancel_from_id(task_id)
    flash('Cancelled task {}.'.format(task_id))
    return redirect(url_for('index'))
