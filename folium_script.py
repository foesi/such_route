import pandas as pd
import folium
from shapely import get_coordinates

from caching import Cache
from data import Canton
from data.station import NearestStation
from routing.valhalla import Valhalla
from such_route import VALHALLA


class FoliumMap:
    def __init__(self, csv_file):
        self.data = pd.read_csv(csv_file, delimiter=';')
        self.avoid_cantons = []
        self.cache = Cache('.such_route_cache', VALHALLA)
        self.cache.load()
        self.routing_service = Valhalla(self.cache)

        avoid_canton_codes = list(pd.read_csv('checkpoints.csv', delimiter=';')['Code'])
        for code in self.data['Code']:
            avoid_canton_codes.remove(code)
        for code in avoid_canton_codes:
            self.avoid_cantons.append(Canton(code, self.cache))

    def create_map(self, output_file="swiss_cantons_map.html"):
        foliumColors = ['blue', 'darkgreen', 'cadetblue', 'lightgray', 'purple', 'orange',
                        'darkred', 'lightblue', 'darkblue', 'darkpurple', 'pink', 'black', 'green', 'red']

        # Initialize the Folium map
        center_lat = self.data['Latitude'].mean()
        center_lng = self.data['Longitude'].mean()
        mymap = folium.Map(location=[center_lat, center_lng], zoom_start=8)

        # Add points to the map
        for index, row in self.data.iterrows():
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=f"{row['Canton']}<br>Comment: {row['Comment']}<br>Order: {row['Order']}",
                icon=folium.Icon(color=foliumColors[row['Group']])
            ).add_to(mymap)

        route = []
        for index, row in self.data.iterrows():
            route.append({'order': row['Order'], 'lat': row['Latitude'], 'lon': row['Longitude']})

        route.sort(key=lambda x: x['order'])
        start_station = NearestStation(self.cache, (route[0]['lat'], route[0]['lon']))
        route.insert(0, {'order': -1, 'lat': start_station.get_position()[1], 'lon': start_station.get_position()[0]})

        for i in range(len(route)-1):
            cur = route[i]
            nex = route[i+1]
            calculated_route = self.routing_service.cache_or_connection(cur['lon'], cur['lat'], nex['lon'],
                                                                        nex['lat']).get_route()

            route_coords = list(map(lambda y: [y[1].item(), y[0].item()], get_coordinates(calculated_route)))

            # change color for the route from the station, to the first checkpoint
            color = 'orange' if i == 0 else 'blue'

            folium.PolyLine(
                locations=route_coords,
                color=color,
                opacity=1,
                smooth_factor=0,
            ).add_to(mymap)

        for canton in self.avoid_cantons:
            polygon = canton.polygon
            coords = list(map(lambda y: [y[1].item(), y[0].item()], get_coordinates(polygon)))
            multi_ring = []
            inner_ring = []
            start_coord = None
            for coord in coords:
                if coord == start_coord:
                    inner_ring.append(coord)
                    multi_ring.append(inner_ring)
                    inner_ring = []
                    start_coord = None
                    continue
                if not start_coord:
                    start_coord = coord
                inner_ring.append(coord)

            folium.Polygon(
                locations=multi_ring,
                color="red",
                fillColor="red",
                opacity=0.5,
                smooth_factor=0,
            ).add_to(mymap)

        # Save the map to an HTML file
        mymap.save(output_file)


if __name__ == "__main__":
    result_map = FoliumMap("checkpoints_ordered.csv")
    result_map.create_map()
