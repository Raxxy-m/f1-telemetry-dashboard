from dash import html, dcc, dash_table
from datetime import datetime
from theme import CARD_STYLE, Theme


def create_layout():

    current_year = datetime.now().year

    year_options = [
        {"label": str(year), "value": year}
        for year in range(2019, current_year + 1)
    ]

    return html.Div(
        [

            # =========================
            # TITLE
            # =========================
            html.H1(
                "F1 Telemetry Dashboard",
                style={
                    "marginBottom": "30px",
                    "fontWeight": "600",
                },
            ),

            # =========================
            # INPUTS
            # =========================
            html.Div(
                [
                    dcc.Dropdown(
                        id="year-dd",
                        options=year_options,
                        value=current_year,
                        clearable=False,
                    ),
                    dcc.Dropdown(id="gp-dd"),
                    dcc.Dropdown(id="session-dd"),
                    dcc.Dropdown(id="drivers-dd", multi=True),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr 1fr 2fr",
                    "gap": "20px",
                    "marginBottom": "40px",
                },
            ),

            # =========================
            # TABS
            # =========================

            dcc.Tabs(
                id="view-tabs",
                value="comparison-tab",
                parent_className="custom-tabs",
                className="custom-tabs-container",
                children=[
                    dcc.Tab(
                        label="Performance Comparison",
                        value="performance-comparison-tab",
                        className="custom-tab",
                        selected_className="custom-tab--selected"
                    ),
                    dcc.Tab(
                        label="Session Analysis",
                        value="session-analysis-tab",
                        className="custom-tab",
                        selected_className="custom-tab--selected"
                    ),
                ],
                style={"marginBottom": "30px"},
            ),

            # =========================
            # TAB CONTENT
            # =========================
            html.Div(id="tab-content"),

            # =========================
            # DEBUG + STORE
            # =========================
            html.Div(id="debug-output"),
            dcc.Store(id="telemetry-store"),
        ],
        style={"padding": "40px"},
    )

# =========================================================
# TAB 1 — PERFORMANCE COMPARISON
# =========================================================

def performance_comparison_layout():
    return html.Div(
        [
            # =========================
            # TELEMETRY SECTION
            # =========================
            html.Div(
                [
                    html.H4("TELEMETRY ANALYSIS",
                            style={"letterSpacing": "2px",
                                   "fontSize": "14px",
                                   "marginBottom": "15px"}
                            ),

                    html.Div(
                        [
                            html.Div(
                                dcc.Graph(id="telemetry-graph"),
                                style={"flex": "3"},
                            ),
                            html.Div(
                                dcc.Graph(id="mini-track-map"),
                                style={"flex": "1"},
                            ),
                        ],
                        style={"display": "flex", "gap": "20px"},
                    ),
                ],
                style=CARD_STYLE,
            ),

            html.Br(),

            # =========================
            # TRACK DELTA
            # =========================
            html.Div(
                [
                    html.H4("TRACK DELTA (FASTEST LAP)",
                            style={"letterSpacing": "2px",
                                   "fontSize": "14px",
                                   "marginBottom": "15px"}),

                    dcc.Graph(id="track-delta"),
                ],
                style=CARD_STYLE,
            ),

            html.Br(),

            # =========================
            # FASTEST LAP TABLE
            # =========================
            html.Div(
                [
                    html.H4("FASTEST LAP SUMMARY",
                            style={"letterSpacing": "2px",
                                   "fontSize": "14px",
                                   "marginBottom": "15px"}),

                    dash_table.DataTable(
                        id="fastest-lap-table",
                        style_header={
                            "backgroundColor": Theme.GRAPH_BG,
                            "color": Theme.FONT_COLOR,
                            "border": "none",
                        },
                        style_cell={
                            "backgroundColor": "transparent",
                            "color": Theme.FONT_COLOR,
                            "border": "none",
                            "padding": "10px",
                        },
                        style_table={"overflowX": "auto"},
                    ),
                ],
                style=CARD_STYLE,
            ),
            html.Br(),
        ]        
    )

# =========================================================
# TAB 2 — SESSION ANALYSIS LAYOUT
# =========================================================

def session_analysis_layout():

    return html.Div(
        [

            # =========================
            # LAP SLIDER
            # =========================
            html.Div(
                [
                    html.H4(
                        "FULL SESSION TELEMETRY",
                        style={
                            "letterSpacing": "2px",
                            "fontSize": "14px",
                            "marginBottom": "15px",
                        },
                    ),

                    html.Label("Select Lap"),

                    dcc.Slider(
                        id="lap-slider",
                        min=1,
                        max=1,
                        step=1,
                        value=1,
                        marks=None,
                        tooltip={"placement": "bottom", "always_visible": False},
                    ),
                ],
                style=CARD_STYLE,
            ),

            html.Br(),

            # =========================
            # TELEMETRY GRAPH
            # =========================
            html.Div(
                [
                    dcc.Graph(id="full-session-telemetry-graph"),
                ],
                style=CARD_STYLE,
            ),

            html.Br(),
            # =========================
            # LAP TIME EVOLUTION GRAPH
            # =========================
            html.Div(
                [
                    dcc.Graph(id="lap-time-evolution-graph")
                ],
                style=CARD_STYLE
            ),
        ]
    )

            