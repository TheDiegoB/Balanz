"""
Portfolio Lab — Parser de PDFs de Balanz v2
Lee el Resumen de Cuenta y extrae posiciones automáticamente.
"""
from __future__ import annotations
import re
import io
from typing import Optional
import pandas as pd

SECTION_MAP = {
    "Acciones":   ("equity",  "Equity",       "ARS", "AR"),
    "Bonos":      ("bono",    "RF",            "ARS", "AR"),
    "Cedears":    ("equity",  "Equity",        "ARS", "US"),
    "Fondos":     ("fondo",   "RF",            "ARS", "AR"),
    "On":         ("on",      "RF",            "USD", "AR"),
    "Obligaciones Negociables": ("on", "RF",   "USD", "AR"),
}

ETF_TICKERS = {"GLD","IAU","SPY","QQQ","EEM","EWZ","EWJ","XLE","XLK","XLF",
               "XLV","XLU","XLI","XLP","XLB","IBIT","ARKK","VTI","IVV",
               "AGG","TLT","HYG","LQD","GDX","PDBC"}

BONO_USD = {"AE38","AL30","AL35","AL41","GD29","GD30","GD35","GD38","GD41","GD46",
            "GD30C","CUAP","BPY26","BPYD7","BPYC6","BPYF5"}

# Fondos cuyo precio de cuotaparte está en USD (no en ARS)
FONDOS_USD_PRECIO = {
    "ESTRA1A", "ESTRA2A", "ESTRA3A", "ESTRA4A",
    "BCRDolarA", "BAHUSDA", "BINCOME", "BCRDolarC",
    "BAHUSDC", "BAHUSDP",
}

FONDO_CONFIG = {
    "BCACCA":    ("Equity",       None,  None),
    "BCMMA":     ("Cash",         55.0,  0.1),
    "BCAHA":     ("Cash",          5.0,  0.2),   # Ahorro corto plazo
    "BCRFA":     ("RF",           55.0,  0.5),   # Dolar Linked ARS
    "INSTITUA":  ("RF",           55.0,  1.0),   # Inflation linked
    "BINFRAA":   ("Alternatives", None,  None),
    "LONGPesosA":("RF",           55.0,  0.5),
    "PER2A":     ("RF",           60.0,  0.3),
    "PER3A":     ("RF",            7.5,  1.5),
    "ESTRA1A":   ("Cash",          5.0,  0.1),
    "ESTRA2A":   ("Cash",          5.0,  0.1),
    "ESTRA3A":   ("Alternatives", None,  None),
    "BCRDolarA": ("RF",            8.0,  3.0),
    "BAHUSDA":   ("RF",            7.5,  1.5),
    "BINCOME":   ("RF",            6.0,  3.0),
    "BMMA":      ("Cash",         55.0,  0.1),
}

BONO_DATA = {
    "AE38": (9.2,  8.5), "AL30": (8.5,  3.2), "AL35": (9.0,  5.5),
    "AL41": (9.5, 11.0), "GD29": (8.0,  2.5), "GD30": (7.8,  3.5),
    "GD35": (9.8,  6.1), "GD38": (9.2,  8.5), "GD41": (9.5, 10.0),
    "GD46": (9.8, 12.0), "CUAP": (7.0,  5.0), "BPY26":(7.0,  0.5),
}


def _parse_num(s: str) -> Optional[float]:
    if not s:
        return None
    s = re.sub(r'[^\d.,]', '', s.strip())
    if not s:
        return None
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace('.', '')
    try:
        return float(s)
    except Exception:
        return None


def parse_balanz_pdf(file_bytes: bytes) -> dict:
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber no instalado. Agregalo a requirements.txt")

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages_text = [p.extract_text() or "" for p in pdf.pages]

    full_text = "\n".join(pages_text)

    # ── Metadata ──────────────────────────────────────────────────────────────
    client_name = ""
    comitente   = ""
    tc_mep      = 1432.65

    m = re.search(r'Cuenta\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+?)\s+Fecha resumen', full_text)
    if m:
        client_name = m.group(1).strip().title()

    m = re.search(r'N°\s*Comitente\s+(\d+)', full_text)
    if m:
        comitente = m.group(1).strip()

    m = re.search(r'MEP\s*\$\s*([\d.,]+)', full_text)
    if m:
        tc_mep = _parse_num(m.group(1)) or tc_mep

    client_id = f"CLI_{comitente}" if comitente else "CLI_NUEVO"

    # ── Parsear posiciones ────────────────────────────────────────────────────
    rows = []
    current_section = None
    # Rastrea si ya entramos en el segundo bloque de Fondos (los USD)
    fondos_count = 0

    # ── Detectar formato del PDF ──────────────────────────────────────────────
    # Formato ARS: precios con "$ 10.750,00"
    # Formato USD: precios con "u$s 9,82" — toda la cartera en USD
    is_usd_pdf = bool(re.search(r'u\$s\s+[\d.,]+', full_text))
    total_usd_direct = None
    if is_usd_pdf:
        m = re.search(r'Total\s+USD\s+([\d.,]+)', full_text)
        if m:
            total_usd_direct = _parse_num(m.group(1))

    # ── Patrones de línea para cada formato ──────────────────────────────────
    # ARS: TICKER Descripción qty 0.00 $ precio $ valor
    line_pattern_ars = re.compile(
        r'^([A-Z][A-Z0-9]+(?:[A-Za-z0-9]*)?)\s+'
        r'(.+?)\s+'
        r'([\d.,]+)\s+'
        r'0\.00\s+'
        r'\$\s*([\d.,]+)\s+'
        r'\$\s*([\d.,]+)\s*$'
    )
    # USD: TICKER Descripción qty 0.00 u$s precio u$s valor
    line_pattern_usd = re.compile(
        r'^([A-Z][A-Z0-9]+(?:[A-Za-z0-9]*)?)\s+'
        r'(.+?)\s+'
        r'([\d.,]+)\s+'
        r'0\.00\s+'
        r'u\$s\s+([\d.,]+)\s+'
        r'u\$s\s+([\d.,]+)\s*$'
    )
    line_pattern = line_pattern_usd if is_usd_pdf else line_pattern_ars

    for text in pages_text:
        for line in text.split('\n'):
            line = line.strip()

            # Detectar sección — contar cuantas veces aparece "Fondos"
            for sec in SECTION_MAP:
                if re.match(rf'^{sec}\s*$', line, re.IGNORECASE):
                    if sec == "Fondos":
                        fondos_count += 1
                    current_section = sec
                    break

            if not current_section:
                continue

            m = line_pattern.match(line)
            if not m:
                continue

            ticker     = m.group(1).strip()
            nombre     = m.group(2).strip()
            nombre     = re.sub(r'^CEDEAR\s+', '', nombre)
            nombre     = re.sub(r'^BONO\s+REP\.\s+ARGENTINA\s+', 'Bono Arg. ', nombre)
            nombre     = re.sub(r'^BONOS\s+REP\.\s+ARG\.\s+', 'Bono Arg. ', nombre)

            cantidad   = _parse_num(m.group(3))
            precio_raw = _parse_num(m.group(4))
            valor_raw  = _parse_num(m.group(5))

            if not valor_raw or valor_raw <= 0:
                continue

            itype, ac, cur, country = SECTION_MAP.get(current_section, ("equity","Equity","ARS","AR"))

            if ticker in ETF_TICKERS:
                itype = "etf"
            if ticker in BONO_USD:
                cur = "USD"; itype = "bono"; ac = "RF"; country = "AR"

            ytm = dur = None
            if itype == "fondo":
                ac_f, ytm_f, dur_f = FONDO_CONFIG.get(ticker, ("RF", None, None))
                ac  = ac_f
                ytm = ytm_f
                dur = dur_f

                if is_usd_pdf:
                    # Todo el PDF está en USD — valor_raw ya es USD directo
                    mv_override = valor_raw
                    cur = "USD"
                else:
                    # PDF ARS — segundo bloque de fondos o tickers conocidos USD
                    is_usd_fund = (fondos_count >= 2) or (ticker in FONDOS_USD_PRECIO)
                    if is_usd_fund:
                        valor_usd = (cantidad or 0) * (precio_raw or 0)
                        mv_override = round(valor_usd, 2) if valor_usd > 0 else valor_raw
                        cur = "USD"
                    else:
                        mv_override = valor_raw
                        cur = "ARS"

            elif itype == "bono" and ticker in BONO_USD:
                if is_usd_pdf:
                    mv_override = valor_raw  # ya en USD
                else:
                    mv_override = round(valor_raw / tc_mep, 0)  # convertir de ARS a USD
                cur = "USD"
                if ticker in BONO_DATA:
                    ytm, dur = BONO_DATA[ticker]

            else:
                # Acciones, CEDEARs, ETFs
                if is_usd_pdf:
                    mv_override = valor_raw  # ya en USD
                    cur = "USD"
                else:
                    mv_override = valor_raw  # en ARS
                    cur = "ARS"

            if itype == "bono" and ticker in BONO_DATA:
                ytm, dur = BONO_DATA[ticker]

            rows.append({
                "client_id":             client_id,
                "ticker":                ticker,
                "instrument_name":       nombre,
                "instrument_type":       itype,
                "quantity":              "",
                "price_override":        "",
                "market_value_override": mv_override,
                "currency":              cur,
                "country":               country,
                "asset_class":           ac,
                "ytm_override":          ytm if ytm else "",
                "duration_override":     dur if dur else "",
                "risk_score_override":   "",
                "tc_mep":                tc_mep,
            })

    # ── Cash ──────────────────────────────────────────────────────────────────
    m_pesos = re.search(r'Pesos\s*\$\s*([\d.,]+)', full_text)
    if m_pesos:
        val = _parse_num(m_pesos.group(1))
        if val and val > 100:
            rows.append({
                "client_id": client_id, "ticker": "CASH_ARS",
                "instrument_name": "Pesos disponibles", "instrument_type": "cash",
                "quantity": "", "price_override": "", "market_value_override": val,
                "currency": "ARS", "country": "AR", "asset_class": "Cash",
                "ytm_override": 55.0, "duration_override": 0, "risk_score_override": "",
                "tc_mep": tc_mep,
            })

    # Cash USD — formato ARS: "Dólares USD X,XX" / formato USD: "Dólares USD X,XX"
    m_usd = re.search(r'Dólares\s+USD\s+([\d.,]+)', full_text)
    if m_usd:
        val = _parse_num(m_usd.group(1))
        if val and val > 1:
            rows.append({
                "client_id": client_id, "ticker": "CASH_USD",
                "instrument_name": "USD disponibles", "instrument_type": "cash",
                "quantity": "", "price_override": "", "market_value_override": round(val, 2),
                "currency": "USD", "country": "Global", "asset_class": "Cash",
                "ytm_override": 5.0, "duration_override": 0, "risk_score_override": "",
                "tc_mep": tc_mep,
            })

    return {
        "client_id":   client_id,
        "client_name": client_name,
        "comitente":   comitente,
        "tc_mep":      tc_mep,
        "holdings":    pd.DataFrame(rows),
    }


def merge_into_holdings(new_df: pd.DataFrame, holdings_path) -> pd.DataFrame:
    from pathlib import Path
    p = Path(holdings_path)
    new_df = new_df.astype(str)
    if p.exists():
        try:
            existing  = pd.read_csv(p, dtype=str)
            client_id = new_df["client_id"].iloc[0]
            if "client_id" in existing.columns:
                existing = existing[existing["client_id"] != client_id]
            # Alinear columnas — agregar las que falten en existing
            for col in new_df.columns:
                if col not in existing.columns:
                    existing[col] = ""
            combined = pd.concat([existing, new_df], ignore_index=True)
        except Exception:
            # Si el CSV está corrupto o vacío, empezar de cero
            combined = new_df
    else:
        combined = new_df
    return combined
