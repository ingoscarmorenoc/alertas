"""Parámetros de la estrategia. Ajuste aquí sin tocar el resto del código."""
import os

# ---------------- Universos de análisis ----------------
# Mediano plazo – EE. UU. (acciones líquidas de gran capitalización)
UNIVERSO_US = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "JPM", "V",
    "MA", "UNH", "XOM", "JNJ", "PG", "HD", "COST", "ABBV", "MRK", "LLY",
    "PEP", "KO", "BAC", "WMT", "CVX", "ADBE", "CRM", "AMD", "NFLX", "ORCL",
    "CSCO", "INTC", "QCOM", "TXN", "AMAT", "MU", "IBM", "CAT", "DE", "GE",
    "HON", "UPS", "LMT", "RTX", "BA", "GS", "MS", "C", "WFC", "AXP",
    "SBUX", "MCD", "NKE", "DIS", "T", "VZ", "PFE", "TMO", "ABT", "DHR",
    "MDT", "LOW", "TGT", "PLTR", "UBER",
]

# Mediano plazo – Colombia (sufijo .CL = Bolsa de Valores de Colombia en Yahoo Finance)
# Se incluyen los ADR colombianos que cotizan en NYSE (EC, CIB, AVAL), más líquidos.
UNIVERSO_CO = [
    "ECOPETROL.CL", "BCOLOMBIA.CL", "PFBCOLOM.CL", "ISA.CL", "GEB.CL", "CELSIA.CL",
    "GRUPOSURA.CL", "PFGRUPSURA.CL", "GRUPOARGOS.CL", "PFGRUPOARG.CL",
    "CEMARGOS.CL", "PFCEMARGOS.CL", "GRUPOAVAL.CL", "PFAVAL.CL", "CORFICOLCF.CL",
    "PFCORFICOL.CL", "PFDAVVNDA.CL", "BOGOTA.CL", "MINEROS.CL", "PROMIGAS.CL",
    "TERPEL.CL", "CNEC.CL", "BVC.CL",
    "EC", "CIB", "AVAL",
]

# Largo plazo – candidatas de dividendos
DIVIDENDOS_US = [
    "JNJ", "PG", "KO", "PEP", "ABBV", "MCD", "ADP", "ITW", "LOW", "TGT",
    "CL", "KMB", "XOM", "CVX", "O", "ED", "NEE", "WMT", "HD", "MSFT",
    "TXN", "AVGO", "CAT", "CB", "AFL", "SYY", "GPC", "EMR", "VZ", "PFE",
    "MDT", "ABT", "LMT", "UPS", "JPM", "PM",
]
DIVIDENDOS_CO = UNIVERSO_CO

# ---------------- Estrategia de mediano plazo ----------------
OBJETIVO_NETO = 0.02        # 2 % de ganancia neta por operación (ya descontadas comisiones)
STOP_LOSS = 0.015           # pérdida máxima tolerada por operación (precio)
MAX_DIAS_OPERACION = 15     # días hábiles máximos que se mantiene una operación
ANOS_BACKTEST = 3           # historial evaluado

# Comisión por operación (compra y venta, como fracción). Ajústela según su comisionista.
COMISION = {
    "US": float(os.getenv("COMISION_US") or 0.0),
    "CO": float(os.getenv("COMISION_CO") or 0.006),
}

# Filtros de la señal técnica
RSI_MIN, RSI_MAX = 35, 58   # retroceso dentro de tendencia alcista, sin sobrecompra
ATR_MIN = 0.012             # volatilidad diaria mínima para que el 2 % sea alcanzable
LIQUIDEZ_MIN = {"US": 20_000_000, "CO": 300_000_000}  # monto diario negociado (USD / COP)

# Calidad mínima exigida en el backtest
MIN_OPERACIONES = 8         # operaciones históricas mínimas para confiar en la estadística
ACIERTO_MIN = 0.50          # % mínimo de operaciones que alcanzaron el +2 %

TOP_N = 10
ZONA_ENTRADA_SUP = 0.003    # alerta de compra si el precio está hasta 0,3 % sobre el cierre previo
ZONA_ENTRADA_INF = 0.03     # ... y no más de 3 % por debajo (caída fuerte = señal invalidada)

# Largo plazo: día en que se envía el ranking de dividendos (0 = lunes)
DIA_DIVIDENDOS = 0
