import logging

import geopy.distance

from caching import Cache


logger = logging.getLogger(__name__)


DEST_COORDS = (7.44411, 46.9469)
# two days in seconds
UNREACHABLE = 172800
DISTANCE_CUTOFF = 120


class RoutingError(Exception):
    pass


class RoutingResult:
    def __init__(self, route_key, cache, cost, distance):
        self._route_key = route_key
        self._cache = cache
        self._cost = cost
        self._distance = distance

    def get_cost(self):
        return self._cost

    def get_distance(self):
        return self._distance

    def get_route(self):
        return self._cache.get_file(self._route_key)


class RoutingService:
    def __init__(self, cache: Cache, ferries=False, nogos=None):
        self.cache = cache
        self._use_ferries = ferries
        self.nogos = nogos or []

    def matrix(self, coordinates):
        raise NotImplementedError()

    def direct_connection(self, source_lon, source_lat, target_lon, target_lat):
        raise NotImplementedError()

    def cache_or_connection(self, source_lon, source_lat, target_lon, target_lat):
        """
        This function returns the shortest distance for the given coordinates.
        It tries to get the distance from the cache, but calculates it otherwise.
        :return: A tuple of the estimated time, distance
        """
        route_key = self.cache.get_route_key((source_lon, source_lat), (target_lon, target_lat), self.nogos)
        if geopy.distance.geodesic((source_lon, source_lat), (target_lon, target_lat)).km > DISTANCE_CUTOFF:
            logger.info(
                f'points are too far apart (start: {(source_lat, source_lon)}, dest: {(target_lat, target_lon)})')
            return RoutingResult(route_key, self.cache, UNREACHABLE, None)

        if cache_hit := self.cache.get((source_lon, source_lat), (target_lon, target_lat), self.nogos):
            time, distance = cache_hit
            logger.info(
                f'distance was found in cache (start: {(source_lon, source_lat)}, dest: {(target_lon, target_lat)}'
                f', avoided_cantons: {", ".join([c.code for c in self.nogos])})')
            return RoutingResult(route_key, self.cache, time, distance)

        # iterate over the shortest routes for this connection, ignoring the avoided cantons
        # if the route does not enter any cantons to avoid, this will be the shortest connection
        if self.nogos:
            for key, (time, distance) in sorted(self.cache.get_all((source_lon, source_lat), (target_lon, target_lat)),
                                                key=lambda x: x[0]):
                if time == UNREACHABLE:
                    continue
                route = self.cache.get_file(key + ':route')
                # intersect the route with every nogo canton, if there is no intersection, cache the result
                hit_nogos = [x.intersect(route) for x in self.nogos]
                if not any(hit_nogos):
                    self.cache.set((time, distance), (source_lon, source_lat), (target_lon, target_lat),
                                   self.nogos)
                    self.cache.set_file(self.cache.get_route_key((source_lon, source_lat), (target_lon, target_lat),
                                                                 self.nogos), route)
                    logger.info(f'reuse shortest route (start: {(source_lat, source_lon)}, dest: {(target_lat, target_lon)})')
                    return RoutingResult(key + ':route', self.cache, time, distance)
        try:
            # if there was no previous cache hit, calculate the shortest route
            (time, distance, route) = self.direct_connection(source_lon, source_lat, target_lon, target_lat)

            self.cache.set_file(route_key, route)
        except RoutingError:
            (time, distance) = UNREACHABLE, None
        self.cache.set((time, distance), (source_lon, source_lat), (target_lon, target_lat), self.nogos)
        if self.nogos:
            logger.info(
                f'calculate route while avoiding cantons '
                f'(start: {(source_lat, source_lon)}, dest: {(target_lat, target_lon)})')
        else:
            logger.info(
                f'calculate route '
                f'(start: {(source_lat, source_lon)}, dest: {(target_lat, target_lon)})')
        return RoutingResult(route_key, self.cache, time, distance)
