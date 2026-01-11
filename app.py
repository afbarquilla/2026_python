import dash
from dash import html
from flask import Flask, render_template_string

# 1. Configuración del servidor Flask base
server = Flask(__name__)

# 2. Configuración de Dash (La Web-App Móvil)
# Le pasamos el servidor Flask para que convivan en el mismo puerto 8000
app = dash.Dash(
    __name__,
    server=server,
    url_base_pathname='/running/',  # Dash vivirá en /running/
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}]
)

# 3. Soporte para instalar como App Móvil (PWA)
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Running Sub-23</title>
        {%favicon%}
        {%css%}
        <link rel="manifest" href="/assets/manifest.json">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="mobile-web-app-capable" content="yes">
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# 4. Diseño de la App de Dash (Lo que verás en el móvil)
app.layout = html.Div([
    html.H1("Dashboard Running"),
    html.P("Preparado para las series de mañana (6x400m)"),
    html.A("Volver al Inicio", href="/")
], style={'padding': '20px', 'textAlign': 'center'})

# 5. Rutas de Flask (Menú de inicio)
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Papel Secante Python</title>
</head>
<body>
    <h1>Bienvenido a mi Servidor</h1>
    <ul>
        <li><a href="/navidad">🎄 Árbol de Navidad</a></li>
        <li><a href="/running/">🏃 Dashboard Running (App Móvil)</a></li>
        <li><a href="/estado">📊 Estado del Servidor</a></li>
    </ul>
</body>
</html>
"""

@server.route("/")
def index():
    return render_template_string(INDEX_HTML)

@server.route("/navidad")
def pagina_navidad():
    return "🎄 Árbol de Navidad (Lógica cargada)"

@server.route("/estado")
def estado():
    return "Servidor funcionando en el puerto 8000"

if __name__ == "__main__":
    # Puerto 8000 interno (mapeado al 8001 en el VPS)
    server.run(host="0.0.0.0", port=8000)