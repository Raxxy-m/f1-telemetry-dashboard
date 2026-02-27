# app.py
import dash
import dash_bootstrap_components as dbc

from layout import create_layout
from theme import COLORS
from callbacks import register_callbacks


app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True
)

app.index_string = f"""
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>F1 Telemetry Dashboard</title>
        {{%favicon%}}
        {{%css%}}
        <style>
            :root {{
                --app-bg: {COLORS['bg_main']};
                --graph-bg: {COLORS['bg_card']};
                --accent: {COLORS['accent_red']};
                --font-color: {COLORS['text_primary']};
            }}
            body {{
                background-color: {COLORS['bg_main']};
                color: {COLORS['text_primary']};
                margin: 0;
                font-family: 'Inter', sans-serif;
            }}
        </style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>
"""

app.layout = create_layout()
register_callbacks(app)

server = app.server

if __name__ == "__main__":
    app.run(debug=True)
