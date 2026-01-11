import os
import glob
import pandas as pd
import xml.etree.ElementTree as ET
from dash import Dash, dcc, html, Input, Output, State, callback_context
import plotly.express as px
import csv
import base64

def cargar_datos_running():
    ruta_folder = os.path.join(os.path.dirname(__file__), "data")
    archivos_tcx = glob.glob(os.path.join(ruta_folder, "*.tcx"))
    lista_entrenos = []
    ns = {'ns': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}
    
    # Lectura de TCX
    for f in archivos_tcx:
        try:
            tree = ET.parse(f)
            root = tree.getroot()
            for activity in root.findall('.//ns:Activity', ns):
                fecha_raw = activity.find('ns:Id', ns).text
                fecha = pd.to_datetime(fecha_raw).strftime('%Y-%m-%d')
                dist = sum([float(l.find('ns:DistanceMeters', ns).text) for l in activity.findall('ns:Lap', ns)])
                segundos = sum([float(l.find('ns:TotalTimeSeconds', ns).text) for l in activity.findall('ns:Lap', ns)])
                if dist > 0:
                    ritmo = (segundos / 60) / (dist / 1000)
                    tipo = "Calidad/Series" if ritmo < 5.0 else "Rodaje/Largo"
                    lista_entrenos.append({"Día": fecha, "Ritmo (min/km)": round(ritmo, 2), "Tipo": tipo, "Distancia (km)": round(dist/1000, 2)})
        except: continue

    df_final = pd.DataFrame(lista_entrenos)

    # Lectura de Manual CSV
    ruta_csv = os.path.join(ruta_folder, "manual.csv")
    if os.path.exists(ruta_csv):
        try:
            df_manual = pd.read_csv(ruta_csv)
            df_final = pd.concat([df_final, df_manual], ignore_index=True)
        except: pass

    if not df_final.empty:
        df_final = df_final.sort_values("Día")
    return df_final

def init_dashboard(server):
    dash_app = Dash(__name__, server=server, url_base_pathname='/running/', suppress_callback_exceptions=True)

    # Esqueleto principal
    dash_app.layout = html.Div([
        dcc.Location(id='url', refresh=False),
        html.Div(id='page-content')
    ])

    # --- CALLBACK DE NAVEGACIÓN ---
    @dash_app.callback(Output('page-content', 'children'), [Input('url', 'pathname')])
    def display_page(pathname):
        # 1. PORTADA DE RUNNING
        if pathname == '/running/' or pathname == '/running':
            return html.Div([
                html.H1("🏃 Gestión de Entrenamiento 5K"),
                html.Div([
                    html.A(html.Button("📊 Ver Dashboard", style={'padding': '15px', 'margin': '10px'}), href='/running/grafica'),
                    html.A(html.Button("📥 Añadir/Subir Datos", style={'padding': '15px', 'margin': '10px'}), href='/running/nuevo'),
                ]),
                html.Br(), html.A("⬅️ Volver al Inicio del Servidor", href="/")
            ], style={'textAlign': 'center', 'padding': '50px'})

        # 2. PÁGINA DE GRÁFICA
        elif pathname == '/running/grafica':
            df = cargar_datos_running()
            if df.empty:
                fig = px.scatter(title="No hay datos todavía")
            else:
                fig = px.scatter(df, x="Día", y="Ritmo (min/km)", color="Tipo", size="Distancia (km)", title="Evolución 5K")
                fig.update_yaxes(autorange="reversed")
                fig.update_xaxes(type='category')
                # Dentro de la función donde creas la gráfica en dashboard.py
                fig.add_hline(y=4.6, line_dash="dash", line_color="red", annotation_text="Objetivo Sub-23 (4:36)")
            
            return html.Div([
                html.H2("Visualización de Progreso"),
                dcc.Graph(figure=fig),
                html.A("⬅️ Volver", href="/running/")
            ], style={'textAlign': 'center'})

        # 3. PÁGINA DE CARGA (FORMULARIO + UPLOAD)
        elif pathname == '/running/nuevo':
            return html.Div([
                html.H2("Añadir Nuevo Entrenamiento"),
                html.Div([
                    html.Div([
                        html.H3("Manual"),
                        dcc.Input(id='f-fecha', type='text', placeholder='YYYY-MM-DD'),
                        dcc.Input(id='f-ritmo', type='number', step=0.01, placeholder='Ritmo (4.35)'),
                        dcc.Input(id='f-dist', type='number', step=0.1, placeholder='Km'),
                        dcc.Dropdown(id='f-tipo', options=[{'label': 'Calidad/Series', 'value': 'Calidad/Series'}, {'label': 'Rodaje/Largo', 'value': 'Rodaje/Largo'}], value='Rodaje/Largo'),
                        html.Button('Guardar', id='btn-save', n_clicks=0),
                    ], style={'flex': '1', 'display': 'flex', 'flexDirection': 'column', 'gap': '10px', 'padding': '20px', 'border': '1px solid #ddd'}),
                    
                    html.Div([
                        html.H3("Garmin (.tcx)"),
                        dcc.Upload(id='upload-data', children=html.Div(['Arrastra o Selecciona']), 
                                  style={'width': '100%', 'height': '100px', 'lineHeight': '100px', 'borderWidth': '2px', 'borderStyle': 'dashed', 'textAlign': 'center'}),
                        html.Div(id='output-upload')
                    ], style={'flex': '1', 'padding': '20px', 'border': '1px solid #ddd'})
                ], style={'display': 'flex', 'gap': '20px', 'maxWidth': '800px', 'margin': '0 auto'}),
                html.Div(id='output-confirm'),
                html.Br(), html.A("⬅️ Volver", href="/running/")
            ], style={'textAlign': 'center'})

        return "404 - Página no encontrada"

    # --- CALLBACK PARA GUARDAR MANUAL ---
    @dash_app.callback(
        Output('output-confirm', 'children'),
        [Input('btn-save', 'n_clicks')],
        [State('f-fecha', 'value'), State('f-ritmo', 'value'), State('f-dist', 'value'), State('f-tipo', 'value')]
    )
    def save_manual(n, date, pace, dist, type_e):
        if n and n > 0 and all([date, pace, dist]):
            ruta_csv = os.path.join(os.path.dirname(__file__), "data", "manual.csv")
            file_exists = os.path.isfile(ruta_csv)
            with open(ruta_csv, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists: writer.writerow(["Día", "Ritmo (min/km)", "Distancia (km)", "Tipo"])
                writer.writerow([date, pace, dist, type_e])
            return f"✅ Guardado: {date}"
        return ""

    # --- CALLBACK PARA GUARDAR SUBIDA ---
    @dash_app.callback(Output('output-upload', 'children'), [Input('upload-data', 'contents')], [State('upload-data', 'filename')])
    def save_upload(contents, filename):
        if contents:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            ruta_destino = os.path.join(os.path.dirname(__file__), "data", filename)
            with open(ruta_destino, 'wb') as f: f.write(decoded)
            return f"✅ {filename} subido."
        return ""

    return dash_app