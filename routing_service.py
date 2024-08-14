import logging

from caching import Cache


logger = logging.getLogger(__name__)


DEST_COORDS = (7.44411, 46.9469)
# two days in seconds
UNREACHABLE = 172800


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
        :return: A tuple of the estimated time, distance, and shape for the route with the lowest cost
        """
        # iterate over the shortest routes for this connection, ignoring the avoided cantons
        # if the route does not enter any cantons to avoid, this will be the shortest connection
    # for (time, distance, route) in sorted(self.cache.get_all((source_lon, source_lat), (target_lon, target_lat)),
    #                                       key=lambda x: x[0]):
    #     # intersect the route with every nogo canton, if there is no intersection, cache the result
    #     hit_nogos = map(lambda x: x.intersect(route), self.nogos)
    #     if not any(hit_nogos):
    #         if self.nogos:
    #             self.cache.set((time, distance, route), (source_lon, source_lat), (target_lon, target_lat),
    #                            self.nogos)
    #             logger.info(
    #                 f'reuse shortest route (start: {(source_lat, source_lon)}, dest: {(target_lat, target_lon)})')
    #         return time, distance, route

        # if there was no previous cache hit, calculate the shortest route
        if cache_hit := self.cache.get((source_lon, source_lat), (target_lon, target_lat)):
            (time, distance, route) = cache_hit
        else:
            (time, distance, route) = self.direct_connection(source_lon, source_lat, target_lon, target_lat)
            self.cache.set((time, distance, route), (source_lon, source_lat), (target_lon, target_lat), self.nogos)
        # if self.nogos:
        #     # save cache for the calculation of routes with cantons to avoid
        #     self.cache.save()
        #     logger.info(
        #         f'calculate route while avoiding cantons '
        #         f'(start: {(source_lat, source_lon)}, dest: {(target_lat, target_lon)})')
        return time, distance, route

    def _calc_matrix_from_coordinates(self, coordinates):
        result = {}
        for source in coordinates:
            if source not in result:
                result[source] = {}
            for target in coordinates:
                if source != target and source != DEST_COORDS:
                    result[source][target] = self.cache_or_connection(source[0], source[1], target[0], target[1])[0]

        # make the time to reach any destination from the final destination Bundesplatz in bern very large, so it will
        # be the final destination for sure
        for unreachable_target in coordinates:
            if unreachable_target != DEST_COORDS:
                result[DEST_COORDS][unreachable_target] = UNREACHABLE

        # save cache after every produced matrix
        self.cache.save()

        return result
