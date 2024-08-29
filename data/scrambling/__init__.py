from typing import Dict

from data import Canton


class Scrambler:
    def __init__(self, checkpoints, cantons: Dict[str, Canton]):
        self._groups = {}
        self._jura = None
        self._dest = None
        for checkpoint in checkpoints:
            if checkpoint['group'] == '8':
                self._jura = (checkpoint['longitude'], checkpoint['latitude'])
                continue
            if checkpoint['group'] == '0':
                self._dest = (checkpoint['longitude'], checkpoint['latitude'])
            if checkpoint['group'] not in self._groups:
                self._groups[checkpoint['group']] = []
            self._groups[checkpoint['group']].append(
                ((checkpoint['longitude'], checkpoint['latitude']), cantons[checkpoint['code']]))

    def calc_matrices(self):
        result = []
        result_matrix = [self._jura]
        result_matrix.extend(map(lambda y: y[0], self._groups['1']))
        result_matrix.extend(map(lambda y: y[0], self._groups['2']))
        result_matrix.extend(map(lambda y: y[0], self._groups['3']))
        result_matrix.extend(map(lambda y: y[0], self._groups['4']))
        result_matrix.extend(map(lambda y: y[0], self._groups['5']))
        result_matrix.extend(map(lambda y: y[0], self._groups['6']))
        result_matrix.extend(map(lambda y: y[0], self._groups['7']))
        result_matrix.append(self._dest)
        result.append((result_matrix, []))

        for elem1 in self._groups['1']:
            for elem2 in self._groups['2']:
                for elem3 in self._groups['3']:
                    for elem4 in self._groups['4']:
                        for elem5 in self._groups['5']:
                            for elem6 in self._groups['6']:
                                for elem7 in self._groups['7']:
                                    result_matrix = [self._jura]
                                    nogos = []
                                    result_matrix.extend(
                                        map(lambda y: y[0], filter(lambda x: x != elem1, self._groups['1'])))
                                    result_matrix.extend(
                                        map(lambda y: y[0], filter(lambda x: x != elem2, self._groups['2'])))
                                    result_matrix.extend(
                                        map(lambda y: y[0], filter(lambda x: x != elem3, self._groups['3'])))
                                    result_matrix.extend(
                                        map(lambda y: y[0], filter(lambda x: x != elem4, self._groups['4'])))
                                    result_matrix.extend(
                                        map(lambda y: y[0], filter(lambda x: x != elem5, self._groups['5'])))
                                    result_matrix.extend(
                                        map(lambda y: y[0], filter(lambda x: x != elem6, self._groups['6'])))
                                    result_matrix.extend(
                                        map(lambda y: y[0], filter(lambda x: x != elem7, self._groups['7'])))
                                    result_matrix.append(self._dest)
                                    nogos.append(elem1[1])
                                    nogos.append(elem2[1])
                                    nogos.append(elem3[1])
                                    nogos.append(elem4[1])
                                    nogos.append(elem5[1])
                                    nogos.append(elem6[1])
                                    nogos.append(elem7[1])
                                    result.append((result_matrix, nogos))

        return result



