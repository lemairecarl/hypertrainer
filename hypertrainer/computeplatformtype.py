from enum import Enum


class ComputePlatformType(Enum):
    LOCAL = 'local'
    CELERY = 'celery'
    HELIOS = 'helios'
    GRAHAM = 'graham'
    BELUGA = 'beluga'