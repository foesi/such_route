import argparse
import csv
import json
import os
import pickle

from brouter import Brouter
from valhalla import Valhalla


DEST_COORDS = '(7.44411, 46.9469)'
# two days in seconds
UNREACHABLE = 172800

# backends
BROUTER = 'brouter'
VALHALLA = 'valhalla'

if __name__ == '__main__':
    '''
    This script creates a distance matrix between given checkpoints defined by latitude and longitude
    '''
    parser = argparse.ArgumentParser(description='Creates inventory for Osternienburger Land')

    parser.add_argument('-f', '--filename', type=str,
                        help='The checkpoint csv file', required=True)
    parser.add_argument('-b', '--backend', type=str, choices=[BROUTER, VALHALLA], default=VALHALLA,
                        help='The routing backend')

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
            checkpoints.append(
                {'longitude': float(line[1]), 'latitude': float(line[0]), 'group': line[2], 'code': line[3],
                 'canton': line[4]})

    coordinates = list(map(lambda x: (x['longitude'], x['latitude']), checkpoints))

    if args.backend == BROUTER:
        routing_backend = Brouter
    elif args.backend == VALHALLA:
        routing_backend = Valhalla
    else:
        routing_backend = Valhalla

    routing_service = routing_backend()

    result_matrix = routing_service.matrix(coordinates)

    # make the time to reach any destination from the final destination Bundesplatz in bern very large, so it will be
    # the final destination for sure
    for unreachable_target in result_matrix[DEST_COORDS]:
        result_matrix[DEST_COORDS][unreachable_target] = UNREACHABLE

    print('save cache')
    with open('.such_route_cache', 'wb') as f:
        pickle.dump(cache, f)

    print(json.dumps(result_matrix))
