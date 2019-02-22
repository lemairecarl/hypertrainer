from pathlib import Path
import os
import signal

from flask import Flask, request, render_template

from experimentmanager import ExperimentManager

app = Flask(__name__)
em = ExperimentManager(start_visdom=False)


@app.route('/', methods=['GET', 'POST'])
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


@app.route('/monitor/<int:task_id>')
def monitor(task_id):
    task = em.tasks[task_id]
    stdout, stderr = task.get_output()
    return render_template('monitor.html', task=task, stdout=stdout, stderr=stderr)


def submit():
    script_path = request.form['script']
    config_path = request.form['config']
    em.launch_script(script_path=Path(script_path), config_file_path=Path(config_path))
    return 'Launching "{}" with "{}".'.format(script_path, config_path)


def kill():
    task_id = int(request.args.get('task_id'))
    os.kill(task_id, signal.SIGTERM)
    return 'Killed task with pid {}.'.format(task_id)
