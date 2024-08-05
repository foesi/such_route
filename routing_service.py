class RoutingService:
    def __init__(self, ferries=True, nogos=None):
        self.ferries = ferries
        self.nogos = nogos

    def matrix(self, coordinates):
        raise NotImplementedError()

    def _direct_connection(self, source_lon, source_lat, target_lon, target_lat):
        raise NotImplementedError()

    def _calc_matrix_from_coordinates(self, coordinates):
        result = {}
        for source in coordinates:
            if str(source) not in result:
                result[str(source)] = {}
            for target in coordinates:
                if source != target:
                    result[str(source)][str(target)] = self._direct_connection(source[0], source[1], target[0],
                                                                               target[1])

        return result
