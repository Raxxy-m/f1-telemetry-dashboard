# theme.py
import plotly.graph_objects as go
import plotly.io as pio

# ==========================================================
# SHARED COLOR SYSTEM
# ==========================================================

COLORS = {
    # Backgrounds
    "bg_main": "#0e1116",
    "bg_card": "#141922",
    "bg_dropdown": "#0f141c",
    "bg_hover": "#1b222c",

    # Borders / Grid
    "border": "#1f2632",
    "grid": "#1f2632",

    # Text
    "text_primary": "#e6edf3",
    "text_muted": "#9aa4b2",

    # Accent
    "accent_red": "#FF1801",

    # Fastest Lap Marker
    "fl_marker": "#FFFFFF"
}

# ==========================================================
# DASH CARD STYLE
# ==========================================================

CARD_STYLE = {
    "background": COLORS["bg_card"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "16px",
    "padding": "20px",
}

# ==========================================================
# PLOTLY TEMPLATE
# ==========================================================

F1_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor=COLORS["bg_main"],
        plot_bgcolor=COLORS["bg_card"],
        font=dict(
            family="Inter, sans-serif",
            color=COLORS["text_primary"]
        ),
        xaxis=dict(
            gridcolor=COLORS["grid"],
            zerolinecolor=COLORS["grid"],
        ),
        yaxis=dict(
            gridcolor=COLORS["grid"],
            zerolinecolor=COLORS["grid"],
        ),
        hoverlabel=dict(
            bgcolor=COLORS["bg_card"],
            bordercolor=COLORS["accent_red"],
            font=dict(color=COLORS["text_primary"])
        ),
        # colorway=[
        #     COLORS["accent_red"],
        #     "#00D2BE",
        #     "#005AFF",
        #     "#DC0000",
        #     "#FF8700",
        # ],
    )
)

pio.templates['f1_dark'] = F1_TEMPLATE
pio.templates.default = 'f1_dark'

# ==========================================================
# HOVER STANDARDIZATION
# ==========================================================

def apply_standard_hover_layout(fig):
    fig.update_layout(hovermode="x unified")
    return fig