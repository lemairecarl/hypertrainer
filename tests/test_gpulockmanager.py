import multiprocessing as mp
import os
import time
from pathlib import Path

import pytest

from hypertrainer.utils import GpuLockManager, PidFile


def try_acquire(q):
    p = PidFile(Path('/tmp/test.lock'))
    q.put(p.try_acquire())
    time.sleep(0.5)
    p.release()


def test_pid():
    q = mp.Queue()
    p1 = mp.Process(target=try_acquire, args=(q,))
    p2 = mp.Process(target=try_acquire, args=(q,))
    p1.start()
    p2.start()

    assert sum((1 if q.get() else 0, 1 if q.get() else 0)) == 1


def try_acquire_gpu(q):
    assert os.environ['CUDA_VISIBLE_DEVICES'] == '0,1'
    gpu_lock = GpuLockManager().acquire_one_gpu()
    q.put(gpu_lock.gpu_id)
    time.sleep(0.5)
    gpu_lock.release()


def test_acquire_one_gpu(monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '0,1')

    q = mp.Queue()
    p1 = mp.Process(target=try_acquire_gpu, args=(q,))
    p2 = mp.Process(target=try_acquire_gpu, args=(q,))
    p1.start()
    p2.start()

    responses = set()
    responses.add(q.get())
    responses.add(q.get())
    assert responses == {'0', '1'}


def test_no_gpu(monkeypatch):
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')

    with pytest.raises(Exception):
        GpuLockManager().acquire_one_gpu()
