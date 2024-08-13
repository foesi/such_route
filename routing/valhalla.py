import io
import json

import requests
import shapely

from routing_service import RoutingService


inv = 1.0 / 1e6


# decode an encoded string from https://valhalla.github.io/valhalla/decoding/
def decode(encoded):
    decoded = []
    previous = [0,0]
    i = 0
    # for each byte
    while i < len(encoded):
        # for each coord (lat, lon)
        ll = [0,0]
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
    def matrix(self, coordinates):
        return self._calc_matrix_from_coordinates(coordinates)

    def direct_connection(self, source_lon, source_lat, target_lon, target_lat):
        json_data = {'locations': [{'lat': source_lat, 'lon': source_lon},
                                   {'lat': target_lat, 'lon': target_lon}],
                     'costing': 'bicycle'}
        if not self._use_ferries:
            # avoid _use_ferries if configured
            json_data['costing_options'] = {'bicycle': {'use_ferry': 0}}

        response = requests.post('http://localhost:8002/route', json=json_data)
        result = json.load(io.BytesIO(response.content))
        # assumption is, there is only one leg. otherwise we have to handle the result differently
        assert len(result['trip']['legs']) == 1
        decoded_route = decode(result['trip']['legs'][0]['shape'])
        route = shapely.LineString(decoded_route)
        return int(result['trip']['summary']['time']), float(result['trip']['summary']['length']), route
