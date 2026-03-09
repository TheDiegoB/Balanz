"""Portfolio Lab — Streamlit App v3 — PDF upload directo"""
import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))

try:
    from engine.analytics import build_portfolio, load_clients, load_config, DATA_DIR, BASE_DIR
    from engine.report import generate_html_report
    from engine.pdf_parser import parse_balanz_pdf, merge_into_holdings
except Exception as e:
    st.error(f"❌ Error al cargar módulos: {e}")
    st.stop()

st.set_page_config(page_title="Portfolio Lab", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
[data-testid="stSidebar"] { background: #1B2A4A; }
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background: rgba(255,255,255,0.05) !important; border: 1px dashed rgba(255,255,255,0.3) !important; border-radius: 8px !important; }
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] { background: #2E4D8A !important; color: white !important; border: 1px solid #4A7FC1 !important; border-radius: 6px !important; }
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover { background: #4A7FC1 !important; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] * { color: rgba(255,255,255,0.45) !important; font-size: 11px !important; }
[data-testid="stMetric"] { background: white; border: 1px solid #E8EDF5; border-radius: 10px; padding: 16px 20px !important; box-shadow: 0 1px 4px rgba(0,0,0,.05); }
[data-testid="stMetricLabel"] { font-size: 11px !important; text-transform: uppercase; letter-spacing: .6px; color: #6B7C9B !important; }
[data-testid="stMetricValue"] { font-family: 'DM Serif Display', serif !important; font-size: 26px !important; color: #1B2A4A !important; }
h1 { font-family: 'DM Serif Display', serif !important; color: #1B2A4A !important; }
h2, h3 { color: #2E4D8A !important; }
.section-header { font-family: 'DM Serif Display', serif; font-size: 20px; color: #1B2A4A; border-bottom: 2px solid #E8EDF5; padding-bottom: 8px; margin: 24px 0 16px; }
.rec-item { background: #F4F6FA; border-left: 3px solid #2E4D8A; padding: 12px 16px; border-radius: 0 6px 6px 0; margin-bottom: 8px; font-size: 13px; line-height: 1.5; }
.rec-ok   { border-left-color: #1A7A4A; background: #F0FBF4; }
.rec-warn { border-left-color: #C0392B; background: #FDF4F3; }
.profile-badge { display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; margin-left: 10px; }
.badge-conservador { background: #D6F5E3; color: #1A7A4A; }
.badge-moderado    { background: #FFF3CD; color: #856404; }
.badge-agresivo    { background: #FADBD8; color: #C0392B; }
.fx-bar { background: #F4F6FA; border-radius: 8px; padding: 10px 14px; font-size: 12px; color: #4A5C7A; margin-bottom: 12px; }
.upload-hint { background: rgba(255,255,255,0.07); border-radius: 8px; padding: 10px 12px; font-size: 11px; color: rgba(255,255,255,0.55) !important; line-height: 1.6; margin-top: 6px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Portfolio Lab")
    st.markdown("---")

    # PDF upload — flujo principal
    st.markdown("##### 📄 Cargar Resumen Balanz")
    pdf_files = st.file_uploader(
        "Subí uno o varios PDFs",
        type="pdf",
        accept_multiple_files=True,
        key="pdf_upload",
        help="ResumenDeCuenta_YYYYMMDD.pdf"
    )
    st.markdown('<div class="upload-hint">Arrastrá el PDF que descargás de Balanz.<br>Se agrega automáticamente al sistema.</div>', unsafe_allow_html=True)

    if pdf_files:
        DATA_DIR.mkdir(exist_ok=True)
        processed = []
        for pdf_file in pdf_files:
            try:
                result = parse_balanz_pdf(pdf_file.read())
                df_new = result["holdings"]
                client_id   = result["client_id"]
                client_name = result["client_name"]

                # Actualizar holdings.csv
                combined = merge_into_holdings(df_new, DATA_DIR / "holdings.csv")
                combined.to_csv(DATA_DIR / "holdings.csv", index=False)

                # Actualizar clients.csv si el cliente no existe
                clients_path = DATA_DIR / "clients.csv"
                if clients_path.exists():
                    cl_df = pd.read_csv(clients_path, dtype=str)
                else:
                    cl_df = pd.DataFrame(columns=["client_id","client_name","risk_profile","base_currency"])

                if client_id not in cl_df["client_id"].values:
                    new_row = pd.DataFrame([{
                        "client_id": client_id,
                        "client_name": client_name,
                        "risk_profile": "moderado",
                        "base_currency": "USD"
                    }])
                    cl_df = pd.concat([cl_df, new_row], ignore_index=True)
                    cl_df.to_csv(clients_path, index=False)

                processed.append(client_name)
            except Exception as e:
                st.error(f"❌ Error en {pdf_file.name}: {e}")

        if processed:
            st.success(f"✅ Cargado: {', '.join(processed)}")
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # Selector de cliente
    try:
        clients_df = load_clients()
        if clients_df.empty:
            st.warning("Sin clientes. Subí un PDF primero.")
            st.stop()
        client_options = {r["client_id"]: r["client_name"] for _, r in clients_df.iterrows()}
        selected_id = st.selectbox("Cliente", list(client_options.keys()),
                                   format_func=lambda x: client_options[x])
    except Exception:
        st.warning("Subí un PDF para comenzar.")
        st.stop()

    st.markdown("---")

    # Perfil de riesgo editable
    try:
        cl_row = clients_df[clients_df["client_id"] == selected_id].iloc[0]
        current_profile = cl_row.get("risk_profile", "moderado")
        new_profile = st.selectbox("Perfil de riesgo", ["conservador","moderado","agresivo"],
                                   index=["conservador","moderado","agresivo"].index(current_profile)
                                   if current_profile in ["conservador","moderado","agresivo"] else 1)
        if new_profile != current_profile:
            clients_df.loc[clients_df["client_id"]==selected_id, "risk_profile"] = new_profile
            clients_df.to_csv(DATA_DIR / "clients.csv", index=False)
            st.cache_data.clear()
            st.rerun()
    except Exception:
        pass

    st.markdown("---")

    # CSV avanzado (colapsado)
    with st.expander("⚙️ Edición manual CSV"):
        up_h = st.file_uploader("holdings.csv", type="csv", key="h")
        if up_h:
            (DATA_DIR/"holdings.csv").write_bytes(up_h.read())
            st.success("✅ Actualizado"); st.cache_data.clear(); st.rerun()
        up_c = st.file_uploader("clients.csv", type="csv", key="c")
        if up_c:
            (DATA_DIR/"clients.csv").write_bytes(up_c.read())
            st.success("✅ Actualizado"); st.cache_data.clear(); st.rerun()

    if st.button("🔄 Recargar datos", use_container_width=True):
        st.cache_data.clear(); st.rerun()

    st.markdown('<div style="font-size:10px;opacity:.3;margin-top:8px">Portfolio Lab v3.0</div>', unsafe_allow_html=True)

# ── Cargar portfolio ──────────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def get_portfolio(cid): return build_portfolio(cid)

with st.spinner("Calculando..."):
    ps = get_portfolio(selected_id)

if ps is None:
    st.error("❌ No se encontraron posiciones para este cliente.")
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown(f"# {ps.client_name}<span class='profile-badge badge-{ps.risk_profile}'>{ps.risk_profile}</span>",
                unsafe_allow_html=True)
    mep = ps.fx_rates.get("MEP", 0)
    ccl = ps.fx_rates.get("CCL", 0)
    st.markdown(f'<div class="fx-bar">💱 TC en vivo — MEP: <b>${mep:,.0f}</b> &nbsp;|&nbsp; CCL: <b>${ccl:,.0f}</b></div>',
                unsafe_allow_html=True)
with c2:
    html_content = generate_html_report(ps)
    st.download_button("📄 Descargar Reporte", data=html_content.encode("utf-8"),
                       file_name=f"reporte_{ps.client_id}.html", mime="text/html",
                       use_container_width=True, type="primary")

st.markdown("---")

# ── KPIs ──────────────────────────────────────────────────────────────────────
st.markdown("##### Patrimonio")
k1, k2, k3, k4 = st.columns(4)
k1.metric("💵 Total USD",          f"USD {ps.total_value_usd:,.0f}")
k2.metric("🇦🇷 Total ARS",        f"$ {ps.total_value_ars:,.0f}")
k3.metric("💵 Instrumentos USD",   f"USD {ps.total_usd_instruments:,.0f}")
k4.metric("💴 Instrumentos ARS",   f"$ {ps.total_ars_instruments:,.0f}")

st.markdown("##### Analytics")
k5, k6, k7, k8, k9 = st.columns(5)
k5.metric("📈 Retorno Esperado",   f"{ps.expected_return:.1f}%")
k6.metric("⏱ Duration (RF)",       f"{ps.portfolio_duration:.1f} años")
k7.metric("⚡ Riesgo",              f"{ps.portfolio_risk_score:.1f}/10")
k8.metric("🔵 HHI",                f"{ps.hhi:.3f}")
ars_pct = ps.exposure_by_currency.get("ARS", 0)
k9.metric("🇦🇷 Expo ARS",         f"{ars_pct:.1f}%")

st.markdown("")

COLORS = ["#1B2A4A","#2E4D8A","#4A7FC1","#00B4D8","#1A7A4A","#FFD166","#EF476F","#B8860B","#6B4E8A","#2ECC71"]

# ── Gráficos + Recomendaciones ────────────────────────────────────────────────
col_l, col_r = st.columns([3, 2])

with col_l:
    st.markdown('<div class="section-header">Exposición</div>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["Clase de Activo", "Moneda", "País"])

    def pie_chart(data_dict, height=290):
        df = pd.DataFrame(data_dict.items(), columns=["Cat", "Peso %"])
        df = df[df["Peso %"] > 0.1]
        fig = px.pie(df, values="Peso %", names="Cat", hole=0.42,
                     color_discrete_sequence=COLORS)
        fig.update_traces(textposition="outside", textinfo="label+percent")
        fig.update_layout(margin=dict(t=20,b=20,l=20,r=20), height=height,
                         showlegend=True, legend=dict(orientation="h", y=-0.15),
                         font_family="DM Sans")
        return fig

    with t1: st.plotly_chart(pie_chart(ps.exposure_by_asset_class), use_container_width=True)
    with t2:
        st.plotly_chart(pie_chart(ps.exposure_by_currency), use_container_width=True)
        st.caption("% por moneda de denominación del instrumento")
    with t3:
        df_cty = pd.DataFrame(ps.exposure_by_country.items(), columns=["País","Peso %"])
        df_cty = df_cty[df_cty["Peso %"] > 0.1].sort_values("Peso %")
        fig = px.bar(df_cty, x="Peso %", y="País", orientation="h",
                     color_discrete_sequence=["#2E4D8A"])
        fig.update_layout(margin=dict(t=10,b=10), height=250, plot_bgcolor="white",
                         font_family="DM Sans", xaxis=dict(gridcolor="#E8EDF5"))
        st.plotly_chart(fig, use_container_width=True)

with col_r:
    st.markdown('<div class="section-header">Recomendaciones</div>', unsafe_allow_html=True)
    for rec in ps.recommendations:
        css = "rec-ok" if rec.startswith("✅") else ("rec-warn" if rec.startswith("⚠️") else "rec-item")
        st.markdown(f'<div class="rec-item {css}">{rec}</div>', unsafe_allow_html=True)

# ── Posiciones ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Posiciones</div>', unsafe_allow_html=True)
h = ps.holdings.copy()
h["market_value_usd"]  = h["market_value_usd"].apply(lambda x: f"USD {x:,.0f}")
h["market_value_orig"] = h.apply(
    lambda r: f"$ {r['market_value_orig']:,.0f}" if r.get("currency_orig") == "ARS"
              else f"USD {r['market_value_orig']:,.0f}", axis=1)
h["weight"]   = h["weight"].apply(lambda x: f"{x:.1f}%")
h["ytm"]      = h["ytm"].apply(lambda x: f"{x:.1f}%" if x > 0 else "—")
h["duration"] = h["duration"].apply(lambda x: f"{x:.1f}" if x > 0 else "—")
h = h.rename(columns={
    "market_value_usd":  "Val. USD",
    "market_value_orig": "Val. Original",
    "currency_orig":     "Moneda",
    "weight":            "Peso %",
    "ytm":               "TIR %",
    "duration":          "Duration",
    "risk_score":        "Riesgo",
    "instrument_name":   "Nombre",
    "instrument_type":   "Tipo",
    "asset_class":       "Clase",
})
st.dataframe(h, use_container_width=True, hide_index=True)

# ── Contribución al riesgo ────────────────────────────────────────────────────
st.markdown('<div class="section-header">Contribución al Riesgo</div>', unsafe_allow_html=True)
h_raw = ps.holdings.copy()
if "risk_score" in h_raw.columns:
    h_raw["contrib"] = (h_raw["weight"] / 100) * h_raw["risk_score"]
    h_raw = h_raw.nlargest(10, "contrib")
    fig = px.bar(h_raw, x="ticker", y="contrib", color="contrib",
                 color_continuous_scale=["#1A7A4A","#FFD166","#C0392B"],
                 labels={"ticker": "", "contrib": "Contribución al Riesgo"})
    fig.update_layout(height=220, margin=dict(t=10,b=10), plot_bgcolor="white",
                     coloraxis_showscale=False, font_family="DM Sans",
                     yaxis=dict(gridcolor="#E8EDF5"))
    st.plotly_chart(fig, use_container_width=True)

# ── Disclaimer ────────────────────────────────────────────────────────────────
cfg = load_config()
st.markdown("---")
st.markdown(f'<div style="font-size:10px;color:#9AAABE;line-height:1.6">'
            f'<b>Disclaimer:</b> {cfg["report"]["disclaimer"]}</div>',
            unsafe_allow_html=True)
