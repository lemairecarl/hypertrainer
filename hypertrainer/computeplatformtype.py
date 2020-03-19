from enum import Enum


class ComputePlatformType(Enum):
    LOCAL = 'local'
    HT = 'htPlatform'
    HELIOS = 'helios'
    GRAHAM = 'graham'
    BELUGA = 'beluga'

    @property
    def abbrev(self):
        if self.value == 'htPlatform':
            return 'ht'
        else:
            return self.value
