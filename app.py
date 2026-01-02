from flask import Flask, render_template_string

app = Flask(__name__)


# HTML simple para el menú de inicio
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Mi Proyecto Python 2026</title>
</head>
<body>
    <h1>Bienvenido a mi Servidor Python</h1>
    <p>Selecciona una aplicación:</p>
    <ul>
        <li><a href="/navidad">🎄 Ver Árbol de Navidad</a></li>
        <li><a href="/estado">📊 Estado del Servidor</a></li>
    </ul>
    <hr>
    <p>Desplegado automáticamente vía Portainer</p>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

# Importamos las funciones de otros archivos
from navidad import obtener_arbol

@app.route("/navidad")
def pagina_navidad():
    return obtener_arbol()

@app.route("/estado")
def estado():
    return "Servidor funcionando en el puerto 8000 (Expuesto en 8001)"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

