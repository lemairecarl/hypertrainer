# HyperTrainer

Trello board:
https://trello.com/b/C1VCfrSW/rncan-experiment-manager

## Launching the dashboard

`cd` to the root of this repo and run `start.sh` (make sure it has execute permission). Then, browse to http://localhost:5000.

## Generating configs for hyperparameter search

First, fill out the `hpsearch` section in your configuration file. See `sample/sample.yaml` for an example.

Then, run:

```
python em.py --hp-search path/to/your/configuration.yaml
```

The child configs will be generated alongside their parent.
