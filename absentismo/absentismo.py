import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import textwrap
import math

# =========================
# CONFIG STREAMLIT (TEMA CLARO)
# =========================
st.set_page_config(page_title="Dashboard de Absentismo", layout="wide")

# =========================
# CSS (CLARO + TARJETAS)
# =========================
st.markdown("""
<style>
    .stApp { background-color: #ffffff; color: #111827; }
    section[data-testid="stSidebar"] { background-color: #f7f8fb; }
    .block-container { padding-top: 1.2rem; padding-bottom: 1.5rem; }

    /* KPI Cards */
    .kpi-card {
        background-color: #ffffff;
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(17,24,39,0.10);
        box-shadow: 0 10px 18px rgba(17,24,39,0.06);
        text-align: center;
        margin-bottom: 14px;
        position: relative;
        overflow: hidden;
    }
    .kpi-card::after {
        content: "";
        position: absolute;
        left: 0; bottom: 0;
        height: 5px; width: 100%;
        background: var(--accent, #00acee);
        opacity: 0.95;
    }
    .kpi-title {
        font-size: 12px;
        color: #6b7280;
        font-weight: 800;
        letter-spacing: 0.10em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 30px;
        font-weight: 900;
        color: #111827;
        line-height: 1.1;
    }

    /* Tabs */
    button[data-baseweb="tab"] { color: #6b7280 !important; }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #111827 !important;
        border-bottom: 2px solid #00acee !important;
    }
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
_BOXED_ANN_NAME = "__boxed_value_label__"

def wrap_labels(text, width=22):
    return "<br>".join(textwrap.wrap(str(text), width=width))

def format_int_es(x):
    try:
        return f"{int(round(float(x))):,}".replace(",", ".")
    except Exception:
        return str(x)

def format_float_es(x, decimals=2):
    try:
        s = f"{float(x):,.{decimals}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)

def apply_light_plotly(fig, title=None, height=None, margin=None):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#111827"),
        title=dict(text=title, x=0.02, xanchor="left") if title else None,
        height=height,
        margin=margin or dict(l=40, r=30, t=60, b=40),
    )
    fig.update_xaxes(
        gridcolor="rgba(17,24,39,0.10)",
        zerolinecolor="rgba(17,24,39,0.20)",
        linecolor="rgba(17,24,39,0.20)",
        ticks="outside"
    )
    fig.update_yaxes(
        gridcolor="rgba(17,24,39,0.10)",
        zerolinecolor="rgba(17,24,39,0.20)",
        linecolor="rgba(17,24,39,0.20)",
        ticks="outside"
    )
    return fig

def _clean_prev_boxed_annotations(fig):
    anns = list(fig.layout.annotations) if fig.layout.annotations else []
    kept = []
    for a in anns:
        if getattr(a, "name", None) == _BOXED_ANN_NAME:
            continue
        kept.append(a)
    fig.update_layout(annotations=kept)

def _disable_native_text_for_bars(fig):
    """Quita cualquier texto nativo de barras (text/texttemplate/textposition) para evitar duplicados."""
    for tr in fig.data:
        if tr.type == "bar":
            tr.text = None
            tr.texttemplate = None
            tr.textposition = None
    return fig

def add_boxed_value_labels_to_bars(fig, decimals=0, suffix="", font_size=12):
    """
    Valores dentro de recuadro: fondo negro, borde blanco, texto blanco.
    - decimals: nº de decimales a mostrar (0 para enteros)
    - suffix: texto a añadir (ej. "%" si lo quieres)
    """
    _clean_prev_boxed_annotations(fig)
    _disable_native_text_for_bars(fig)

    for tr in fig.data:
        if tr.type != "bar":
            continue

        xref = tr.xaxis if getattr(tr, "xaxis", None) else "x"
        yref = tr.yaxis if getattr(tr, "yaxis", None) else "y"
        is_horizontal = (getattr(tr, "orientation", None) == "h")

        xs = list(tr.x) if tr.x is not None else []
        ys = list(tr.y) if tr.y is not None else []

        values = xs if is_horizontal else ys

        # Formateo: decimales si procede
        if decimals == 0:
            texts = [f"{format_int_es(v)}{suffix}" for v in values]
        else:
            texts = [f"{format_float_es(v, decimals)}{suffix}" for v in values]

        for i in range(min(len(xs), len(ys), len(texts))):
            xval = xs[i]
            yval = ys[i]
            label = texts[i]

            if is_horizontal:
                x_pos = (xval / 2) if isinstance(xval, (int, float)) else xval
                y_pos = yval
            else:
                x_pos = xval
                y_pos = (yval / 2) if isinstance(yval, (int, float)) else yval

            fig.add_annotation(
                x=x_pos, y=y_pos,
                xref=xref, yref=yref,
                text=str(label),
                showarrow=False,
                font=dict(color="white", size=font_size),
                bgcolor="black",
                bordercolor="white",
                borderwidth=1,
                borderpad=3,
                align="center",
                name=_BOXED_ANN_NAME,
            )

    return fig

def add_boxed_value_labels_to_pies(fig, mode="value+percent", value_decimals=0, percent_decimals=1, font_size=11):
    """
    Recuadros en pie/donut usando annotations sobre cada porción.
    mode: "percent" | "value" | "value+percent"
    """
    _clean_prev_boxed_annotations(fig)

    for tr in fig.data:
        if tr.type != "pie":
            continue

        values = list(tr.values) if tr.values is not None else []
        if not values:
            continue

        total = sum(v for v in values if isinstance(v, (int, float))) or 1.0

        dom = getattr(tr, "domain", None)
        x0, x1 = (0.0, 1.0)
        y0, y1 = (0.0, 1.0)
        if dom and getattr(dom, "x", None):
            x0, x1 = float(dom.x[0]), float(dom.x[1])
        if dom and getattr(dom, "y", None):
            y0, y1 = float(dom.y[0]), float(dom.y[1])

        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        w = (x1 - x0)
        h = (y1 - y0)
        r = 0.33 * min(w, h)

        rotation = float(getattr(tr, "rotation", 0) or 0)
        direction = getattr(tr, "direction", "counterclockwise") or "counterclockwise"
        clockwise = (direction == "clockwise")

        start_deg = rotation
        cum = 0.0

        # Oculta labels nativos del pie
        tr.textinfo = "none"

        for v in values:
            if not isinstance(v, (int, float)):
                continue

            frac = v / total
            sweep_deg = frac * 360.0

            mid_deg = start_deg + (-1 if clockwise else 1) * (cum + sweep_deg / 2.0)
            theta = math.radians(mid_deg)

            x = cx + r * math.cos(theta)
            y = cy + r * math.sin(theta)

            pct = frac * 100.0
            value_txt = format_float_es(v, value_decimals) if value_decimals > 0 else format_int_es(v)
            pct_txt = f"{format_float_es(pct, percent_decimals)}%"

            if mode == "percent":
                text = pct_txt
            elif mode == "value":
                text = value_txt
            else:
                text = f"{value_txt}<br>{pct_txt}"

            fig.add_annotation(
                x=x, y=y,
                xref="paper", yref="paper",
                text=text,
                showarrow=False,
                font=dict(color="white", size=font_size),
                bgcolor="black",
                bordercolor="white",
                borderwidth=1,
                borderpad=3,
                align="center",
                name=_BOXED_ANN_NAME,
            )

            cum += sweep_deg

    return fig

@st.cache_data
def load_data():
    df = pd.read_csv("absentismo/data/absentismo_integrado.csv", sep=";")
    if "computable_indice" in df.columns:
        mapeo_bool = {'verdadero': True, 'falso': False, 'true': True, 'false': False, '1': True, '0': False}
        df["computable_indice"] = (
            df["computable_indice"]
            .astype(str).str.lower().str.strip()
            .map(mapeo_bool)
            .fillna(False)
        )
    df["consejeria"] = df["consejeria"].fillna("Desconocida")
    for col in ["situaciones_ausencia", "jornadas_ausencia", "valor_resumen", "media_empleados"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

# =========================
# APP
# =========================
def main():
    st.title("📊 Cuadro de Mando: Análisis de Absentismo")
    df = load_data()

    st.sidebar.header("Filtro de Entidad")
    opciones_cons = ["Todas"] + sorted(df["consejeria"].unique().tolist())
    cons_sel = st.sidebar.selectbox("Selecciona Consejería:", opciones_cons)

    df_indices_raw = df[df["tipo_fila"] == "resumen"].copy()
    df_causas_raw = df[df["tipo_fila"] == "causa"].copy()
    df_solo_totales = df_causas_raw[df_causas_raw["causa"].str.contains("TOTAL", case=False, na=False)].copy()
    df_detalle_puro = df_causas_raw[~df_causas_raw["causa"].str.contains("TOTAL", case=False, na=False)].copy()

    if cons_sel == "Todas":
        df_f_res, df_f_tot, df_f_det = df_indices_raw, df_solo_totales, df_detalle_puro
    else:
        df_f_res = df_indices_raw[df_indices_raw["consejeria"] == cons_sel]
        df_f_tot = df_solo_totales[df_solo_totales["consejeria"] == cons_sel]
        df_f_det = df_detalle_puro[df_detalle_puro["consejeria"] == cons_sel]

    plantilla_total = df_f_tot["media_empleados"].sum()
    jor_tot = df_f_tot["jornadas_ausencia"].sum()
    sit_tot = df_f_tot["situaciones_ausencia"].sum()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Estratégico", "🔍 Operativo", "📄 PDF", "🏥 Salud", "⚙️ Resto causas"])

    # --- TAB 1: ESTRATÉGICO ---
    with tab1:
        v_gen = df_f_res[df_f_res["causa"].str.contains("Índice General", case=False)]["valor_resumen"].mean()
        v_salud = df_f_res[df_f_res["causa"].str.contains("CAUSAS DE SALUD", case=False)]["valor_resumen"].mean()

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.markdown(
                f'<div class="kpi-card" style="--accent:#00acee;"><div class="kpi-title">Índice General</div>'
                f'<div class="kpi-value">{format_float_es(v_gen,2)}%</div></div>',
                unsafe_allow_html=True
            )
        with k2:
            st.markdown(
                f'<div class="kpi-card" style="--accent:#ff9900;"><div class="kpi-title">Impacto Salud</div>'
                f'<div class="kpi-value">{format_float_es(v_salud,2)}%</div></div>',
                unsafe_allow_html=True
            )
        with k3:
            st.markdown(
                f'<div class="kpi-card" style="--accent:#2ecc71;"><div class="kpi-title">Jornadas</div>'
                f'<div class="kpi-value">{format_int_es(jor_tot)}</div></div>',
                unsafe_allow_html=True
            )
        with k4:
            st.markdown(
                f'<div class="kpi-card" style="--accent:#e74c3c;"><div class="kpi-title">Situaciones</div>'
                f'<div class="kpi-value">{format_int_es(sit_tot)}</div></div>',
                unsafe_allow_html=True
            )
        with k5:
            st.markdown(
                f'<div class="kpi-card" style="--accent:#9b59b6;"><div class="kpi-title">Plantilla</div>'
                f'<div class="kpi-value">{format_int_es(plantilla_total)}</div></div>',
                unsafe_allow_html=True
            )

        st.divider()
        col_g1, col_g2 = st.columns(2)

        if cons_sel == "Todas":
            with col_g1:
                st.markdown("#### Índice General por Consejería")
                df_g1 = df_indices_raw[df_indices_raw["causa"].str.contains("Índice General", case=False)].sort_values("valor_resumen")
                fig1 = px.bar(
                    df_g1, y="consejeria", x="valor_resumen",
                    orientation="h",
                    color="valor_resumen",
                    color_continuous_scale="Blues",
                )
                fig1.update_layout(coloraxis_showscale=False, yaxis_title="", xaxis_title="")
                fig1.update_traces(marker_line=dict(color="rgba(17,24,39,0.25)", width=1))
                apply_light_plotly(fig1)
                add_boxed_value_labels_to_bars(fig1, decimals=2, suffix="", font_size=12)  # 2 decimales
                st.plotly_chart(fig1, use_container_width=True)

            with col_g2:
                st.markdown("#### Impacto Salud por Consejería")
                df_g2 = df_indices_raw[df_indices_raw["causa"].str.contains("CAUSAS DE SALUD", case=False)].sort_values("valor_resumen")
                fig2 = px.bar(
                    df_g2, y="consejeria", x="valor_resumen",
                    orientation="h",
                    color="valor_resumen",
                    color_continuous_scale="Reds",
                )
                fig2.update_layout(coloraxis_showscale=False, yaxis_title="", xaxis_title="")
                fig2.update_traces(marker_line=dict(color="rgba(17,24,39,0.25)", width=1))
                apply_light_plotly(fig2)
                add_boxed_value_labels_to_bars(fig2, decimals=2, suffix="", font_size=12)  # 2 decimales
                st.plotly_chart(fig2, use_container_width=True)

        else:
            avg_gen_global = df_indices_raw[df_indices_raw["causa"].str.contains("Índice General", case=False)]["valor_resumen"].mean()
            avg_salud_global = df_indices_raw[df_indices_raw["causa"].str.contains("CAUSAS DE SALUD", case=False)]["valor_resumen"].mean()
            diff_gen = v_gen - avg_gen_global
            diff_salud = v_salud - avg_salud_global

            with col_g1:
                st.markdown(f"#### {cons_sel} vs Media Global")
                st.metric(
                    label="Variación Índice",
                    value=f"{format_float_es(v_gen,2)}%",
                    delta=f"{format_float_es(diff_gen,2)} pp vs media",   # ✅ pp
                    delta_color="inverse" if diff_gen > 0 else "normal",
                )
                df_c1 = pd.DataFrame({"Entidad": [cons_sel, "Media Global"], "Valor": [v_gen, avg_gen_global]})
                fig3 = px.bar(
                    df_c1, x="Entidad", y="Valor", color="Entidad",
                    color_discrete_map={cons_sel: "#00acee", "Media Global": "#d1d5db"},
                )
                fig3.update_traces(marker_line=dict(color="rgba(17,24,39,0.25)", width=1))
                fig3.update_layout(showlegend=False, xaxis_title="", yaxis_title="")
                apply_light_plotly(fig3, height=360, margin=dict(l=30, r=30, t=60, b=30))
                add_boxed_value_labels_to_bars(fig3, decimals=2, suffix="", font_size=12)  # 2 decimales
                st.plotly_chart(fig3, use_container_width=True)

            with col_g2:
                st.markdown(f"#### {cons_sel} vs Media Global")
                st.metric(
                    label="Variación Salud",
                    value=f"{format_float_es(v_salud,2)}%",
                    delta=f"{format_float_es(diff_salud,2)} pp vs media",  # ✅ pp
                    delta_color="inverse" if diff_salud > 0 else "normal",
                )
                df_c2 = pd.DataFrame({"Entidad": [cons_sel, "Media Global"], "Valor": [v_salud, avg_salud_global]})
                fig4 = px.bar(
                    df_c2, x="Entidad", y="Valor", color="Entidad",
                    color_discrete_map={cons_sel: "#ff9900", "Media Global": "#d1d5db"},
                )
                fig4.update_traces(marker_line=dict(color="rgba(17,24,39,0.25)", width=1))
                fig4.update_layout(showlegend=False, xaxis_title="", yaxis_title="")
                apply_light_plotly(fig4, height=360, margin=dict(l=30, r=30, t=60, b=30))
                add_boxed_value_labels_to_bars(fig4, decimals=2, suffix="", font_size=12)  # 2 decimales
                st.plotly_chart(fig4, use_container_width=True)

    # --- TAB 2: OPERATIVO ---
    with tab2:
        st.subheader(f"Análisis Combinado: {cons_sel}")
        c_f1, c_f2, c_f3 = st.columns([1, 2, 1])

        with c_f1:
            opcion_comp = st.radio("Causas:", ["Todas", "Solo Computables", "No Computables"], horizontal=True, key="rad_op")
            df_op_filt = df_f_det.copy()
            if opcion_comp == "Solo Computables":
                df_op_filt = df_op_filt[df_op_filt["computable_indice"] == True]
            elif opcion_comp == "No Computables":
                df_op_filt = df_op_filt[df_op_filt["computable_indice"] == False]

        with c_f2:
            todas_causas = sorted(df_op_filt["causa"].unique().tolist())
            causas_sel = st.multiselect("Filtrar causas:", todas_causas, key="multi_op")
            if causas_sel:
                df_op_filt = df_op_filt[df_op_filt["causa"].isin(causas_sel)]

        with c_f3:
            num_top = st.slider("Mostrar top:", 5, 25, 10, key="slid_op")

        df_op_grp = df_op_filt.groupby("causa").agg({"jornadas_ausencia": "sum", "situaciones_ausencia": "sum"}).reset_index()
        df_top = df_op_grp.sort_values("jornadas_ausencia", ascending=True).tail(num_top).copy()
        df_top["causa_wrapped"] = df_top["causa"].apply(wrap_labels)
        alt_op = 250 + (num_top * 75)

        fig_fusion = make_subplots(
            rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.15,
            subplot_titles=("Volumen (Casos)", "Impacto (Jornadas)")
        )

        fig_fusion.add_trace(
            go.Bar(
                y=df_top["causa_wrapped"], x=df_top["situaciones_ausencia"], orientation="h",
                marker=dict(color="#e74c3c", line=dict(color="rgba(17,24,39,0.25)", width=1)),
                name="Casos",
            ),
            row=1, col=1
        )

        fig_fusion.add_trace(
            go.Bar(
                y=df_top["causa_wrapped"], x=df_top["jornadas_ausencia"], orientation="h",
                marker=dict(color="#2ecc71", line=dict(color="rgba(17,24,39,0.25)", width=1)),
                name="Jornadas",
            ),
            row=1, col=2
        )

        fig_fusion.update_layout(showlegend=False, xaxis=dict(autorange="reversed"))
        apply_light_plotly(fig_fusion, height=alt_op, margin=dict(l=300, r=50, t=80, b=50))
        add_boxed_value_labels_to_bars(fig_fusion, decimals=0, suffix="", font_size=12)  # enteros
        st.plotly_chart(fig_fusion, use_container_width=True)

    # --- TAB 3: PDF ---
    with tab3:
        st.subheader("Resumen Formato PDF")
        if not df_f_det.empty:
            t_pdf = df_f_det.groupby("causa").agg({"situaciones_ausencia": "sum", "jornadas_ausencia": "sum"}).reset_index()
            p_den = plantilla_total if plantilla_total > 0 else 1
            t_pdf["INDICA 1"] = t_pdf["jornadas_ausencia"] / p_den
            t_pdf["INDICA 2"] = (t_pdf["jornadas_ausencia"] * 100) / jor_tot if jor_tot > 0 else 0
            t_pdf.columns = ["CAUSA", "Situaciones", "Jornadas", "INDICA 1", "INDICA 2"]
            fila_t = pd.DataFrame({"CAUSA": ["TOTAL"], "Situaciones": [sit_tot], "Jornadas": [jor_tot],
                                   "INDICA 1": [jor_tot / p_den], "INDICA 2": [100.0]})
            t_fin = pd.concat([t_pdf, fila_t], ignore_index=True)

            st.table(
                t_fin.style.format({
                    "Situaciones": lambda x: format_int_es(x),
                    "Jornadas": lambda x: format_float_es(x, 2),
                    "INDICA 1": lambda x: format_float_es(x, 4),
                    "INDICA 2": lambda x: f"{format_float_es(x, 2)}%",
                }).set_properties(
                    subset=pd.IndexSlice[len(t_fin) - 1, :],
                    **{'font-weight': 'bold', 'background-color': '#f3f4f6'}
                )
            )

    # --- TAB 4: SALUD ---
    with tab4:
        st.subheader(f"Detalle de Salud: {cons_sel}")
        causas_salud = [
            "Enfermedad o accidente sin incapacidad temporal",
            "Enfermedad o accidente con incapacidad temporal",
            "Asistir a consulta médica o asistencia sanitaria de carácter personal"
        ]
        df_salud = df_f_det[df_f_det["causa"].isin(causas_salud)].copy()

        if df_salud.empty:
            st.info("Sin datos.")
        else:
            df_s_grp = df_salud.groupby("causa").agg({"situaciones_ausencia": "sum", "jornadas_ausencia": "sum"}).reset_index()
            df_s_grp["causa_w"] = df_s_grp["causa"].apply(wrap_labels)

            fig_mirror = make_subplots(
                rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.15,
                subplot_titles=("Casos", "Jornadas")
            )
            fig_mirror.add_trace(
                go.Bar(
                    y=df_s_grp["causa_w"], x=df_s_grp["situaciones_ausencia"], orientation="h",
                    marker=dict(color="#e74c3c", line=dict(color="rgba(17,24,39,0.25)", width=1)),
                ),
                row=1, col=1
            )
            fig_mirror.add_trace(
                go.Bar(
                    y=df_s_grp["causa_w"], x=df_s_grp["jornadas_ausencia"], orientation="h",
                    marker=dict(color="#2ecc71", line=dict(color="rgba(17,24,39,0.25)", width=1)),
                ),
                row=1, col=2
            )

            fig_mirror.update_layout(showlegend=False, xaxis=dict(autorange="reversed"))
            apply_light_plotly(fig_mirror, height=450, margin=dict(l=250, r=50, t=70, b=50))
            add_boxed_value_labels_to_bars(fig_mirror, decimals=0, suffix="", font_size=12)
            st.plotly_chart(fig_mirror, use_container_width=True)

            st.divider()
            c_p1, c_p2 = st.columns(2)

            with c_p1:
                fig_p1 = px.pie(df_s_grp, values="situaciones_ausencia", names="causa", hole=0.45, title="% Casos")
                apply_light_plotly(fig_p1, height=420, margin=dict(l=20, r=20, t=60, b=20))
                add_boxed_value_labels_to_pies(fig_p1, mode="value+percent", value_decimals=0, percent_decimals=1, font_size=11)
                st.plotly_chart(fig_p1, use_container_width=True)

            with c_p2:
                fig_p2 = px.pie(df_s_grp, values="jornadas_ausencia", names="causa", hole=0.45, title="% Jornadas")
                apply_light_plotly(fig_p2, height=420, margin=dict(l=20, r=20, t=60, b=20))
                add_boxed_value_labels_to_pies(fig_p2, mode="value+percent", value_decimals=0, percent_decimals=1, font_size=11)
                st.plotly_chart(fig_p2, use_container_width=True)

            st.table(
                df_s_grp[["causa", "situaciones_ausencia", "jornadas_ausencia"]]
                .rename(columns={"causa": "Causa", "situaciones_ausencia": "Casos", "jornadas_ausencia": "Jornadas"})
                .style.format({
                    "Casos": lambda x: format_int_es(x),
                    "Jornadas": lambda x: format_float_es(x, 2),
                })
            )

    # --- TAB 5: RESTO CAUSAS ---
    with tab5:
        st.subheader(f"Resto Causas Computables - {cons_sel}")
        causas_salud_excluir = [
            "Enfermedad o accidente sin incapacidad temporal",
            "Enfermedad o accidente con incapacidad temporal",
            "Asistir a consulta médica o asistencia sanitaria de carácter personal"
        ]
        df_resto = df_f_det[(df_f_det["computable_indice"] == True) & (~df_f_det["causa"].isin(causas_salud_excluir))].copy()

        if df_resto.empty:
            st.info("Sin datos.")
        else:
            num_top_resto = st.slider("Mostrar top:", 3, 20, 10, key="slid_r")

            df_r_grp = df_resto.groupby("causa").agg({"situaciones_ausencia": "sum", "jornadas_ausencia": "sum"}).reset_index()
            df_r_top = df_r_grp.sort_values("jornadas_ausencia", ascending=False).head(num_top_resto).copy()

            df_r_plot = df_r_top.sort_values("jornadas_ausencia", ascending=True)
            df_r_plot["causa_w"] = df_r_plot["causa"].apply(wrap_labels)
            alt_r = 250 + (num_top_resto * 85)

            fig_mirror_r = make_subplots(
                rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.2,
                subplot_titles=("Casos", "Jornadas")
            )
            fig_mirror_r.add_trace(
                go.Bar(
                    y=df_r_plot["causa_w"], x=df_r_plot["situaciones_ausencia"], orientation="h",
                    marker=dict(color="#e74c3c", line=dict(color="rgba(17,24,39,0.25)", width=1)),
                ),
                row=1, col=1
            )
            fig_mirror_r.add_trace(
                go.Bar(
                    y=df_r_plot["causa_w"], x=df_r_plot["jornadas_ausencia"], orientation="h",
                    marker=dict(color="#2ecc71", line=dict(color="rgba(17,24,39,0.25)", width=1)),
                ),
                row=1, col=2
            )
            fig_mirror_r.update_layout(showlegend=False, xaxis=dict(autorange="reversed"))
            apply_light_plotly(fig_mirror_r, height=alt_r, margin=dict(l=300, r=50, t=70, b=50))
            add_boxed_value_labels_to_bars(fig_mirror_r, decimals=0, suffix="", font_size=12)
            st.plotly_chart(fig_mirror_r, use_container_width=True)

            st.divider()
            c_ind1, c_ind2 = st.columns(2)

            with c_ind1:
                st.markdown("#### Ocasiones")
                f_occ = px.bar(
                    df_r_plot, x="situaciones_ausencia", y="causa_w",
                    orientation="h",
                    color_discrete_sequence=["#e74c3c"],
                )
                f_occ.update_traces(marker_line=dict(color="rgba(17,24,39,0.25)", width=1))
                f_occ.update_layout(yaxis_title="", xaxis_title="")
                apply_light_plotly(f_occ, height=alt_r, margin=dict(l=220, r=30, t=60, b=40))
                add_boxed_value_labels_to_bars(f_occ, decimals=0, suffix="", font_size=12)
                st.plotly_chart(f_occ, use_container_width=True)

            with c_ind2:
                st.markdown("#### Jornadas")
                f_jor = px.bar(
                    df_r_plot, x="jornadas_ausencia", y="causa_w",
                    orientation="h",
                    color_discrete_sequence=["#2ecc71"],
                )
                f_jor.update_traces(marker_line=dict(color="rgba(17,24,39,0.25)", width=1))
                f_jor.update_layout(yaxis_title="", xaxis_title="")
                apply_light_plotly(f_jor, height=alt_r, margin=dict(l=220, r=30, t=60, b=40))
                add_boxed_value_labels_to_bars(f_jor, decimals=0, suffix="", font_size=12)
                st.plotly_chart(f_jor, use_container_width=True)

            st.table(
                df_r_top.rename(columns={"causa": "Causa", "situaciones_ausencia": "Casos", "jornadas_ausencia": "Jornadas"})
                .style.format({
                    "Casos": lambda x: format_int_es(x),
                    "Jornadas": lambda x: format_float_es(x, 2),
                })
            )

if __name__ == "__main__":
    main()