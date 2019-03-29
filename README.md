# HyperTrainer

HyperTrainer is a machine learning experiment manager and dashboard. Features:

* Run hyperparameter searches (you don't have to change your code)
* Visualize your metrics with interactive plots; see your logs
* Record all your traninig results in one place; export as csv
* Launch and monitor training runs on different platforms in an uniform manner (Local, HPC, AWS, ...)

![Screenshot](https://raw.githubusercontent.com/lemairecarl/hypertrainer/master/hypertrainer.png)

HyperTrainer is compatible with Python scripts that accept a single YAML as input, instead of command-line args. In terms of reproducibility, a YAML file is much better than a set of command-line args.

Trello board:
https://trello.com/b/C1VCfrSW/rncan-experiment-manager

## Setup

Since this project depends on https://github.com/Semantic-Org/Semantic-UI-CSS; you will need to run this command inside the repo:

```
git submodule update --init --recursive
```

## Launching the dashboard

`cd` to the root of this repo and run `start.sh` (make sure it has execute permission). Then, browse to http://localhost:5000.

## Tutorial

In this tutorial we will start a dummy training task. To launch a task, HyperTrainer needs 2 things: a Python script, and a YAML config to feed to it.

### 1. Setup directories

The **script directory** is where HyperTrainer looks for scripts and configs. You can put symlinks of your scripts there. For now, let's set it to the `hypertrainer/sample/` directory of this repo:

```
# cd to this repo
export HYPERTRAINER_SCRIPTS="./hypertrainer/sample"
```

[TODO: `$HYPERTRAINER_PATH` should exist and contain the list of directories to scan to find scripts and configs. It should not be necessary to move/link scripts to a single directory.]

The **root output directory** is where all the outputs of locally running scripts should go. By default, it is set to `~/hypertrainer/output` (configure this using `$HYPERTRAINER_OUTPUT`). Inside this directory, HyperTrainer will create a subdirectory for each local task. This subdirectory should contain the stdout, stderr, metrics and all other outputs of your script.

[TODO: the subfolder should be the working directory of the script]

### 2. Submit a task

First, fire up the dashboard (see section above). Using the web UI, submit the script `dummy.py` with the config `epochs_test.yaml` (those files are now in `$HYPERTRAINER_SCRIPTS`). Be sure to select the "local" platform. After having clicked "Submit", you should see the task appear in the table.

### 3. Monitor a task

When you refresh the dashboard, a number of columns will update to inform you of the status and progress of your tasks. To see the stdout and stderr, select the task, then click on "Monitor". The monitoring page contains one tab for each `.log` or `.txt` file in the output path of the script.

_See section "Log Formats" to know how to give HyperTrainer the info it needs._

[TODO: Tabs for `iterations.log` and `metric_*.log` should be hidden.]

### 4. Visualize a task

Submit the script `dummy.py` with the config `plot_test.yaml`. Then, select the task and click on "Monitor". A dummy loss curve will appear in an interactive plot.

_See section "Log Formats" to know how to communicate your metrics to HyperTrainer._

### 5. Run an hyperparameter search

Submit the script `dummy.py` with the config `hp_test.yaml`. You should see three tasks appear in the table. These tasks are all the same, except that they have a different value in their config YAML for `training.learning_rate`. The configuration of the hyperparameter search is inside `hp_test.yaml` -- have a look at it.

## Log Formats

HyperTrainer will look for certain TSV (tab-separated values) files in the output path of your scripts:

* `epochs.log`: Training progress at the epoch level. Expected columns:
    * epoch_index
    * unix_timestamp
* `iterations.log`: Training progress at the iteration level. Expected columns:
    * epoch_index
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

[TODO: change extension from `.log` to `.tsv`; Remove `epochs.log`]

## Acknowledgements

I would like to thank Natural Resources Canada for supporting this project.