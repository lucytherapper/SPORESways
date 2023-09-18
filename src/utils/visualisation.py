import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.patches as mpatches
from matplotlib.legend_handler import HandlerBase
from matplotlib.text import Text
import matplotlib.gridspec as gridspec
import seaborn as sns
import seaborn.objects as so
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from scipy.spatial import distance_matrix
from scipy.cluster.hierarchy import dendrogram

from src.utils.parameters import *
from src.utils.data_io import *

# Define open circles for plotting 'All other SPORES'
pts = np.linspace(0, np.pi * 2, 24)
circ = np.c_[np.sin(pts) / 2, -np.cos(pts) / 2]
vert = np.r_[circ, circ[::-1] * 0.7]
open_circle = mpl.path.Path(vert)


POWER_TECH_COLORS = {
    "All other SPORES": "#b9b9b9",
    "Nuclear": "#cc0000",
    "nuclear": "#cc0000",
    "Battery": "#8fce00",
    "CCGT": "#8fce00",
    "ccgt": "#8fce00",
    # "CHP": "#ce7e00",
    # "chp": "#ce7e00",
    "Gas turbines": "#ce7e00",
    "PV": "#ffd966",
    "pv": "#ffd966",
    "Onshore wind": "#674ea7",
    "onshore wind": "#674ea7",
    "Offshore wind": "#e062db",
    "offshore wind": "#e062db",
    "Wind": "#674ea7",
    "Hydro": "#2986cc",
    "hydro": "#2986cc",
    "Coal": "#000000",  # Black = #000000, Grey = #808080
    "coal": "#000000",
    "International transmission": "#008080",
}


metric_plot_order = {
    "curtailment": 2,
    "electricity_production_gini": 5,
    "average_national_import": 4,
    "fuel_autarky_gini": 6,
    "storage_discharge_capacity": 1,
    "transport_electrification": 9,
    "heat_electrification": 8,
    "biofuel_utilisation": 3,
    "ev_flexibility": 7,
}
tech_plot_names = {
    "Battery": "Battery",
    "Gas turbines": "Gas turbines",
    "Coal": "Coal",
    "Hydro": "Hydro",
    "International transmission": "International\ntransmission",
    "Offshore wind": "Offshore\nwind",
    "Onshore wind": "Onshore\nwind",
    "PV": "PV",
    "Nuclear": "Nuclear",
}
metric_plot_names = {
    "curtailment": "Curtailment",
    "electricity_production_gini": "Electricity production\nGini coefficient",
    "average_national_import": "Average\nnational import",
    "fuel_autarky_gini": "Fuel autarky\nGini coefficient",
    "storage_discharge_capacity": "Storage discharge\ncapacity",
    "transport_electrification": "Transport\nelectrification",
    "heat_electrification": "Heat\nelectrification",
    "biofuel_utilisation": "Biofuel\nutilisation",
    "ev_flexibility": "EV as flexibility",
}
primary_energy_plot_names = {
    "Biofuels": "Biofuels",
    "Coal": "Coal",
    "Natural gas": "Natural gas",
    "Oil": "Oil",
    "Waste": "Waste",
    "Renewable electricity": "Renewable electricity",
    "Net natural gas import": "Net natural\ngas import",
    "Net oil import": "Net oil\nimport",
    "Net electricity import": "Net electricity\nimport",
}
metric_range_formatting = {
    "curtailment": lambda x: x.round(0).astype(int),
    "electricity_production_gini": lambda x: x.round(2),
    "average_national_import": lambda x: x.round(0).astype(int),
    "fuel_autarky_gini": lambda x: x.round(2),
    "storage_discharge_capacity": lambda x: x.round(0).astype(int)
    if x.name == "max"
    else x.round(2),
    "transport_electrification": lambda x: x.round(0).astype(int),
    "heat_electrification": lambda x: x.round(0).astype(int),
    "biofuel_utilisation": lambda x: x.round(0).astype(int),
    "ev_flexibility": lambda x: x.round(2),
}
FIGWIDTH = 6.77165


class HandlerNumber(HandlerBase):
    def __init__(self, number, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.number = number

    def create_artists(
        self, legend, orig_handle, xdescent, ydescent, width, height, fontsize, trans
    ):
        tx = Text(
            xdescent + 0.5 * (width - xdescent),
            ydescent,
            str(self.number),
            fontsize=fontsize,
            ha="center",
            va="center",
            color="black",
        )
        return [tx]


def normalise_to_max(x):
    max_value = abs(x).max()
    return x / max_value


def hex_to_greyscale(hex_value):
    # Convert hex to RGB
    r, g, b = (int(hex_value.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))

    # Convert RGB to grayscale and then to hex
    grey_value = int(0.2989 * r + 0.5870 * g + 0.1140 * b)
    return "#{:02x}{:02x}{:02x}".format(grey_value, grey_value, grey_value)


POWER_TECH_COLORS_GREYED = {
    tech: hex_to_greyscale(color) for tech, color in POWER_TECH_COLORS.items()
}


def get_color_dict2(label_list):
    color_palette = sns.color_palette("bright")
    colors = {
        label_list[i]: color_palette[i % len(color_palette)]
        for i in range(len(label_list))
    }
    colors["rest_color"] = color_palette[-3]
    return colors


def get_color_dict(label_list):
    # Define colours
    colors = {
        label_list[i]: (
            sns.color_palette("bright")[:-3] + sns.color_palette("bright")[-2:]
        )[i]
        for i in range(len(label_list))
    }
    colors["rest_color"] = sns.color_palette("bright")[-3]
    return colors


def remove_top_and_right_spines(ax):
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    # ax.xaxis.set_ticks_position("bottom")
    # ax.yaxis.set_ticks_posittion("left")


def plot_scenario_capacity_stacked_barchart2(
    power_capacity,
    n_spores_per_cluster,
    year,
    ax,
    spores_amount_y_offset=20,
    greyed_out_scenarios=[],
):
    scenario_description = describe_scenario(power_capacity)
    scenario_values = scenario_description.loc[
        :, ["cluster", "technology", "mean"]
    ].pivot_table(index="cluster", columns="technology")["mean"]

    # Plot figure
    scenario_values.plot(ax=ax, kind="bar", stacked=True, color=POWER_TECH_COLORS)
    ax.set_xlabel(f"{year}", weight="bold")
    ax.set_ylabel("Average installed capacity [GW]", weight="bold")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)

    # Annotate number of SPORE in each cluster on top of each bar
    for cluster_number, spores_count in enumerate(n_spores_per_cluster):
        ax.text(
            cluster_number,
            # FIXME: Scale this to the max total capacity that exist in the figure
            scenario_values.sum(axis=1)[cluster_number] + spores_amount_y_offset,
            f"{spores_count}",
            va="center",
            ha="center",
        )

    # Grey out bars if needed
    techs = scenario_values.columns.to_list()
    for tech_index, bar_container in enumerate(ax.containers):
        tech = techs[tech_index]
        for cluster_index, bar in enumerate(bar_container):
            if cluster_index in greyed_out_scenarios:
                bar.set_facecolor(POWER_TECH_COLORS_GREYED[tech])

    # Remove legend
    ax.get_legend().remove()
    # Remove top and right spines
    remove_top_and_right_spines(ax)


def plot_scenario_capacity_stacked_barchart(
    scenario_values,
    n_spores_per_cluster,
    year,
    ax,
    spores_amount_y_offset=20,
    greyed_out_scenarios=[],
):
    # Plot figure
    scenario_bars = scenario_values.plot(
        ax=ax, kind="bar", stacked=True, color=POWER_TECH_COLORS
    )
    ax.set_xlabel(f"{year}", weight="bold")
    ax.set_ylabel("Average installed capacity [GW]", weight="bold")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)

    # Annotate number of SPORE in each cluster on top of each bar
    for cluster_number, spores_count in enumerate(n_spores_per_cluster):
        ax.text(
            cluster_number,
            # FIXME: Scale this to the max total capacity that exist in the figure
            scenario_values.sum(axis=1)[cluster_number] + spores_amount_y_offset,
            f"{spores_count}",
            va="center",
            ha="center",
        )

    # Grey out bars if needed
    techs = scenario_values.columns.to_list()
    for tech_index, bar_container in enumerate(ax.containers):
        tech = techs[tech_index]
        for cluster_index, bar in enumerate(bar_container):
            if cluster_index in greyed_out_scenarios:
                bar.set_facecolor(POWER_TECH_COLORS_GREYED[tech])

    # Remove legend
    ax.get_legend().remove()
    # Remove top and right spines
    remove_top_and_right_spines(ax)


def plot_metrics_distribution(ax, metrics, year, focus_cluster=None, plot_boxes=False):
    # Calculate metric ranges and get units
    metric_ranges = metrics.groupby(level="metric").agg(["min", "max"])
    metric_units = (
        metrics.index.to_frame(index=False)
        .drop_duplicates(subset="metric")
        .set_index("metric")["unit"]
        .to_dict()
    )

    # Normalise metrics
    metrics_normalised = (
        metrics.groupby(["metric"]).transform(normalise_to_max).reset_index()
    )

    # Calculate min, max for focus cluster (for plotting boxes)
    max_scenario = (
        metrics_normalised.loc[
            (metrics_normalised.cluster == focus_cluster), ["paper_metrics", "metric"]
        ]
        .groupby("metric")
        .max()["paper_metrics"]
    )
    min_scenario = (
        metrics_normalised.loc[
            (metrics_normalised.cluster == focus_cluster), ["paper_metrics", "metric"]
        ]
        .groupby("metric")
        .min()["paper_metrics"]
    )

    # Get colors dictionary for metric
    metric_labels = list(metrics.index.unique(level="metric"))
    cluster_labels = list(metrics.index.unique(level="cluster"))
    metric_colors = get_color_dict2(metric_labels)
    cluster_colors = get_color_dict2(cluster_labels)

    # Get SPORES to plot in color (SPORES that belong to a specific cluster)
    # spores_to_plot_in_color = metrics.xs(focus_cluster, level="cluster").index.unique(level="spore")
    spores_to_plot_in_color = metrics_normalised[
        (metrics_normalised.cluster == focus_cluster)
    ].spore.values

    #
    sns.stripplot(
        ax=ax,
        data=metrics_normalised[
            ~metrics_normalised.spore.isin(spores_to_plot_in_color)
        ],
        x="metric",
        y="paper_metrics",
        marker="o",
        color=metric_colors["rest_color"],
        alpha=0.5,
        s=3,
    )
    # Color focus scenario
    if focus_cluster is not None:
        sns.stripplot(
            data=metrics_normalised[
                metrics_normalised.spore.isin(spores_to_plot_in_color)
            ],
            x="metric",
            y="paper_metrics",
            alpha=0.5,
            ax=ax,
            marker="o",
            palette=metric_colors,
            s=3,
        )
    # Format y-axis
    ax.set_ylabel("Normalised metric score", weight="bold")
    # Format x-axis
    ax.set_xlabel("")
    ax.set_xticks(range(len(metric_labels)))
    ax.set_xticklabels(metric_labels, fontsize=10)
    xticklabels = []
    _x = 0
    for ticklabel in ax.get_xticklabels():
        _metric = ticklabel.get_text()

        # Plot boxes
        if plot_boxes:
            xmin = _x - 0.2
            xmax = _x + 0.2
            height = max_scenario.loc[_metric] - min_scenario.loc[_metric]
            height += 0.018
            ax.add_patch(
                mpl.patches.Rectangle(
                    xy=(xmin, min_scenario.loc[_metric] - 0.009),
                    height=height,
                    width=(xmax - xmin),
                    fc="None",
                    ec=metric_colors[_metric],
                    linestyle="--",
                    lw=0.75,
                    zorder=10,
                ),
            )
            _x += 1

        # Format x-axis labels
        metric_range = metric_ranges.apply(metric_range_formatting[_metric]).loc[
            _metric
        ]
        _unit = metric_units.get(_metric)
        if _unit == "percentage":
            _unit = " %"
        elif _unit == "fraction":
            _unit = ""
        else:
            _unit = " " + _unit
        xticklabels.append(
            f"{metric_plot_names[_metric]}\n({metric_range['min']} - {metric_range['max']}){_unit}"
        )
    ax.set_xticklabels(xticklabels, fontsize=9)

    # FIXME: get unique spores only
    # print(spores_to_plot_in_color)

    # Set figure title
    # n_spores_per_cluster = count_spores_per_cluster(metrics)
    # ax.set_title(
    #     f"Scenario {focus_cluster} ({year}): {n_spores_per_cluster[focus_cluster]} SPORES"
    # )

    # Remove top and right spines
    remove_top_and_right_spines(ax)


def plot_metrics_distribution_based_on_spores(ax, metrics, focus_spores=None):
    # Calculate metric ranges and get units
    metric_ranges = metrics.groupby(level="metric").agg(["min", "max"])
    metric_units = (
        metrics.index.to_frame(index=False)
        .drop_duplicates(subset="metric")
        .set_index("metric")["unit"]
        .to_dict()
    )

    # Normalise metrics
    metrics_normalised = (
        metrics.groupby(["metric"]).transform(normalise_to_max).reset_index()
    )

    # Calculate min, max for focus cluster (for plotting boxes)
    max_scenario = (
        metrics_normalised.loc[
            (metrics_normalised.spore.isin(focus_spores)), ["paper_metrics", "metric"]
        ]
        .groupby("metric")
        .max()["paper_metrics"]
    )
    min_scenario = (
        metrics_normalised.loc[
            (metrics_normalised.spore.isin(focus_spores)), ["paper_metrics", "metric"]
        ]
        .groupby("metric")
        .min()["paper_metrics"]
    )

    # Get colors dictionary for metric
    metric_labels = list(metrics.index.unique(level="metric"))
    metric_colors = get_color_dict2(metric_labels)

    #
    sns.stripplot(
        ax=ax,
        data=metrics_normalised[~metrics_normalised.spore.isin(focus_spores)],
        x="metric",
        y="paper_metrics",
        marker="o",
        color=metric_colors["rest_color"],
        alpha=0.5,
        s=3,
    )
    # Color focus scenario
    if focus_spores is not None:
        sns.stripplot(
            data=metrics_normalised[metrics_normalised.spore.isin(focus_spores)],
            x="metric",
            y="paper_metrics",
            alpha=0.5,
            ax=ax,
            marker="o",
            palette=metric_colors,
            s=3,
        )
    # Format y-axis
    ax.set_ylabel("Normalised metric score", weight="bold")
    # Format x-axis
    ax.set_xlabel("")
    ax.set_xticks(range(len(metric_labels)))
    ax.set_xticklabels(metric_labels, fontsize=10)
    xticklabels = []
    _x = 0
    for ticklabel in ax.get_xticklabels():
        _metric = ticklabel.get_text()

        # Plot boxes
        xmin = _x - 0.2
        xmax = _x + 0.2
        height = max_scenario.loc[_metric] - min_scenario.loc[_metric]
        height += 0.018
        ax.add_patch(
            mpl.patches.Rectangle(
                xy=(xmin, min_scenario.loc[_metric] - 0.009),
                height=height,
                width=(xmax - xmin),
                fc="None",
                ec=metric_colors[_metric],
                linestyle="--",
                lw=0.75,
                zorder=10,
            ),
        )
        _x += 1

        # Format x-axis labels
        metric_range = metric_ranges.apply(metric_range_formatting[_metric]).loc[
            _metric
        ]
        _unit = metric_units.get(_metric)
        if _unit == "percentage":
            _unit = " %"
        elif _unit == "fraction":
            _unit = ""
        else:
            _unit = " " + _unit
        xticklabels.append(
            f"{metric_plot_names[_metric]}\n({metric_range['min']} - {metric_range['max']}){_unit}"
        )
    ax.set_xticklabels(xticklabels, fontsize=9)

    # Remove top and right spines
    remove_top_and_right_spines(ax)


def plot_capacity_distribution(ax, capacity, year, resolution, focus_cluster=None):
    # Calculate metric ranges
    capacity_ranges = (
        capacity.groupby(level=["region", "technology"])
        .agg(["min", "max"])
        .droplevel("region")
    )

    # Normalise capacity
    capacity_normalised = (
        capacity.groupby(level=["region", "technology"])
        .transform(normalise_to_max)
        .reset_index()
    )
    print(capacity)
    print(capacity_normalised)
    # Calculate min, max for focus cluster (for plotting boxes)
    max_scenario = (
        capacity_normalised.loc[
            (capacity_normalised.cluster == focus_cluster),
            ["capacity_gw", "technology"],
        ]
        .groupby("technology")
        .max()["capacity_gw"]
    )
    min_scenario = (
        capacity_normalised.loc[
            (capacity_normalised.cluster == focus_cluster),
            ["capacity_gw", "technology"],
        ]
        .groupby("technology")
        .min()["capacity_gw"]
    )

    # Get colors dictionary for metric
    tech_labels = list(capacity.index.unique(level="technology"))
    cluster_labels = list(capacity.index.unique(level="cluster"))

    cluster_colors = get_color_dict2(cluster_labels)

    # Get SPORES to plot in color (SPORES that belong to a specific cluster)
    # spores_to_plot_in_color = metrics.xs(focus_cluster, level="cluster").index.unique(level="spore")
    spores_to_plot_in_color = capacity_normalised[
        (capacity_normalised.cluster == focus_cluster)
    ].spore.values

    #
    sns.stripplot(
        ax=ax,
        data=capacity_normalised[
            ~capacity_normalised.spore.isin(spores_to_plot_in_color)
        ],
        x="technology",
        y="capacity_gw",
        marker="o",
        color=cluster_colors["rest_color"],
        alpha=0.5,
        s=3,
    )
    # Color focus scenario
    if focus_cluster is not None:
        sns.stripplot(
            data=capacity_normalised[
                capacity_normalised.spore.isin(spores_to_plot_in_color)
            ],
            x="technology",
            y="capacity_gw",
            alpha=0.5,
            ax=ax,
            marker="o",
            palette=POWER_TECH_COLORS,
            s=3,
        )

    # Format y-axis
    ax.set_ylabel("Normalised installed capacity", weight="bold")

    # Format x-axis
    ax.set_xlabel("")
    ax.set_xticks(range(len(tech_labels)))
    ax.set_xticklabels(tech_labels, fontsize=10)
    xticklabels = []
    _x = 0

    for ticklabel in ax.get_xticklabels():
        _tech = ticklabel.get_text()

        # Plot boxes
        xmin = _x - 0.2
        xmax = _x + 0.2
        height = max_scenario.loc[_tech] - min_scenario.loc[_tech]
        height += 0.018
        ax.add_patch(
            mpl.patches.Rectangle(
                xy=(xmin, min_scenario.loc[_tech] - 0.009),
                height=height,
                width=(xmax - xmin),
                fc="None",
                ec=POWER_TECH_COLORS[_tech],
                linestyle="--",
                lw=0.75,
                zorder=10,
            ),
        )
        _x += 1

        # Format x-axis labels
        capacity_range = capacity_ranges.loc[_tech].round(0).astype(int)
        xticklabels.append(
            f"{_tech}\n({capacity_range['min']} - {capacity_range['max']}) gw"
        )
    ax.set_xticklabels(xticklabels, fontsize=9)

    # Remove top and right spines
    remove_top_and_right_spines(ax)


def plot_capacity_distribution_based_on_spores(
    ax, capacity, focus_spores=None, color=None
):
    # Calculate metric ranges
    capacity_ranges = (
        capacity.groupby(level=["region", "technology"])
        .agg(["min", "max"])
        .droplevel("region")
    )

    # Normalise capacity
    capacity_normalised = (
        capacity.groupby(level=["region", "technology"])
        .transform(normalise_to_max)
        .reset_index()
    )

    # Calculate min, max for focus cluster (for plotting boxes)
    max_scenario = (
        capacity_normalised.loc[
            (capacity_normalised.spore.isin(focus_spores)),
            ["capacity_gw", "technology"],
        ]
        .groupby("technology")
        .max()["capacity_gw"]
    )
    min_scenario = (
        capacity_normalised.loc[
            (capacity_normalised.spore.isin(focus_spores)),
            ["capacity_gw", "technology"],
        ]
        .groupby("technology")
        .min()["capacity_gw"]
    )

    # Get colors dictionary for metric
    tech_labels = list(capacity.index.unique(level="technology"))
    cluster_labels = list(capacity.index.unique(level="cluster"))

    cluster_colors = get_color_dict2(cluster_labels)

    # Get SPORES to plot in color (SPORES that belong to a specific cluster)
    # spores_to_plot_in_color = metrics.xs(focus_cluster, level="cluster").index.unique(level="spore")
    # spores_to_plot_in_color = capacity_normalised[
    #     (capacity_normalised.cluster == focus_cluster)
    # ].spore.values

    #
    sns.stripplot(
        ax=ax,
        data=capacity_normalised[~capacity_normalised.spore.isin(focus_spores)],
        x="technology",
        y="capacity_gw",
        marker="o",
        color=cluster_colors["rest_color"],
        alpha=0.5,
        s=3,
    )
    # Color focus scenario
    if focus_spores is not None:
        sns.stripplot(
            data=capacity_normalised[capacity_normalised.spore.isin(focus_spores)],
            x="technology",
            y="capacity_gw",
            alpha=0.5,
            ax=ax,
            marker="o",
            palette=POWER_TECH_COLORS,
            s=3,
        )

    # Format y-axis
    ax.set_ylabel("Normalised installed capacity", weight="bold")

    # Format x-axis
    ax.set_xlabel("")
    ax.set_xticks(range(len(tech_labels)))
    ax.set_xticklabels(tech_labels, fontsize=10)
    xticklabels = []
    _x = 0

    for ticklabel in ax.get_xticklabels():
        _tech = ticklabel.get_text()

        # Plot boxes
        xmin = _x - 0.2
        xmax = _x + 0.2
        height = max_scenario.loc[_tech] - min_scenario.loc[_tech]
        height += 0.018
        ax.add_patch(
            mpl.patches.Rectangle(
                xy=(xmin, min_scenario.loc[_tech] - 0.009),
                height=height,
                width=(xmax - xmin),
                fc="None",
                ec=POWER_TECH_COLORS[_tech],
                linestyle="--",
                lw=0.75,
                zorder=10,
            ),
        )
        _x += 1

        # Format x-axis labels
        capacity_range = capacity_ranges.loc[_tech].round(0).astype(int)
        xticklabels.append(
            f"{_tech}\n({capacity_range['min']} - {capacity_range['max']})\ngw"
        )
    ax.set_xticklabels(xticklabels, fontsize=9)

    # Remove top and right spines
    remove_top_and_right_spines(ax)


def format_axis_for_capacity_distibution_plot(ax, capacity):
    tech_labels = list(capacity.index.unique(level="technology"))

    # Calculate metric ranges
    capacity_ranges = (
        capacity.groupby(level=["region", "technology"])
        .agg(["min", "max"])
        .droplevel("region")
    )

    # Format y-axis
    ax.set_ylabel("Normalised installed capacity", weight="bold")

    # Format x-axis
    ax.set_xlabel("")
    ax.set_xticks(range(len(tech_labels)))
    ax.set_xticklabels(tech_labels, fontsize=10)
    xticklabels = []
    _x = 0

    for ticklabel in ax.get_xticklabels():
        _tech = ticklabel.get_text()

        # Format x-axis labels
        capacity_range = capacity_ranges.loc[_tech].round(0).astype(int)
        xticklabels.append(
            f"{_tech}\n({capacity_range['min']} - {capacity_range['max']})\ngw"
        )
    ax.set_xticklabels(xticklabels, fontsize=9)

    # Remove top and right spines
    remove_top_and_right_spines(ax)


def plot_capacity_pathway(power_capacity):
    pass


def plot_elbow_figure(wcss, min_clusters, max_clusters, spatial_resolution, year):
    # Using Elbow method
    plt.figure()
    plt.plot(range(min_clusters, max_clusters + 1), wcss, marker="o")
    plt.xlabel("Number of Clusters")
    plt.ylabel("WCSS")
    plt.savefig(
        f"../figures/appendices/finding_optimal_n_scenarios/elbow_method_{spatial_resolution}_{year}.png",
        bbox_inches="tight",
        dpi=120,
    )
    plt.title(f"Elbow Method for {year}")


def plot_silhouette_score(
    silhouette_scores, min_clusters, max_clusters, spatial_resolution, year
):
    plt.figure()
    plt.plot(range(min_clusters, max_clusters + 1), silhouette_scores, marker="o")
    plt.xlabel("Number of Clusters")
    plt.ylabel("Silhouette Score")
    plt.savefig(
        f"../figures/appendices/finding_optimal_n_scenarios/silhouette_method_{spatial_resolution}_{year}.png",
        bbox_inches="tight",
        dpi=120,
    )
    plt.title(f"Silhouette Score Method for {year}")


def plot_scenario_barchart_legend(ax, handles, labels, year, n_spores):
    handles_colored = [
        mpatches.Patch(facecolor=POWER_TECH_COLORS[tech], label=tech) for tech in labels
    ]
    handles = handles_colored
    proxy_spores_per_cluster = mpatches.Rectangle(
        (0, 0),
        1,
        1,
        fc="w",
        fill=False,
        edgecolor="none",
        label=f"Number of SPORES\nper scenario",
    )
    handles.insert(0, proxy_spores_per_cluster)
    labels.insert(0, proxy_spores_per_cluster.get_label())

    proxy_spores = mpatches.Rectangle(
        (0, 0),
        1,
        1,
        fc="w",
        fill=False,
        edgecolor="none",
        label=f"Total number of\nSPORES in {year}",
    )
    handles.append(proxy_spores)
    labels.append(proxy_spores.get_label())

    ax.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(0, 1),
        frameon=False,
        handler_map={
            proxy_spores_per_cluster: HandlerNumber(42),
            proxy_spores: HandlerNumber(n_spores),
        },
    )
    ax.axis("off")


def plot_scenario_analysis_barchart(
    scenario_description,
    n_spores_per_cluster,
    resolution,
    value_to_plot="mean",
    years=["2030", "2050"],
):
    if resolution == "Europe":
        spores_amount_y_offset = 200
    else:
        spores_amount_y_offset = 20

    # Distribute the width of the subfigures according to the number of scenarios in each figure
    n_clusters_2030 = len(n_spores_per_cluster.get("2030"))
    n_clusters_2050 = len(n_spores_per_cluster.get("2050"))
    n_spores_2030 = n_spores_per_cluster.get("2030").sum()
    n_spores_2050 = n_spores_per_cluster.get("2050").sum()

    with sns.plotting_context("paper", font_scale=1.5):
        ax = {}
        # fig = plt.figure(figsize=(20, 11))
        fig = plt.figure(figsize=(2.5 * FIGWIDTH, 1.25 * FIGWIDTH * 9 / 16))
        gs = gridspec.GridSpec(
            2, 2, height_ratios=[2, 18], width_ratios=[n_clusters_2030, n_clusters_2050]
        )

        ax["title"] = plt.subplot(gs[0, 0], frameon=False)
        plot_title(
            ax["title"],
            title=f"Scenarios, {resolution}",
        )
        ax["2030"] = fig.add_subplot(gs[1, 0])
        ax["2050"] = fig.add_subplot(gs[1, 1], sharey=ax["2030"])

        axs_idx = 0
        for year in years:
            # value_to_plot = "mean"
            scenario_values = (
                scenario_description.get(year)
                .loc[:, ["cluster", "technology", value_to_plot]]
                .pivot_table(index="cluster", columns="technology")[value_to_plot]
            )
            plot_scenario_capacity_stacked_barchart(
                scenario_values=scenario_values,
                n_spores_per_cluster=n_spores_per_cluster.get(year),
                year=year,
                ax=ax[year],
                spores_amount_y_offset=spores_amount_y_offset,
            )
            axs_idx += 1

        # Add legend
        handles, labels = ax["2030"].get_legend_handles_labels()

        proxy_spores_per_cluster = mpatches.Rectangle(
            (0, 0),
            1,
            1,
            fc="w",
            fill=False,
            edgecolor="none",
            label=f"Number of SPORES\nper scenario",
        )
        handles.insert(0, proxy_spores_per_cluster)
        labels.insert(0, proxy_spores_per_cluster.get_label())

        proxy_2030_spores = mpatches.Rectangle(
            (0, 0),
            1,
            1,
            fc="w",
            fill=False,
            edgecolor="none",
            label=f"Total number of\nSPORES in 2030",
        )
        handles.append(proxy_2030_spores)
        labels.append(proxy_2030_spores.get_label())

        proxy_2050_spores = mpatches.Rectangle(
            (0, 0),
            1,
            1,
            fc="w",
            fill=False,
            edgecolor="none",
            label=f"Total number of\nSPORES in 2050",
        )
        handles.append(proxy_2050_spores)
        labels.append(proxy_2050_spores.get_label())

        ax["2050"].legend(
            handles,
            labels,
            loc="upper left",
            bbox_to_anchor=(1, 1),
            frameon=False,
            handler_map={
                proxy_spores_per_cluster: HandlerNumber(42),
                proxy_2030_spores: HandlerNumber(n_spores_2030),
                proxy_2050_spores: HandlerNumber(n_spores_2050),
            },
        )

        plt.tight_layout(pad=1)
        plt.savefig(
            f"../figures/appendices/scenario_analysis/barchart_{resolution}_silhouette.png",
            bbox_inches="tight",
            dpi=120,
        )


def plot_title(ax_title, title):
    ax_title.axis("off")
    ax_title.text(0, 1, title, va="bottom", ha="left", fontweight="bold")


def plot_subfigure_letter(ax_letter, letter):
    ax_letter.axis("off")
    ax_letter.text(0, 1, letter, va="top", ha="right", fontweight="bold")


def plot_capacity_bar(
    ax, scenario_description, year, focus_scenario, value_to_plot="mean"
):
    # Calculate mean values for focus scenarios
    focus_scenario_values = (
        scenario_description.get(year)
        .loc[
            scenario_description.get(year)["cluster"] == focus_scenario,
            ["cluster", "technology", value_to_plot],
        ]
        .pivot_table(index="cluster", columns="technology")[value_to_plot]
    )
    # Plot
    focus_scenario_values.plot.bar(
        ax=ax, stacked=True, color=POWER_TECH_COLORS, width=1
    )

    ax.set_xticklabels([])
    ax.set_xticks([])
    ax.set_ylabel("Average installed capacity [GW]", weight="bold")
    # ax.set_ylim(ymax=prod_sum_max)
    ax.set_xlim((-0.5, 0.5))
    # handles, labels = ax.get_legend_handles_labels()
    ax.legend().set_visible(False)
    ax.set_xlabel("")


def plot_scenario_analysis(
    power_capacity,
    paper_metrics,
    spatial_resolution,
    scenario_description,
    scenario_number,
    year,
):
    # FIXME: determine number of technologies and metrics dynamically
    n_techs = 6
    n_metrics = 5
    n_total = n_techs + n_metrics
    n_rows = 2
    n_cols = 3
    n_spores_per_cluster = count_spores_per_cluster(paper_metrics.get(year))
    n_spores = n_spores_per_cluster.get(scenario_number)
    n_spores_total = len(power_capacity.get(year).index.unique(level="spore"))

    with sns.plotting_context("paper", font_scale=1.5):
        ax = {}
        fig = plt.figure(figsize=(20, 11))
        gs = mpl.gridspec.GridSpec(
            nrows=n_rows,
            ncols=n_cols,
            figure=fig,
            hspace=0.1,
            wspace=0.3,
            width_ratios=[1, (n_techs / n_total) * 25, (n_metrics / n_total) * 25],
            height_ratios=[2, 18],
        )
        _row = 0

        # Plot figure title
        ax["title"] = plt.subplot(gs[_row, :], frameon=False)
        plot_title(
            ax["title"],
            title=f"{spatial_resolution} scenario {scenario_number}, {year} ({n_spores} / {n_spores_total} SPORES)",
        )

        # Plot capacity bar for focus scenario
        ax["capacity_bar"] = plt.subplot(gs[1, 0], frameon=False)
        plot_capacity_bar(
            ax=ax["capacity_bar"],
            scenario_description=scenario_description,
            year=year,
            focus_scenario=scenario_number,
            value_to_plot="mean",
        )

        # Plot capacity distribution for focus scenario
        ax["capacity_distribution"] = plt.subplot(gs[1, 1], frameon=True)
        plot_capacity_distribution(
            ax=ax["capacity_distribution"],
            capacity=power_capacity.get(year),
            year=year,
            resolution=spatial_resolution,
            focus_cluster=scenario_number,
        )

        # Plot metrics distribution for focus scenario
        ax["metrics_distribution"] = plt.subplot(gs[1, 2], frameon=True)
        plot_metrics_distribution(
            ax=ax["metrics_distribution"],
            metrics=paper_metrics.get(year),
            year="2030",
            focus_cluster=scenario_number,
        )

        plt.tight_layout(pad=1)
        plt.savefig(
            f"../figures/appendices/scenario_analysis/analysis_v0_{spatial_resolution}.png",
            bbox_inches="tight",
            dpi=120,
        )


def plot_scenario_analysis_v1(
    power_capacity,
    grid_capacity,
    paper_metrics,
    spatial_resolution,
    scenario_description,
    scenario_description_eu,
    infeasible_european_scenarios,
    n_spores_per_cluster_eu,
    scenario_number,
    year,
    max_link_capacity,
):
    # FIXME: this data transformation is now done on multiple places --> do this in a more efficient way on a logical place
    # See: plot_scenario_analysis_barchart
    # See: plot_capacity_bar
    scenario_values_eu = (
        scenario_description_eu.get(year)
        .loc[:, ["cluster", "technology", "mean"]]
        .pivot_table(index="cluster", columns="technology")["mean"]
    )

    # FIXME: determine number of technologies and metrics dynamically
    n_techs = 6
    n_metrics = 5
    n_total = n_techs + n_metrics
    n_rows = 3
    n_cols = 3
    n_spores_per_cluster = count_spores_per_cluster(paper_metrics.get(year))
    n_spores = n_spores_per_cluster.get(scenario_number)
    n_spores_total = len(power_capacity.get(year).index.unique(level="spore"))

    with sns.plotting_context("paper", font_scale=1.5):
        ax = {}
        fig = plt.figure(figsize=(2.5 * FIGWIDTH, 2.5 * FIGWIDTH * 9 / 16))
        gs = mpl.gridspec.GridSpec(
            nrows=n_rows,
            ncols=n_cols,
            figure=fig,
            hspace=0.2,
            wspace=0.4,
            width_ratios=[1, 11, 12],
            height_ratios=[2, 16, 16],
        )
        _row = 0
        alpha_idx = 0

        # Plot figure title
        ax["title"] = plt.subplot(gs[0, :], frameon=False)
        plot_title(
            ax["title"],
            title=f"{spatial_resolution} scenario {scenario_number}, {year} ({n_spores} / {n_spores_total} SPORES)",
        )

        # Plot capacity bar for focus scenario
        ax["capacity_bar"] = plt.subplot(gs[1, 0], frameon=False)
        plot_capacity_bar(
            ax=ax["capacity_bar"],
            scenario_description=scenario_description,
            year=year,
            focus_scenario=scenario_number,
            value_to_plot="mean",
        )

        # Plot capacity distribution for focus scenario
        ax["capacity_distribution"] = plt.subplot(gs[1, 1], frameon=True)
        plot_capacity_distribution(
            ax=ax["capacity_distribution"],
            capacity=power_capacity.get(year),
            year=year,
            resolution=spatial_resolution,
            focus_cluster=scenario_number,
        )

        # Plot metrics distribution for focus scenario
        ax["metrics_distribution"] = plt.subplot(gs[1, 2], frameon=True)
        plot_metrics_distribution(
            ax=ax["metrics_distribution"],
            metrics=paper_metrics.get(year),
            year="2030",
            focus_cluster=scenario_number,
        )

        # Plot European scenarios that are still possible in the given national scenario
        ax["european_scenarios"] = plt.subplot(gs[2, 0:2], frameon=True)
        plot_scenario_capacity_stacked_barchart(
            scenario_values=scenario_values_eu,
            n_spores_per_cluster=n_spores_per_cluster_eu.get(year),
            year=year,
            greyed_out_scenarios=infeasible_european_scenarios,
            ax=ax["european_scenarios"],
            spores_amount_y_offset=200,
        )
        ax["european_scenarios"].set_xlabel(
            f"Scenarios, Europe ({year})", weight="bold"
        )

        # Plot power grid capacity map
        ax["grid_capacity"] = plt.subplot(gs[2, 2], frameon=True)
        # ax["grid_capacity"].text(
        #     0.5, 0.5, "Grid Map", ha="center", va="center", fontsize=10
        # )
        plot_grid_capacity_map(
            ax_map=ax["grid_capacity"],
            grid_capacity=grid_capacity.get(year),
            max_link_capacity=max_link_capacity,
            focus_scenario=scenario_number,
            spatial_resolution=spatial_resolution,
        )

        plt.tight_layout(pad=1)
        plt.savefig(
            f"../figures/appendices/scenario_analysis/v1/{spatial_resolution}_sc{scenario_number}_{year}.png",
            bbox_inches="tight",
            dpi=120,
        )


def plot_grid_capacity_map(
    ax_map, grid_capacity, max_link_capacity, focus_scenario, spatial_resolution
):
    # Prepare data
    scenario_description = grid_capacity.groupby(
        ["importing_region", "exporting_region", "cluster"]
    ).agg(["min", "median", "mean", "max"])
    link_capacities = scenario_description.loc[
        scenario_description.index.get_level_values("cluster") == focus_scenario
    ].droplevel(level="cluster")
    link_capacity_max = grid_capacity.max()
    link_capacities_filtered = link_capacities.xs(
        spatial_resolution, level="importing_region", drop_level=False
    )

    # Get countries and corresponding centroids
    countries = gpd.read_file("../data/raw/europe-NUTS0.geojson")
    countries["country_code"] = countries["country_code"].map(REGION_MAPPING)
    countries["index"] = countries["country_code"]
    countries = countries.set_index("index")

    representative_points = countries.geometry.representative_point()

    def _add_line(
        ax, point_from, point_to, color, lw, dashes=(None, None), linestyle="-"
    ):
        ax.add_line(
            mpl.lines.Line2D(
                xdata=(point_from[0], point_to[0]),
                ydata=(point_from[1], point_to[1]),
                color=color,
                lw=lw,
                linestyle=linestyle,
                dashes=dashes,
            )
        )

    def _add_links(ax, link_caps, cap_max):
        links_completed = []
        for link in link_caps.index:
            if sorted(link) in links_completed:  # every link comes up twice
                continue

            cap = link_caps.loc[link]
            point_from = (
                representative_points.loc[link[0]].x,
                representative_points.loc[link[0]].y,
            )
            point_to = (
                representative_points.loc[link[1]].x,
                representative_points.loc[link[1]].y,
            )
            _add_line(ax, point_from, point_to, color="#a9a9a999", lw=0.5)
            _add_line(ax, point_from, point_to, color="blue", lw=5 * cap / cap_max)

            links_completed.append(sorted(link))

    countries.plot(ax=ax_map, facecolor="#add8e6", edgecolor="white", linewidth=0.5)
    _add_links(
        ax_map,
        link_capacities["mean"],
        max_link_capacity,
    )

    ax_map.annotate(
        f"",
        fontweight="bold",
        xy=(0.5, 1.1),
        xycoords="axes fraction",
        horizontalalignment="center",
        fontsize="small",
    )
    ax_map.axis("off")


def plot_scenario_analysis_v2(
    power_capacity,
    paper_metrics,
    spatial_resolution,
    scenario_description,
    scenario_description_eu,
    infeasible_european_scenarios,
    n_spores_per_cluster_eu,
    scenario_number,
    year,
    value_to_plot="median",
):
    # FIXME: this data transformation is now done on multiple places --> do this in a more efficient way on a logical place
    # See: plot_scenario_analysis_barchart
    # See: plot_capacity_bar
    scenario_values_eu = (
        scenario_description_eu.get(year)
        .loc[:, ["cluster", "technology", value_to_plot]]
        .pivot_table(index="cluster", columns="technology")[value_to_plot]
    )

    # FIXME: determine number of technologies and metrics dynamically
    n_rows = 4
    n_cols = 4
    n_spores_per_cluster = count_spores_per_cluster(paper_metrics.get(year))
    n_spores = n_spores_per_cluster.get(scenario_number)
    n_spores_total = len(power_capacity.get(year).index.unique(level="spore"))

    with sns.plotting_context("paper", font_scale=1.5):
        ax = {}
        fig = plt.figure(figsize=(2.5 * FIGWIDTH, 2.5 * FIGWIDTH * 9 / 16))
        gs = mpl.gridspec.GridSpec(
            nrows=n_rows,
            ncols=n_cols,
            figure=fig,
            hspace=0.2,
            wspace=0.4,
            width_ratios=[1, 21, 5, 9],
            height_ratios=[2, 16, 1, 16],
        )
        _row = 0
        alpha_idx = 0

        # Plot figure title
        ax["title"] = plt.subplot(gs[0, :], frameon=False)
        plot_title(
            ax["title"],
            title=f"{spatial_resolution} scenario {scenario_number}, {year} ({n_spores} / {n_spores_total} SPORES)",
        )

        # Plot capacity bar for focus scenario
        ax["capacity_bar"] = plt.subplot(gs[1, 0], frameon=False)
        plot_capacity_bar(
            ax=ax["capacity_bar"],
            scenario_description=scenario_description,
            year=year,
            focus_scenario=scenario_number,
            value_to_plot=value_to_plot,
        )
        ax["capacity_bar"].annotate(
            "A",
            fontweight="bold",
            xy=(0, 1.1),
            xycoords="axes fraction",
            horizontalalignment="left",
            fontsize="small",
        )

        # Plot capacity distribution for focus scenario
        ax["capacity_distribution"] = plt.subplot(gs[1, 1], frameon=True)
        plot_capacity_distribution(
            ax=ax["capacity_distribution"],
            capacity=power_capacity.get(year),
            year=year,
            resolution=spatial_resolution,
            focus_cluster=scenario_number,
        )
        ax["capacity_distribution"].annotate(
            "B",
            fontweight="bold",
            xy=(0, 1.1),
            xycoords="axes fraction",
            horizontalalignment="left",
            fontsize="small",
        )

        # Plot metrics distribution for focus scenario
        ax["metrics_distribution"] = plt.subplot(gs[1, 2:], frameon=True)
        plot_metrics_distribution(
            ax=ax["metrics_distribution"],
            metrics=paper_metrics.get(year),
            year="2030",
            focus_cluster=scenario_number,
        )
        ax["metrics_distribution"].annotate(
            "C",
            fontweight="bold",
            xy=(0, 1.1),
            xycoords="axes fraction",
            horizontalalignment="left",
            fontsize="small",
        )

        # Plot European scenarios that are still possible in the given national scenario
        ax["european_scenarios"] = plt.subplot(gs[3, 0:2], frameon=True)
        plot_scenario_capacity_stacked_barchart(
            scenario_values=scenario_values_eu,
            n_spores_per_cluster=n_spores_per_cluster_eu.get(year),
            year=year,
            greyed_out_scenarios=infeasible_european_scenarios,
            ax=ax["european_scenarios"],
            spores_amount_y_offset=200,
        )
        ax["european_scenarios"].set_xlabel(
            f"Scenarios, Europe ({year})", weight="bold"
        )
        ax["european_scenarios"].annotate(
            "D",
            fontweight="bold",
            xy=(0, 1.1),
            xycoords="axes fraction",
            horizontalalignment="left",
            fontsize="small",
        )
        # Add legend
        handles, labels = ax["european_scenarios"].get_legend_handles_labels()

        ax["european_scenarios_legend"] = plt.subplot(gs[3, 2], frameon=False)
        plot_scenario_barchart_legend(
            ax=ax["european_scenarios_legend"],
            handles=handles,
            labels=labels,
            year=year,
            n_spores=n_spores_total,
        )

        plt.tight_layout(pad=1)
        plt.savefig(
            f"../figures/appendices/scenario_analysis/v2/{spatial_resolution}_sc{scenario_number}_silhouette_{year}.png",
            bbox_inches="tight",
            dpi=120,
        )
