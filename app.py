from flask import Flask, render_template_string
# Importamos la función que inicializa el dashboard desde la carpeta running
from running.dashboard import init_dashboard 

app = Flask(__name__)

# Inicializamos el dashboard de running pasándole este servidor Flask
init_dashboard(app)

# Tu menú de inicio ahora con la ruta organizada
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head><title>Mi Proyecto Python 2026</title></head>
<body>
    <h1>Bienvenido a mi Servidor Python</h1>
    <p>Selecciona una aplicación:</p>
    <ul>
        <li><a href="/navidad">🎄 Ver Árbol de Navidad</a></li>
        <li><a href="/running/">🏃 Dashboard Running (Organizado en carpeta)</a></li>
        <li><a href="/estado">📊 Estado del Servidor</a></li>
    </ul>
    <hr>
    <p>Desplegado automáticamente vía Portainer</p>
</body>
</html>
"""


# Al inicializar la app de Dash
app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    external_scripts=['https://cdnjs.cloudflare.com/ajax/libs/manifest.json/1.0.0/manifest.json']
)

# Añadir esto al layout para el soporte de Web-App
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









@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

# Mantenemos la lógica de navidad y estado
try:
    from navidad import obtener_arbol
except ImportError:
    def obtener_arbol(): return "Árbol no encontrado"

@app.route("/navidad")
def pagina_navidad():
    return obtener_arbol()

@app.route("/estado")
def estado():
    return "Servidor funcionando (Lógica de running movida a su propia carpeta)"

if __name__ == "__main__":
    # Seguimos usando el puerto 8000 (mapeado al 8001 en tu VPS)
    app.run(host="0.0.0.0", port=8000)