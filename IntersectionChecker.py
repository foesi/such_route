from OSMPythonTools.overpass import Overpass
from shapely.geometry import LineString, Polygon, MultiPolygon
import geojson
import matplotlib.pyplot as plt
import matplotlib.patches as patches



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
      
        shapely_object = create_shapely_polygons(coordinates)

        self._allCantons[canton_code] = shapely_object

    def draw_line_and_polygon(self, polyline, polygonToDraw):
        fig, ax = plt.subplots()        
        if isinstance(polygonToDraw, MultiPolygon):
            for geom in polygonToDraw.geoms:
                patch = patches.Polygon(list(geom.exterior.coords), closed=True, edgecolor='blue', facecolor='lightblue')
                ax.add_patch(patch)
        else:
            coords = list(polygonToDraw.exterior.coords)            
            patch = patches.Polygon(coords, closed=True, edgecolor='blue', facecolor='lightblue')
            # Plot using Matplotlib
            ax.add_patch(patch)
        
        # Extract x and y coordinates from the LineString
        x, y = polyline.xy

        # Plot the LineString
        ax.plot(x, y, label="LineString", color='red', linewidth=2)

        ax.set_aspect('equal')

        # Show plot
        plt.show()


if __name__ == "__main__":
    # draw is only for the debugging!
    # myCheck = CheckIntersectionRouteCanton(True,['CH-ZH','CH-GE','CH-VS'])
    myCheck = CheckIntersectionRouteCanton(True)

    myCheck.Check('test/brouter.geojson', 'CH-VS')

    myCheck.Check('test/BellizonaGenf.geojson', 'CH-VS')
    myCheck.Check('test/ZurichGenf.geojson', 'CH-VS')

    myCheck.Check('test/BellizonaGenf.geojson', 'CH-ZH')
    myCheck.Check('test/ZurichGenf.geojson', 'CH-ZH')

    myCheck.Check('test/BellizonaGenf.geojson', 'CH-GE')
    myCheck.Check('test/ZurichGenf.geojson', 'CH-GE')

