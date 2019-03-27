from bokeh.plotting import figure
from bokeh.embed import components


def generate_plots(metrics_data):
    # metrics_data is a dict: {string: numpy_array}

    # select the tools we want
    TOOLS = "pan,wheel_zoom,box_zoom,reset,save"

    plots = {}
    for name, data in metrics_data.items():
        p = figure(title=name.capitalize(), tools=TOOLS, plot_width=400, plot_height=300)
        p.line(x=data[:, 0], y=data[:, 1])
        plots[name] = p

    script, div = components(plots)
    return script, div
