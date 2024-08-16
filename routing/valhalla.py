import io
import json

import requests
import shapely
from OSMPythonTools.overpass import Overpass
from shapely import LineString, MultiLineString

from caching import Cache
from routing_service import RoutingService, RoutingError

inv = 1.0 / 1e6


# decode an encoded string from https://valhalla.github.io/valhalla/decoding/
def decode(encoded):
    decoded = []
    previous = [0, 0]
    i = 0
    # for each byte
    while i < len(encoded):
        # for each coord (lat, lon)
        ll = [0, 0]
        for j in [0, 1]:
            shift = 0
            byte = 0x20
            # keep decoding bytes until you have this coord
            while byte >= 0x20:
                byte = ord(encoded[i]) - 63
                i += 1
                ll[j] |= (byte & 0x1f) << shift
                shift += 5
            # get the final value adding the previous offset and remember it for the next
            ll[j] = previous[j] + (~(ll[j] >> 1) if ll[j] & 1 else (ll[j] >> 1))
            previous[j] = ll[j]
        # scale by the precision and chop off long coords also flip the positions so
        # its the far more standard lon,lat instead of lat,lon
        decoded.append([float('%.6f' % (ll[1] * inv)), float('%.6f' % (ll[0] * inv))])
    # hand back the list of coordinates
    return decoded


class Valhalla(RoutingService):
    def __init__(self, cache: Cache, ferries=False, nogos=None):
        super().__init__(cache, ferries, nogos)
        self.avoid_canton_locations = {}

        def calc_avoided_locations(canton):
            cache_key = f'valhalla:intersection_points:{canton.code}'
            if cache_hit := self.cache.get_generic(cache_key):
                return cache_hit
            border = canton.polygon.boundary
            min_lon, min_lat, max_lon, max_lat = canton.polygon.bounds

            overpass = Overpass(endpoint='https://overpass.kumi.systems/api/')
            result = overpass.query(
                f'rel["ISO3166-2"="{canton.code}"];'
                f'way(r);'
                f'way[highway~"^(motorway|trunk|primary|secondary|tertiary|unclassified|'
                f'residential|living_street|service|(motorway|trunk|primary|secondary)_link)$"](around:0)({min_lat},{min_lon},{max_lat},{max_lon});out geom;',
                out='json', timeout=6000)
            intersection_points = []
            for street in result.elements():
                geometry = street.geometry().coordinates
                if isinstance(geometry[0][0], list):
                    line = MultiLineString(geometry)
                else:
                    line = LineString(geometry)
                intersections = shapely.intersection(border, line)
                if intersections.geom_type == 'Point':
                    intersection_coords = [intersections.coords]
                elif intersections.geom_type == 'MultiPoint':
                    intersection_coords = [geo.coords for geo in intersections.geoms]
                elif intersections.geom_type == 'GeometryCollection':
                    intersection_coords = [geo.coords for geo in intersections.geoms]

                for coords in intersection_coords:
                    point = {'lat': coords[0][1], 'lon': coords[0][0]}
                    intersection_points.append(point)
            self.cache.set_generic(cache_key, intersection_points)
            return intersection_points

        for canton in self.nogos:
            self.avoid_canton_locations[canton] = calc_avoided_locations(canton)

    def matrix(self, coordinates):
        return self._calc_matrix_from_coordinates(coordinates)

    def direct_connection(self, source_lon, source_lat, target_lon, target_lat):
        json_data = {'locations': [{'lat': source_lat, 'lon': source_lon},
                                   {'lat': target_lat, 'lon': target_lon}],
                     'costing_options': {
                       'bicycle': {
                         'bicycle_type': 'road',
                       }
                     },
                     'costing': 'bicycle'}
        if not self._use_ferries:
            # avoid _use_ferries if configured
            json_data['costing_options']['bicycle']['use_ferry'] = 0
        json_data['costing_options']['bicycle']['avoid_bad_surfaces'] = 0.8
        json_data['costing_options']['bicycle']['use_roads'] = 0.8

        if self.nogos:
            excluded_locations = []
            for canton in self.nogos:
                excluded_locations.extend(self.avoid_canton_locations[canton])
            json_data['exclude_locations'] = excluded_locations

        response = requests.post('http://localhost:8002/route', json=json_data)
        result = json.load(io.BytesIO(response.content))

        if 'error' in result:
            raise RoutingError(result['error'])

        # assumption is, there is only one leg. otherwise we have to handle the result differently
        assert len(result['trip']['legs']) == 1
        decoded_route = decode(result['trip']['legs'][0]['shape'])
        route = shapely.LineString(decoded_route)
        return int(result['trip']['summary']['time']), float(result['trip']['summary']['length']), route
