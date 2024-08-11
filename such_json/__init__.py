import json
import re


class TupleKeyEncoder(json.JSONEncoder):
    """
    Taken from https://stackoverflow.com/questions/15721363/preserve-python-tuples-with-json
    """
    def encode(self, obj):
        def hint_tuples(item):
            if isinstance(item, tuple):
                if len(item) == 2:
                    return f'({item[0]}, {item[1]})'
                raise TypeError('Only duples are allowed.')
            if isinstance(item, dict):
                return {hint_tuples(key): hint_tuples(value) for key, value in item.items()}
            else:
                return item

        return super(TupleKeyEncoder, self).encode(hint_tuples(obj))


def hinted_tuple_hook(obj):
    if isinstance(obj, dict):
        new_dict = {}
        for key in obj:
            if match := re.match(r'\(([\d.]+), ?([\d.]+)\)', key):
                new_dict[(float(match.group(1)), float(match.group(2)))] = obj[key]
            else:
                new_dict[key] = obj[key]
        return new_dict
    else:
        return obj


def dump(obj, fp):
    enc = TupleKeyEncoder()
    fp.write(enc.encode(obj))


def load(fp):
    return json.load(fp, object_hook=hinted_tuple_hook)
