"""Seguimiento de operaciones: las que genera el sistema (simuladas) y las reales del usuario."""
import json
from pathlib import Path

import pandas as pd

import config as cfg
from estrategia import mercado_de, niveles, retorno_neto

BASE = Path(__file__).parent
ARCH_OPS = BASE / "datos" / "operaciones.json"
ARCH_POS = BASE / "posiciones.csv"


def cargar_ops():
    try:
        d = json.loads(ARCH_OPS.read_text(encoding="utf-8"))
        return {"abiertas": d.get("abiertas", []), "cerradas": d.get("cerradas", [])}
    except Exception:
        return {"abiertas": [], "cerradas": []}


def guardar_ops(ops):
    ARCH_OPS.parent.mkdir(exist_ok=True)
    ops["cerradas"] = ops["cerradas"][-300:]
    ARCH_OPS.write_text(json.dumps(ops, ensure_ascii=False, indent=2), encoding="utf-8")


def leer_posiciones():
    if not ARCH_POS.exists():
        return pd.DataFrame(columns=["ticker", "precio_compra", "cantidad", "fecha_compra"])
    df = pd.read_csv(ARCH_POS, comment="#").dropna(subset=["ticker", "precio_compra"])
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    return df


def abrir(ops, fila, ts, fecha):
    ops["abiertas"].append({"ticker": fila["ticker"], "entrada": fila["precio"], "ts_entrada": ts,
                            "fecha_entrada": fecha, "objetivo": fila["objetivo"], "stop": fila["stop"],
                            "confianza": fila["confianza"]})


def actualizar_simuladas(ops, analisis, fecha):
    """Cierra las operaciones simuladas que tocaron objetivo, stop, perdieron impulso o vencieron."""
    cierres, siguen = [], []
    for op in ops["abiertas"]:
        a = analisis.get(op["ticker"])
        if not a:
            siguen.append(op)
            continue
        df = a["df"]
        try:
            posteriores = df[df.index > pd.Timestamp(op["ts_entrada"])]
        except Exception:
            posteriores = df.iloc[0:0]
        motivo = salida = None
        for _, r in posteriores.iterrows():
            if r["Low"] <= op["stop"]:
                motivo, salida = "stop-loss", min(r["Open"], op["stop"])
                break
            if r["High"] >= op["objetivo"]:
                motivo, salida = "objetivo alcanzado", op["objetivo"]
                break
            if r["EMA9"] < r["EMA21"]:
                motivo, salida = "pérdida de impulso", r["Close"]
                break
        if motivo is None and len(posteriores) >= cfg.MAX_BARRAS:
            motivo, salida = "plazo máximo", a["fila"]["precio"]
        if motivo:
            cerrada = {**op, "salida": float(salida), "fecha_salida": fecha, "motivo": motivo,
                       "retorno": retorno_neto(op["entrada"], float(salida), mercado_de(op["ticker"]))}
            ops["cerradas"].append(cerrada)
            cierres.append(cerrada)
        else:
            siguen.append(op)
    ops["abiertas"] = siguen
    return cierres


def revisar_reales(analisis):
    filas = []
    for _, r in leer_posiciones().iterrows():
        t, compra = r["ticker"], float(r["precio_compra"])
        a = analisis.get(t)
        precio = a["fila"]["precio"] if a else None
        obj, stop = niveles(compra, t)
        if precio is None:
            estado = "Sin precio"
        elif precio >= obj:
            estado = "Vender: objetivo alcanzado"
        elif precio <= stop:
            estado = "Vender: stop-loss"
        elif a["fila"]["estado"] == "Bajista":
            estado = "Vender: pérdida de impulso"
        else:
            estado = "Mantener"
        filas.append({"ticker": t, "entrada": compra, "actual": precio, "objetivo": obj, "stop": stop,
                      "retorno": retorno_neto(compra, precio, mercado_de(t)) if precio else None,
                      "estado": estado, "tipo": "Real"})
    return filas


def resumen(ops):
    c = ops["cerradas"]
    if not c:
        return {"operaciones": 0, "acierto": None, "ganadoras": None, "ret_total": None}
    r = [x["retorno"] for x in c]
    total = 1.0
    for x in r:
        total *= 1 + x
    return {"operaciones": len(c),
            "acierto": sum(x["motivo"] == "objetivo alcanzado" for x in c) / len(c),
            "ganadoras": sum(x > 0 for x in r) / len(c), "ret_total": total - 1}
