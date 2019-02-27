from pathlib import Path

from hypertrainer.task import Task


class ExperimentManager:
    def __init__(self):
        self.tasks = {}
    
    def submit(self, script_path: Path, config_file_path: Path):
        t = Task(script_path, config_file_path)
        t.submit()
        self.tasks[t.task_id] = t
        
    def cancel_from_id(self, task_id):
        self.tasks[task_id].cancel()


experiment_manager = ExperimentManager()
