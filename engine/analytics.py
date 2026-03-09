"""
Portfolio Lab — Motor de cálculo v2
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
def _find_base_dir() -> Path:
    candidates = [
        Path(__file__).parent.parent,
        Path(__file__).parent,
        Path.cwd(),
        Path("/mount/src/balanz"),
        Path("/mount/src/portfolio-lab"),
    ]
    for p in candidates:
        if (p / "config.yaml").exists():
            return p
    return Path.cwd()

BASE_DIR    = _find_base_dir()
CONFIG_PATH = BASE_DIR / "config.yaml"
DATA_DIR    = BASE_DIR / "data"

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {
            "expected_return": {"RF": 7.5, "Equity": 10.0, "Alternatives": 6.0, "Cash": 5.0},
            "default_risk_score": {"bono": 4, "on": 4, "fondo": 3, "etf": 6, "equity": 7, "commodities": 5, "cash": 1},
            "thresholds": {
                "conservador": {"max_ar_pct": 40, "max_equity_pct": 5,  "max_duration": 2.0, "min_cash_pct": 10, "max_cash_pct": 30, "max_hhi": 0.20, "max_risk_score": 4.0},
                "moderado":    {"max_ar_pct": 60, "max_equity_pct": 25, "max_duration": 3.5, "min_cash_pct": 5,  "max_cash_pct": 25, "max_hhi": 0.25, "max_risk_score": 6.0},
                "agresivo":    {"max_ar_pct": 70, "max_equity_pct": 50, "max_duration": 7.0, "min_cash_pct": 2,  "max_cash_pct": 20, "max_hhi": 0.35, "max_risk_score": 8.0},
            },
            "fx_fallback": {"ARS_to_USD": 0.00096},
            "report": {"firm_name": "Balanz — Asesor Independiente", "disclaimer": "Este informe tiene carácter exclusivamente informativo.", "logo_text": "PORTFOLIO LAB"},
        }
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def load_clients() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "clients.csv", dtype=str).fillna("")

def load_holdings() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "holdings.csv", dtype=str)
    num_cols = ["quantity","price_override","market_value_override",
                "ytm_override","duration_override","risk_score_override"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def load_master() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "instruments_master.csv", dtype=str)
    for c in ["default_ytm","default_duration","default_risk_score"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def fetch_prices(tickers: list[str]) -> dict[str, float]:
    prices = {}
    if not tickers:
        return prices
    try:
        import yfinance as yf
        raw = yf.download(tickers, period="2d", auto_adjust=True, progress=False)
        if "Close" in raw.columns:
            last = raw["Close"].ffill().iloc[-1]
            if isinstance(last, pd.Series):
                prices = last.dropna().to_dict()
            else:
                prices = {tickers[0]: float(last)} if not np.isnan(float(last)) else {}
    except Exception:
        pass
    return prices

def get_fx_rates(config: dict) -> dict:
    """Retorna {MEP: X, CCL: X, Oficial: X} ARS por 1 USD"""
    fallback_rate = 1.0 / config["fx_fallback"]["ARS_to_USD"]
    rates = {"MEP": fallback_rate, "CCL": fallback_rate, "Oficial": fallback_rate}
    try:
        import urllib.request, json
        with urllib.request.urlopen("https://dolarapi.com/v1/dolares", timeout=3) as r:
            data = json.loads(r.read())
        for d in data:
            if d["casa"] == "bolsa"           and d.get("venta"): rates["MEP"]     = float(d["venta"])
            if d["casa"] == "contadoconliqui" and d.get("venta"): rates["CCL"]     = float(d["venta"])
            if d["casa"] == "oficial"         and d.get("venta"): rates["Oficial"] = float(d["venta"])
    except Exception:
        pass
    return rates

@dataclass
class PortfolioSummary:
    client_id: str
    client_name: str
    risk_profile: str
    base_currency: str
    total_value_usd: float
    total_value_ars: float          # total en ARS al TC MEP
    total_usd_instruments: float   # valor instrumentos denominados en USD
    total_ars_instruments: float   # valor instrumentos denominados en ARS (en ARS)
    holdings: pd.DataFrame
    expected_return: float
    portfolio_duration: float
    portfolio_risk_score: float
    hhi: float
    exposure_by_asset_class: dict
    exposure_by_currency: dict     # ahora usa valor original en cada moneda
    exposure_by_country: dict
    recommendations: list[str]
    fx_rates: dict
    warnings: list[str] = field(default_factory=list)


def build_portfolio(client_id: str) -> Optional[PortfolioSummary]:
    cfg     = load_config()
    clients = load_clients()
    hold    = load_holdings()
    master  = load_master()

    client_row = clients[clients["client_id"] == client_id]
    if client_row.empty:
        return None
    client = client_row.iloc[0]

    h = hold[hold["client_id"] == client_id].copy()
    if h.empty:
        return None

    h = h.merge(master.add_prefix("m_").rename(columns={"m_ticker":"ticker"}),
                on="ticker", how="left")

    fx_rates = get_fx_rates(cfg)
    fx = 1.0 / fx_rates["MEP"]  # ARS -> USD

    # ── Precios live ──────────────────────────────────────────────────────────
    need_price = h[h["market_value_override"].isna() &
                   h["price_override"].isna() &
                   h["quantity"].notna()]["ticker"].tolist()
    live_prices = fetch_prices(need_price) if need_price else {}

    def calc_mv(row):
        """Retorna (mv_usd, mv_original, currency_orig)"""
        cur = str(row.get("currency","USD")).upper()
        if pd.notna(row.get("market_value_override")):
            mv_orig = float(row["market_value_override"])
        else:
            price = (row.get("price_override") or live_prices.get(row["ticker"]) or 0)
            qty   = row.get("quantity") or 0
            mv_orig = float(qty) * float(price)
        mv_usd = mv_orig * fx if cur == "ARS" else mv_orig
        return mv_usd, mv_orig, cur

    results = h.apply(calc_mv, axis=1, result_type="expand")
    h["market_value_usd"] = results[0].fillna(0)
    h["market_value_orig"] = results[1].fillna(0)   # en moneda original
    h["currency_orig"] = results[2]

    total_usd = h["market_value_usd"].sum()
    if total_usd == 0:
        return None
    h["weight"] = h["market_value_usd"] / total_usd

    # Totales por moneda (en su propia moneda)
    total_ars_instruments = h[h["currency_orig"]=="ARS"]["market_value_orig"].sum()
    total_usd_instruments = h[h["currency_orig"]=="USD"]["market_value_orig"].sum()
    total_ars = total_usd * fx_rates["MEP"]  # todo convertido a ARS

    # ── YTM ───────────────────────────────────────────────────────────────────
    def get_ytm(row):
        if pd.notna(row.get("ytm_override")):   return float(row["ytm_override"])
        if pd.notna(row.get("m_default_ytm")):  return float(row["m_default_ytm"])
        ac = str(row.get("asset_class","")).strip()
        return cfg["expected_return"].get(ac, cfg["expected_return"]["Equity"])

    h["ytm"] = h.apply(get_ytm, axis=1)
    expected_return = (h["weight"] * h["ytm"]).sum()

    # ── Duration ──────────────────────────────────────────────────────────────
    def get_dur(row):
        if pd.notna(row.get("duration_override")):    return float(row["duration_override"])
        if pd.notna(row.get("m_default_duration")):   return float(row["m_default_duration"])
        return 0.0

    h["duration"] = h.apply(get_dur, axis=1)
    rf_mask  = h["asset_class"] == "RF"
    rf_total = h.loc[rf_mask, "market_value_usd"].sum()
    portfolio_duration = (
        (h.loc[rf_mask, "market_value_usd"] * h.loc[rf_mask, "duration"]).sum() / rf_total
        if rf_total > 0 else 0.0
    )

    # ── Risk score ────────────────────────────────────────────────────────────
    def get_risk(row):
        if pd.notna(row.get("risk_score_override")):    return float(row["risk_score_override"])
        if pd.notna(row.get("m_default_risk_score")):   return float(row["m_default_risk_score"])
        itype = str(row.get("instrument_type","cash")).lower()
        return cfg["default_risk_score"].get(itype, 5)

    h["risk_score"] = h.apply(get_risk, axis=1)
    portfolio_risk  = (h["weight"] * h["risk_score"]).sum()

    # ── HHI ───────────────────────────────────────────────────────────────────
    hhi = (h["weight"] ** 2).sum()

    # ── Exposures — usando valor en moneda ORIGINAL para moneda ───────────────
    def exposure_usd(col):
        return (h.groupby(col)["weight"].sum() * 100).round(1).to_dict()

    def exposure_currency_real():
        """% por moneda usando valor original en cada denominación"""
        grp = h.groupby("currency_orig")["market_value_usd"].sum()
        return (grp / total_usd * 100).round(1).to_dict()

    exp_ac  = exposure_usd("asset_class")
    exp_cur = exposure_currency_real()   # ← ahora correcto
    exp_cty = exposure_usd("country")

    # ── Recomendaciones ───────────────────────────────────────────────────────
    profile = str(client["risk_profile"]).lower()
    thr  = cfg["thresholds"].get(profile, cfg["thresholds"]["moderado"])
    recs = []

    ar_pct   = sum(v for k,v in exp_cty.items() if k == "AR")
    eq_pct   = exp_ac.get("Equity", 0)
    cash_pct = exp_ac.get("Cash", 0)
    ars_pct  = exp_cur.get("ARS", 0)

    if ar_pct > thr["max_ar_pct"]:
        recs.append(f"⚠️ Alta concentración Argentina ({ar_pct:.0f}% > límite {thr['max_ar_pct']}%). Considerar ETFs globales o activos dolarizados en exterior.")
    if eq_pct > thr["max_equity_pct"]:
        recs.append(f"⚠️ Renta variable elevada ({eq_pct:.0f}%) para perfil {profile}. Límite: {thr['max_equity_pct']}%. Rotar a renta fija.")
    if portfolio_duration > thr["max_duration"]:
        recs.append(f"⚠️ Duration alta ({portfolio_duration:.1f} años). Máximo para {profile}: {thr['max_duration']} años. Acortar con LECAPs o instrumentos cortos.")
    if cash_pct > thr["max_cash_pct"]:
        recs.append(f"💡 Exceso de liquidez ({cash_pct:.0f}%). Considerar colocar en instrumentos acordes al perfil {profile}.")
    if cash_pct < thr["min_cash_pct"]:
        recs.append(f"💡 Liquidez baja ({cash_pct:.0f}%). Mantener al menos {thr['min_cash_pct']}% en cash/money market.")
    if hhi > thr["max_hhi"]:
        recs.append(f"⚠️ Concentración alta (HHI={hhi:.2f} > {thr['max_hhi']}). Diversificar: reducir posiciones grandes o agregar instrumentos.")
    if portfolio_risk > thr["max_risk_score"]:
        recs.append(f"⚠️ Riesgo agregado ({portfolio_risk:.1f}/10) supera límite para {profile} ({thr['max_risk_score']}/10).")
    if ars_pct > 50 and profile == "conservador":
        recs.append(f"💡 Alta exposición en ARS ({ars_pct:.0f}%). Perfil conservador se beneficia de cobertura en USD o instrumentos dólar-linked.")
    if not recs:
        recs.append("✅ La cartera está alineada con el perfil de riesgo. Sin observaciones críticas.")

    # ── Holdings display ──────────────────────────────────────────────────────
    display_cols = ["ticker","instrument_name","instrument_type","currency_orig",
                    "country","asset_class","market_value_usd","market_value_orig","weight",
                    "ytm","duration","risk_score"]
    display_cols = [c for c in display_cols if c in h.columns]
    hd = h[display_cols].copy()
    hd["market_value_usd"]  = hd["market_value_usd"].round(0)
    hd["market_value_orig"] = hd["market_value_orig"].round(0)
    hd["weight"]      = (hd["weight"] * 100).round(1)
    hd["ytm"]         = hd["ytm"].round(2)
    hd["duration"]    = hd["duration"].round(2)
    hd["risk_score"]  = hd["risk_score"].round(1)
    hd = hd.sort_values("weight", ascending=False).reset_index(drop=True)

    return PortfolioSummary(
        client_id=client_id,
        client_name=client["client_name"],
        risk_profile=profile,
        base_currency=client["base_currency"],
        total_value_usd=round(total_usd, 0),
        total_value_ars=round(total_ars, 0),
        total_usd_instruments=round(total_usd_instruments, 0),
        total_ars_instruments=round(total_ars_instruments, 0),
        holdings=hd,
        expected_return=round(expected_return, 2),
        portfolio_duration=round(portfolio_duration, 2),
        portfolio_risk_score=round(portfolio_risk, 2),
        hhi=round(hhi, 4),
        exposure_by_asset_class=exp_ac,
        exposure_by_currency=exp_cur,
        exposure_by_country=exp_cty,
        recommendations=recs,
        fx_rates=fx_rates,
    )
