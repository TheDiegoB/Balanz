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
               "IBIT","ARKK","VTI","IVV","AGG","TLT","HYG","LQD","GDX"}

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

    line_pattern = re.compile(
        r'^([A-Z][A-Z0-9]+(?:[A-Za-z0-9]*)?)\s+'
        r'(.+?)\s+'
        r'([\d.,]+)\s+'       # cantidad
        r'0\.00\s+'           # garantia
        r'\$\s*([\d.,]+)\s+'  # precio
        r'\$\s*([\d.,]+)\s*$' # valor actual
    )

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

                # ── CLAVE: fondos con precio en USD ──────────────────────────
                # El segundo bloque de Fondos en el PDF (fondos_count >= 2)
                # o tickers conocidos como USD — precio está en USD
                is_usd_fund = (fondos_count >= 2) or (ticker in FONDOS_USD_PRECIO)

                if is_usd_fund:
                    # precio_raw está en USD, cantidad es cuotapartes
                    # valor_raw es el valor en ARS que ya calculó Balanz (qty * precio * TC)
                    # Pero lo más preciso es: qty * precio_usd = valor en USD
                    valor_usd = (cantidad or 0) * (precio_raw or 0)
                    if valor_usd > 0:
                        mv_override = round(valor_usd, 2)
                        cur = "USD"
                    else:
                        # fallback: usar valor ARS del PDF
                        mv_override = valor_raw
                        cur = "ARS"
                else:
                    mv_override = valor_raw
                    cur = "ARS"

            elif itype == "bono" and ticker in BONO_USD:
                # bonos soberanos USD: valor_raw está en ARS, convertir a USD
                mv_override = round(valor_raw / tc_mep, 0)
                cur = "USD"
                if ticker in BONO_DATA:
                    ytm, dur = BONO_DATA[ticker]
            else:
                # acciones, CEDEARs: valor en ARS directamente
                mv_override = valor_raw
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
            })

    m_usd = re.search(r'Dólares\s+USD\s+([\d.,]+)', full_text)
    if m_usd:
        val = _parse_num(m_usd.group(1))
        if val and val > 1:
            rows.append({
                "client_id": client_id, "ticker": "CASH_USD",
                "instrument_name": "USD MEP disponibles", "instrument_type": "cash",
                "quantity": "", "price_override": "", "market_value_override": round(val, 2),
                "currency": "USD", "country": "Global", "asset_class": "Cash",
                "ytm_override": 5.0, "duration_override": 0, "risk_score_override": "",
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
    if p.exists():
        existing = pd.read_csv(p, dtype=str)
        client_id = new_df["client_id"].iloc[0]
        existing  = existing[existing["client_id"] != client_id]
        combined  = pd.concat([existing, new_df.astype(str)], ignore_index=True)
    else:
        combined = new_df.astype(str)
    return combined
