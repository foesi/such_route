from typing import Optional, Tuple

from OSMPythonTools.overpass import Overpass

from caching import Cache
from routing.valhalla import Valhalla


# search radius in km
RADIUS = 20


class NearestStation:
    def __init__(self, cache: Cache, near_point: Optional[Tuple[float, float]] = None,
                 position: Optional[Tuple[float, float]] = None, routing_algorithm = None):
        self._cache = cache
        self._position = position
        self._near_point = near_point
        self._cost = None
        if not position:
            if cache_hit := cache.get_generic(f'station:{near_point[0]},{near_point[1]}'):
                self._position = cache_hit[0]
                return
            overpass = Overpass(endpoint='https://overpass.kumi.systems/api/')
            result = overpass.query(
                f'(node["railway"="station"](around:{RADIUS * 1000},{near_point[0]},{near_point[1]}););out body geom;',
                out='json')
            routing = routing_algorithm if routing_algorithm else Valhalla(cache)
            if len(result.elements()) == 0:
                raise ValueError(
                    f'There is no station in a {RADIUS}km radius, you have to provide the nearest station manually.')
            for elem in result.elements():
                coords = elem.geometry().coordinates
                try:
                    cost = routing.direct_connection(self._near_point[1], self._near_point[0], coords[0], coords[1])
                except KeyError:
                    continue
                if not self._cost:
                    self._cost = cost
                    self._position = (coords[0], coords[1])
                if cost < self._cost:
                    self._cost = cost
                    self._position = (coords[0], coords[1])
            cache.set_generic(f'station:{near_point[0]},{near_point[1]}', self._position)
            cache.set_generic(f'station_cost:{near_point[0]},{near_point[1]}', self._cost)
            cache.save()
        if not self._cost:
            if cache_hit := cache.get_generic(f'station_cost:{near_point[0]},{near_point[1]}'):
                self._cost = cache_hit
            else:
                routing = routing_algorithm if routing_algorithm else Valhalla(cache)
                self._cost = routing.direct_connection(self._near_point[1], self._near_point[0], self._position[0],
                                                       self._position[1])
                cache.set_generic(f'station_cost:{near_point[0]},{near_point[1]}', self._cost)
                cache.save()

    def get_cost(self):
        return self._cost

    def get_position(self):
        return self._position
