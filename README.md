# HyperTrainer

HyperTrainer is a machine learning experiment manager and dashboard. Features:

* Run hyperparameter searches (you don't have to change your code)
* Visualize your metrics with interactive plots; see your logs
* Record all your traninig results in one place; export as csv
* Launch and monitor training runs on different computing platforms in an uniform
  manner (Local, HPC, AWS, ...)

![Screenshot](https://raw.githubusercontent.com/lemairecarl/hypertrainer/master/hypertrainer.png)

HyperTrainer is compatible with Python scripts that accept a single YAML as input,
instead of command-line args. In terms of reproducibility, a YAML file is much
better than a set of command-line args.

Trello board:
https://trello.com/b/C1VCfrSW/rncan-experiment-manager

## Setup

Since this project depends on https://github.com/Semantic-Org/Semantic-UI-CSS;
you will need to run this command inside the repo:

```bash
git submodule update --init --recursive
```

## Launching the dashboard

`cd` to the root of this repo and run `start.sh` (make sure it has execute
permission). Then, browse to http://localhost:5000.

## Tutorial

In this tutorial we will start dummy training tasks. To launch a task,
HyperTrainer needs 2 things: a Python script, and a YAML config to feed to it.

### 1. Setup directories

`$HYPERTRAINER_PATH` is the **scripts PATH**, and works similarly to the
`$PATH` environment variable on Linux. It should contain a colon-separated list
of paths (e.g. `HYPERTRAINER_PATH=/path/a:/path/b`) where HyperTrainer will look
for scripts and configs. For now, let's set it to the `hypertrainer/sample/`
directory of this repo:

```bash
export HYPERTRAINER_PATH="<path to this repo>/hypertrainer/sample"
# to persist the variable, add the previous line to your ~/.bashrc 
```

The **root output directory** is where all the outputs of locally running scripts
should go. By default, it is set to `~/hypertrainer/output` (configure this using
`$HYPERTRAINER_OUTPUT`). Inside this directory, HyperTrainer will create a
subdirectory for each local task. This subdirectory should contain the stdout,
stderr, metrics and all other outputs of your script.

### 2. Submit a task

First, fire up the dashboard (see section above). Using the web UI, submit the
script `dummy.py` with the config `epochs_test.yaml`. Be sure to select the
"local" platform. After having clicked "Submit", you should see the task appear
in the table.

### 3. Monitor a task

When you refresh the dashboard, a number of columns will update to inform you
of the status and progress of your tasks. To see the stdout and stderr, click
on a task. The monitoring panel will appear; it contains one tab for each
`.log` or `.txt` file in the output path of the script.

_See section "Log Formats" to know how to give HyperTrainer the info it needs._

### 4. Visualize a task

Submit the script `dummy.py` with the config `plot_test.yaml`. Then, select the
task and click on "Monitor". A dummy loss curve will appear in an interactive
plot.

_See section "Log Formats" to know how to communicate your metrics to
HyperTrainer._

### 5. Run an hyperparameter search

Submit the script `dummy.py` with the config `hp_test.yaml`. You should see
three tasks appear in the table. These tasks are all the same, except that they
have a different value in their config YAML for `training.learning_rate`. The
configuration of the hyperparameter search is inside `hp_test.yaml` -- have a
look at it.

## Log Formats

HyperTrainer will look for certain files in the
output path of your scripts (which should contain tab-separated values):

* `progress.log`: Training progress at the iteration level. Expected columns:
    * epoch_index
    * phase (e.g. `'train'` or `'valid'`)
    * iteration_index
    * num_iter_per_epoch
    * unix_timestamp
* `metric_*.log`: Value of a metric at each epoch (e.g. training loss). This will generate a line plot. Expected columns:
    * epoch_index
    * value
* `metric_classwise_*.log`: Value of a metric for each class, at each epoch. This will generate a multi-line plot. Expected columns:
    * epoch_index
    * class_index_or_str
    * value

## Acknowledgements

I would like to thank Natural Resources Canada for supporting this project.