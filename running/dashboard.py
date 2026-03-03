import os
import glob
import pandas as pd
import xml.etree.ElementTree as ET
from dash import Dash, dcc, html, Input, Output, State, no_update, callback_context, ALL
import plotly.express as px
import plotly.graph_objects as go
import csv
import datetime
import json
import base64
from garminconnect import Garmin

# --- CONFIGURACIÓN DE RUTAS ---
RUTA_DATA = os.path.join(os.path.dirname(__file__), "data")
if not os.path.exists(RUTA_DATA):
    os.makedirs(RUTA_DATA)

# --- LÓGICA DE DATOS ---
def cargar_datos_running():
    archivos_tcx = glob.glob(os.path.join(RUTA_DATA, "*.tcx"))
    lista_entrenos = []
    ns = {'ns': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}
    
    for f in archivos_tcx:
        try:
            tree = ET.parse(f)
            root = tree.getroot()
            for activity in root.findall('.//ns:Activity', ns):
                fecha_raw = activity.find('ns:Id', ns).text
                fecha = pd.to_datetime(fecha_raw)
                laps = activity.findall('ns:Lap', ns)
                dist_m = sum([float(l.find('ns:DistanceMeters', ns).text) for l in laps])
                segundos = sum([float(l.find('ns:TotalTimeSeconds', ns).text) for l in laps])
                dist_km = round(dist_m / 1000, 2)
                ritmo = round((segundos / 60) / dist_km, 2) if dist_km > 0 else 0
                
                lista_entrenos.append({
                    "Fecha": fecha, "Día": fecha.strftime('%Y-%m-%d'), 
                    "Ritmo (min/km)": ritmo, "Distancia (km)": dist_km, 
                    "Segundos": segundos, "Origen": os.path.basename(f)
                })
        except: continue
    
    df_sesiones = pd.DataFrame(lista_entrenos)
    
    ruta_csv = os.path.join(RUTA_DATA, "manual.csv")
    if os.path.exists(ruta_csv):
        try:
            df_manual = pd.read_csv(ruta_csv)
            df_manual.columns = df_manual.columns.str.strip()
            df_manual["Fecha"] = pd.to_datetime(df_manual["Día"])
            df_manual["Origen"] = "manual.csv"
            df_manual["Segundos"] = df_manual["Ritmo (min/km)"] * 60 * df_manual["Distancia (km)"]
            df_sesiones = pd.concat([df_sesiones, df_manual], ignore_index=True)
        except: pass
        
    if df_sesiones.empty: return pd.DataFrame(), pd.DataFrame()
    
    df_sesiones = df_sesiones.sort_values("Fecha")
    
    df_resumen = df_sesiones.groupby('Día').agg({
        'Distancia (km)': 'sum', 
        'Segundos': 'sum'
    }).reset_index()
    df_resumen['Ritmo Medio'] = round((df_resumen['Segundos'] / 60) / df_resumen['Distancia (km)'], 2)
    df_resumen['Sesiones'] = df_sesiones.groupby('Día').size().values

    return df_sesiones, df_resumen

def init_dashboard(server):
    dash_app = Dash(__name__, server=server, url_base_pathname='/running/', suppress_callback_exceptions=True)

    dash_app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Running App</title>
        {%css%}
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
            :root {
                --bg-1: #f5efe6;
                --bg-2: #eef5f2;
                --ink: #1b1f24;
                --muted: #5b6168;
                --card: #ffffff;
                --accent: #ff6b35;
                --accent-2: #1b998b;
                --shadow: 0 20px 45px rgba(27, 31, 36, 0.12);
            }
            body {
                font-family: "Space Grotesk", "Trebuchet MS", sans-serif;
                background:
                    radial-gradient(1200px 500px at 20% -10%, rgba(255, 107, 53, 0.15), transparent 60%),
                    radial-gradient(900px 600px at 90% 0%, rgba(27, 153, 139, 0.12), transparent 55%),
                    linear-gradient(180deg, var(--bg-1), var(--bg-2));
                color: var(--ink);
                margin: 0;
                padding: 0;
            }
            .app-container { width: 100%; max-width: 980px; margin: 0 auto; min-height: 100vh; padding: 18px 16px 40px; box-sizing: border-box; }
            .modern-card { background: var(--card); border-radius: 26px; margin: 16px 0; padding: 22px; box-shadow: var(--shadow); }
            .hero-card { background: linear-gradient(135deg, #ffffff 0%, #fff6ee 100%); border: 1px solid rgba(27, 31, 36, 0.06); }
            .hero-top { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
            .hero-title { font-family: "Fraunces", serif; font-size: 28px; margin: 0; }
            .hero-sub { margin: 6px 0 0; color: var(--muted); font-size: 14px; }
            .pill-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
            .pill { border-radius: 999px; padding: 6px 12px; font-size: 12px; background: rgba(27, 153, 139, 0.12); color: var(--accent-2); font-weight: 600; }
            .chart-card { background: #0f1114; color: white; border-radius: 26px; padding: 18px 18px 14px; box-shadow: 0 18px 40px rgba(15, 17, 20, 0.25); }
            .chart-title { font-size: 14px; color: rgba(255,255,255,0.75); margin: 0 0 8px; }
            .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px; border-top: 1px solid rgba(255,255,255,0.12); padding-top: 14px; }
            .stat-box { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: rgba(255,255,255,0.7); }
            .stat-box b { display: block; font-size: 18px; letter-spacing: 0; color: white; margin-top: 4px; }
            .day-totals { margin-top: 16px; display: grid; gap: 8px; }
            .day-total-row { display: grid; grid-template-columns: 1fr auto; gap: 8px; padding: 10px 12px; border-radius: 12px; background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.85); font-size: 13px; }
            .day-total-main { font-weight: 600; color: white; }
            .day-total-meta { font-size: 12px; color: rgba(255,255,255,0.7); }
            .day-total-value { text-align: right; font-weight: 600; color: white; }
            .dropdown-wrap { min-width: 150px; }
            .dropdown-wrap .Select-control { border-radius: 999px; border: 1px solid rgba(27, 31, 36, 0.08); box-shadow: none; }
            .dropdown-wrap .Select-placeholder, .dropdown-wrap .Select-value-label { color: var(--ink) !important; font-weight: 600; }
            .white-card { background: var(--card); border-radius: 22px; margin: 14px 0; padding: 22px; box-shadow: 0 10px 24px rgba(0,0,0,0.06); }
            .btn-nav { background: #ffffff; color: var(--ink); border-radius: 16px; padding: 16px; text-decoration: none; font-weight: 700; display: block; text-align: center; margin: 10px 0; box-shadow: 0 6px 16px rgba(0,0,0,0.05); font-size: 15px; border: none; cursor: pointer; }
            .btn-nav.accent { background: var(--accent); color: white; }
            .btn-nav.ghost { background: rgba(27, 31, 36, 0.04); color: var(--ink); }
            .input-field { background: #f2f3f5; border: none; border-radius: 12px; padding: 14px; width: 100%; box-sizing: border-box; font-size: 15px; margin-bottom: 12px; }
            .session-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #ececec; }
            .btn-del-small { color: #d7263d; border: 1px solid #d7263d; border-radius: 8px; background: none; font-weight: 700; cursor: pointer; padding: 8px 12px; }
            .upload-zone { border: 2px dashed #cbd0d6; border-radius: 14px; padding: 20px; text-align: center; color: #6b7076; background: #fafafa; font-size: 14px; }
            .anim-rise { animation: rise 0.6s ease-out both; }
            .delay-1 { animation-delay: 0.12s; }
            @keyframes rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
            @media (max-width: 720px) {
                .hero-top { flex-direction: column; align-items: flex-start; }
                .stats-grid { grid-template-columns: 1fr 1fr; }
                .app-container { padding: 14px 14px 32px; }
            }
        </style>
    </head>
    <body><div class="app-container">{%app_entry%}</div><footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>
'''

    dash_app.layout = html.Div([
        dcc.Location(id='url', refresh=False),
        html.Div(id='page-content')
    ])

    @dash_app.callback(Output('page-content', 'children'), [Input('url', 'pathname')])
    def display_page(pathname):
        if pathname == '/running/grafica':
            return html.Div([
                html.Div(className="modern-card hero-card anim-rise", children=[
                    html.Div(className="hero-top", children=[
                        html.Div(children=[
                            html.H2("Dashboard", className="hero-title"),
                            html.P("Resumen de entrenos y ritmo", className="hero-sub")
                        ]),
                        html.Div(className="dropdown-wrap", children=[
                            dcc.Dropdown(
                                id='time-filter',
                                options=[{'label': 'Individual', 'value': 'IND'}, {'label': 'Weekly', 'value': 'W'}, {'label': 'Monthly', 'value': 'ME'}],
                                value='IND', clearable=False
                            )
                        ])
                    ]),
                    html.Div(className="pill-row", children=[
                        html.Div("Pulso de rendimiento", className="pill"),
                        html.Div("Filtrado dinamico", className="pill")
                    ])
                ]),
                html.Div(className="chart-card anim-rise delay-1", children=[
                    html.P("Actividad", className="chart-title"),
                    dcc.Graph(id='main-graph', config={'displayModeBar': False}),
                    html.Div(id='summary-stats-footer', className="stats-grid"),
                    html.Div(id='day-totals', className="day-totals")
                ]),
                html.A("Volver", href="/running/", className="btn-nav ghost")
            ])

        elif pathname == '/running/nuevo':
            return html.Div([
                html.Div(style={'padding':'30px 20px 10px', 'textAlign':'center'}, children=[html.H1("Añadir")]),
                html.Div(id='import-options', children=[
                    html.Button('☁️ Garmin Cloud Sync', id='show-garmin-form', className="btn-nav", style={'width':'calc(100% - 30px)'}),
                    html.Button('📂 Subir Archivo TCX', id='show-upload-form', className="btn-nav", style={'width':'calc(100% - 30px)'}),
                    html.Button('✍️ Entrada Manual', id='show-manual-form', className="btn-nav", style={'width':'calc(100% - 30px)'}),
                ]),
                html.Div(id='view-garmin', style={'display':'none'}, className="white-card", children=[
                    html.H3("Garmin Sync"),
                    dcc.Input(id='garmin-email', type='email', placeholder='Email', className="input-field"),
                    dcc.Input(id='garmin-pass', type='password', placeholder='Pass', className="input-field"),
                    dcc.DatePickerSingle(id='garmin-date-picker', date=datetime.date.today()),
                    html.Button('IMPORTAR', id='btn-sync-date', className="btn-nav", style={'width':'100%', 'background':'#6a11cb', 'color':'white', 'marginLeft':0}),
                    dcc.Loading(html.Div(id='output-sync-status'))
                ]),
                html.Div(id='view-upload', style={'display':'none'}, className="white-card", children=[
                    html.H3("Archivo TCX"),
                    dcc.Upload(id='upload-data', className="upload-zone", children=['Arrastra o selecciona archivo'], multiple=True),
                    html.Div(id='output-upload-status')
                ]),
                html.Div(id='view-manual', style={'display':'none'}, className="white-card", children=[
                    html.H3("Manual"),
                    dcc.Input(id='f-fecha', type='text', placeholder='AAAA-MM-DD', className="input-field"),
                    dcc.Input(id='f-ritmo', type='number', step=0.01, placeholder='Ritmo', className="input-field"),
                    dcc.Input(id='f-dist', type='number', step=0.01, placeholder='Km', className="input-field"),
                    html.Button('GUARDAR', id='btn-save-manual', className="btn-nav", style={'width':'100%', 'background':'#34C759', 'color':'white', 'marginLeft':0}),
                    html.Div(id='output-manual-status')
                ]),
                html.Button('⬅ Cambiar método', id='btn-reset-import', className="btn-nav", style={'display':'none', 'width':'calc(100% - 30px)', 'background':'#E5E5EA'}),
                html.A("Cancelar", href="/running/", className="btn-nav", style={'color':'#8e8e93'})
            ])

        elif pathname == '/running/gestionar':
            return html.Div([
                html.Div(className="white-card", children=[
                    html.H2("Gestionar / Borrar"),
                    dcc.DatePickerSingle(id='manage-date-picker', date=datetime.date.today(), display_format='YYYY-MM-DD')
                ]),
                html.Div(id='manage-sessions-list'),
                html.Div(id='output-delete-status', style={'textAlign':'center', 'color':'red'}),
                html.A("⬅ Volver", href="/running/", className="btn-nav")
            ])
        
        else: # HOME
            return html.Div([
                html.Div(style={'padding':'60px 20px 30px', 'textAlign':'center'}, children=[
                    html.H1("Running App", style={'fontSize':'36px', 'color':'#6a11cb'}),
                    html.P("Track your limits", style={'color':'#8e8e93'})
                ]),
                html.A("📊 Mi Dashboard", href='/running/grafica', className="btn-nav"),
                html.A("📥 Añadir Actividad", href='/running/nuevo', className="btn-nav"),
                html.A("🗑️ Gestionar Datos", href='/running/gestionar', className="btn-nav", style={'color':'#ff3b30'})
            ])

    # --- CALLBACKS DE NAVEGACIÓN ---
    @dash_app.callback(
        [Output('import-options', 'style'), Output('view-garmin', 'style'), Output('view-upload', 'style'), 
         Output('view-manual', 'style'), Output('btn-reset-import', 'style')],
        [Input('show-garmin-form', 'n_clicks'), Input('show-upload-form', 'n_clicks'), 
         Input('show-manual-form', 'n_clicks'), Input('btn-reset-import', 'n_clicks')],
        prevent_initial_call=True
    )
    def switch_forms(n1, n2, n3, n4):
        ctx = callback_context
        tid = ctx.triggered[0]['prop_id'].split('.')[0]
        off, on = {'display':'none'}, {'display':'block'}
        if tid == 'btn-reset-import': return on, off, off, off, off
        if tid == 'show-garmin-form': return off, on, off, off, on
        if tid == 'show-upload-form': return off, off, on, off, on
        if tid == 'show-manual-form': return off, off, off, on, on
        return no_update

    # --- CALLBACK: GRÁFICA MODERNA ---
    @dash_app.callback(
        [Output('main-graph', 'figure'), Output('summary-stats-footer', 'children'), Output('day-totals', 'children')],
        [Input('time-filter', 'value'), Input('main-graph', 'clickData')]
    )
    def update_dashboard(periodo, clickData):
        df_s, df_r = cargar_datos_running()
        if df_s.empty: return go.Figure(), [], []
        
        fig = go.Figure()

        if periodo == 'IND':
            # Líneas verticales de conexión (estilo Activity)
            for d in df_s['Día'].unique():
                fig.add_vline(x=d, line_width=1, line_dash="solid", line_color="rgba(255,255,255,0.15)")

            # Puntos de sesión (Apple Health Style)
            fig.add_trace(go.Scatter(
                x=df_s['Día'], y=df_s['Ritmo (min/km)'],
                mode='markers',
                marker=dict(
                    size=12, color='white', opacity=0.9,
                    line=dict(width=2, color='rgba(255,255,255,0.4)')
                ),
                customdata=df_s[['Distancia (km)', 'Ritmo (min/km)', 'Origen']],
                hovertemplate="<b>Sesión</b><br>%{customdata[0]} km<extra></extra>"
            ))
            
            # Iconos de agrupación (Diamantes)
            fig.add_trace(go.Scatter(
                x=df_r['Día'], y=[0]*len(df_r),
                mode='markers', yaxis='y2',
                marker=dict(symbol='diamond', size=16, color='rgba(255,255,255,0.3)', line=dict(width=1, color='white')),
                customdata=df_r[['Distancia (km)', 'Ritmo Medio', 'Sesiones']],
                hovertemplate="<b>Total día</b><br>%{customdata[0]} km totales<extra></extra>"
            ))
            # Ritmo invertido (Estándar running: rápido arriba)
            fig.update_layout(yaxis=dict(autorange="reversed"))
        else:
            # Vista Semanal / Mensual (Curva Spline)
            df_ag = df_s.set_index('Fecha').resample(periodo).agg({'Distancia (km)':'sum'}).reset_index()
            fig.add_trace(go.Scatter(
                x=df_ag['Fecha'], y=df_ag['Distancia (km)'],
                mode='lines+markers',
                line=dict(shape='spline', width=4, color='white'),
                fill='tozeroy', fillcolor='rgba(255,255,255,0.05)'
            ))

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, tickfont=dict(color='white', size=10), type='category'),
            yaxis=dict(showgrid=False, tickfont=dict(color='white', size=10), zeroline=False),
            yaxis2=dict(visible=False, overlaying='y', side='right', range=[-1, 8]),
            margin=dict(l=0,r=0,t=10,b=0), height=320, showlegend=False
        )

        # Resumen dinámico (último día o selección)
        latest = df_r.iloc[-1]
        data = [latest['Distancia (km)'], latest['Ritmo Medio'], latest['Sesiones']]
        if clickData:
            cd = clickData['points'][0].get('customdata', [])
            if len(cd) == 3: data = cd
            elif len(cd) == 2: data = [cd[0], cd[1], "1"]

        footer = [
            html.Div(className="stat-box", children=[html.Span("KM TOTAL"), html.B(f"{data[0]}")]),
            html.Div(className="stat-box", children=[html.Span("RITMO MEDIO"), html.B(f"{data[1]}")]),
            html.Div(className="stat-box", children=[html.Span("SESIONES"), html.B(f"{data[2]}")])
        ]
        totals = [
            html.Div(className="day-total-row", children=[
                html.Div(children=[
                    html.Div(row['Día'], className="day-total-main"),
                    html.Div(f"Ritmo medio: {row['Ritmo Medio']}  |  Sesiones: {row['Sesiones']}", className="day-total-meta")
                ]),
                html.Div(f"{row['Distancia (km)']} km", className="day-total-value")
            ])
            for _, row in df_r.sort_values('Día', ascending=False).iterrows()
        ]
        return fig, footer, totals

    # --- CALLBACKS TÉCNICOS ---
    @dash_app.callback(Output('output-sync-status', 'children'), [Input('btn-sync-date', 'n_clicks')], [State('garmin-email', 'value'), State('garmin-pass', 'value'), State('garmin-date-picker', 'date')], prevent_initial_call=True)
    def sync_g(n, e, p, d):
        try:
            c = Garmin(e, p); c.login()
            acts = c.get_activities_by_date(d, d, "running")
            for a in acts:
                path = os.path.join(RUTA_DATA, f"garmin_{a['activityId']}.tcx")
                if not os.path.exists(path):
                    with open(path, "wb") as f: f.write(c.download_activity(a['activityId'], dl_fmt=c.ActivityDownloadFormat.TCX))
            return "✅ Sincronizado"
        except: return "❌ Error credenciales"

    @dash_app.callback(Output('output-upload-status', 'children'), [Input('upload-data', 'contents')], [State('upload-data', 'filename')])
    def upload_tcx(contents, filenames):
        if contents:
            for c, f in zip(contents, filenames):
                with open(os.path.join(RUTA_DATA, f), 'wb') as file: file.write(base64.b64decode(c.split(',')[1]))
            return "✅ Subido"
        return ""

    @dash_app.callback(Output('manage-sessions-list', 'children'), [Input('manage-date-picker', 'date'), Input('output-delete-status', 'children')])
    def list_to_del(date_sel, _):
        if not date_sel: return ""
        df, _ = cargar_datos_running()
        if df.empty: return ""
        df_dia = df[df['Día'] == date_sel]
        return [html.Div(className="session-item", children=[
            html.Div([html.B(f"{row['Distancia (km)']} km"), html.Br(), html.Span(f"Ritmo: {row['Ritmo (min/km)']}")]),
            html.Button("BORRAR", id={'type': 'del-btn', 'index': f"{row['Origen']}IDSEP{row['Día']}IDSEP{row['Distancia (km)']}"}, className="btn-del-small")
        ]) for i, row in df_dia.iterrows()]

    @dash_app.callback(Output('output-delete-status', 'children'), [Input({'type': 'del-btn', 'index': ALL}, 'n_clicks')], prevent_initial_call=True)
    def process_del(n):
        ctx = callback_context
        if not ctx.triggered or not any(n): return no_update
        target = json.loads(ctx.triggered[0]['prop_id'].split('.')[0])['index']
        origen, fecha, dist = target.split('IDSEP')
        if origen == "manual.csv":
            df_m = pd.read_csv(os.path.join(RUTA_DATA, "manual.csv"))
            df_m = df_m[~((df_m['Día'].astype(str)==str(fecha)) & (df_m['Distancia (km)'].astype(str)==str(dist)))]
            df_m.to_csv(os.path.join(RUTA_DATA, "manual.csv"), index=False)
        else:
            fp = os.path.join(RUTA_DATA, origen.replace('_',' '))
            if os.path.exists(fp): os.remove(fp)
        return "✅ Eliminado"

    return dash_app
