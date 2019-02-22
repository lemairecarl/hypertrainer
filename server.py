from pathlib import Path

from flask import Flask, request, render_template

from experimentmanager import ExperimentManager

app = Flask(__name__)
em = ExperimentManager(start_visdom=False)


@app.route('/')
def home(msg=None):
    return render_template('index.html', msg=msg)


@app.route('/submit', methods=['POST'])
def action():
    script_path = request.form['script']
    config_path = request.form['config']
    em.launch_script(script_path=Path(script_path), config_file_path=Path(config_path))
    return home('Launching "{}" with "{}".'.format(script_path, config_path))


@app.route('/monitor')
def monitor():
    return render_template('monitor.html', all_outputs = em.get_all_outputs())
