from caching import Cache


DEST_COORDS = (7.44411, 46.9469)
# two days in seconds
UNREACHABLE = 172800


class RoutingService:
    def __init__(self, cache: Cache, ferries=False, nogos=None):
        self.cache = cache
        self._use_ferries = ferries
        self._nogos = nogos

    def matrix(self, coordinates):
        raise NotImplementedError()

    def _direct_connection(self, source_lon, source_lat, target_lon, target_lat):
        raise NotImplementedError()

    def _cache_or_connection(self, source_lon, source_lat, target_lon, target_lat):
        if cache_hit := self.cache.get((source_lon, source_lat), (target_lon, target_lat)):
            return cache_hit
        result = self._direct_connection(source_lon, source_lat, target_lon, target_lat)
        self.cache.set(result, (source_lon, source_lat), (target_lon, target_lat), self._nogos)
        return result

    def _calc_matrix_from_coordinates(self, coordinates):
        result = {}
        for source in coordinates:
            if source not in result:
                result[source] = {}
            for target in coordinates:
                if source != target and source != DEST_COORDS:
                    result[source][target] = self._cache_or_connection(source[0], source[1], target[0], target[1])

        # make the time to reach any destination from the final destination Bundesplatz in bern very large, so it will
        # be the final destination for sure
        for unreachable_target in coordinates:
            if unreachable_target != DEST_COORDS:
                result[DEST_COORDS][unreachable_target] = UNREACHABLE

        return result
