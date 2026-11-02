"""Descarga de datos, indicadores, señales horarias y backtesting."""
import os

import numpy as np
import pandas as pd
import requests
import yfinance as yf

import config as cfg

ZONA = "America/Bogota"


def mercado_de(t):
    return "CO" if t.upper().endswith(".CL") else "US"


def _extraer(datos, t):
    if datos is None or datos.empty:
        return None
    if isinstance(datos.columns, pd.MultiIndex):
        return datos[t] if t in datos.columns.get_level_values(0) else None
    return datos


def descargar(tickers, periodo, intervalo):
    try:
        datos = yf.download(tickers, period=periodo, interval=intervalo, group_by="ticker",
                            auto_adjust=False, progress=False, threads=True)
    except Exception as e:
        print(f"[aviso] Descarga {intervalo}: {e}")
        return {}
    res = {}
    for t in tickers:
        df = _extraer(datos, t)
        if df is not None:
            df = df.dropna(subset=["Close"])
            if not df.empty:
                res[t] = df.copy()
    return res


def precio_finnhub(t):
    """Precio en tiempo real para EE. UU. si se configuró FINNHUB_KEY (opcional, gratuito)."""
    clave = os.getenv("FINNHUB_KEY")
    if not clave or mercado_de(t) != "US":
        return None
    try:
        r = requests.get("https://finnhub.io/api/v1/quote", params={"symbol": t, "token": clave}, timeout=10)
        c = r.json().get("c")
        return float(c) if c else None
    except Exception:
        return None


def indicadores(df):
    df = df.copy()
    c, h, l = df["Close"], df["High"], df["Low"]
    for n, col in ((cfg.EMA_RAPIDA, "EMA9"), (cfg.EMA_LENTA, "EMA21"),
                   (cfg.EMA_TENDENCIA, "EMA50"), (cfg.EMA_FONDO, "EMA200")):
        df[col] = c.ewm(span=n, adjust=False).mean()
    delta = c.diff()
    gan = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    per = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["RSI"] = 100 - 100 / (1 + gan / per.replace(0, np.nan))
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["MACD_H"] = macd - macd.ewm(span=9, adjust=False).mean()
    return df


def senal_compra(df):
    cruce = (df["EMA9"] > df["EMA21"]) & (df["EMA9"].shift(1) <= df["EMA21"].shift(1))
    rebote = (df["Low"] <= df["EMA21"]) & (df["Close"] > df["EMA21"]) & (df["EMA9"] > df["EMA21"])
    cond = ((cruce | rebote) & (df["Close"] > df["EMA50"]) & (df["Close"] > df["EMA200"])
            & df["RSI"].between(cfg.RSI_MIN, cfg.RSI_MAX) & (df["MACD_H"] > df["MACD_H"].shift(1)))
    return cond.fillna(False)


def multiplicadores(mercado):
    c = cfg.COMISION[mercado]
    return (1 + cfg.OBJETIVO_NETO) * (1 + c) / (1 - c), 1 - cfg.STOP_LOSS


def niveles(precio, t):
    mo, ms = multiplicadores(mercado_de(t))
    return precio * mo, precio * ms


def retorno_neto(entrada, salida, mercado):
    c = cfg.COMISION[mercado]
    return salida * (1 - c) / (entrada * (1 + c)) - 1


def backtest(df, mercado):
    """Compra en la apertura de la vela siguiente a la señal. Sale por objetivo, stop,
    pérdida de impulso (EMA9 < EMA21) o tiempo. Si una vela toca stop y objetivo, cuenta el stop."""
    mo, ms = multiplicadores(mercado)
    s = senal_compra(df).to_numpy()
    bajista = (df["EMA9"] < df["EMA21"]).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    i, n, ops = cfg.EMA_FONDO, len(df), []
    while i < n - 1:
        if not s[i] or not np.isfinite(o[i + 1]) or o[i + 1] <= 0:
            i += 1
            continue
        e = o[i + 1]
        obj, stop = e * mo, e * ms
        fin, salida, motivo, j = i + 1 + cfg.MAX_BARRAS, None, None, i + 1
        for j in range(i + 1, min(fin, n)):
            if l[j] <= stop:
                salida, motivo = min(o[j], stop), "stop"
                break
            if h[j] >= obj:
                salida, motivo = obj, "objetivo"
                break
            if bajista[j] and j > i + 1:
                salida, motivo = c[j], "salida técnica"
                break
        if salida is None:
            if fin > n:
                break
            j = fin - 1
            salida, motivo = c[j], "tiempo"
        ops.append((motivo, retorno_neto(e, salida, mercado), j - i))
        i = j + 1
    if not ops:
        return {"operaciones": 0, "acierto": 0.0, "ganadoras": 0.0, "ret_medio": 0.0,
                "ret_total": 0.0, "barras_medio": 0.0}
    r = np.array([x[1] for x in ops])
    return {"operaciones": len(ops),
            "acierto": float(np.mean([x[0] == "objetivo" for x in ops])),
            "ganadoras": float(np.mean(r > 0)),
            "ret_medio": float(r.mean()),
            "ret_total": float(np.prod(1 + r) - 1),
            "barras_medio": float(np.mean([x[2] for x in ops]))}


def confianza(bt):
    if bt["operaciones"] >= cfg.MIN_OPERACIONES and bt["acierto"] >= cfg.ACIERTO_ALTA and bt["ret_medio"] > 0:
        return "alta"
    if bt["operaciones"] >= 5 and bt["ret_medio"] > 0:
        return "media"
    return "baja"


def _hora_local(idx):
    try:
        return idx.tz_convert(ZONA) if idx.tz is not None else idx
    except Exception:
        return idx


def estadisticas_3a(diario):
    c = diario["Close"].dropna()
    c = c[c.index >= c.index[-1] - pd.DateOffset(years=3)]
    if len(c) < 20:
        return None, None, None
    return (float(c.iloc[-1] / c.iloc[0] - 1), float(c.pct_change().std() * np.sqrt(252)),
            float((c / c.cummax() - 1).min()))


def analizar(tickers):
    """Analiza cada acción con velas de 1 hora (2 años) y datos diarios (3 años)."""
    horario = descargar(tickers, "730d", "60m")
    diario = descargar(tickers, "3y", "1d")
    resultado = {}
    for t in tickers:
        dfd = diario.get(t)
        dfh = horario.get(t)
        base = "horario"
        if dfh is None or len(dfh) < 300:
            dfh, base = dfd, "diario"   # la BVC no siempre publica velas horarias en Yahoo
        if dfh is None or len(dfh) < cfg.EMA_FONDO + 20:
            print(f"[aviso] Sin datos suficientes para {t}")
            continue
        try:
            m = mercado_de(t)
            df = indicadores(dfh)
            bt = backtest(df, m)
            s = senal_compra(df)
            u = df.iloc[-1]
            precio = precio_finnhub(t) or float(u["Close"])
            previo = None
            if dfd is not None and len(dfd) >= 2:
                ult_dia = _hora_local(dfh.index)[-1].date()
                fechas = [x.date() for x in dfd.index]
                previo = float(dfd["Close"].iloc[-2] if fechas[-1] == ult_dia else dfd["Close"].iloc[-1])
            if bool(s.iloc[-2:].any()) and confianza(bt) != "baja":
                estado = "Comprar"   # solo si la estrategia ha funcionado en esta acción
            elif u["EMA9"] < u["EMA21"]:
                estado = "Bajista"
            elif u["Close"] > u["EMA50"]:
                estado = "Alcista"
            else:
                estado = "Neutral"
            obj, stop = niveles(precio, t)
            ret3, vol3, dd3 = estadisticas_3a(dfd) if dfd is not None else (None, None, None)
            ts = s[s].index[-1] if bool(s.iloc[-2:].any()) else None
            fila = {"ticker": t, "nombre": cfg.NOMBRES.get(t, t),
                    "grupo": "Colombia" if t in cfg.LISTA_CO else "EE. UU.",
                    "precio": precio, "var_dia": (precio / previo - 1) if previo else None,
                    "rsi": float(u["RSI"]), "estado": estado, "base": base,
                    "objetivo": obj, "stop": stop, "confianza": confianza(bt),
                    "ret_3a": ret3, "vol_anual": vol3, "max_caida_3a": dd3,
                    "senal_ts": str(ts) if ts is not None else None, **bt}
            fila["puntaje"] = fila["acierto"] * 100 + fila["ret_medio"] * 1000
            resultado[t] = {"fila": fila, "df": df, "diario": dfd}
        except Exception as e:
            print(f"[aviso] Error analizando {t}: {e}")
    return resultado
