import argparse
import csv
import os
import such_json as json


from caching import Cache
from data import Canton
from data.scrambling import Scrambler
from routing.brouter import Brouter
from routing.valhalla import Valhalla


# backends
BROUTER = 'brouter'
VALHALLA = 'valhalla'

if __name__ == '__main__':
    '''
    This script creates a distance matrix between given checkpoints defined by latitude and longitude
    '''
    parser = argparse.ArgumentParser(description='Creates distance matrices for the SUCH route')

    parser.add_argument('-f', '--filename', type=str,
                        help='The checkpoint csv file', required=True)
    parser.add_argument('-b', '--backend', type=str, choices=[BROUTER, VALHALLA], default=VALHALLA,
                        help='The routing backend')

    args = parser.parse_args()

    checkpoints = []

    with open(args.filename, 'r') as csv_file:
        checkpoint_reader = csv.reader(csv_file, delimiter=';')
        for i, line in enumerate(checkpoint_reader):
            if i == 0:
                continue
            checkpoints.append(
                {'longitude': float(line[1]), 'latitude': float(line[0]), 'group': line[2], 'code': line[3],
                 'canton': line[4]})

    if args.backend == BROUTER:
        routing_backend = Brouter
    elif args.backend == VALHALLA:
        routing_backend = Valhalla
    else:
        routing_backend = Valhalla

    cache = Cache('.such_route_cache', args.backend)
    cache.load()

    cantons = {i['code']: Canton(i['code'], cache) for i in checkpoints}

    cache.save()

    for coordinates, nogos in Scrambler(checkpoints, cantons).calc_matrices():
        routing_service = routing_backend(cache, nogos=nogos)
        result_matrix = routing_service.matrix(coordinates)
        if not os.path.exists('results'):
            os.mkdir('results')
        nogos_string = ','.join(map(lambda x: x.code, nogos)) if nogos else ''
        filename = 'distance_matrix.json' if not nogos_string else f'distance_matrix-{nogos_string}.json'
        with open(f'results/{filename}', "w") as f:
            json.dump(result_matrix, f)

    cache.save()
