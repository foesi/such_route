import csv

from caching import Cache
from data.station import NearestStation

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

    nearest_stations = {}

    for checkpoint in checkpoints:
        try:
            nearest_stations[checkpoint['code']] = NearestStation(cache, near_point=(
                checkpoint['latitude'], checkpoint['longitude']))
        except (ValueError, KeyError):
            print(f'error for canton {checkpoint["canton"]}')

    print(nearest_stations)
