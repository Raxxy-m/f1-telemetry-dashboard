from datetime import datetime

from dash import dash_table, dcc, html

from theme import COLORS

GRAPH_CONFIG = {
    "displaylogo": False,
    "displayModeBar": False,
    "responsive": True,
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
            html.Main(
                [
                    html.Header(
                        [
                            html.Div(
                                [
                                    html.Div("F1 Telemetry Data Platform", className="app-badge"),
                                    html.H1("Formula 1 Engineering Dashboard", className="dashboard-title"),
                                    html.P(
                                        "High-density telemetry, delta analysis and session pace intelligence.",
                                        className="dashboard-subtitle",
                                    ),
                                    html.P(
                                        "Season, event and session filters update all visual layers for archive analysis.",
                                        className="toolbar-meta",
                                    ),
                                ],
                                className="toolbar-left",
                            ),
                        ],
                        className="dashboard-topbar",
                    ),
                    html.Section(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Div("Archive Info", className="archive-banner-kicker"),
                                            html.Div(
                                                "Select season, event and session",
                                                id="archive-session-title",
                                                className="archive-banner-title",
                                            ),
                                        ],
                                        className="archive-banner-left",
                                    ),
                                    html.Button(
                                        "Live App",
                                        id="archive-banner-action",
                                        className="archive-banner-action archive-banner-action--disabled",
                                        type="button",
                                        disabled=True,
                                        n_clicks=0,
                                    ),
                                ],
                                className="archive-banner",
                            ),
                            html.Div(
                                "Viewing: -- / -- / --",
                                id="archive-view-context",
                                className="archive-view-context",
                            ),
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
                        className="archive-toolbar",
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    section_header(
                                        "Race Results",
                                        "Race Classification",
                                        "Finishing order, delta to winner and best lap.",
                                    ),
                                    dash_table.DataTable(
                                        id="race-results-table",
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
                                            "textAlign": 'left',
                                        },
                                        style_cell={
                                            "backgroundColor": "transparent",
                                            "color": COLORS["text_primary"],
                                            "border": "none",
                                            "padding": "8px 10px",
                                            "fontSize": "12px",
                                            "fontFamily": "'JetBrains Mono', 'SFMono-Regular', Menlo, Monaco, Consolas, monospace",
                                            "fontVariantNumeric": "tabular-nums",
                                            "textAlign": "left",
                                        },
                                        style_data_conditional=[
                                            {
                                                "if": {"column_type": "numeric"},
                                                "textAlign": "left",
                                            }
                                        ],
                                        style_table={
                                            "overflowX": "auto",
                                            "overflowY": "auto",
                                            "width": "100%",
                                            "maxHeight": "320px",
                                        },
                                    ),
                                    html.Div(id="race-results-note", className="fastest-lap-note"),
                                ],
                                className="section-card",
                            ),
                            html.Div(
                                [
                                    section_header(
                                        "Race Intel",
                                        "Delta Comparison Snapshot",
                                        "Quick look at who was faster and where.",
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
                                    dcc.Graph(
                                        id="delta-graph",
                                        className="chart-surface",
                                        config=GRAPH_CONFIG,
                                        style={"height": "340px"},
                                    ),
                                ],
                                className="section-card",
                            ),
                            html.Div(
                                [
                                    section_header(
                                        "Race Intel",
                                        "Driver Fastest Lap Analysis",
                                        "Compare speed, throttle, brake, RPM and gear by distance. Hover to reveal mini-map context.",
                                    ),
                                    html.Div(
                                        [
                                            html.Label("Visible Channels", className="control-label"),
                                            html.Div(
                                                [
                                                    html.Button(
                                                        [html.Span(className="overlay-eye"), html.Span("Speed", className="overlay-toggle-label")],
                                                        id={"type": "overlay-toggle-btn", "graph": "speed"},
                                                        className="overlay-toggle-pill overlay-toggle-pill--active",
                                                        n_clicks=0,
                                                        type="button",
                                                    ),
                                                    html.Button(
                                                        [html.Span(className="overlay-eye"), html.Span("Throttle", className="overlay-toggle-label")],
                                                        id={"type": "overlay-toggle-btn", "graph": "throttle"},
                                                        className="overlay-toggle-pill overlay-toggle-pill--active",
                                                        n_clicks=0,
                                                        type="button",
                                                    ),
                                                    html.Button(
                                                        [html.Span(className="overlay-eye"), html.Span("Brake", className="overlay-toggle-label")],
                                                        id={"type": "overlay-toggle-btn", "graph": "brake"},
                                                        className="overlay-toggle-pill overlay-toggle-pill--active",
                                                        n_clicks=0,
                                                        type="button",
                                                    ),
                                                    html.Button(
                                                        [html.Span(className="overlay-eye"), html.Span("RPM", className="overlay-toggle-label")],
                                                        id={"type": "overlay-toggle-btn", "graph": "rpm"},
                                                        className="overlay-toggle-pill overlay-toggle-pill--active",
                                                        n_clicks=0,
                                                        type="button",
                                                    ),
                                                    html.Button(
                                                        [html.Span(className="overlay-eye"), html.Span("Gear", className="overlay-toggle-label")],
                                                        id={"type": "overlay-toggle-btn", "graph": "gear"},
                                                        className="overlay-toggle-pill overlay-toggle-pill--active",
                                                        n_clicks=0,
                                                        type="button",
                                                    ),
                                                ],
                                                className="overlay-toggle-group",
                                            ),
                                        ],
                                        className="overlay-toggle-shell",
                                    ),
                                    html.Div(id="overlay-driver-kpis", className="overlay-kpi-strip"),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    dcc.Graph(
                                                        id="telemetry-overlay-graph",
                                                        className="chart-surface",
                                                        config=GRAPH_CONFIG,
                                                        clear_on_unhover=True,
                                                        style={"height": "650px"},
                                                    ),
                                                ],
                                                className="overlay-main-stack",
                                            ),
                                            html.Div(
                                                [
                                                    html.Div(
                                                        [
                                                            dcc.Graph(
                                                                id="mini-track-map",
                                                                className="chart-surface mini-track-graph",
                                                                config=GRAPH_CONFIG,
                                                                style={"height": "260px"},
                                                            ),
                                                        ],
                                                        className="mini-track-drawer-inner",
                                                    ),
                                                ],
                                                id="mini-track-drawer",
                                                className="mini-track-drawer",
                                            ),
                                        ],
                                        className="overlay-stage",
                                    ),
                                    html.Div(
                                        [
                                            dcc.Graph(
                                                id="track-delta",
                                                className="chart-surface",
                                                config=GRAPH_CONFIG,
                                                style={"height": "360px"},
                                            ),
                                            dcc.Graph(
                                                id="speed-profile-graph",
                                                className="chart-surface",
                                                config=GRAPH_CONFIG,
                                                style={"height": "360px"},
                                            ),
                                        ],
                                        className="telemetry-secondary-grid",
                                    ),
                                ],
                                className="section-card",
                            ),
                            html.Div(
                                [
                                    section_header(
                                        "Session Analysis",
                                        "Lap Telemetry Drilldown",
                                        "Inspect one lap and compare it with that driver's best lap in this session.",
                                    ),
                                    html.Div(
                                        [
                                            html.Div(
                                                [
                                                    html.Label("Drilldown Driver", className="control-label"),
                                                    html.Div(id="lap-driver-buttons", className="lap-driver-buttons"),
                                                ],
                                                className="lap-driver-picker",
                                            ),
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
                                            html.Div(id="lap-context", className="lap-context"),
                                        ],
                                        className="slider-shell",
                                    ),
                                    dcc.Graph(
                                        id="full-session-telemetry-graph",
                                        className="chart-surface",
                                        config=GRAPH_CONFIG,
                                        style={"height": "720px"},
                                    ),
                                    html.Div(
                                        [
                                            dcc.Graph(
                                                id="lap-delta-fastest-graph",
                                                className="chart-surface",
                                                config=GRAPH_CONFIG,
                                                style={"height": "400px"},
                                            ),
                                            dcc.Graph(
                                                id="lap-time-evolution-graph",
                                                className="chart-surface",
                                                config=GRAPH_CONFIG,
                                                style={"height": "400px"},
                                            ),
                                        ],
                                        className="session-bottom-grid",
                                    ),
                                ],
                                className="section-card section-card--lap-controls",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            section_header(
                                                "Race Intel",
                                                "Sector Delta",
                                                "Per-sector benchmark between selected drivers.",
                                            ),
                                            dcc.Graph(
                                                id="sector-delta-bars",
                                                className="chart-surface",
                                                config=GRAPH_CONFIG,
                                                style={"height": "300px"},
                                            ),
                                        ],
                                        className="section-card",
                                    ),
                                    html.Div(
                                        [
                                            section_header(
                                                "Race Intel",
                                                "Fastest Laptime Comparison",
                                                "Compact laptime benchmark table for selected drivers.",
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
                                                style_header_conditional=[
                                                    {
                                                        "if": {"column_id": "Sector1"},
                                                        "color": "#ff7d70",
                                                    },
                                                    {
                                                        "if": {"column_id": "Sector2"},
                                                        "color": "#ffd166",
                                                    },
                                                    {
                                                        "if": {"column_id": "Sector3"},
                                                        "color": "#4ce39a",
                                                    },
                                                ],
                                                style_cell={
                                                    "backgroundColor": "transparent",
                                                    "color": COLORS["text_primary"],
                                                    "border": "none",
                                                    "padding": "8px 10px",
                                                    "fontSize": "12px",
                                                    "fontFamily": "'JetBrains Mono', 'SFMono-Regular', Menlo, Monaco, Consolas, monospace",
                                                    "fontVariantNumeric": "tabular-nums",
                                                    "textAlign": "right",
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
                                            html.Div(id="fastest-lap-note", className="fastest-lap-note"),
                                        ],
                                        className="section-card",
                                    ),
                                ],
                                className="summary-grid",
                            ),
                            html.Pre(id="debug-output", className="debug-output"),
                            dcc.Store(id="telemetry-store"),
                            dcc.Store(id="lap-driver-store"),
                            dcc.Store(
                                id="overlay-toggle-store",
                                data=["speed", "throttle", "brake", "rpm", "gear"],
                            ),
                        ],
                        className="archive-view",
                    ),
                ],
                className="dashboard-content",
            ),
        ],
        className="main_container",
    )
