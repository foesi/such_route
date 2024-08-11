import io
import json

import requests

from routing_service import RoutingService


class Brouter(RoutingService):
    def matrix(self, coordinates):
        return self._calc_matrix_from_coordinates(coordinates)

    def direct_connection(self, source_lon, source_lat, target_lon, target_lat):
        coords = f'{source_lon},{source_lat}|{target_lon},{target_lat}'
        response = requests.get(f'http://localhost:17777/brouter?lonlats={coords}&profile=fastbike&format=geojson')
        result = json.load(io.BytesIO(response.content))
        return int(result['features'][0]['properties']['total-time'])
