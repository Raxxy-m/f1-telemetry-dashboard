import plotly.graph_objects as go
import plotly.io as pio

# ==========================================================
# SHARED COLOR SYSTEM
# ==========================================================

COLORS = {
    # Surfaces
    "bg_main": "#0b0f15",
    "surface_1": "#111722",
    "surface_2": "#141c28",
    "surface_3": "#182131",
    "bg_card": "#141c28",
    "bg_dropdown": "#0f151f",
    "bg_hover": "#1d2838",

    # Borders
    "border_subtle": "#273245",
    "border_strong": "#34445d",
    "border": "#273245",
    "grid": "rgba(147, 161, 181, 0.14)",

    # Text
    "text_primary": "#edf2f8",
    "text_secondary": "#bcc7d6",
    "text_tertiary": "#93a1b5",
    "text_muted": "#93a1b5",

    # Status / Accent
    "accent_red": "#FF1801",
    "accent_drs": "#00d97e",
    "warning_amber": "#ffb020",
    "sector_purple": "#b56cff",

    # Telemetry palette
    "telemetry_1": "#FF1801",
    "telemetry_2": "#00d2be",
    "telemetry_3": "#4da3ff",
    "telemetry_4": "#ffc857",
    "telemetry_5": "#f78c6b",
    "telemetry_6": "#9b8cff",
    "telemetry_7": "#72e3ff",

    # Misc
    "fl_marker": "#ffffff",
}

# ==========================================================
# DASH CARD STYLE
# ==========================================================

CARD_STYLE = {
    "background": COLORS["surface_2"],
    "border": f"1px solid {COLORS['border_subtle']}",
    "borderRadius": "12px",
    "padding": "16px",
}

# ==========================================================
# PLOTLY TEMPLATE
# ==========================================================

plotly_f1_dark_template = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            color=COLORS["text_primary"],
            size=12,
        ),
        colorway=[
            COLORS["telemetry_1"],
            COLORS["telemetry_2"],
            COLORS["telemetry_3"],
            COLORS["telemetry_4"],
            COLORS["telemetry_5"],
            COLORS["telemetry_6"],
            COLORS["telemetry_7"],
        ],
        margin=dict(l=42, r=20, t=46, b=38),
        title=dict(
            x=0.01,
            y=0.97,
            xanchor="left",
            yanchor="top",
            font=dict(
                size=13,
                color=COLORS["text_secondary"],
            ),
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=COLORS["surface_1"],
            bordercolor=COLORS["border_subtle"],
            font=dict(color=COLORS["text_primary"], size=11),
            align="left",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=11, color=COLORS["text_tertiary"]),
            traceorder="normal",
            itemclick="toggleothers",
            itemdoubleclick="toggle",
        ),
        xaxis=dict(
            showline=True,
            linewidth=1,
            linecolor=COLORS["border_subtle"],
            showgrid=True,
            gridcolor=COLORS["grid"],
            gridwidth=0.6,
            zeroline=False,
            ticks="outside",
            ticklen=4,
            tickcolor=COLORS["text_tertiary"],
            tickfont=dict(color=COLORS["text_tertiary"], size=10),
            title_font=dict(color=COLORS["text_tertiary"], size=11),
        ),
        yaxis=dict(
            showline=True,
            linewidth=1,
            linecolor=COLORS["border_subtle"],
            showgrid=True,
            gridcolor=COLORS["grid"],
            gridwidth=0.6,
            zeroline=False,
            ticks="outside",
            ticklen=4,
            tickcolor=COLORS["text_tertiary"],
            tickfont=dict(color=COLORS["text_tertiary"], size=10),
            title_font=dict(color=COLORS["text_tertiary"], size=11),
        ),
    )
)

# Backward-compatible alias
F1_TEMPLATE = plotly_f1_dark_template

pio.templates["plotly_f1_dark_template"] = plotly_f1_dark_template
pio.templates["f1_dark"] = plotly_f1_dark_template
pio.templates.default = "plotly_f1_dark_template"


# ==========================================================
# HOVER STANDARDIZATION
# ==========================================================


def apply_standard_hover_layout(fig):
    fig.update_layout(
        template="plotly_f1_dark_template",
        hovermode="x unified",
    )
    return fig
