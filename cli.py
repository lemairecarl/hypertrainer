from IPython import start_ipython
from termcolor import colored
from traitlets.config import Config

from hypertrainer.experimentmanager import experiment_manager as em

commands = {
    'create': em.create_tasks,
    'update': em.update_tasks,
    'get': em.get_tasks,
    'archive': em.archive_tasks_by_id,
    'delete': em.delete_tasks_by_id,
    'cancel': em.cancel_tasks
}
namespace = {'em': em}
namespace.update(commands)


def print_help():
    def print_colored(s):
        print(colored(s, 'blue'))

    print_colored('Available shortcuts:')
    print_colored(', '.join(commands.keys()))
    print_colored('Type help(command) for details.')
    print_colored('The ExperimentManager instance is available as "em".')


if __name__ == '__main__':
    globals().update(commands)  # Add shorthands in scope

    print('[[[[ HyperTrainer Command Line Interface ]]]]')
    print_help()

    exec_lines = [
        '%load_ext autoreload',
        '%autoreload 2'
    ]
    ipython_config = Config()
    ipython_config.TerminalIPythonApp.exec_lines = exec_lines
    start_ipython(config=ipython_config, user_ns=namespace)
