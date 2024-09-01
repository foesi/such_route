import argparse
import csv
import json
import logging
import os

from caching import Cache
from data import Canton
from data.scrambling import Scrambler
from routing.valhalla import Valhalla

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    '''
    This script creates all "stupid" distance matrix between given checkpoints defined by latitude and longitude
    '''

    logger.info('Started')

    parser = argparse.ArgumentParser(description='Creates distance matrices for the SUCH route')

    parser.add_argument('-f', '--filename', type=str,
                        help='The checkpoint csv file', required=True)

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

    routing_backend = Valhalla

    cache = Cache('.such_route_cache', args.backend)
    cache.load()

    cantons = {i['code']: Canton(i['code'], cache) for i in checkpoints}

    cache.save()

    for coordinates, nogos in Scrambler(checkpoints, cantons).calc_matrices():
        routing_service = routing_backend(cache, nogos=nogos)
        result_matrix = {}
        if not nogos:
            # calculate the complete matrix for all checkpoints
            for source in coordinates:
                for target in coordinates:
                    if source != target:
                        if source not in result_matrix:
                            result_matrix[source] = {}
                        result_matrix[source][target], _, _ = routing_service.direct_connection(source[0], source[1],
                                                                                                target[0], target[1])
        else:
            # hacky: get the distances from the cache
            for source in coordinates:
                for target in coordinates:
                    if source != target:
                        if source not in result_matrix:
                            result_matrix[source] = {}
                        result_matrix[source][target], _, _ = cache.get(source, target)
        if not os.path.exists('dummy_results'):
            os.mkdir('dummy_results')
        nogos_string = ','.join(map(lambda x: x.code, nogos)) if nogos else ''
        filename = 'distance_matrix.json' if not nogos_string else f'distance_matrix-{nogos_string}.json'
        with open(f'dummy_results/{filename}', "w") as f:
            json.dump(result_matrix, f)
