from __future__ import division
from __future__ import print_function

import plotly.graph_objs as go
from plotly.offline import plot

from cea.plots.color_code import ColorCodeCEA
from cea.plots.variable_naming import NAMING, LOGO

COLOR = ColorCodeCEA()


def energy_use_intensity(data_frame, analysis_fields, title, output_path):
    # CALCULATE GRAPH
    traces_graph = calc_graph(analysis_fields, data_frame)

    # CALCULATE TABLE
    traces_table = calc_table(analysis_fields, data_frame)

    # PLOT GRAPH
    traces_graph.append(traces_table)
    layout = go.Layout(images=LOGO, title=title, barmode='stack',
                       yaxis=dict(title='Energy Use Intensity [kWh/m2.yr]', domain=[0.35, 1]),
                       xaxis=dict(title='Scenario Name'))
    fig = go.Figure(data=traces_graph, layout=layout)
    plot(fig, auto_open=False, filename=output_path)

    return {'data': traces_graph, 'layout': layout}


def calc_table(analysis_fields, data_frame):
    median = data_frame[analysis_fields].median().round(2).tolist()
    # calculate graph
    anchors = []
    load_names = []
    for field in analysis_fields:
        data_frame[field] = data_frame[field] * 1000 / data_frame["GFA_m2"]  # in kWh/m2y
        anchors.append(calc_top_three_anchor_loads(data_frame, field))
        load_names.append(NAMING[field.split('_', 1)[0]] + ' (' + field.split('_', 1)[0] + ')')

    table = go.Table(domain=dict(x=[0, 1.0], y=[0, 0.2]),
                     header=dict(values=['Load Name', 'Median [kWh/m2.yr]', 'Top 3 more efficient']),
                     cells=dict(values=[load_names, median, anchors]))

    return table


def calc_graph(analysis_fields, data_frame):
    # calculate graph
    graph = []
    for field in analysis_fields:
        data_frame[field] = data_frame[field] * 1000 / data_frame["GFA_m2"]  # in kWh/m2y
    data_frame['total'] = total = data_frame[analysis_fields].sum(axis=1)
    data_frame = data_frame.sort_values(by='total', ascending=False)  # this will get the maximum value to the left
    for field in analysis_fields:
        y = data_frame[field]
        total_perc = (y / total * 100).round(2).values
        total_perc_txt = ["(" + str(x) + " %)" for x in total_perc]
        trace = go.Bar(x=data_frame.index, y=y, name=field.split('_', 1)[0], text=total_perc_txt, orientation='v',
                       marker=dict(color=COLOR.get_color_rgb(field.split('_', 1)[0])))
        graph.append(trace)

    return graph


def calc_top_three_anchor_loads(data_frame, field):
    data_frame = data_frame.sort_values(by=field, ascending=True)
    anchor_list = data_frame[:3].index.values
    return anchor_list
