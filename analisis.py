"""Indicadores técnicos, señales de mediano plazo y backtesting sobre 3 años."""
import numpy as np
import pandas as pd
import yfinance as yf

import config as cfg


def mercado_de(ticker):
    return "CO" if ticker.upper().endswith(".CL") else "US"


def _extraer(datos, t):
    if isinstance(datos.columns, pd.MultiIndex):
        if t not in datos.columns.get_level_values(0):
            return None
        return datos[t]
    return datos


def descargar(tickers, periodo="4y"):
    """4 años: 3 de backtest + margen para la media de 200 días."""
    if not tickers:
        return {}
    datos = yf.download(tickers, period=periodo, interval="1d", group_by="ticker",
                        auto_adjust=True, progress=False, threads=True)
    resultado = {}
    for t in tickers:
        try:
            df = _extraer(datos, t)
            if df is None:
                continue
            df = df.dropna(subset=["Close"])
            if not df.empty:
                resultado[t] = df.copy()
        except Exception as e:
            print(f"[aviso] {t}: {e}")
    faltantes = set(tickers) - set(resultado)
    if faltantes:
        print(f"[aviso] Sin datos para: {', '.join(sorted(faltantes))}")
    return resultado


def precios_actuales(tickers):
    """Último precio disponible (las fuentes gratuitas pueden tener ~15 min de retraso)."""
    precios = {}
    try:
        datos = yf.download(tickers, period="5d", interval="5m", group_by="ticker",
                            auto_adjust=False, progress=False, threads=True)
    except Exception:
        datos = pd.DataFrame()
    for t in tickers:
        try:
            s = _extraer(datos, t)["Close"].dropna()
            if not s.empty:
                precios[t] = float(s.iloc[-1])
                continue
        except Exception:
            pass
        try:
            precios[t] = float(yf.Ticker(t).fast_info["last_price"])
        except Exception:
            print(f"[aviso] Sin precio actual para {t}")
    return precios


def indicadores(df):
    df = df.copy()
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    df["SMA20"] = c.rolling(20).mean()
    df["SMA50"] = c.rolling(50).mean()
    df["SMA200"] = c.rolling(200).mean()
    delta = c.diff()
    ganancia = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    perdida = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["RSI"] = 100 - 100 / (1 + ganancia / perdida.replace(0, np.nan))
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["MACD_H"] = macd - macd.ewm(span=9, adjust=False).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["ATR_PCT"] = tr.rolling(14).mean() / c
    df["LIQ"] = (c * v).rolling(20).mean()
    return df


def condicion_entrada(df, mercado):
    cond = ((df["Close"] > df["SMA50"]) & (df["SMA50"] > df["SMA200"])
            & df["RSI"].between(cfg.RSI_MIN, cfg.RSI_MAX)
            & (df["MACD_H"] > df["MACD_H"].shift(1))
            & (df["ATR_PCT"] >= cfg.ATR_MIN)
            & (df["LIQ"] >= cfg.LIQUIDEZ_MIN[mercado]))
    return cond.fillna(False)


def multiplicadores(mercado):
    c = cfg.COMISION[mercado]
    objetivo = (1 + cfg.OBJETIVO_NETO) * (1 + c) / (1 - c)   # precio que deja 2 % neto
    return objetivo, 1 - cfg.STOP_LOSS


def niveles(precio, ticker):
    mo, ms = multiplicadores(mercado_de(ticker))
    return precio * mo, precio * ms


def retorno_neto(entrada, salida, mercado):
    c = cfg.COMISION[mercado]
    return salida * (1 - c) / (entrada * (1 + c)) - 1


def backtest(df, mercado):
    """Simula cada señal: compra en la apertura siguiente; sale en objetivo, stop o por tiempo.
    Si en un mismo día se tocan stop y objetivo, se asume el stop (criterio conservador)."""
    mo, ms = multiplicadores(mercado)
    senal = condicion_entrada(df, mercado).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    inicio = df.index[-1] - pd.DateOffset(years=cfg.ANOS_BACKTEST)
    i, n, ops = max(200, int(np.searchsorted(df.index, inicio))), len(df), []
    while i < n - 1:
        if not senal[i]:
            i += 1
            continue
        entrada = o[i + 1]
        if not np.isfinite(entrada) or entrada <= 0:
            i += 1
            continue
        obj, stop = entrada * mo, entrada * ms
        fin, salida, motivo, j = i + 1 + cfg.MAX_DIAS_OPERACION, None, None, i + 1
        for j in range(i + 1, min(fin, n)):
            if l[j] <= stop:
                salida, motivo = min(o[j], stop), "stop"
                break
            if h[j] >= obj:
                salida, motivo = obj, "objetivo"
                break
        if salida is None:
            if fin > n:
                break  # operación todavía abierta: no se cuenta
            j = fin - 1
            salida, motivo = c[j], "tiempo"
        ops.append({"motivo": motivo, "retorno": retorno_neto(entrada, salida, mercado), "dias": j - i})
        i = j + 1
    if not ops:
        return {"operaciones": 0, "acierto": 0.0, "ret_medio": 0.0, "ret_total": 0.0, "dias_medio": 0.0}
    r = np.array([x["retorno"] for x in ops])
    return {
        "operaciones": len(ops),
        "acierto": float(np.mean([x["motivo"] == "objetivo" for x in ops])),
        "ret_medio": float(r.mean()),
        "ret_total": float(np.prod(1 + r) - 1),
        "dias_medio": float(np.mean([x["dias"] for x in ops])),
    }


def estadisticas_3a(df):
    c = df["Close"]
    c3 = c[c.index >= c.index[-1] - pd.DateOffset(years=3)]
    ret = c3.iloc[-1] / c3.iloc[0] - 1
    vol = c3.pct_change().std() * np.sqrt(252)
    dd = (c3 / c3.cummax() - 1).min()
    return float(ret), float(vol), float(dd)


def analizar_df(t, df):
    m = mercado_de(t)
    df = indicadores(df)
    bt = backtest(df, m)
    ult = df.iloc[-1]
    obj, stop = niveles(float(ult["Close"]), t)
    ret3, vol3, dd3 = estadisticas_3a(df)
    fila = {
        "ticker": t, "precio": float(ult["Close"]), "rsi": float(ult["RSI"]),
        "senal_hoy": bool(condicion_entrada(df, m).iloc[-1]),
        "tendencia": bool(ult["Close"] > ult["SMA50"] > ult["SMA200"]),
        "objetivo": obj, "stop": stop,
        "ret_3a": ret3, "vol_anual": vol3, "max_caida_3a": dd3, **bt,
    }
    fila["puntaje"] = fila["acierto"] * 100 + fila["ret_medio"] * 1000
    return fila, df


def analizar_universo(tickers):
    filas = []
    for t, df in descargar(tickers).items():
        if len(df) < 260:
            continue
        try:
            filas.append(analizar_df(t, df)[0])
        except Exception as e:
            print(f"[aviso] Error analizando {t}: {e}")
    return pd.DataFrame(filas)


def seleccionar_top(res, n):
    """Devuelve (compras con señal activa, acciones en vigilancia para completar el top)."""
    if res.empty:
        return res, res
    valido = ((res["operaciones"] >= cfg.MIN_OPERACIONES) & (res["ret_medio"] > 0)
              & (res["acierto"] >= cfg.ACIERTO_MIN))
    compra = res[valido & res["senal_hoy"]].sort_values("puntaje", ascending=False).head(n)
    vigilancia = (res[valido & res["tendencia"] & ~res["senal_hoy"]]
                  .sort_values("puntaje", ascending=False).head(n - len(compra)))
    return compra, vigilancia
