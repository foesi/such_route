import csv

from geojson import MultiPolygon
from matplotlib import pyplot as plt, patches

from caching import Cache
from data import Canton


def draw_line_and_polygon(line, polygon):
    fig, ax = plt.subplots()
    if isinstance(polygon, MultiPolygon):
        for geom in polygon.geoms:
            patch = patches.Polygon(list(geom.exterior.coords), closed=True, edgecolor='blue', facecolor='lightblue')
            ax.add_patch(patch)
    else:
        coords = list(polygon.exterior.coords)
        patch = patches.Polygon(coords, closed=True, edgecolor='blue', facecolor='lightblue')
        # Plot using Matplotlib
        ax.add_patch(patch)

    # Extract x and y coordinates from the LineString
    x, y = line.xy

    # Plot the LineString
    ax.plot(x, y, label="LineString", color='red', linewidth=2)

    ax.set_aspect('equal')

    # Show plot
    plt.show()


test_cases = [
    ('CH-VS', 'test/brouter.geojson'),
    ('CH-VS', 'test/BellizonaGenf.geojson'),
    ('CH-VS', 'test/ZurichGenf.geojson'),
    ('CH-ZH', 'test/BellizonaGenf.geojson'),
    ('CH-ZH', 'test/ZurichGenf.geojson'),
    ('CH-GE', 'test/BellizonaGenf.geojson'),
    ('CH-GE', 'test/ZurichGenf.geojson'),
]


if __name__ == '__main__':
    checkpoints = []
    with open('checkpoints.csv', 'r') as csv_file:
        checkpoint_reader = csv.reader(csv_file, delimiter=';')
        for i, line in enumerate(checkpoint_reader):
            if i == 0:
                continue
            checkpoints.append(
                {'longitude': float(line[1]), 'latitude': float(line[0]), 'group': line[2], 'code': line[3],
                 'canton': line[4]})

    cache = Cache('.such_route_cache', "valhalla")
    cache.load()

    cantons = {i['code']: Canton(i['code'], cache) for i in checkpoints}

    def test(code, route_file):
        line = Canton.line_from_geojson(route_file)
        cantons[code].intersect(line)
        draw_line_and_polygon(line, cantons[code].polygon)
