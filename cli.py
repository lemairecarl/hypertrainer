from typing import Union, Iterable

from IPython import start_ipython
from termcolor import colored
from traitlets.config import Config

from hypertrainer.experimentmanager import experiment_manager as em


def print_help():
    def print_colored(s):
        print(colored(s, 'blue'))

    print_colored('Available commands:')
    print_colored(', '.join(commands.keys()) + ', print_help')
    print_colored('Type help(command) for details.')
    print_colored('The ExperimentManager instance is available as "em".')


def by_id_helper(f, squeeze_returned_list=False):
    squeeze_returned_list_doc = 'If the returned list has length 1, the element is returned instead.'

    def _f(int_or_iterable: Union[int, Iterable], *more_ints):
        """{d}

        Examples:
            {f}(1)         # Single int
            {f}(1, 3, 2)   # Multiple ints
            {f}(range(4))  # Iterable
        """

        if isinstance(int_or_iterable, int):
            ids = [int_or_iterable]
        elif hasattr(int_or_iterable, '__iter__'):
            ids = list(int_or_iterable)
        else:
            raise TypeError
        ids += more_ints

        return_val = f(ids)
        if squeeze_returned_list and isinstance(return_val, list) and len(return_val) == 1:
            return_val = return_val[0]
        return return_val
    _f.__name__ = f.__name__
    desc = f.__doc__.strip()
    if squeeze_returned_list:
        desc += '\n\n' + squeeze_returned_list_doc
    _f.__doc__ = str(_f.__doc__).format(d=desc, f=f.__name__)
    return _f


commands = {
    'create': em.create_tasks,
    'show': em.print_tasks,
    'get': by_id_helper(em.get_tasks_by_id, squeeze_returned_list=True),
    'config': em.print_task_config,
    'out': em.print_output,
    'archive': by_id_helper(em.archive_tasks_by_id),
    'unarchive': by_id_helper(em.unarchive_tasks_by_id),
    'delete': by_id_helper(em.delete_tasks_by_id),
    'cancel': by_id_helper(em.cancel_tasks_by_id),
    'resume': by_id_helper(em.resume_tasks_by_id),
    'export_csv': em.export_csv,
    'export_yaml': em.export_yaml
}
symbols = [
    'em',
    'print_help'
]
namespace = {s: globals()[s] for s in symbols}
namespace.update(commands)


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
    ipython_config.TerminalIPythonApp.display_banner = False
    start_ipython(config=ipython_config, user_ns=namespace)
