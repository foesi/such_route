import argparse
import csv
import json
import os
import pickle

from brouter import Brouter

if __name__ == '__main__':
    '''
    This script creates a distance matrix between given checkpoints defined by latitude and longitude
    '''
    parser = argparse.ArgumentParser(description='Creates inventory for Osternienburger Land')

    parser.add_argument('-f', '--filename', type=str,
                        help='The checkpoint csv file', required=True)

    args = parser.parse_args()

    if os.path.exists('.such_route_cache'):
        with open('.such_route_cache', 'rb') as f:
            cache = pickle.load(f)
    else:
        cache = {}

    checkpoints = []

    with open(args.filename, 'r') as csv_file:
        checkpoint_reader = csv.reader(csv_file, delimiter=';')
        for i, line in enumerate(checkpoint_reader):
            if i == 0:
                continue
            checkpoints.append({'longitude': float(line[1]), 'latitude': float(line[0]), 'canton': line[2]})

    coordinates = map(lambda x: (x['longitude'], x['latitude']), checkpoints)

    routing_service = Brouter()

    result_matrix = routing_service.matrix(coordinates)

    print('save cache')
    with open('.such_route_cache', 'wb') as f:
        pickle.dump(cache, f)

    print(json.dumps(result_matrix))
