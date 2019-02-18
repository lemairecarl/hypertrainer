from functools import reduce


CSS_STYLE_TAG = '<style>' \
                'td{ padding: 0 0.4em 0 0.4em ; }' \
                'div.h{ font-weight: bold; margin-top: 0.4em; }' \
                '</style>'


def get_item_at_path(obj, path, sep='.', default=KeyError):
    """Use this method like this: `get_item_with_path(obj, 'a.b.c')` to get the item `obj['a']['b']['c']`."""
    try:
        return reduce(lambda o, k: o[k], [obj] + path.split(sep))
    except (IndexError, KeyError):
        if default is KeyError:
            raise
        else:
            return default


def set_item_at_path(obj, path, value, sep='.'):
    """The setter alternative to `get_item_with_path()`."""
    path_tokens = path.split(sep)
    leaf_obj = reduce(lambda o, k: o[k], [obj] + path_tokens[:-1])
    leaf_obj[path_tokens[-1]] = value
    
    
def make_html_table(table, style=True):
    html = CSS_STYLE_TAG if style else ''
    for vals in table:
        html += '<tr>' + ''.join(['<td>{}</td>'.format(x) for x in vals]) + '</tr>'
    html = '<table>' + html + '</table>'
    return html


def make_info_tables(tables_dict):
    html = CSS_STYLE_TAG
    for name, table in tables_dict.items():
        html += '<div class="h">{}</div>'.format(name)
        html += make_html_table(table)
    return html