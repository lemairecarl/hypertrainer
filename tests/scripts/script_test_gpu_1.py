import os
import time

vd = os.environ['CUDA_VISIBLE_DEVICES']
print(f'gpu_id={vd}')

num_gpus = len(vd.split(','))
if vd == '' or num_gpus != 1:
    raise Exception('There must be one visible gpu.')

time.sleep(0.5)
