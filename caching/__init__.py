import os
import pickle
from typing import Optional, Iterable


class Cache:
    def __init__(self, filename, algorithm):
        self._filename = filename
        self._algorithm = algorithm
        self._cache = {}
    
    def load(self):
        print('load cache')
        if os.path.exists(self._filename):
            with open(self._filename, 'rb') as f:
                self._cache = pickle.load(f)
                
    def save(self):
        print('save cache')
        with open(self._filename, 'wb') as f:
            pickle.dump(self._cache, f)
            
    def _get_key(self, start: (float, float), dest: (float, float), cantons=None) -> str:
        """
        Create the key depending on start, destination, avoided cantons and type of routing _algorithm.
        :param start: start coordinates: tuple of (lon, lat)
        :param dest: destination coordinates: tuple of (lon, lat)
        :param cantons: list of cantons which will be avoided
        :return: the key for the given parameter set
        """
        key = f'{self._algorithm}:{start}:{dest}'
        if cantons:
            key = key + ','.join(map(lambda x: x.code, cantons))
        return key

    def get(self, start: (float, float), dest: (float, float), cantons=None) -> Optional[int]:
        """
        Get a cache value from the given parameters.
        :param start: start coordinates: tuple of (lon, lat)
        :param dest: destination coordinates: tuple of (lon, lat)
        :param cantons: list of cantons which will be avoided
        :return: the cached value on a hit, otherwise None
        """
        key = self._get_key(start, dest, cantons)
        if key in self._cache:
            return self._cache[key]
        return None
    
    def get_all(self, start: (float, float), dest: (float, float)) -> Iterable[int]:
        """
        Get all the cache hits independently from the avoided cantons.
        :param start: start coordinates: tuple of (lon, lat)
        :param dest: destination coordinates: tuple of (lon, lat)
        :return:
        """
        key_template = self._get_key(start, dest)
        for key in self._cache:
            if key.startswith(key_template):
                yield self._cache[key]
    
    def set(self, value: int, start: (float, float), dest: (float, float), cantons=None):
        """
        Set the key value pair in the cache
        :param value: time between start end destination
        :param start: start coordinates: tuple of (lon, lat)
        :param dest: destination coordinates: tuple of (lon, lat)
        :param cantons: list of cantons which will be avoided
        """
        key = self._get_key(start, dest, cantons)
        self._cache[key] = value
