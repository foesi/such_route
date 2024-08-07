import geojson
from OSMPythonTools.overpass import Overpass
from geojson import MultiPolygon
from shapely import Polygon, LineString


def create_shapely_polygons(geometry):
    polygons = []

    for coords in geometry:
        # Shapely expects a sequence of (x, y) or (lon, lat) tuples
        # Depending on the structure of coordinates, you might need to unwrap nested lists
        polygon = Polygon(coords) if len(coords[0]) == 2 else Polygon(coords[0])
        polygons.append(polygon)

    if len(polygons) == 1:
        return polygons[0]  # Return as a single Polygon
    else:
        return MultiPolygon(polygons)  # Return as a MultiPolygon


def get_polygon_from_canton_code(canton_code):
    overpass = Overpass(endpoint='https://overpass.kumi.systems/api/')
    result = overpass.query(
        f'(relation["type"="boundary"]["boundary"="administrative"]["ISO3166-2"="{canton_code}"];);out body geom;',
        out='json').elements()[0]
    coordinates = result.geometry().coordinates

    return create_shapely_polygons(coordinates)


class Canton:
    def __init__(self, code, cache):
        self.code = code
        if cache_hit := cache.get_generic(code):
            self.polygon = cache_hit
        else:
            polygon = get_polygon_from_canton_code(code)
            cache.set_generic(code, polygon)
            self.polygon = polygon

    @staticmethod
    def line_from_geojson(route_file):
        # Load GeoJSON data
        with open(route_file, encoding='utf-8') as f:
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
        return polyline

    def intersect(self, polyline):
        # Check if the LineString intersects with the Polygon
        intersects = polyline.intersects(self.polygon)
        print("Does the line intersect the polygon?", intersects)
        return bool(intersects)


