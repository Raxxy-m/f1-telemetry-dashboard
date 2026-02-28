from datetime import datetime

from dash import dash_table, dcc, html

from theme import COLORS

GRAPH_CONFIG = {
    "displaylogo": False,
    "displayModeBar": False,
}


def section_header(kicker, title, subtitle=None):
    children = [
        html.Div(kicker, className="section-kicker"),
        html.H2(title, className="section-heading"),
    ]
    if subtitle:
        children.append(html.P(subtitle, className="section-subtitle"))
    return html.Div(children, className="section-header")


def control_field(label, component, wide=False):
    field_class = "control-field control-field--wide" if wide else "control-field"
    return html.Div(
        [
            html.Label(label, className="control-label"),
            component,
        ],
        className=field_class,
    )


def metric_card(title, value="--", detail="Waiting for driver selection"):
    return html.Div(
        [
            html.Div(title, className="metric-card-title"),
            html.Div(value, className="metric-card-value"),
            html.Div(detail, className="metric-card-detail"),
        ],
        className="metric-card",
    )


def create_layout():
    current_year = datetime.now().year

    year_options = [
        {"label": str(year), "value": year}
        for year in range(2019, current_year + 1)
    ]

    return html.Div(
        [
            html.Header(
                [
                    html.Div(
                        [
                            html.Div("F1 Telemetry Platform", className="app-badge"),
                            html.H1("Race Engineering Dashboard", className="dashboard-title"),
                            html.P(
                                "High-density telemetry, delta analysis and session pace intelligence.",
                                className="dashboard-subtitle",
                            ),
                            html.P(
                                "Season, event and session filters update all visual layers in real time.",
                                className="toolbar-meta",
                            ),
                        ],
                        className="toolbar-left",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    control_field(
                                        "Season",
                                        dcc.Dropdown(
                                            id="year-dd",
                                            options=year_options,
                                            value=current_year,
                                            clearable=False,
                                            className="f1-dropdown",
                                        ),
                                    ),
                                    control_field(
                                        "Grand Prix",
                                        dcc.Dropdown(id="gp-dd", className="f1-dropdown"),
                                    ),
                                    control_field(
                                        "Session",
                                        dcc.Dropdown(id="session-dd", className="f1-dropdown"),
                                    ),
                                    control_field(
                                        "Drivers",
                                        dcc.Dropdown(id="drivers-dd", multi=True, className="f1-dropdown"),
                                        wide=True,
                                    ),
                                ],
                                className="control-bar",
                            ),
                        ],
                        className="toolbar-right",
                    ),
                ],
                className="dashboard-topbar",
            ),
            html.Main(
                [
                    dcc.Tabs(
                        id="view-tabs",
                        value="performance-comparison-tab",
                        parent_className="custom-tabs",
                        className="custom-tabs-container",
                        children=[
                            dcc.Tab(
                                label="Performance Comparison",
                                value="performance-comparison-tab",
                                className="custom-tab",
                                selected_className="custom-tab--selected",
                            ),
                            dcc.Tab(
                                label="Session Analysis",
                                value="session-analysis-tab",
                                className="custom-tab",
                                selected_className="custom-tab--selected",
                            ),
                        ],
                    ),
                    html.Div(
                        [
                            html.Div(
                                performance_comparison_layout(),
                                id="performance-tab-content",
                            ),
                            html.Div(
                                session_analysis_layout(),
                                id="session-tab-content",
                                style={"display": "none"},
                            ),
                        ],
                        className="tab-body",
                    ),
                    html.Pre(id="debug-output", className="debug-output"),
                    dcc.Store(id="telemetry-store"),
                ],
                className="dashboard-content",
            ),
        ],
        className="main_container",
    )


def performance_comparison_layout():
    return html.Div(
        [
            html.Div(
                [
                    section_header(
                        "Race Intel",
                        "Comparative Performance Snapshot",
                        "Key deltas and split losses from fastest-lap telemetry.",
                    ),
                    html.Div(
                        id="comparison-kpi-cards",
                        className="metric-grid",
                        children=[
                            metric_card("Fastest Lap Gap"),
                            metric_card("Top Speed Delta"),
                            metric_card("Average Speed Delta"),
                            metric_card("Largest Sector Swing"),
                        ],
                    ),
                    html.Div(
                        [
                            html.Div(
                                dcc.Graph(
                                    id="delta-graph",
                                    className="chart-surface",
                                    config=GRAPH_CONFIG,
                                    style={"height": "360px"},
                                ),
                                className="delta-grid-main",
                            ),
                            html.Div(
                                dcc.Graph(
                                    id="sector-delta-bars",
                                    className="chart-surface",
                                    config=GRAPH_CONFIG,
                                    style={"height": "360px"},
                                ),
                                className="delta-grid-side",
                            ),
                        ],
                        className="delta-grid",
                    ),
                ],
                className="section-card",
            ),
            html.Div(
                [
                    section_header(
                        "Telemetry",
                        "Driver Overlay Analysis",
                        "Compare speed, throttle, RPM, brake and gear with synchronized cursor tracking and live mini-map context.",
                    ),
                    html.Div(
                        [
                            html.Div(
                                dcc.Graph(
                                    id="telemetry-graph",
                                    className="chart-surface",
                                    config=GRAPH_CONFIG,
                                    style={"height": "910px"},
                                ),
                                className="telemetry-main",
                            ),
                            html.Div(
                                dcc.Graph(
                                    id="mini-track-map",
                                    className="chart-surface mini-track-graph",
                                    config=GRAPH_CONFIG,
                                    style={"height": "360px"},
                                ),
                                className="telemetry-mini mini-track-companion",
                            ),
                        ],
                        className="telemetry-grid",
                    ),
                ],
                className="section-card",
            ),
            html.Div(
                [
                    section_header(
                        "Delta",
                        "Track Segment Advantage",
                        "Binary track map highlights who is ahead through each sector segment.",
                    ),
                    dcc.Graph(
                        id="track-delta",
                        className="chart-surface",
                        config=GRAPH_CONFIG,
                        style={"height": "500px"},
                    ),
                ],
                className="section-card",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            section_header(
                                "Distribution",
                                "Speed Band Occupancy",
                                "How much lap distance each driver spends in each speed zone.",
                            ),
                            dcc.Graph(
                                id="speed-profile-graph",
                                className="chart-surface",
                                config=GRAPH_CONFIG,
                                style={"height": "320px"},
                            ),
                        ],
                        className="section-card",
                    ),
                    html.Div(
                        [
                            section_header(
                                "Summary",
                                "Fastest Lap Table",
                                "Compact benchmark table for selected drivers.",
                            ),
                            dash_table.DataTable(
                                id="fastest-lap-table",
                                fixed_rows={"headers": True},
                                style_as_list_view=True,
                                style_header={
                                    "backgroundColor": COLORS["surface_2"],
                                    "color": COLORS["text_secondary"],
                                    "border": "none",
                                    "fontWeight": 600,
                                    "fontSize": "11px",
                                    "letterSpacing": "0.08em",
                                    "textTransform": "uppercase",
                                },
                                style_cell={
                                    "backgroundColor": "transparent",
                                    "color": COLORS["text_primary"],
                                    "border": "none",
                                    "padding": "8px 10px",
                                    "fontSize": "12px",
                                    "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    "fontVariantNumeric": "tabular-nums",
                                    "textAlign": "left",
                                },
                                style_data_conditional=[
                                    {
                                        "if": {"column_type": "numeric"},
                                        "textAlign": "right",
                                    }
                                ],
                                style_table={
                                    "overflowX": "auto",
                                    "overflowY": "auto",
                                    "maxHeight": "320px",
                                },
                            ),
                        ],
                        className="section-card",
                    ),
                ],
                className="summary-grid",
            ),
        ],
        className="performance-view",
    )


def session_analysis_layout():
    return html.Div(
        [
            html.Div(
                [
                    section_header(
                        "Session",
                        "Lap Telemetry Drilldown",
                        "Inspect one driver lap with distance-based speed trace.",
                    ),
                    html.Div(
                        [
                            html.Label("Select Lap", className="control-label"),
                            html.Div(
                                [
                                    html.Button("Prev", id="lap-prev-btn", className="lap-nav-btn", n_clicks=0),
                                    dcc.Input(
                                        id="lap-input",
                                        type="number",
                                        min=1,
                                        max=1,
                                        step=1,
                                        value=1,
                                        className="lap-number-input",
                                    ),
                                    html.Span("/ 1 laps", id="lap-max-label", className="lap-max-label"),
                                    html.Button("Next", id="lap-next-btn", className="lap-nav-btn", n_clicks=0),
                                ],
                                className="lap-stepper",
                            ),
                            dcc.Slider(
                                id="lap-slider",
                                min=1,
                                max=1,
                                step=1,
                                value=1,
                                marks=None,
                                tooltip={"placement": "bottom", "always_visible": False},
                            ),
                            html.Div(id="lap-context", className="lap-context"),
                        ],
                        className="slider-shell",
                    ),
                ],
                className="section-card",
            ),
            html.Div(
                [
                    section_header(
                        "Lap Drilldown",
                        "Selected Lap vs Fastest Lap",
                        "Distance-synchronized telemetry channels for one driver.",
                    ),
                    dcc.Graph(
                        id="full-session-telemetry-graph",
                        className="chart-surface",
                        config=GRAPH_CONFIG,
                        style={"height": "760px"},
                    ),
                ],
                className="section-card",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            section_header(
                                "Consistency",
                                "Lap Time Evolution",
                                "Trend, compound phases and fastest-lap highlight.",
                            ),
                            dcc.Graph(
                                id="lap-time-evolution-graph",
                                className="chart-surface",
                                config=GRAPH_CONFIG,
                                style={"height": "430px"},
                            ),
                        ],
                        className="section-card",
                    ),
                    html.Div(
                        [
                            section_header(
                                "Reference Delta",
                                "Delta to Fastest Lap",
                                "Positive values indicate time loss versus the fastest lap.",
                            ),
                            dcc.Graph(
                                id="lap-delta-fastest-graph",
                                className="chart-surface",
                                config=GRAPH_CONFIG,
                                style={"height": "360px"},
                            ),
                        ],
                        className="section-card",
                    ),
                ],
                className="session-bottom-grid",
            ),
        ],
        className="session-view",
    )
