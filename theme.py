# theme.py
import os
from dotenv import load_dotenv

load_dotenv()

class Theme:
    APP_BG = os.getenv("APP_BG")
    CARD_BG = os.getenv("CARD_BG")
    GRAPH_BG = os.getenv("GRAPH_BG")
    GRID_COLOR = os.getenv("GRID_COLOR")

    ACCENT_PRIMARY = os.getenv("ACCENT_PRIMARY")
    ACCENT_BLUE = os.getenv("ACCENT_BLUE")
    ACCENT_GREEN = os.getenv("ACCENT_GREEN")

    FONT_COLOR = os.getenv("FONT_COLOR")
    USE_GLASSMORPHISM = os.getenv("USE_GLASSMORPHISM") == "True"


CARD_STYLE = {
    "background": Theme.CARD_BG,
    "border": "1px solid rgba(255,255,255,0.05)",
    "borderRadius": "16px",
    "padding": "20px",
}

if Theme.USE_GLASSMORPHISM:
    CARD_STYLE["backdropFilter"] = "blur(12px)"


GRAPH_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=Theme.GRAPH_BG,
    font=dict(color=Theme.FONT_COLOR),
)
