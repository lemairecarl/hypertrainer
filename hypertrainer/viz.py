import itertools

from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.palettes import Category10


def generate_plots(metrics_data):
    # metrics_data is a dict: {string: numpy_array}

    # select the tools we want
    TOOLS = "pan,wheel_zoom,box_zoom,reset,save"

    plots = {}
    for name, data in metrics_data.items():
        p = figure(title=name.capitalize(), tools=TOOLS, plot_width=500, plot_height=300)
        if type(data) is dict:
            colors = itertools.cycle(Category10[10])
            for label, sub_data in data.items():
                p.line(x=sub_data[:, 0], y=sub_data[:, 1], legend=label, color=next(colors))
        else:
            p.line(x=data[:, 0], y=data[:, 1])
        plots[name] = p

    script, div = components(plots)
    return script, div
