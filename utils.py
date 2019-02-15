from functools import reduce


def get_item_at_path(obj, path, sep='.'):
    """Use this method like this: `get_item_with_path(obj, 'a.b.c')` to get the item `obj['a']['b']['c']`."""
    return reduce(lambda o, k: o[k], [obj] + path.split(sep))


def set_item_at_path(obj, path, value, sep='.'):
    """The setter alternative to `get_item_with_path()`."""
    path_tokens = path.split(sep)
    leaf_obj = reduce(lambda o, k: o[k], [obj] + path_tokens[:-1])
    leaf_obj[path_tokens[-1]] = value