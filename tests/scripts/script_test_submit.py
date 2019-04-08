import sys
from pathlib import Path

if __name__ == '__main__':
    config_file = sys.argv[1]
    assert Path(config_file).exists()
    assert Path('config.yaml').exists()

    print('printing to stdout')
    print('printing to stderr', file=sys.stderr)
