from pathlib import Path

if __name__ == '__main__':
    with Path('i_was_here.txt').open('a') as f:
        f.write('X')
