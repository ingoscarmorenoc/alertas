"""Selección de acciones de dividendos para largo plazo (horizonte mínimo de 5 años)."""
import time

import numpy as np
import pandas as pd
import yfinance as yf


def _num(x):
    try:
        x = float(x)
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def evaluar(t):
    tk = yf.Ticker(t)
    hist = tk.history(period="5y", auto_adjust=False)
    divs = tk.dividends
    if hist.empty or divs.empty:
        return None
    if divs.index.tz is not None:
        divs.index = divs.index.tz_convert(None)
    precio = float(hist["Close"].iloc[-1])
    hoy = pd.Timestamp.today()
    rendimiento = divs[divs.index > hoy - pd.DateOffset(years=1)].sum() / precio
    anual = divs.groupby(divs.index.year).sum()
    anual = anual[anual.index < hoy.year].tail(6)          # años completos
    cagr_div = ((anual.iloc[-1] / anual.iloc[0]) ** (1 / (len(anual) - 1)) - 1
                if len(anual) >= 5 and anual.iloc[0] > 0 else None)
    recortes = int((anual.pct_change() < -0.05).sum())
    cagr_precio = (hist["Close"].iloc[-1] / hist["Close"].iloc[0]) ** (1 / 5) - 1
    try:
        info = tk.info or {}
    except Exception:
        info = {}
    payout = _num(info.get("payoutRatio"))
    roe = _num(info.get("returnOnEquity"))
    deuda = _num(info.get("debtToEquity"))

    # Puntaje 0-100
    p = min(rendimiento, 0.07) / 0.07 * 25
    if rendimiento > 0.10:
        p -= 10                                            # posible "trampa de rendimiento"
    p += (np.clip(cagr_div, 0, 0.10) / 0.10 * 20) if cagr_div is not None else 0
    p += {0: 15, 1: 7}.get(recortes, 0)
    p += 5 if payout is None else (15 if 0.2 <= payout <= 0.7 else 7 if 0.7 < payout <= 0.9 else 0)
    p += (np.clip(roe, 0, 0.25) / 0.25 * 10) if roe is not None else 5
    p += 5 if deuda is None else (10 if deuda < 100 else 5 if deuda < 200 else 0)
    p += np.clip(cagr_precio, 0, 0.12) / 0.12 * 5
    return {
        "ticker": t, "nombre": info.get("shortName", t), "precio": precio,
        "rendimiento": float(rendimiento), "crec_div_5a": cagr_div, "recortes_5a": recortes,
        "payout": payout, "roe": roe, "deuda_patrimonio": deuda,
        "crec_precio_5a": float(cagr_precio), "puntaje": float(p),
    }


def analizar_dividendos(tickers):
    filas = []
    for t in tickers:
        try:
            fila = evaluar(t)
            if fila and fila["rendimiento"] > 0:
                filas.append(fila)
        except Exception as e:
            print(f"[aviso] Dividendos {t}: {e}")
        time.sleep(0.4)  # evita bloqueos por exceso de consultas
    df = pd.DataFrame(filas)
    return df.sort_values("puntaje", ascending=False) if not df.empty else df
