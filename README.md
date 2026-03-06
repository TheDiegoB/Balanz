# 📊 Portfolio Lab — Balanz

Motor de analytics de carteras para asesores independientes.  
Calcula retorno esperado, duration, exposición, riesgo y genera recomendaciones automáticas por perfil.

---

## 🚀 Correr localmente (2 comandos)

```bash
# 1. Instalar dependencias (una sola vez)
pip install -r requirements.txt

# 2. Correr la app
streamlit run app.py
```

Abre automáticamente en `http://localhost:8501`

---

## ☁️ Subir a Streamlit Cloud (gratis, sin instalar nada)

1. Subí esta carpeta a un repo de GitHub
2. Entrá a [share.streamlit.io](https://share.streamlit.io)
3. Conectá tu repo → seleccioná `app.py` → Deploy
4. En 2 minutos tenés la app online, accesible desde cualquier dispositivo

---

## 📂 Estructura

```
portfolio-lab/
├── app.py                  # UI principal (Streamlit)
├── config.yaml             # Supuestos y umbrales (editar acá)
├── requirements.txt
├── data/
│   ├── clients.csv         # Registro de clientes
│   ├── holdings.csv        # Posiciones por cliente
│   └── instruments_master.csv  # Base de instrumentos con defaults
├── engine/
│   ├── analytics.py        # Motor de cálculo
│   └── report.py           # Generador HTML/PDF
└── reports/                # Reportes generados (se crea automáticamente)
```

---

## 📋 Cómo cargar datos

### Opción A — Desde la app (drag & drop)
En el sidebar de la app → "Cargar CSVs" → subís `holdings.csv` o `clients.csv` directamente.

### Opción B — Editar archivos CSV directamente
Editá los archivos en `data/` con Excel o cualquier editor de texto.

---

## 📄 Formato de CSVs

### clients.csv
```csv
client_id,client_name,risk_profile,base_currency
CLI001,García Roberto,conservador,USD
CLI002,Martínez Ana,moderado,USD
```
- `risk_profile`: `conservador` / `moderado` / `agresivo`
- `base_currency`: `USD` / `ARS`

### holdings.csv
```csv
client_id,ticker,instrument_name,instrument_type,quantity,price_override,market_value_override,currency,country,asset_class,ytm_override,duration_override,risk_score_override
CLI001,AL30,Bono AL30,bono,5000,,63500,USD,AR,RF,8.5,3.2,
CLI001,SPY,S&P 500 ETF,etf,50,,,USD,US,Equity,,,
CLI001,CASH_USD,Liquidez USD,cash,,,15000,USD,Global,Cash,5.0,0,
```

**Reglas de market value:**
- Si ponés `market_value_override` → se usa ese valor directamente
- Si ponés `quantity` + `price_override` → `market_value = quantity × price`
- Si ponés solo `quantity` → intenta bajar el precio de **yfinance** (funciona para SPY, GLD, AAPL, etc.)
- Para bonos argentinos → siempre conviene usar `market_value_override` (precio × nominal / 100)

**Campos opcionales:**
- `ytm_override` → si está, se usa en lugar del default del `instruments_master.csv`
- `duration_override` → idem
- `risk_score_override` → idem (escala 1-10)
- `price_override` → precio manual si no querés yfinance

### instruments_master.csv
Base de instrumentos con defaults. Si un ticker no está acá, usa los valores del `config.yaml`.

---

## ⚙️ Configuración (config.yaml)

Editá `config.yaml` para cambiar:
- **Retorno esperado** por asset class
- **Umbrales** por perfil (máx % Argentina, máx duration, etc.)
- **Risk scores** default por tipo de instrumento
- **Tipo de cambio fallback** (si no hay internet)
- **Branding** del reporte (nombre firma, disclaimer)

---

## 📊 Métricas calculadas

| Métrica | Descripción |
|---------|-------------|
| **Retorno esperado** | Yield ponderado: YTM para RF, expected return por asset class para equity |
| **Duration** | Macaulay aproximada, ponderada por valor de mercado, solo instrumentos RF |
| **Riesgo agregado** | Score 1-10 ponderado por peso. Configurable por instrumento |
| **HHI** | Índice Herfindahl-Hirschman: 0=muy diversificado, 1=todo en 1 activo |
| **Exposición** | % del portfolio por asset class, moneda y país |

---

## 🤖 Motor de recomendaciones

Las recomendaciones se generan automáticamente por reglas configurables en `config.yaml`:

| Condición | Recomendación |
|-----------|--------------|
| % Argentina > umbral | Aumentar diversificación global |
| % Equity > umbral para el perfil | Rotar a renta fija |
| Duration > máximo del perfil | Acortar duration |
| Cash > umbral | Invertir el exceso |
| Cash < mínimo | Aumentar liquidez |
| HHI > umbral | Diversificar posiciones |
| Risk score > máximo | Revisar posiciones de alto riesgo |

---

## 🔗 Integración con el Google Sheet

El Sheet de Balanz y Portfolio Lab son complementarios:

| Herramienta | Para qué |
|-------------|----------|
| **Google Sheet** | Gestión diaria, rotaciones, reporte rápido por cliente |
| **Portfolio Lab** | Analytics profundo, PDF de propuesta, recomendaciones automáticas |

**Flujo sugerido:**
1. Cargás posiciones en el Sheet
2. Exportás holdings como CSV
3. Lo subís al Portfolio Lab (sidebar → drag & drop)
4. Obtenés analytics y bajás el reporte HTML para enviar al cliente
