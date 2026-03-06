"""
Portfolio Lab — Generador de reportes HTML/PDF
"""
from __future__ import annotations
import io
from datetime import date
from pathlib import Path
from engine.analytics import PortfolioSummary, load_config

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def _color_risk(score: float) -> str:
    if score <= 3:   return "#1A7A4A"
    if score <= 6:   return "#B8860B"
    return "#C0392B"

def _color_pct(val: float, limit: float) -> str:
    return "#C0392B" if val > limit else "#1B2A4A"


def generate_html_report(ps: PortfolioSummary) -> str:
    cfg = load_config()
    today = date.today().strftime("%d/%m/%Y")
    profile = ps.risk_profile.capitalize()

    # Holdings table rows
    rows_html = ""
    for _, row in ps.holdings.iterrows():
        dur = f"{row['duration']:.1f}" if row.get('duration', 0) > 0 else "—"
        ytm = f"{row['ytm']:.1f}%" if row.get('ytm', 0) > 0 else "—"
        rows_html += f"""
        <tr>
          <td><b>{row['ticker']}</b></td>
          <td>{row.get('instrument_name','')}</td>
          <td>{row.get('asset_class','')}</td>
          <td>{row.get('currency','')}</td>
          <td style="text-align:right">${row['market_value_usd']:,.0f}</td>
          <td style="text-align:right"><b>{row['weight']:.1f}%</b></td>
          <td style="text-align:center">{ytm}</td>
          <td style="text-align:center">{dur}</td>
          <td style="text-align:center;color:{_color_risk(row['risk_score'])}">{row['risk_score']:.0f}/10</td>
        </tr>"""

    # Exposure bars
    def bars(exp_dict: dict, title: str) -> str:
        items = sorted(exp_dict.items(), key=lambda x: -x[1])
        html = f"<h3>{title}</h3>"
        for k, v in items:
            html += f"""
            <div class="bar-row">
              <span class="bar-label">{k}</span>
              <div class="bar-track">
                <div class="bar-fill" style="width:{min(v,100):.0f}%"></div>
              </div>
              <span class="bar-pct">{v:.1f}%</span>
            </div>"""
        return html

    # Recommendations
    recs_html = "".join(f"<li>{r}</li>" for r in ps.recommendations)

    # HHI interpretation
    hhi_label = "Baja" if ps.hhi < 0.15 else ("Media" if ps.hhi < 0.25 else "Alta")
    hhi_color = "#1A7A4A" if ps.hhi < 0.15 else ("#B8860B" if ps.hhi < 0.25 else "#C0392B")

    disclaimer = cfg["report"]["disclaimer"]
    firm = cfg["report"]["firm_name"]

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diagnóstico de Cartera — {ps.client_name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'DM Sans', sans-serif; background: #F4F6FA; color: #1B2A4A; font-size: 13px; }}
  .page {{ max-width: 960px; margin: 0 auto; background: white; }}

  /* Header */
  .header {{ background: #1B2A4A; color: white; padding: 36px 48px 28px; }}
  .header-top {{ display: flex; justify-content: space-between; align-items: flex-start; }}
  .firm-name {{ font-family: 'DM Serif Display', serif; font-size: 22px; letter-spacing: 0.5px; }}
  .report-date {{ font-size: 11px; opacity: .7; text-align: right; }}
  .client-block {{ margin-top: 20px; border-top: 1px solid rgba(255,255,255,.2); padding-top: 16px; }}
  .client-name {{ font-family: 'DM Serif Display', serif; font-size: 28px; }}
  .client-meta {{ display: flex; gap: 24px; margin-top: 6px; font-size: 11px; opacity: .8; }}
  .badge {{ background: rgba(255,255,255,.15); padding: 3px 10px; border-radius: 20px; }}

  /* KPI cards */
  .kpis {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 1px; background: #E8EDF5; }}
  .kpi {{ background: white; padding: 20px 24px; }}
  .kpi-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: .8px; color: #6B7C9B; font-weight: 600; }}
  .kpi-value {{ font-family: 'DM Serif Display', serif; font-size: 28px; color: #1B2A4A; margin-top: 4px; }}
  .kpi-sub {{ font-size: 10px; color: #9AAABE; margin-top: 2px; }}

  /* Sections */
  .section {{ padding: 32px 48px; border-bottom: 1px solid #E8EDF5; }}
  .section-title {{ font-family: 'DM Serif Display', serif; font-size: 20px; color: #2E4D8A; margin-bottom: 20px;
                    padding-bottom: 10px; border-bottom: 2px solid #E8EDF5; }}

  /* Table */
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ background: #1B2A4A; color: white; padding: 8px 10px; text-align: left; font-weight: 500;
        font-size: 10px; text-transform: uppercase; letter-spacing: .5px; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #F0F3F9; }}
  tr:hover td {{ background: #F8FAFD; }}
  tr:nth-child(even) td {{ background: #FAFBFD; }}
  tr:nth-child(even):hover td {{ background: #F0F3F9; }}

  /* Exposure bars */
  .exposure-grid {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 32px; }}
  .bar-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
  .bar-label {{ width: 100px; font-size: 11px; color: #4A5C7A; flex-shrink: 0; }}
  .bar-track {{ flex: 1; height: 6px; background: #E8EDF5; border-radius: 3px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: linear-gradient(90deg, #2E4D8A, #4A7FC1); border-radius: 3px; }}
  .bar-pct {{ width: 38px; font-size: 11px; font-weight: 600; color: #1B2A4A; text-align: right; }}
  h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .6px; color: #6B7C9B;
        font-weight: 600; margin-bottom: 12px; }}

  /* Recommendations */
  .recs ul {{ padding-left: 0; list-style: none; }}
  .recs li {{ padding: 12px 16px; margin-bottom: 8px; border-radius: 6px;
              background: #F4F6FA; border-left: 3px solid #2E4D8A;
              line-height: 1.5; font-size: 12.5px; }}

  /* Footer */
  .footer {{ padding: 24px 48px; background: #F4F6FA; }}
  .disclaimer {{ font-size: 10px; color: #9AAABE; line-height: 1.6; }}

  @media print {{
    body {{ background: white; }}
    .page {{ box-shadow: none; }}
  }}
</style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="header">
    <div class="header-top">
      <div class="firm-name">PORTFOLIO LAB</div>
      <div class="report-date">Diagnóstico de Cartera<br>{today}<br>{firm}</div>
    </div>
    <div class="client-block">
      <div class="client-name">{ps.client_name}</div>
      <div class="client-meta">
        <span class="badge">Perfil: {profile}</span>
        <span class="badge">Moneda base: {ps.base_currency}</span>
        <span class="badge">Total: USD {ps.total_value_usd:,.0f}</span>
      </div>
    </div>
  </div>

  <!-- KPIs -->
  <div class="kpis">
    <div class="kpi">
      <div class="kpi-label">Retorno Esperado</div>
      <div class="kpi-value" style="color:#1A7A4A">{ps.expected_return:.1f}%</div>
      <div class="kpi-sub">anual ponderado</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Duration (RF)</div>
      <div class="kpi-value">{ps.portfolio_duration:.1f}</div>
      <div class="kpi-sub">años — Macaulay aprox.</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Riesgo Agregado</div>
      <div class="kpi-value" style="color:{_color_risk(ps.portfolio_risk_score)}">{ps.portfolio_risk_score:.1f}<span style="font-size:14px">/10</span></div>
      <div class="kpi-sub">score ponderado</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Concentración HHI</div>
      <div class="kpi-value" style="color:{hhi_color}">{ps.hhi:.3f}</div>
      <div class="kpi-sub">{hhi_label} concentración</div>
    </div>
  </div>

  <!-- HOLDINGS -->
  <div class="section">
    <div class="section-title">Posiciones</div>
    <table>
      <thead>
        <tr>
          <th>Ticker</th><th>Instrumento</th><th>Clase</th><th>Moneda</th>
          <th style="text-align:right">Val. USD</th>
          <th style="text-align:right">Peso %</th>
          <th style="text-align:center">TIR/Yield</th>
          <th style="text-align:center">Duration</th>
          <th style="text-align:center">Riesgo</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <!-- EXPOSICIÓN -->
  <div class="section">
    <div class="section-title">Exposición</div>
    <div class="exposure-grid">
      {bars(ps.exposure_by_asset_class, "Por Clase de Activo")}
      {bars(ps.exposure_by_currency, "Por Moneda")}
      {bars(ps.exposure_by_country, "Por País")}
    </div>
  </div>

  <!-- RECOMENDACIONES -->
  <div class="section recs">
    <div class="section-title">Recomendaciones</div>
    <ul>{recs_html}</ul>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    <div class="disclaimer"><b>Disclaimer:</b> {disclaimer}</div>
  </div>

</div>
</body>
</html>"""
    return html


def save_report(ps: PortfolioSummary) -> Path:
    html = generate_html_report(ps)
    path = REPORTS_DIR / f"reporte_{ps.client_id}_{date.today().isoformat()}.html"
    path.write_text(html, encoding="utf-8")
    return path
