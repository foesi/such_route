import io
import json

import requests

from routing_service import RoutingService


class Valhalla(RoutingService):
    def matrix(self, coordinates):
        return self._calc_matrix_from_coordinates(coordinates)

    def _direct_connection(self, source_lon, source_lat, target_lon, target_lat):
        json_request = {'locations': [{'lat': source_lat, 'lon': source_lon},
                                      {'lat': target_lat, 'lon': target_lon}],
                        'costing': 'bicycle'}
        if not self.ferries:
            # avoid ferries if configured
            json_request['costing_options'] = {'bicycle': {'use_ferry': 0}}
        response = requests.get(f'http://localhost:8002/route?json={json.dumps(json_request)}')
        result = json.load(io.BytesIO(response.content))
        return int(result['trip']['summary']['time'])
