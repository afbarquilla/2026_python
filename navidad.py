from flask import Response

def arbol_navidad(altura=10):
    lineas = []
    for i in range(altura):
        espacios = " " * (altura - i - 1)
        estrellas = "*" * (2 * i + 1)
        lineas.append(espacios + estrellas)

    tronco_altura = altura // 3
    tronco_ancho = altura // 3 if altura // 3 % 2 == 1 else altura // 3 + 1
    espacios_tronco = " " * (altura - tronco_ancho // 2 - 1)
    for _ in range(tronco_altura):
        lineas.append(espacios_tronco + "|" * tronco_ancho)

    lineas.append("")
    lineas.append("🎄 ¡Feliz Navidad y feliz año 2026! 🎄")
    return "\n".join(lineas)

def obtener_arbol():
    tree_text = arbol_navidad(altura=12)
    return Response(tree_text, mimetype="text/plain")