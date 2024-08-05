from OSMPythonTools.overpass import Overpass
from shapely import polygons
from matplotlib.patches import Polygon as MplPolygon
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely.geometry import LineString
import geojson

class CheckIntersectionRouteCanton:
    def __init__(self, draw=False, allCantons=None):
        self._draw = draw
        self._allCantons = dict()
        
        # Provide list of all unique canton codes and save them in a dictionary
        if allCantons:
            for code in allCantons:
                self.get_polygon_from_canton_code(code)

    def Check(self, routeGeoJson, canton_code):
        # Load GeoJSON data
        with open(routeGeoJson, encoding='utf-8') as f:
            geojson_data = geojson.load(f)

        # Assuming the GeoJSON contains a single LineString or MultiLineString geometry
        # Extract coordinates (adjust depending on the GeoJSON structure)
        if geojson_data['type'] == 'FeatureCollection':
            coordinates = geojson_data['features'][0]['geometry']['coordinates']
        elif geojson_data['type'] == 'Feature':
            coordinates = geojson_data['geometry']['coordinates']
        else:
            coordinates = geojson_data['coordinates']

        # If height (third value) is included in the coordinates, remove it
        coordinates = [(lon, lat) for lon, lat, _ in coordinates]

        # Create a Shapely Polyline (LineString) object
        polyline = LineString(coordinates)

        self.get_polygon_from_canton_code(canton_code)

        # Check if the LineString intersects with the Polygon
        intersects = polyline.intersects(self._allCantons[canton_code])
        print("Does the line intersect the polygon?", intersects)

        if self._draw:
            self.draw_line_and_polygon(polyline, self._allCantons[canton_code])
        
        return intersects

    def get_polygon_from_canton_code(self, canton_code):
        if canton_code in self._allCantons:
            return
        overpass = Overpass(endpoint='https://overpass.kumi.systems/api/')
        result = overpass.query(f'(relation["type"="boundary"]["boundary"="administrative"]["ISO3166-2"="{canton_code}"];);out body geom;', out='json').elements()[0]
        coordinates = result.geometry().coordinates       

        def flatten_coordinates(nested_list):
            flattened = []
            
            def flatten(sublist):
                for item in sublist:
                    if isinstance(item[0], (list, tuple)):  # If the first element is a list or tuple, we have another level of nesting
                        flatten(item)
                    else:
                        flattened.append(tuple(item))  # Convert to tuple to ensure immutability
            
            flatten(nested_list)
            return flattened
        
        flattened_coordinates = flatten_coordinates(coordinates)

        # Create a Polygon object
        polygon = polygons(flattened_coordinates)

        self._allCantons[canton_code] = polygon

    def draw_line_and_polygon(self, polyline, polygonToDraw):
        coords = list(polygonToDraw.exterior.coords)
        # Convert Shapely Polygon to Matplotlib format
        mpl_polygon = MplPolygon(coords, closed=True, edgecolor='black', facecolor='blue', alpha=0.5)
        # Extract x and y coordinates from the LineString
        x, y = polyline.xy

        # Plot using Matplotlib
        fig, ax = plt.subplots()
        ax.add_patch(mpl_polygon)

        # Plot the LineString
        ax.plot(x, y, label="LineString", color='red', linewidth=2)

        ax.set_aspect('equal')

        # Show plot
        plt.show()


# # Load GeoJSON data
# with open('BellizonaGenf.geojson', encoding='utf-8') as f: #ZurichGenf
#     geojson_data = geojson.load(f)

# # Assuming the GeoJSON contains a single LineString or MultiLineString geometry
# # Extract coordinates (adjust depending on the GeoJSON structure)
# if geojson_data['type'] == 'FeatureCollection':
#     coordinates = geojson_data['features'][0]['geometry']['coordinates']
# elif geojson_data['type'] == 'Feature':
#     coordinates = geojson_data['geometry']['coordinates']
# else:
#     coordinates = geojson_data['coordinates']

# # If height (third value) is included in the coordinates, remove it
# coordinates = [(lon, lat) for lon, lat, _ in coordinates]

# # Create a Shapely Polyline (LineString) object
# polyline = LineString(coordinates)

# overpass = Overpass(endpoint='https://overpass.kumi.systems/api/')
# result = overpass.query('(relation["type"="boundary"]["boundary"="administrative"]["ISO3166-2"="CH-VS"];);out body geom;', out='json').elements()[0]
# polygon = polygons(result.geometry().coordinates)
# print(polygon)

# shapely_polygon = polygon[0]

# if isinstance(shapely_polygon, Polygon):
#     coords = list(shapely_polygon.exterior.coords)
# else:
#     # If not, create a Shapely Polygon from the NumPy array
#     shapely_polygon = Polygon(shapely_polygon)
#     coords = list(shapely_polygon.exterior.coords)

# # Convert Shapely Polygon to Matplotlib format
# mpl_polygon = MplPolygon(coords, closed=True, edgecolor='black', facecolor='blue', alpha=0.5)

# # Check if the LineString intersects with the Polygon
# intersects = polyline.intersects(shapely_polygon)

# print("Does the line intersect the polygon?", intersects)

if __name__ == "__main__":
    # draw is only for the debugging!
    #myCheck = CheckIntersectionRouteCanton(True,['CH-ZH','CH-GE','CH-VS'])

    myCheck.Check('brouter.geojson','CH-VS')

    myCheck.Check('BellizonaGenf.geojson','CH-VS')
    myCheck.Check('ZurichGenf.geojson','CH-VS')

    myCheck.Check('BellizonaGenf.geojson','CH-ZH')
    myCheck.Check('ZurichGenf.geojson','CH-ZH')

    myCheck.Check('BellizonaGenf.geojson','CH-GE')
    myCheck.Check('ZurichGenf.geojson','CH-GE')

