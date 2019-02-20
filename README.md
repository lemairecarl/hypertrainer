# HyperTrainer

Trello board:
https://trello.com/b/C1VCfrSW/rncan-experiment-manager

## Generating configs for hyperparameter search

First, fill out the `hpsearch` section in your configuration file. See `sample/sample.yaml` for an example.

Then, run:

```
python em.py --hp-search path/to/your/configuration.yaml
```

The child configs will be generated alongside their parent.

## Visualizing experiment progress and results

First, set the `EM_CONFIGS_PATH` environment variable to the directory containing your config files. (You can set it to `sample/`.)

Then, run:

```
python server.py
```

and browse to http://localhost:8097/. Use the menu bar to select the "environment" corresponding to the task you want to visualize.
