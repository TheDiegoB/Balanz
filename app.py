"""Portfolio Lab — Z Capital — v4"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path
from datetime import date

APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))

try:
    from engine.analytics import build_portfolio, load_clients, load_config, load_master, DATA_DIR
    from engine.report import generate_html_report
    from engine.pdf_parser import parse_balanz_pdf, merge_into_holdings
except Exception as e:
    st.error(f"❌ Error al cargar módulos: {e}"); st.stop()

cfg_global = load_config()
APP_TITLE  = cfg_global.get("report", {}).get("app_title", "Portfolio Lab — Z Capital")
GOLD, DARK, NAVY, BLUE = "#C9A84C", "#0A0A0A", "#1B2A4A", "#2E4D8A"
COLORS = ["#1B2A4A","#2E4D8A","#4A7FC1","#C9A84C","#1A7A4A","#EF476F","#B8860B","#6B4E8A","#00B4D8","#2ECC71"]

st.set_page_config(page_title=APP_TITLE, page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600;700&display=swap');
html,body,[class*="css"]{{font-family:'DM Sans',sans-serif;}}
[data-testid="stSidebar"]{{background:{DARK}!important;border-right:1px solid #1a1a1a;}}
[data-testid="stSidebar"] *{{color:#E0E0E0!important;}}
[data-testid="stSidebar"] label{{color:#888!important;font-size:11px!important;text-transform:uppercase;letter-spacing:.5px;}}
[data-testid="stSidebar"] [data-testid="stSelectbox"]>div>div{{background:#1a1a1a!important;border:1px solid #333!important;border-radius:6px!important;}}
[data-testid="stSidebar"] [data-testid="stSelectbox"] svg{{fill:{GOLD}!important;}}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]{{background:#111!important;border:1px dashed {GOLD}55!important;border-radius:8px!important;}}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]{{background:#1a1a1a!important;color:{GOLD}!important;border:1px solid {GOLD}66!important;border-radius:6px!important;}}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover{{background:{GOLD}22!important;border-color:{GOLD}!important;}}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] *{{color:#555!important;font-size:11px!important;}}
[data-testid="stMetric"]{{background:white;border:1px solid #E8EDF5;border-radius:10px;padding:16px 20px!important;box-shadow:0 1px 4px rgba(0,0,0,.05);}}
[data-testid="stMetricLabel"]{{font-size:11px!important;text-transform:uppercase;letter-spacing:.6px;color:#6B7C9B!important;}}
[data-testid="stMetricValue"]{{font-family:'DM Serif Display',serif!important;font-size:26px!important;color:{NAVY}!important;}}
h1{{font-family:'DM Serif Display',serif!important;color:{NAVY}!important;}}
h2,h3{{color:{BLUE}!important;}}
.section-header{{font-family:'DM Serif Display',serif;font-size:20px;color:{NAVY};border-bottom:2px solid #E8EDF5;padding-bottom:8px;margin:24px 0 16px;}}
.rec-item{{background:#F4F6FA;border-left:3px solid {BLUE};padding:12px 16px;border-radius:0 6px 6px 0;margin-bottom:8px;font-size:13px;line-height:1.5;}}
.rec-ok{{border-left-color:#1A7A4A;background:#F0FBF4;}}
.rec-warn{{border-left-color:#C0392B;background:#FDF4F3;}}
.profile-badge{{display:inline-block;padding:4px 14px;border-radius:20px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-left:10px;}}
.badge-conservador{{background:#D6F5E3;color:#1A7A4A;}}
.badge-moderado{{background:#FFF3CD;color:#856404;}}
.badge-agresivo{{background:#FADBD8;color:#C0392B;}}
.fx-bar{{background:#F4F6FA;border-radius:8px;padding:10px 14px;font-size:12px;color:#4A5C7A;margin-bottom:12px;}}
.upload-hint{{background:#111;border-radius:8px;padding:10px 12px;font-size:11px;color:#666!important;line-height:1.6;margin-top:6px;}}
.zcap-logo{{font-family:'DM Serif Display',serif;font-size:22px;color:{GOLD};letter-spacing:2px;font-weight:700;}}
.zcap-sub{{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:2px;margin-top:-4px;}}
.sidebar-divider{{border:none;border-top:1px solid #1a1a1a;margin:12px 0;}}
.client-card{{background:#111;border:1px solid #222;border-radius:8px;padding:12px 14px;margin:8px 0;}}
.client-name{{font-size:14px;font-weight:600;color:white!important;}}
.client-meta{{font-size:11px;color:#666!important;margin-top:2px;}}
.rot-tag-pendiente{{background:#FFF3CD;color:#856404;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;}}
.rot-tag-ejecutada{{background:#D6F5E3;color:#1A7A4A;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;}}
.rot-tag-descartada{{background:#F0F0F0;color:#888;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;}}
.rot-card{{background:white;border:1px solid #E8EDF5;border-radius:10px;padding:16px 20px;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,.04);}}
</style>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def load_rotaciones() -> pd.DataFrame:
    p = DATA_DIR / "rotaciones.csv"
    if p.exists():
        return pd.read_csv(p, dtype=str).fillna("")
    return pd.DataFrame(columns=["client_id","client_name","fecha","vender_ticker",
        "vender_tipo","vender_nominal","comprar_ticker","comprar_tipo",
        "tesis","mejora_tir","prioridad","estado"])

def save_rotaciones(df: pd.DataFrame):
    DATA_DIR.mkdir(exist_ok=True)
    df.to_csv(DATA_DIR / "rotaciones.csv", index=False)

def load_clients_full() -> pd.DataFrame:
    p = DATA_DIR / "clients.csv"
    if not p.exists():
        return pd.DataFrame(columns=["client_id","client_name","risk_profile",
                                     "base_currency","horizonte","objetivo","tolerancia"])
    df = pd.read_csv(p, dtype=str).fillna("")
    for col in ["horizonte","objetivo","tolerancia"]:
        if col not in df.columns:
            df[col] = ""
    return df

def save_clients(df: pd.DataFrame):
    df.to_csv(DATA_DIR / "clients.csv", index=False)

def pie_chart(data_dict, height=280):
    df = pd.DataFrame(data_dict.items(), columns=["Cat","Peso %"])
    df = df[df["Peso %"] > 0.1]
    fig = px.pie(df, values="Peso %", names="Cat", hole=0.42, color_discrete_sequence=COLORS)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(margin=dict(t=20,b=20,l=20,r=20), height=height,
                     showlegend=True, legend=dict(orientation="h",y=-0.15), font_family="DM Sans")
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="zcap-logo">Z CAPITAL</div>', unsafe_allow_html=True)
    st.markdown('<div class="zcap-sub">Portfolio Lab</div>', unsafe_allow_html=True)
    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

    st.markdown('<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">📄 Cargar Resumen Balanz</div>', unsafe_allow_html=True)
    pdf_files = st.file_uploader("PDF", type="pdf", accept_multiple_files=True,
                                  key="pdf_upload", label_visibility="collapsed")
    st.markdown('<div class="upload-hint">Arrastrá el ResumenDeCuenta.pdf de Balanz.</div>', unsafe_allow_html=True)

    if pdf_files:
        DATA_DIR.mkdir(exist_ok=True)
        processed = []
        for pdf_file in pdf_files:
            try:
                result    = parse_balanz_pdf(pdf_file.read())
                cid, cname = result["client_id"], result["client_name"]
                combined  = merge_into_holdings(result["holdings"], DATA_DIR / "holdings.csv")
                combined.to_csv(DATA_DIR / "holdings.csv", index=False)
                cl_df = load_clients_full()
                if cid not in cl_df["client_id"].values:
                    new_row = pd.DataFrame([{"client_id":cid,"client_name":cname,
                        "risk_profile":"moderado","base_currency":"USD",
                        "horizonte":"","objetivo":"","tolerancia":""}])
                    cl_df = pd.concat([cl_df, new_row], ignore_index=True)
                    save_clients(cl_df)
                processed.append(cname)
            except Exception as e:
                st.error(f"❌ {pdf_file.name}: {e}")
        if processed:
            st.success(f"✅ {', '.join(processed)}")
            st.cache_data.clear(); st.rerun()

    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)

    clients_df = load_clients_full()
    if clients_df.empty:
        st.markdown('<div class="upload-hint">Sin clientes. Subí un PDF primero.</div>', unsafe_allow_html=True)
        st.stop()

    st.markdown('<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Cliente</div>', unsafe_allow_html=True)
    client_options = {r["client_id"]: r["client_name"] for _, r in clients_df.iterrows()}
    selected_id = st.selectbox("Cliente", list(client_options.keys()),
                                format_func=lambda x: client_options[x],
                                label_visibility="collapsed")

    cl_row   = clients_df[clients_df["client_id"] == selected_id].iloc[0]
    profile  = cl_row.get("risk_profile","moderado")
    pc       = {"conservador":"#1A7A4A","moderado":"#856404","agresivo":"#C0392B"}.get(profile,"#856404")
    horizonte = cl_row.get("horizonte","—") or "—"
    objetivo  = cl_row.get("objetivo","—") or "—"

    st.markdown(f'''<div class="client-card">
        <div class="client-name">{cl_row["client_name"]}</div>
        <div class="client-meta" style="color:{pc}!important">▪ {profile.upper()}</div>
        <div class="client-meta">{horizonte} · {objetivo}</div>
    </div>''', unsafe_allow_html=True)

    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px">Perfil</div>', unsafe_allow_html=True)
    new_profile = st.selectbox("Perfil", ["conservador","moderado","agresivo"],
        index=["conservador","moderado","agresivo"].index(profile)
              if profile in ["conservador","moderado","agresivo"] else 1,
        label_visibility="collapsed")
    if new_profile != profile:
        clients_df.loc[clients_df["client_id"]==selected_id,"risk_profile"] = new_profile
        save_clients(clients_df); st.cache_data.clear(); st.rerun()

    st.markdown('<hr class="sidebar-divider">', unsafe_allow_html=True)
    with st.expander("⚙️ CSV manual"):
        up_h = st.file_uploader("holdings.csv", type="csv", key="h")
        if up_h: (DATA_DIR/"holdings.csv").write_bytes(up_h.read()); st.cache_data.clear(); st.rerun()
        up_c = st.file_uploader("clients.csv", type="csv", key="c")
        if up_c: (DATA_DIR/"clients.csv").write_bytes(up_c.read()); st.cache_data.clear(); st.rerun()
    if st.button("🔄 Recargar", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    st.markdown(f'<div style="font-size:10px;color:#333;margin-top:16px;text-align:center">Z Capital © {date.today().year}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Cargar portfolio
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def get_portfolio(cid): return build_portfolio(cid)

with st.spinner("Calculando..."):
    ps = get_portfolio(selected_id)

if ps is None:
    st.error("❌ No se encontraron posiciones."); st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
hc1, hc2 = st.columns([3,1])
with hc1:
    st.markdown(f"# {ps.client_name}<span class='profile-badge badge-{ps.risk_profile}'>{ps.risk_profile}</span>",
                unsafe_allow_html=True)
    mep = ps.fx_rates.get("MEP",0); ccl = ps.fx_rates.get("CCL",0)
    st.markdown(f'<div class="fx-bar">💱 MEP: <b>${mep:,.0f}</b> &nbsp;|&nbsp; CCL: <b>${ccl:,.0f}</b> &nbsp;·&nbsp; <span style="color:{GOLD};font-weight:600">Z Capital</span></div>',
                unsafe_allow_html=True)
with hc2:
    html_rep = generate_html_report(ps)
    st.download_button("📄 Descargar Reporte", data=html_rep.encode("utf-8"),
                       file_name=f"reporte_{ps.client_id}.html", mime="text/html",
                       use_container_width=True, type="primary")

st.markdown("---")

# KPIs
k1,k2,k3,k4 = st.columns(4)
k1.metric("💵 Total USD",        f"USD {ps.total_value_usd:,.0f}")
k2.metric("🇦🇷 Total ARS",      f"$ {ps.total_value_ars:,.0f}")
k3.metric("💵 Instrumentos USD", f"USD {ps.total_usd_instruments:,.0f}")
k4.metric("💴 Instrumentos ARS", f"$ {ps.total_ars_instruments:,.0f}")

k5,k6,k7,k8,k9 = st.columns(5)
k5.metric("📈 Retorno Esperado", f"{ps.expected_return:.1f}%")
k6.metric("⏱ Duration (RF)",     f"{ps.portfolio_duration:.1f} años")
k7.metric("⚡ Riesgo",            f"{ps.portfolio_risk_score:.1f}/10")
k8.metric("🔵 HHI",              f"{ps.hhi:.3f}")
k9.metric("🇦🇷 Expo ARS",       f"{ps.exposure_by_currency.get('ARS',0):.1f}%")
st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📊 Diagnóstico", "🎯 vs Modelo", "🔄 Rotaciones", "📋 Ficha Cliente"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DIAGNÓSTICO
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    col_l, col_r = st.columns([3,2])
    with col_l:
        st.markdown('<div class="section-header">Exposición</div>', unsafe_allow_html=True)
        t1,t2,t3 = st.tabs(["Clase de Activo","Moneda","País"])
        with t1: st.plotly_chart(pie_chart(ps.exposure_by_asset_class), use_container_width=True)
        with t2:
            st.plotly_chart(pie_chart(ps.exposure_by_currency), use_container_width=True)
            st.caption("% por moneda de denominación del instrumento")
        with t3:
            df_c = pd.DataFrame(ps.exposure_by_country.items(), columns=["País","Peso %"])
            df_c = df_c[df_c["Peso %"]>0.1].sort_values("Peso %")
            fig  = px.bar(df_c, x="Peso %", y="País", orientation="h", color_discrete_sequence=[BLUE])
            fig.update_layout(margin=dict(t=10,b=10), height=250, plot_bgcolor="white",
                             font_family="DM Sans", xaxis=dict(gridcolor="#E8EDF5"))
            st.plotly_chart(fig, use_container_width=True)
    with col_r:
        st.markdown('<div class="section-header">Recomendaciones</div>', unsafe_allow_html=True)
        for rec in ps.recommendations:
            css = "rec-ok" if rec.startswith("✅") else ("rec-warn" if rec.startswith("⚠️") else "rec-item")
            st.markdown(f'<div class="rec-item {css}">{rec}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header">Posiciones</div>', unsafe_allow_html=True)
    h = ps.holdings.copy()
    h["market_value_usd"]  = h["market_value_usd"].apply(lambda x: f"USD {x:,.0f}")
    h["market_value_orig"] = h.apply(lambda r: f"$ {r['market_value_orig']:,.0f}"
        if r.get("currency_orig")=="ARS" else f"USD {r['market_value_orig']:,.0f}", axis=1)
    h["weight"]   = h["weight"].apply(lambda x: f"{x:.1f}%")
    h["ytm"]      = h["ytm"].apply(lambda x: f"{x:.1f}%" if x>0 else "—")
    h["duration"] = h["duration"].apply(lambda x: f"{x:.1f}" if x>0 else "—")
    h = h.rename(columns={"market_value_usd":"Val. USD","market_value_orig":"Val. Original",
        "currency_orig":"Moneda","weight":"Peso %","ytm":"TIR %","duration":"Duration",
        "risk_score":"Riesgo","instrument_name":"Nombre","instrument_type":"Tipo","asset_class":"Clase"})
    st.dataframe(h, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-header">Contribución al Riesgo</div>', unsafe_allow_html=True)
    h_raw = ps.holdings.copy()
    h_raw["contrib"] = (h_raw["weight"]/100) * h_raw["risk_score"]
    fig = px.bar(h_raw.nlargest(10,"contrib"), x="ticker", y="contrib", color="contrib",
                 color_continuous_scale=["#1A7A4A","#FFD166","#C0392B"],
                 labels={"ticker":"","contrib":"Contribución al Riesgo"})
    fig.update_layout(height=220, margin=dict(t=10,b=10), plot_bgcolor="white",
                     coloraxis_showscale=False, font_family="DM Sans", yaxis=dict(gridcolor="#E8EDF5"))
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — VS MODELO
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    modelo = cfg_global.get("model_portfolios",{}).get(ps.risk_profile,{})
    if not modelo:
        st.info("No hay cartera modelo configurada para este perfil.")
    else:
        actual      = ps.exposure_by_asset_class
        all_classes = sorted(set(list(modelo.keys()) + list(actual.keys())))
        df_vs = pd.DataFrame({
            "Clase":  all_classes,
            "Modelo": [float(modelo.get(c,0)) for c in all_classes],
            "Actual": [round(actual.get(c,0),1) for c in all_classes],
        })
        df_vs["Desvío"] = df_vs["Actual"] - df_vs["Modelo"]

        st.markdown('<div class="section-header">Cartera Actual vs Benchmark</div>', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Modelo", x=df_vs["Clase"], y=df_vs["Modelo"],
                             marker_color="#E8EDF5", marker_line_color=NAVY, marker_line_width=1.5))
        fig.add_trace(go.Bar(name="Actual", x=df_vs["Clase"], y=df_vs["Actual"],
                             marker_color=BLUE))
        fig.update_layout(barmode="group", height=320, plot_bgcolor="white",
                         font_family="DM Sans", margin=dict(t=10,b=10),
                         legend=dict(orientation="h",y=1.1),
                         yaxis=dict(gridcolor="#E8EDF5",title="%"), xaxis=dict(title=""))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="section-header">Análisis de Desvíos</div>', unsafe_allow_html=True)
        dc1, dc2 = st.columns([2,3])
        with dc1:
            for _, row in df_vs.iterrows():
                dev = row["Desvío"]
                color = "#1A7A4A" if abs(dev)<3 else ("#856404" if abs(dev)<10 else "#C0392B")
                icon  = "✅" if abs(dev)<3 else ("⚠️" if abs(dev)<10 else "🔴")
                st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;
                    padding:10px 14px;background:white;border:1px solid #E8EDF5;border-radius:8px;margin-bottom:6px;">
                    <div style="font-weight:600;color:{NAVY}">{row['Clase']}</div>
                    <div style="font-size:13px;color:#6B7C9B">
                        Modelo: <b>{row['Modelo']:.0f}%</b> · Actual: <b>{row['Actual']:.1f}%</b>
                    </div>
                    <div style="color:{color};font-weight:700">{icon} {dev:+.1f}%</div>
                </div>""", unsafe_allow_html=True)
        with dc2:
            colors_dev = [BLUE if d>=0 else "#C0392B" for d in df_vs["Desvío"]]
            fig2 = go.Figure(go.Bar(x=df_vs["Clase"], y=df_vs["Desvío"],
                marker_color=colors_dev, text=[f"{d:+.1f}%" for d in df_vs["Desvío"]],
                textposition="outside"))
            fig2.add_hline(y=0, line_color=NAVY, line_width=1)
            fig2.update_layout(height=280, plot_bgcolor="white", font_family="DM Sans",
                              margin=dict(t=30,b=10), yaxis=dict(gridcolor="#E8EDF5",title="Desvío %"),
                              title=dict(text="Desvío Actual − Modelo", font_size=13, x=0))
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown('<div class="section-header">Métricas vs Objetivo</div>', unsafe_allow_html=True)
        thr = cfg_global.get("thresholds",{}).get(ps.risk_profile,{})
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Retorno Esperado",   f"{ps.expected_return:.1f}%")
        m2.metric("Duration actual",    f"{ps.portfolio_duration:.1f} años",
                  delta=f"Máx: {thr.get('max_duration','—')} años", delta_color="off")
        m3.metric("Riesgo score",       f"{ps.portfolio_risk_score:.1f}/10",
                  delta=f"Máx: {thr.get('max_risk_score','—')}/10", delta_color="off")
        m4.metric("HHI Concentración",  f"{ps.hhi:.3f}",
                  delta=f"Máx: {thr.get('max_hhi','—')}", delta_color="off")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ROTACIONES
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    rot_df     = load_rotaciones()
    rot_client = rot_df[rot_df["client_id"]==selected_id].copy()

    cf, cl = st.columns([2,3])
    with cf:
        st.markdown('<div class="section-header">Nueva Rotación</div>', unsafe_allow_html=True)
        TIPOS = ["Bono Soberano","ON Corporativa","LECAP","Bono CER","Dólar Linked","CEDEAR","Acción","ETF","FCI","Cash"]
        v_ticker  = st.text_input("Vender — Ticker", placeholder="Ej: AL30").upper()
        v_tipo    = st.selectbox("Tipo (venta)", TIPOS, key="vt")
        v_nominal = st.text_input("Nominal", placeholder="Ej: 500000")
        st.markdown("---")
        c_ticker  = st.text_input("Comprar — Ticker", placeholder="Ej: GD30").upper()
        c_tipo    = st.selectbox("Tipo (compra)", TIPOS, key="ct")
        tesis     = st.text_area("Tesis / Motivo", height=80)
        mejora    = st.text_input("Mejora TIR est.", placeholder="Ej: +1.5%")
        prioridad = st.selectbox("Prioridad", ["Alta","Media","Baja"])

        if st.button("➕ Agregar", use_container_width=True, type="primary"):
            if v_ticker and c_ticker and tesis:
                nueva = pd.DataFrame([{
                    "client_id": selected_id, "client_name": ps.client_name,
                    "fecha": str(date.today()),
                    "vender_ticker": v_ticker, "vender_tipo": v_tipo, "vender_nominal": v_nominal,
                    "comprar_ticker": c_ticker, "comprar_tipo": c_tipo,
                    "tesis": tesis, "mejora_tir": mejora, "prioridad": prioridad, "estado": "Pendiente",
                }])
                rot_df = pd.concat([rot_df, nueva], ignore_index=True)
                save_rotaciones(rot_df); st.success("✅ Guardado"); st.rerun()
            else:
                st.warning("Completá ticker venta, compra y tesis.")

    with cl:
        st.markdown('<div class="section-header">Rotaciones Registradas</div>', unsafe_allow_html=True)
        if rot_client.empty:
            st.markdown('<div style="background:#F4F6FA;border-radius:8px;padding:16px;color:#6B7C9B;font-size:13px;">Sin rotaciones para este cliente.</div>', unsafe_allow_html=True)
        else:
            for idx, row in rot_client.iterrows():
                estado    = row.get("estado","Pendiente")
                tag_class = {"Pendiente":"rot-tag-pendiente","Ejecutada":"rot-tag-ejecutada",
                             "Descartada":"rot-tag-descartada"}.get(estado,"rot-tag-pendiente")
                prio_col  = {"Alta":"#C0392B","Media":"#856404","Baja":"#1A7A4A"}.get(row.get("prioridad","Media"),"#856404")
                st.markdown(f"""<div class="rot-card">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <span style="font-size:16px;font-weight:700;color:{NAVY}">
                            {row.get('vender_ticker','?')} → {row.get('comprar_ticker','?')}
                        </span>
                        <div>
                            <span class="{tag_class}">{estado}</span>
                            &nbsp;<span style="color:{prio_col};font-size:11px;font-weight:600">{row.get('prioridad','')}</span>
                        </div>
                    </div>
                    <div style="font-size:12px;color:#6B7C9B;margin-bottom:6px;">
                        <b>Venta:</b> {row.get('vender_tipo','')} {f"· {row.get('vender_nominal','')}" if row.get('vender_nominal') else ''}
                        &nbsp;|&nbsp; <b>Compra:</b> {row.get('comprar_tipo','')}
                        {f"&nbsp;|&nbsp; <b>Mejora TIR:</b> {row.get('mejora_tir','')}" if row.get('mejora_tir') else ''}
                        &nbsp;·&nbsp; {row.get('fecha','')}
                    </div>
                    <div style="font-size:13px;color:{NAVY};font-style:italic;">"{row.get('tesis','')}"</div>
                </div>""", unsafe_allow_html=True)
                bc1,bc2,bc3 = st.columns(3)
                if bc1.button("✅ Ejecutada",  key=f"ej_{idx}",   use_container_width=True):
                    rot_df.loc[idx,"estado"]="Ejecutada";   save_rotaciones(rot_df); st.rerun()
                if bc2.button("🗑 Descartar",  key=f"desc_{idx}", use_container_width=True):
                    rot_df.loc[idx,"estado"]="Descartada";  save_rotaciones(rot_df); st.rerun()
                if bc3.button("❌ Eliminar",   key=f"del_{idx}",  use_container_width=True):
                    rot_df = rot_df.drop(idx); save_rotaciones(rot_df); st.rerun()

        if not rot_df.empty:
            st.markdown("---")
            rc1,rc2,rc3 = st.columns(3)
            rc1.metric("Total rotaciones", len(rot_df))
            rc2.metric("Pendientes", len(rot_df[rot_df["estado"]=="Pendiente"]))
            rc3.metric("Ejecutadas", len(rot_df[rot_df["estado"]=="Ejecutada"]))
            st.download_button("📥 Descargar CSV", rot_df.to_csv(index=False).encode(),
                               "rotaciones.csv","text/csv", use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — FICHA CLIENTE
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    cl_edit = clients_df[clients_df["client_id"]==selected_id].iloc[0].copy()
    ext_cfg = cfg_global.get("client_extended_fields",{})
    fc1, fc2 = st.columns([1,1])

    with fc1:
        st.markdown('<div class="section-header">Datos del Cliente</div>', unsafe_allow_html=True)
        new_name = st.text_input("Nombre completo", value=cl_edit.get("client_name",""))

        hor_opts = [""] + ext_cfg.get("horizonte_opciones",["< 1 año","1-3 años","3-5 años","> 5 años"])
        cur_hor  = cl_edit.get("horizonte","")
        new_horizonte = st.selectbox("Horizonte de inversión", hor_opts,
            index=hor_opts.index(cur_hor) if cur_hor in hor_opts else 0)

        obj_opts = [""] + ext_cfg.get("objetivo_opciones",[])
        cur_obj  = cl_edit.get("objetivo","")
        new_objetivo = st.selectbox("Objetivo principal", obj_opts,
            index=obj_opts.index(cur_obj) if cur_obj in obj_opts else 0)

        tol_opts = [""] + ext_cfg.get("tolerancia_opciones",[])
        cur_tol  = cl_edit.get("tolerancia","")
        new_tolerancia = st.selectbox("Tolerancia a pérdida", tol_opts,
            index=tol_opts.index(cur_tol) if cur_tol in tol_opts else 0)

        if st.button("💾 Guardar ficha", type="primary", use_container_width=True):
            idx = clients_df[clients_df["client_id"]==selected_id].index[0]
            clients_df.loc[idx,"client_name"]  = new_name
            clients_df.loc[idx,"horizonte"]    = new_horizonte
            clients_df.loc[idx,"objetivo"]     = new_objetivo
            clients_df.loc[idx,"tolerancia"]   = new_tolerancia
            save_clients(clients_df)
            st.success("✅ Ficha actualizada"); st.cache_data.clear(); st.rerun()

    with fc2:
        st.markdown('<div class="section-header">Resumen</div>', unsafe_allow_html=True)
        fields = [
            ("ID Balanz",    selected_id),
            ("Perfil",       profile.upper()),
            ("Horizonte",    cl_edit.get("horizonte","—") or "—"),
            ("Objetivo",     cl_edit.get("objetivo","—") or "—"),
            ("Tolerancia",   cl_edit.get("tolerancia","—") or "—"),
            ("Total USD",    f"USD {ps.total_value_usd:,.0f}"),
            ("Total ARS",    f"$ {ps.total_value_ars:,.0f}"),
            ("Retorno esp.", f"{ps.expected_return:.1f}%"),
            ("Duration RF",  f"{ps.portfolio_duration:.1f} años"),
            ("Riesgo",       f"{ps.portfolio_risk_score:.1f}/10"),
        ]
        for label, val in fields:
            st.markdown(f"""<div style="display:flex;justify-content:space-between;
                padding:8px 12px;border-bottom:1px solid #F0F0F0;">
                <span style="color:#6B7C9B;font-size:12px;text-transform:uppercase;letter-spacing:.4px">{label}</span>
                <span style="color:{NAVY};font-weight:600;font-size:13px">{val}</span>
            </div>""", unsafe_allow_html=True)

# ── Disclaimer ────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(f'<div style="font-size:10px;color:#9AAABE;line-height:1.6"><b>Disclaimer:</b> {cfg_global["report"]["disclaimer"]}</div>',
            unsafe_allow_html=True)
