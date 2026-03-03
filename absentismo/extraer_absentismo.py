import os
import re
import unicodedata
import pandas as pd
import pdfplumber

# =========================
# CONFIG
# =========================
PDF_FOLDER = "./pdfs"   # carpeta con TODOS los PDFs
OUT_XLSX = "absentismo_integrado.xlsx"
OUT_CSV  = "absentismo_integrado.csv"

# En tu PDF real: 4 números al final en la tabla de causas (Situaciones, Jornadas, INDICA 1, INDICA 2)
N_NUMS_CAUSAS = 4

DEBUG = True  # pon False cuando ya funcione

# =========================
# Conversión numérica (CORRECTA para decimales con punto)
# =========================
def parse_num(s: str):
    """
    Interpreta:
      - 7.28  -> 7.28  (decimal)
      - 80.16 -> 80.16 (decimal)
      - 12.516 -> 12516 (miles)
      - 1.234.567 -> 1234567 (miles)
      - 1.234,56 -> 1234.56 (si apareciera formato con coma)
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None

    s = s.replace(" ", "").replace("%", "")

    # Coma decimal (ES)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except:
            return None

    # Puntos: decimal o miles
    if "." in s:
        parts = s.split(".")

        # un punto
        if len(parts) == 2:
            left, right = parts
            if left.isdigit() and right.isdigit():
                # 2 dígitos -> decimal
                if len(right) == 2:
                    return float(s)
                # 3 dígitos -> miles
                if len(right) == 3:
                    return float(left + right)
            # fallback
            try:
                return float(s)
            except:
                return None

        # varios puntos
        last = parts[-1]
        if all(p.isdigit() for p in parts):
            # último grupo 2 dígitos -> decimal, resto miles
            if len(last) == 2:
                whole = "".join(parts[:-1])
                return float(whole + "." + last)
            # grupos de 3 -> miles
            if all(len(p) == 3 for p in parts[1:]):
                return float("".join(parts))
            # fallback: quita puntos
            return float("".join(parts))

        # fallback
        try:
            return float(s)
        except:
            return None

    # sin separadores
    try:
        return float(s)
    except:
        return None

# =========================
# Normalización texto
# =========================
def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def norm_line(s: str) -> str:
    """
    - minúsculas
    - sin tildes
    - quita relleno tipo "...."
    - espacios normalizados
    """
    s = strip_accents(s).lower()
    s = re.sub(r"[\.·•]+", " ", s)     # elimina .... y puntos de relleno
    s = re.sub(r"\s+", " ", s).strip()
    return s

def last_number_in_line(s: str):
    nums = re.findall(r"(\d+(?:[.,]\d+)?)", s or "")
    return parse_num(nums[-1]) if nums else None

def first_number_in_line(s: str):
    m = re.search(r"(\d+(?:[.,]\d+)?)", s or "")
    return parse_num(m.group(1)) if m else None

# =========================
# Cabecera
# =========================
def extract_header(text: str) -> dict:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]

    def value_after_label(label_regex: str):
        for i, l in enumerate(lines):
            m = re.search(label_regex, l, re.IGNORECASE)
            if m:
                if m.lastindex and m.group(m.lastindex):
                    v = m.group(m.lastindex).strip()
                    if v:
                        return v
                if i + 1 < len(lines):
                    return lines[i + 1].strip()
        return None

    consejeria = value_after_label(r"^CONSEJER[IÍ]A\s*[:\-]?\s*(.*)$")

    unidad = value_after_label(r"^UNIDAD\s*[:\-]?\s*(.*)$")
    if unidad:
        unidad = re.sub(r"\s*N[ºo]\s*de\s*Empleados.*$", "", unidad, flags=re.IGNORECASE).strip()

    media_empleados = None
    for l in lines:
        m = re.search(r"N[ºo]\s*de\s*Empleados\s*P[úu]blicos\s*(\d+)", l, re.IGNORECASE)
        if m:
            media_empleados = int(m.group(1))
            break

    periodo_control = value_after_label(r"^Periodo\s*de\s*Control\s*[:\-]?\s*(.*)$")

    return {
        "consejeria": consejeria,
        "unidad": unidad,
        "periodo_control": periodo_control,
        "media_empleados": media_empleados,
    }

# =========================
# Tabla de causas
# =========================
def parse_causa_row(cells, n_nums=4):
    """
    Fila típica:
      Causa ...  X  1395 1337 1.90 10.68
    """
    cells = [("" if c is None else str(c).strip()) for c in cells]
    cells = [c for c in cells if c != ""]
    if not cells:
        return None

    computable = any(c.upper() == "X" for c in cells)

    all_nums = re.findall(r"\b\d+(?:[.,]\d+)?\b", " ".join(cells))
    if len(all_nums) < n_nums:
        return None

    nums = [parse_num(x) for x in all_nums[-n_nums:]]

    causa_parts = []
    for c in cells:
        if c.upper() == "X":
            continue
        if re.fullmatch(r"\d+(?:[.,]\d+)?", c):
            continue
        causa_parts.append(c)
    causa = " ".join(causa_parts).strip()

    return causa, computable, nums

# =========================
# Índices (texto completo de páginas, sin recortes)
# =========================
INDEX_IMPORTANCIA = "Importancia de las CAUSAS DE SALUD respecto al ABSENTISMO GENERAL"
INDEX_GENERAL     = "Índice General de ABSENTISMO"

def extract_indices_from_page_text(page_text: str):
    """
    - Busca en TODA la página
    - Si el número no está en la misma línea, lo toma de una de las siguientes 1-3 líneas
    """
    raw_lines = [l.strip() for l in (page_text or "").splitlines() if l.strip()]
    norm_lines = [norm_line(l) for l in raw_lines]

    out = {}

    # Importancia...
    for i, nl in enumerate(norm_lines):
        if "importancia de las causas de salud" in nl and "absentismo general" in nl:
            v = last_number_in_line(raw_lines[i])
            if v is None:
                for j in range(i + 1, min(i + 4, len(raw_lines))):
                    v2 = first_number_in_line(raw_lines[j])
                    if v2 is not None:
                        v = v2
                        break
            if v is not None:
                out[INDEX_IMPORTANCIA] = v
            break

    # Índice general...
    for i, nl in enumerate(norm_lines):
        if "indice general de absentismo" in nl:
            v = last_number_in_line(raw_lines[i])
            if v is None:
                for j in range(i + 1, min(i + 3, len(raw_lines))):
                    v2 = first_number_in_line(raw_lines[j])
                    if v2 is not None:
                        v = v2
                        break
            if v is not None:
                out[INDEX_GENERAL] = v
            break

    return out

# =========================
# Extracción por PDF
# =========================
def extract_pdf_rows(pdf_path: str) -> list[dict]:
    pdf_name = os.path.basename(pdf_path)
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        header = extract_header(pdf.pages[0].extract_text() or "")

        indices_found = {}

        for pageno, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""

            # 1) Causas
            tables = page.extract_tables() or []
            for t in tables:
                if not t or len(t) < 2:
                    continue
                head = " ".join([(c or "").strip() for c in t[0]]).upper()
                if "CAUSAS" not in head:
                    continue

                for r in t[1:]:
                    parsed = parse_causa_row(r, n_nums=N_NUMS_CAUSAS)
                    if not parsed:
                        continue

                    causa, computable, nums = parsed
                    situaciones, jornadas, indica1, indica2 = nums

                    rows.append({
                        **header,
                        "tipo_fila": "causa",
                        "causa": causa,
                        "computable_indice": bool(computable),
                        "situaciones_ausencia": situaciones,
                        "jornadas_ausencia": jornadas,
                        "indica1": indica1,
                        "indica2": indica2,
                        "valor_resumen": None,
                        "pagina": pageno,
                        "pdf_origen": pdf_name,
                    })

            # 2) Índices
            found_here = extract_indices_from_page_text(page_text)
            indices_found.update(found_here)

        # 3) Añadir SIEMPRE 2 filas resumen por PDF (si falta valor, quedará vacío)
        rows.append({
            **header,
            "tipo_fila": "resumen",
            "causa": INDEX_IMPORTANCIA,
            "computable_indice": None,
            "situaciones_ausencia": None,
            "jornadas_ausencia": None,
            "indica1": None,
            "indica2": None,
            "valor_resumen": indices_found.get(INDEX_IMPORTANCIA, None),
            "pagina": None,
            "pdf_origen": pdf_name,
        })
        rows.append({
            **header,
            "tipo_fila": "resumen",
            "causa": INDEX_GENERAL,
            "computable_indice": None,
            "situaciones_ausencia": None,
            "jornadas_ausencia": None,
            "indica1": None,
            "indica2": None,
            "valor_resumen": indices_found.get(INDEX_GENERAL, None),
            "pagina": None,
            "pdf_origen": pdf_name,
        })

    return rows

# =========================
# Integración carpeta -> 1 archivo
# =========================
def integrate_folder(folder: str) -> pd.DataFrame:
    files = [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    if DEBUG:
        print(f"[DEBUG] PDFs encontrados en {os.path.abspath(folder)}: {len(files)}")
        for f in files[:20]:
            print("  -", f)

    all_rows = []
    for fn in files:
        path = os.path.join(folder, fn)
        if DEBUG:
            print(f"[DEBUG] Procesando: {fn}")
        all_rows.extend(extract_pdf_rows(path))

    df = pd.DataFrame(all_rows)

    if "media_empleados" in df.columns:
        df["media_empleados"] = pd.to_numeric(df["media_empleados"], errors="coerce").astype("Int64")

    for c in ["situaciones_ausencia", "jornadas_ausencia", "indica1", "indica2", "valor_resumen"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

if __name__ == "__main__":
    df = integrate_folder(PDF_FOLDER)

    # Guarda CSV primero (no suele bloquearse)
    df.to_csv(OUT_CSV, index=False, sep=";")

    # Excel puede estar bloqueado si lo tienes abierto
    try:
        if os.path.exists(OUT_XLSX):
            os.remove(OUT_XLSX)
        df.to_excel(OUT_XLSX, index=False)
        print(f"OK: generado {OUT_XLSX} y {OUT_CSV}")
    except PermissionError:
        print(f"NO pude escribir {OUT_XLSX} (seguramente está abierto en Excel).")
        print(f"Pero sí generé {OUT_CSV}. Cierra Excel y vuelve a ejecutar.")