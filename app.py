from flask import Flask, Response

app = Flask(__name__)


def arbol_navidad(altura=10):
    lineas = []

    # Parte frondosa del árbol
    for i in range(altura):
        espacios = " " * (altura - i - 1)
        estrellas = "*" * (2 * i + 1)
        lineas.append(espacios + estrellas)

    # Tronco
    tronco_altura = altura // 3
    tronco_ancho = altura // 3 if altura // 3 % 2 == 1 else altura // 3 + 1
    espacios_tronco = " " * (altura - tronco_ancho // 2 - 1)
    for _ in range(tronco_altura):
        lineas.append(espacios_tronco + "|" * tronco_ancho)

    # Mensaje de felicitación
    lineas.append("")
    lineas.append("🎄  ¡Feliz Navidad y feliz año 2026!  🎄")
    lineas.append("Que tu código compile a la primera 😄")

    return "\n".join(lineas)


@app.get("/")
def hello_tree():
    tree_text = arbol_navidad(altura=12)
    # Devolvemos texto plano para que se vea bien en el navegador
    return Response(tree_text, mimetype="text/plain")


if __name__ == "__main__":
    # Importante: escuchar en 0.0.0.0 para que Coolify lo pueda exponer
    app.run(host="0.0.0.0", port=8000)

