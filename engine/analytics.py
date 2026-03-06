"""
Portfolio Lab — Motor de cálculo
Cálculos de retorno, duration, exposición, concentración y riesgo.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────────────
# Busca los archivos en múltiples ubicaciones posibles
# (local, Streamlit Cloud /mount/src/..., etc.)
def _find_base_dir() -> Path:
    candidates = [
        Path(__file__).parent.parent,           # estructura normal: engine/../
        Path(__file__).parent,                  # engine/ mismo
        Path.cwd(),                             # directorio de trabajo
        Path("/mount/src/balanz"),              # Streamlit Cloud
        Path("/mount/src/portfolio-lab"),       # Streamlit Cloud alt
    ]
    for p in candidates:
        if (p / "config.yaml").exists():
            return p
    # Fallback: usar cwd y crear data si no existe
    return Path.cwd()

BASE_DIR    = _find_base_dir()
CONFIG_PATH = BASE_DIR / "config.yaml"
DATA_DIR    = BASE_DIR / "data"

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        # Config mínima de fallback
        return {
            "expected_return": {"RF": 7.5, "Equity": 10.0, "Alternatives": 6.0, "Cash": 5.0},
            "default_risk_score": {"bono": 4, "on": 4, "fondo": 3, "etf": 6, "equity": 7, "commodities": 5, "cash": 1},
            "thresholds": {
                "conservador": {"max_ar_pct": 40, "max_equity_pct": 5, "max_duration": 2.0, "min_cash_pct": 10, "max_cash_pct": 30, "max_hhi": 0.20, "max_risk_score": 4.0},
                "moderado":    {"max_ar_pct": 60, "max_equity_pct": 25, "max_duration": 3.5, "min_cash_pct": 5,  "max_cash_pct": 25, "max_hhi": 0.25, "max_risk_score": 6.0},
                "agresivo":    {"max_ar_pct": 70, "max_equity_pct": 50, "max_duration": 7.0, "min_cash_pct": 2,  "max_cash_pct": 20, "max_hhi": 0.35, "max_risk_score": 8.0},
            },
            "fx_fallback": {"ARS_to_USD": 0.00096},
            "report": {"firm_name": "Balanz — Asesor Independiente", "disclaimer": "Este informe tiene carácter exclusivamente informativo.", "logo_text": "PORTFOLIO LAB"},
        }
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

# ── Data loaders ─────────────────────────────────────────────────────────────

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
    num_cols = ["default_ytm","default_duration","default_risk_score"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# ── Price fetcher ─────────────────────────────────────────────────────────────

def fetch_prices(tickers: list[str]) -> dict[str, float]:
    """Intenta yfinance; si falla devuelve dict vacío (modo offline)."""
    prices = {}
    if not tickers:
        return prices
    try:
        import yfinance as yf
        raw = yf.download(tickers, period="1d", auto_adjust=True, progress=False)
        if "Close" in raw.columns:
            last = raw["Close"].iloc[-1]
            if isinstance(last, pd.Series):
                prices = last.dropna().to_dict()
            else:
                prices = {tickers[0]: float(last)} if not np.isnan(last) else {}
    except Exception:
        pass
    return prices

# ── FX ────────────────────────────────────────────────────────────────────────

def get_fx_ars_to_usd(config: dict) -> float:
    """TC ARS→USD: intenta dolarapi, fallback a config."""
    try:
        import urllib.request, json
        with urllib.request.urlopen("https://dolarapi.com/v1/dolares", timeout=3) as r:
            data = json.loads(r.read())
        mep = next((d for d in data if d["casa"] == "bolsa"), None)
        if mep and mep.get("venta"):
            return 1.0 / float(mep["venta"])
    except Exception:
        pass
    return config["fx_fallback"]["ARS_to_USD"]

# ── Core analytics ────────────────────────────────────────────────────────────

@dataclass
class PortfolioSummary:
    client_id: str
    client_name: str
    risk_profile: str
    base_currency: str
    total_value_usd: float
    holdings: pd.DataFrame          # enriquecido con pesos y métricas
    expected_return: float          # % anual ponderado
    portfolio_duration: float       # años (solo RF)
    portfolio_risk_score: float     # 1-10 ponderado
    hhi: float                      # Herfindahl
    exposure_by_asset_class: dict
    exposure_by_currency: dict
    exposure_by_country: dict
    recommendations: list[str]
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

    # Merge con master para defaults
    h = h.merge(master.add_prefix("m_").rename(columns={"m_ticker":"ticker"}),
                on="ticker", how="left")

    # FX
    fx = get_fx_ars_to_usd(cfg)

    # ── Calcular market value en USD ──────────────────────────────────────
    # Obtener precios de yfinance para lo que no tiene override
    need_price = h[h["market_value_override"].isna() &
                   h["price_override"].isna() &
                   h["quantity"].notna()]["ticker"].tolist()
    live_prices = fetch_prices(need_price) if need_price else {}

    def calc_mv(row):
        if pd.notna(row.get("market_value_override")):
            mv = float(row["market_value_override"])
        else:
            price = (row.get("price_override")
                     or live_prices.get(row["ticker"])
                     or 0)
            qty = row.get("quantity") or 0
            mv = float(qty) * float(price)

        # Convertir ARS → USD
        if str(row.get("currency","")).upper() == "ARS":
            mv = mv * fx
        return mv

    h["market_value_usd"] = h.apply(calc_mv, axis=1)
    # Reemplazar NaN por 0 (instrumentos sin precio disponible)
    h["market_value_usd"] = h["market_value_usd"].fillna(0)
    total = h["market_value_usd"].sum()
    if total == 0:
        return None
    h["weight"] = h["market_value_usd"] / total

    # ── YTM / expected return ──────────────────────────────────────────────
    def get_ytm(row):
        if pd.notna(row.get("ytm_override")):
            return float(row["ytm_override"])
        if pd.notna(row.get("m_default_ytm")):
            return float(row["m_default_ytm"])
        ac = str(row.get("asset_class","")).strip()
        return cfg["expected_return"].get(ac, cfg["expected_return"]["Equity"])

    h["ytm"] = h.apply(get_ytm, axis=1)
    expected_return = (h["weight"] * h["ytm"]).sum()

    # ── Duration (solo RF) ────────────────────────────────────────────────
    def get_dur(row):
        if pd.notna(row.get("duration_override")):
            return float(row["duration_override"])
        if pd.notna(row.get("m_default_duration")):
            return float(row["m_default_duration"])
        return 0.0

    h["duration"] = h.apply(get_dur, axis=1)
    rf_mask = h["asset_class"].isin(["RF"])
    rf_total = h.loc[rf_mask, "market_value_usd"].sum()
    if rf_total > 0:
        portfolio_duration = (
            h.loc[rf_mask, "market_value_usd"] * h.loc[rf_mask, "duration"]
        ).sum() / rf_total
    else:
        portfolio_duration = 0.0

    # ── Risk score ────────────────────────────────────────────────────────
    def get_risk(row):
        if pd.notna(row.get("risk_score_override")):
            return float(row["risk_score_override"])
        if pd.notna(row.get("m_default_risk_score")):
            return float(row["m_default_risk_score"])
        itype = str(row.get("instrument_type","cash")).lower()
        return cfg["default_risk_score"].get(itype, 5)

    h["risk_score"] = h.apply(get_risk, axis=1)
    portfolio_risk = (h["weight"] * h["risk_score"]).sum()

    # ── HHI ──────────────────────────────────────────────────────────────
    hhi = (h["weight"] ** 2).sum()

    # ── Exposures ────────────────────────────────────────────────────────
    def exposure(col):
        return (h.groupby(col)["weight"].sum() * 100).round(1).to_dict()

    exp_ac  = exposure("asset_class")
    exp_cur = exposure("currency")
    exp_cty = exposure("country")

    # ── Recommendations ───────────────────────────────────────────────────
    profile = str(client["risk_profile"]).lower()
    thr = cfg["thresholds"].get(profile, cfg["thresholds"]["moderado"])
    recs = []

    ar_pct = sum(v for k,v in exp_cty.items() if k == "AR")
    eq_pct = exp_ac.get("Equity", 0)
    cash_pct = exp_ac.get("Cash", 0)
    ars_pct = exp_cur.get("ARS", 0)

    if ar_pct > thr["max_ar_pct"]:
        recs.append(
            f"⚠️ Alta concentración Argentina ({ar_pct:.0f}% > límite {thr['max_ar_pct']}%). "
            f"Considerar aumentar exposición a ETFs globales (SPY, QQQ) o activos dolarizados en exterior."
        )
    if eq_pct > thr["max_equity_pct"]:
        recs.append(
            f"⚠️ Renta variable elevada ({eq_pct:.0f}%) para perfil {profile}. "
            f"Límite sugerido: {thr['max_equity_pct']}%. Rotar a renta fija de calidad."
        )
    if portfolio_duration > thr["max_duration"]:
        recs.append(
            f"⚠️ Duration de cartera alta ({portfolio_duration:.1f} años) para perfil {profile}. "
            f"Máximo sugerido: {thr['max_duration']} años. Acortar via LECAPs o instrumentos cortos."
        )
    if cash_pct > thr["max_cash_pct"]:
        recs.append(
            f"💡 Exceso de liquidez ({cash_pct:.0f}%). "
            f"Considerar colocar parte en instrumentos acordes al perfil {profile}."
        )
    if cash_pct < thr["min_cash_pct"]:
        recs.append(
            f"💡 Liquidez baja ({cash_pct:.0f}%). "
            f"Mantener al menos {thr['min_cash_pct']}% en cash o money market."
        )
    if hhi > thr["max_hhi"]:
        recs.append(
            f"⚠️ Concentración alta (HHI={hhi:.2f} > {thr['max_hhi']}). "
            f"Diversificar: agregar más instrumentos o reducir posiciones grandes."
        )
    if portfolio_risk > thr["max_risk_score"]:
        recs.append(
            f"⚠️ Riesgo agregado ({portfolio_risk:.1f}/10) supera el límite para perfil {profile} "
            f"({thr['max_risk_score']}/10). Revisar posiciones de mayor riesgo."
        )
    if ars_pct > 50 and profile == "conservador":
        recs.append(
            f"💡 Alta exposición en ARS ({ars_pct:.0f}%). "
            f"Perfil conservador se beneficia de cobertura en USD o instrumentos dólar-linked."
        )
    if not recs:
        recs.append("✅ La cartera está alineada con el perfil de riesgo. Sin observaciones críticas.")

    # Preparar holdings display
    display_cols = ["ticker","instrument_name","instrument_type","currency","country",
                    "asset_class","market_value_usd","weight","ytm","duration","risk_score"]
    display_cols = [c for c in display_cols if c in h.columns]
    h_display = h[display_cols].copy()
    h_display["market_value_usd"] = h_display["market_value_usd"].round(0)
    h_display["weight"] = (h_display["weight"] * 100).round(1)
    h_display["ytm"]    = h_display["ytm"].round(2)
    h_display["duration"] = h_display["duration"].round(2)
    h_display["risk_score"] = h_display["risk_score"].round(1)
    h_display = h_display.sort_values("weight", ascending=False).reset_index(drop=True)

    return PortfolioSummary(
        client_id=client_id,
        client_name=client["client_name"],
        risk_profile=profile,
        base_currency=client["base_currency"],
        total_value_usd=round(total, 0),
        holdings=h_display,
        expected_return=round(expected_return, 2),
        portfolio_duration=round(portfolio_duration, 2),
        portfolio_risk_score=round(portfolio_risk, 2),
        hhi=round(hhi, 4),
        exposure_by_asset_class=exp_ac,
        exposure_by_currency=exp_cur,
        exposure_by_country=exp_cty,
        recommendations=recs,
    )
