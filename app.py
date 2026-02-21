# app.py
import dash
import dash_bootstrap_components as dbc

from layout import create_layout
from theme import Theme
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
                --app-bg: {Theme.APP_BG};
                --graph-bg: {Theme.GRAPH_BG};
                --accent: {Theme.ACCENT_PRIMARY};
                --font-color: {Theme.FONT_COLOR};
            }}
            body {{
                background-color: {Theme.APP_BG};
                color: {Theme.FONT_COLOR};
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
