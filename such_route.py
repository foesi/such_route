import argparse
import csv
import logging
import multiprocessing
import os
import such_json as json


from caching import Cache
from data import Canton
from data.scrambling import Scrambler
from routing.brouter import Brouter
from routing.valhalla import Valhalla
from routing_service import DEST_COORDS, UNREACHABLE

logger = logging.getLogger(__name__)


# backends
BROUTER = 'brouter'
VALHALLA = 'valhalla'

if __name__ == '__main__':
    '''
    This script creates a distance matrix between given checkpoints defined by latitude and longitude
    '''

    logging.basicConfig(level=logging.INFO)
    logger.info('Started')

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
        logger.info(f'calculate new matrix (avoided cantons: {", ".join([c.code for c in nogos])})')
        routing_service = routing_backend(cache, nogos=nogos)
        result_matrix = {}

        def get_connection(arguments):
            source, target = arguments
            if source != target and source != DEST_COORDS:
                return source, target, routing_service.cache_or_connection(source[0], source[1], target[0],
                                                                           target[1]).get_cost()
            else:
                return None, None, None

        with multiprocessing.Pool(multiprocessing.cpu_count() - 1) as p:
            arguments = []
            for source in coordinates:
                for target in coordinates:
                    arguments.append((source, target))
            for (source, target, cost) in p.imap_unordered(get_connection, arguments):
                if source and target:
                    if source not in result_matrix:
                        result_matrix[source] = {}
                    result_matrix[source][target] = cost

        # make the time to reach any destination from the final destination Bundesplatz in bern very large, so it will
        # be the final destination for sure
        if DEST_COORDS not in result_matrix:
            result_matrix[DEST_COORDS] = {}
        for unreachable_target in coordinates:
            if unreachable_target != DEST_COORDS:
                result_matrix[DEST_COORDS][unreachable_target] = UNREACHABLE

        # save cache after every produced matrix
        cache.save()

        if not os.path.exists('results'):
            os.mkdir('results')
        nogos_string = ','.join(map(lambda x: x.code, nogos)) if nogos else ''
        filename = 'distance_matrix.json' if not nogos_string else f'distance_matrix-{nogos_string}.json'
        with open(f'results/{filename}', "w") as f:
            json.dump(result_matrix, f)

    cache.save()
