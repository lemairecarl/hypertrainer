import datetime

from flask import (
    Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
)

from hypertrainer import viz
from hypertrainer.computeplatformtype import ComputePlatformType
from hypertrainer.task import Task
from hypertrainer.experimentmanager import experiment_manager as em
from hypertrainer.utils import get_item_at_path

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    show_archived = 'show_archived' in session
    return render_template('index.html',
                           tasks=em.get_tasks(proj=session.get('project'), archived=show_archived),
                           platforms=em.list_platforms(as_str=True), projects=em.list_projects(),
                           cur_proj=session.get('project'),
                           show_archived=show_archived)


@bp.route('/act', methods=['GET', 'POST'])
def perform_action():
    action = request.args.get('action')
    if action == 'submit':
        return submit()
    elif action == 'kill':
        return kill()
    elif action == 'bulk':
        # Bulk action on selected tasks
        task_ids = [k.split('-')[1] for k, v in request.form.items() if k.startswith('check-') and v]
        a = request.form['action']
        if a == 'Cancel':
            em.cancel_tasks(em.get_tasks_by_id(task_ids))
            flash('Cancelled task(s) {}.'.format(', '.join(task_ids)))
        elif a == 'Archive':
            em.archive_tasks_by_id(task_ids)
        elif a == 'Unarchive':
            em.unarchive_tasks_by_id(task_ids)
        elif a == 'Delete':
            em.delete_tasks_by_id(task_ids)
        elif a == 'Resume':
            em.resume_tasks(em.get_tasks_by_id(task_ids))
            flash('Resubmitted task(s) {}.'.format(', '.join(task_ids)))
        else:
            raise NotImplementedError
    elif action == 'chooseproject':
        session['project'] = request.args.get('p')
    elif action == 'show_archived':
        session['show_archived'] = 1
    elif action == 'hide_archived':
        session.pop('show_archived', None)
    elif action is None:
        pass
    else:
        raise NotImplementedError

    return redirect(url_for('index'))


@bp.route('/monitor/<task_id>')
def monitor(task_id):
    task = Task.get(Task.id == task_id)
    em.monitor(task)
    selected_log = 'out' if 'out' in task.logs else 'yaml'

    viz_scripts, viz_divs = None, None
    if len(task.metrics) > 0:
        viz_scripts, viz_divs = viz.generate_plots(task.metrics)

    return render_template('monitor.html', task=task, selected_log=selected_log,
                           viz_scripts=viz_scripts, viz_divs=viz_divs)


@bp.route('/enum')
def enum_platforms():
    return jsonify(em.list_platforms(as_str=True))


@bp.route('/update/<platform>')
def update(platform):
    def format_time_delta(seconds):
        if seconds is None:
            return ''
        else:
            return str(datetime.timedelta(seconds=int(seconds)))

    tasks = em.get_tasks(ComputePlatformType(platform), proj=session.get('project'))
    data = {}
    for t in tasks:
        data[t.id] = {
            'status': t.status.value,
            'epoch': t.cur_epoch,
            'total_epochs': get_item_at_path(t.config, 'training.num_epochs', default=None),
            'iter': f'{t.cur_phase} {t.cur_iter + 1} / {t.iter_per_epoch}',
            'ep_time_remain': format_time_delta(t.ep_time_remain),
            'total_time_remain': format_time_delta(t.total_time_remain)
        }
    return jsonify(data)


def submit():
    platform = request.form['platform']
    config_file = request.form['config']
    project = request.form['project']
    tags = request.form['tags']
    em.create_tasks(platform, config_file, project=project, tags=tags)
    flash('Submitted "{}" on {}.'.format(config_file, platform), 'success')
    return redirect(url_for('index'))


def kill():
    task_id = request.args.get('task_id')
    em.cancel_tasks(task_id)
    flash('Cancelled task {}.'.format(task_id))
    return redirect(url_for('index'))
