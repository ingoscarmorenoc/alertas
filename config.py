"""Parámetros del sistema. Ajuste aquí sin tocar el resto del código."""
import os

# ---------------- Acciones vigiladas ----------------
LISTA_CO = ["ECOPETROL.CL", "GEB.CL", "PFCIBEST.CL", "PFGRUPSURA.CL",
            "PROMIGAS.CL", "ISA.CL", "EXITO.CL"]
LISTA_US = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "AMD", "TSLA",
            "ORCL", "CRM", "ADBE", "NFLX", "PLTR", "INTC", "QCOM", "MU", "CSCO"]

NOMBRES = {
    "ECOPETROL.CL": "Ecopetrol", "GEB.CL": "Grupo Energía Bogotá", "PFCIBEST.CL": "Grupo Cibest (pref.)",
    "PFGRUPSURA.CL": "Grupo Sura (pref.)", "PROMIGAS.CL": "Promigas", "ISA.CL": "ISA", "EXITO.CL": "Grupo Éxito",
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "GOOGL": "Alphabet", "AMZN": "Amazon",
    "META": "Meta", "AVGO": "Broadcom", "AMD": "AMD", "TSLA": "Tesla", "ORCL": "Oracle",
    "CRM": "Salesforce", "ADBE": "Adobe", "NFLX": "Netflix", "PLTR": "Palantir", "INTC": "Intel",
    "QCOM": "Qualcomm", "MU": "Micron", "CSCO": "Cisco",
}

# Dividendos (largo plazo)
DIVIDENDOS_US = ["JNJ", "PG", "KO", "PEP", "ABBV", "MCD", "ADP", "ITW", "LOW", "CL", "KMB",
                 "XOM", "CVX", "O", "ED", "NEE", "WMT", "HD", "MSFT", "TXN", "AVGO", "CAT",
                 "CB", "AFL", "SYY", "EMR", "VZ", "PFE", "ABT", "LMT", "JPM", "PM"]
DIVIDENDOS_CO = LISTA_CO

# ---------------- Estrategia de corto plazo (velas de 1 hora) ----------------
OBJETIVO_NETO = 0.02      # ganancia neta buscada por operación (descontadas comisiones)
STOP_LOSS = 0.01          # pérdida máxima tolerada (precio)
MAX_BARRAS = 21           # horas de mercado máximas por operación (~3 días)
EMA_RAPIDA, EMA_LENTA, EMA_TENDENCIA, EMA_FONDO = 9, 21, 50, 200
RSI_MIN, RSI_MAX = 45, 70

COMISION = {
    "US": float(os.getenv("COMISION_US") or 0.0),
    "CO": float(os.getenv("COMISION_CO") or 0.006),
}

# Confianza según el backtest de 2 años en velas horarias
MIN_OPERACIONES = 10
ACIERTO_ALTA = 0.50

# ---------------- Horarios (hora Colombia) ----------------
HORA_REPORTE = 10         # reporte completo + panel
DIA_DIVIDENDOS = 0        # 0 = lunes
