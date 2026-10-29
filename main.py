"""Punto de entrada.
   python main.py diario            -> top 10 EE. UU. y Colombia + estado de posiciones (+ dividendos los lunes)
   python main.py intradia          -> alertas de compra/venta durante la jornada
   python main.py ticker ECOPETROL.CL -> análisis individual de 3 años
   python main.py dividendos        -> ranking de dividendos a demanda
"""
import datetime as dt
import html
import json
import os
import sys
from pathlib import Path

import pandas as pd

import config as cfg
from analisis import (analizar_df, analizar_universo, descargar, indicadores, mercado_de,
                      niveles, precios_actuales, retorno_neto, seleccionar_top)
from dividendos import analizar_dividendos
from notificar import correo, telegram

BASE = Path(__file__).parent
DATOS, SALIDA = BASE / "datos", BASE / "salida"
ARCH_SENALES, ARCH_ENVIADAS = DATOS / "senales_hoy.json", DATOS / "alertas_enviadas.json"
ARCH_POS = BASE / "posiciones.csv"

AVISO = ("<i>Herramienta de apoyo basada en estadística histórica; no constituye asesoría "
         "financiera ni garantiza resultados. Verifique antes de operar.</i>")


# ---------------- utilidades ----------------
def hoy():
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).date()  # hora Colombia


def esc(x):
    return html.escape(str(x))


def fmt(x):
    return "—" if x is None or pd.isna(x) else f"{x:,.2f}"


def pct(x):
    return "—" if x is None or pd.isna(x) else f"{x * 100:.1f}%"


def leer_json(ruta, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(ruta, datos):
    DATOS.mkdir(exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def leer_posiciones():
    if not ARCH_POS.exists():
        return pd.DataFrame(columns=["ticker", "precio_compra", "cantidad", "fecha_compra"])
    df = pd.read_csv(ARCH_POS, comment="#").dropna(subset=["ticker", "precio_compra"])
    df["ticker"] = df["ticker"].str.strip().str.upper()
    return df


def tabla_html(df, columnas):
    if df is None or df.empty:
        return "<p>Sin resultados que cumplan los filtros.</p>"
    cab = "".join(f"<th style='background:#1f3a5f;color:#fff;padding:6px'>{t}</th>" for _, t, _ in columnas)
    filas = ""
    for k, (_, r) in enumerate(df.iterrows()):
        fondo = "#f4f7fb" if k % 2 else "#ffffff"
        celdas = "".join(f"<td style='padding:6px;border-bottom:1px solid #ddd'>{f(r[c])}</td>"
                         for c, _, f in columnas)
        filas += f"<tr style='background:{fondo}'>{celdas}</tr>"
    return (f"<table style='border-collapse:collapse;font-family:Arial;font-size:13px'>"
            f"<tr>{cab}</tr>{filas}</table>")


def envolver_html(titulo, cuerpo):
    return (f"<div style='font-family:Arial;color:#222;max-width:900px'>"
            f"<h2 style='color:#1f3a5f'>{titulo}</h2>{cuerpo}"
            f"<p style='font-size:11px;color:#777;margin-top:24px'>{AVISO}</p></div>")


COLS_TOP = [("ticker", "Acción", esc), ("precio", "Precio", fmt), ("rsi", "RSI", lambda x: f"{x:.0f}"),
            ("acierto", "Acierto 3a", pct), ("operaciones", "Op. 3a", lambda x: int(x)),
            ("ret_medio", "Ret. medio/op.", pct), ("dias_medio", "Días prom.", lambda x: f"{x:.1f}"),
            ("objetivo", "Vender en (+2% neto)", fmt), ("stop", "Stop-loss", fmt)]
COLS_DIV = [("ticker", "Acción", esc), ("nombre", "Empresa", esc), ("precio", "Precio", fmt),
            ("rendimiento", "Rend. dividendo", pct), ("crec_div_5a", "Crec. div. 5a", pct),
            ("recortes_5a", "Recortes", lambda x: int(x)), ("payout", "Payout", pct),
            ("roe", "ROE", pct), ("crec_precio_5a", "Crec. precio 5a", pct),
            ("puntaje", "Puntaje", lambda x: f"{x:.0f}")]


def lineas_top(df, titulo):
    if df.empty:
        return [f"<b>{titulo}</b>: sin señales que cumplan todos los filtros hoy."]
    out = [f"<b>{titulo}</b>"]
    for k, (_, r) in enumerate(df.iterrows(), 1):
        out.append(f"{k}. <b>{esc(r.ticker)}</b> {fmt(r.precio)} · acierto 3a {pct(r.acierto)} "
                   f"({int(r.operaciones)} op.) · vender {fmt(r.objetivo)} · stop {fmt(r.stop)}")
    return out


def lineas_div(df, titulo):
    if df is None or df.empty:
        return [f"<b>{titulo}</b>: sin datos."]
    out = [f"<b>{titulo}</b>"]
    for k, (_, r) in enumerate(df.head(cfg.TOP_N).iterrows(), 1):
        out.append(f"{k}. <b>{esc(r.ticker)}</b> · rend. {pct(r.rendimiento)} · crec. div 5a "
                   f"{pct(r.crec_div_5a)} · payout {pct(r.payout)} · puntaje {r.puntaje:.0f}")
    return out


# ---------------- posiciones ----------------
def revisar_posiciones(precios):
    pos = leer_posiciones()
    filas = []
    for _, r in pos.iterrows():
        t, compra = r["ticker"], float(r["precio_compra"])
        p = precios.get(t)
        obj, stop = niveles(compra, t)
        dias = None
        try:
            dias = (pd.Timestamp(hoy()) - pd.Timestamp(r["fecha_compra"])).days
        except Exception:
            pass
        if p is None:
            estado = "Sin precio"
        elif p >= obj:
            estado = "VENDER: objetivo alcanzado"
        elif p <= stop:
            estado = "VENDER: stop-loss"
        elif dias is not None and dias > cfg.MAX_DIAS_OPERACION * 1.4:
            estado = "Revisar: superó el plazo máximo"
        else:
            estado = "Mantener"
        filas.append({"ticker": t, "compra": compra, "actual": p, "objetivo": obj, "stop": stop,
                      "ret_neto": retorno_neto(compra, p, mercado_de(t)) if p else None,
                      "dias": dias, "estado": estado})
    return pd.DataFrame(filas)


COLS_POS = [("ticker", "Acción", esc), ("compra", "Compra", fmt), ("actual", "Actual", fmt),
            ("ret_neto", "Resultado neto", pct), ("objetivo", "Objetivo", fmt), ("stop", "Stop", fmt),
            ("dias", "Días", lambda x: "—" if pd.isna(x) else int(x)), ("estado", "Estado", esc)]


# ---------------- modos ----------------
def modo_dividendos(enviar=True):
    div_us = analizar_dividendos(cfg.DIVIDENDOS_US)
    div_co = analizar_dividendos(cfg.DIVIDENDOS_CO)
    if enviar:
        fecha = hoy().isoformat()
        telegram("\n".join([f"💰 <b>Ranking de dividendos (largo plazo) – {fecha}</b>", ""]
                           + lineas_div(div_us, "EE. UU.") + [""] + lineas_div(div_co, "Colombia")))
        cuerpo = ("<h3>EE. UU.</h3>" + tabla_html(div_us.head(cfg.TOP_N), COLS_DIV)
                  + "<h3>Colombia</h3>" + tabla_html(div_co.head(cfg.TOP_N), COLS_DIV))
        correo(f"Ranking de dividendos – {fecha}", envolver_html("Ranking de dividendos", cuerpo))
    return div_us, div_co


def modo_diario():
    fecha = hoy().isoformat()
    res_us = analizar_universo(cfg.UNIVERSO_US)
    res_co = analizar_universo(cfg.UNIVERSO_CO)
    compra_us, vig_us = seleccionar_top(res_us, cfg.TOP_N)
    compra_co, vig_co = seleccionar_top(res_co, cfg.TOP_N)

    senales = []
    for grupo, df in (("EE. UU.", compra_us), ("Colombia", compra_co)):
        for _, r in df.iterrows():
            senales.append({"ticker": r.ticker, "grupo": grupo, "precio_ref": r.precio,
                            "zona_max": r.precio * (1 + cfg.ZONA_ENTRADA_SUP),
                            "zona_min": r.precio * (1 - cfg.ZONA_ENTRADA_INF)})
    guardar_json(ARCH_SENALES, {"fecha": fecha, "senales": senales})

    SALIDA.mkdir(exist_ok=True)
    completo = pd.concat([res_us.assign(grupo="EE. UU."), res_co.assign(grupo="Colombia")],
                         ignore_index=True)
    ruta_csv = SALIDA / f"analisis_3a_{fecha}.csv"
    completo.to_csv(ruta_csv, index=False, encoding="utf-8-sig")

    precios = dict(zip(completo.get("ticker", []), completo.get("precio", [])))
    pos = leer_posiciones()
    faltan = [t for t in pos["ticker"] if t not in precios]
    if faltan:
        precios.update(precios_actuales(faltan))
    estado_pos = revisar_posiciones(precios)

    texto = [f"📊 <b>Reporte diario – {fecha}</b>", ""]
    texto += lineas_top(compra_us, "🇺🇸 Top compras EE. UU.")
    if not vig_us.empty:
        texto.append("En vigilancia: " + ", ".join(vig_us["ticker"]))
    texto += [""] + lineas_top(compra_co, "🇨🇴 Top compras Colombia")
    if not vig_co.empty:
        texto.append("En vigilancia: " + ", ".join(vig_co["ticker"]))
    if not estado_pos.empty:
        texto += ["", "<b>Mis posiciones</b>"]
        for _, r in estado_pos.iterrows():
            texto.append(f"• {esc(r.ticker)}: {pct(r.ret_neto)} neto · {esc(r.estado)}")
    texto += ["", "Recibirá alertas durante la jornada si el precio entra en zona de compra.", AVISO]
    telegram("\n".join(texto))

    cuerpo = ("<h3>🇺🇸 Top compras EE. UU.</h3>" + tabla_html(compra_us, COLS_TOP)
              + "<h4>En vigilancia (tendencia alcista, sin gatillo hoy)</h4>" + tabla_html(vig_us, COLS_TOP)
              + "<h3>🇨🇴 Top compras Colombia</h3>" + tabla_html(compra_co, COLS_TOP)
              + "<h4>En vigilancia</h4>" + tabla_html(vig_co, COLS_TOP)
              + "<h3>Mis posiciones</h3>" + tabla_html(estado_pos, COLS_POS)
              + "<p>Se adjunta el análisis completo de 3 años de todas las acciones evaluadas.</p>")
    correo(f"Reporte diario de bolsa – {fecha}", envolver_html(f"Reporte diario – {fecha}", cuerpo),
           [ruta_csv])

    if hoy().weekday() == cfg.DIA_DIVIDENDOS or os.getenv("FORZAR_DIVIDENDOS") == "1":
        modo_dividendos()


def modo_intradia():
    fecha = hoy().isoformat()
    datos = leer_json(ARCH_SENALES, {})
    senales = datos.get("senales", []) if datos.get("fecha") == fecha else []
    pos = leer_posiciones()
    enviadas = leer_json(ARCH_ENVIADAS, {})
    if enviadas.get("fecha") != fecha:
        enviadas = {"fecha": fecha, "claves": []}
    tickers = sorted(set([s["ticker"] for s in senales]) | set(pos["ticker"]))
    if not tickers:
        print("Sin señales ni posiciones que vigilar.")
        return
    precios = precios_actuales(tickers)
    alertas = []

    for s in senales:
        t, p, clave = s["ticker"], precios.get(s["ticker"]), f"C:{s['ticker']}"
        if p and s["zona_min"] <= p <= s["zona_max"] and clave not in enviadas["claves"]:
            obj, stop = niveles(p, t)
            alertas.append(f"🟢 <b>COMPRAR {esc(t)}</b> ({s['grupo']}) a ~{fmt(p)}\n"
                           f"   Vender en {fmt(obj)} (+2% neto) · Stop-loss {fmt(stop)}")
            enviadas["claves"].append(clave)

    for _, r in pos.iterrows():
        t, p = r["ticker"], precios.get(r["ticker"])
        if not p:
            continue
        obj, stop = niveles(float(r["precio_compra"]), t)
        neto = retorno_neto(float(r["precio_compra"]), p, mercado_de(t))
        if p >= obj and f"VO:{t}" not in enviadas["claves"]:
            alertas.append(f"🔴 <b>VENDER {esc(t)}</b> – objetivo alcanzado a {fmt(p)} ({pct(neto)} neto)")
            enviadas["claves"].append(f"VO:{t}")
        elif p <= stop and f"VS:{t}" not in enviadas["claves"]:
            alertas.append(f"⚠️ <b>VENDER {esc(t)}</b> – stop-loss a {fmt(p)} ({pct(neto)} neto)")
            enviadas["claves"].append(f"VS:{t}")

    guardar_json(ARCH_ENVIADAS, enviadas)
    if alertas:
        telegram("⏰ <b>Alertas de mercado</b>\n\n" + "\n\n".join(alertas) + "\n\n" + AVISO)
        correo(f"Alertas de mercado – {fecha}",
               envolver_html("Alertas de mercado", "<br><br>".join(a.replace("\n", "<br>") for a in alertas)))
    else:
        print("Sin alertas nuevas.")


def modo_ticker(t):
    t = t.strip().upper()
    datos = descargar([t])
    if t not in datos or len(datos[t]) < 260:
        telegram(f"No hay historial suficiente para <b>{esc(t)}</b>. Verifique el símbolo en Yahoo Finance.")
        return
    f, df = analizar_df(t, datos[t])
    u, a = df.iloc[-1], df.iloc[-2]
    m = mercado_de(t)
    checks = [
        ("Precio sobre la media de 50 días", u.Close > u.SMA50),
        ("Media de 50 sobre media de 200 (tendencia alcista)", u.SMA50 > u.SMA200),
        (f"RSI entre {cfg.RSI_MIN} y {cfg.RSI_MAX} (actual {u.RSI:.0f})", cfg.RSI_MIN <= u.RSI <= cfg.RSI_MAX),
        ("MACD acelerando al alza", u.MACD_H > a.MACD_H),
        (f"Volatilidad suficiente (ATR {pct(u.ATR_PCT)})", u.ATR_PCT >= cfg.ATR_MIN),
        ("Liquidez mínima", u.LIQ >= cfg.LIQUIDEZ_MIN[m]),
    ]
    lineas = [f"🔎 <b>Análisis de {esc(t)}</b> – {hoy().isoformat()}", "",
              f"Precio: {fmt(f['precio'])} · Rentabilidad 3 años: {pct(f['ret_3a'])}",
              f"Volatilidad anual: {pct(f['vol_anual'])} · Caída máxima 3a: {pct(f['max_caida_3a'])}", "",
              "<b>Backtest de la estrategia (3 años)</b>",
              f"Operaciones: {f['operaciones']} · Acierto (+2% neto): {pct(f['acierto'])}",
              f"Resultado medio por operación: {pct(f['ret_medio'])} · Acumulado: {pct(f['ret_total'])}",
              f"Duración promedio: {f['dias_medio']:.1f} días", "",
              "<b>Condiciones de compra hoy</b>"]
    lineas += [f"{'✅' if ok else '❌'} {txt}" for txt, ok in checks]
    lineas += ["", f"<b>Señal de compra hoy: {'SÍ' if f['senal_hoy'] else 'NO'}</b>",
               f"Si compra a {fmt(f['precio'])}: vender en {fmt(f['objetivo'])} · stop {fmt(f['stop'])}"]
    div = analizar_dividendos([t])
    if not div.empty:
        d = div.iloc[0]
        lineas += ["", "<b>Perfil de dividendos</b>",
                   f"Rendimiento: {pct(d.rendimiento)} · Crec. dividendo 5a: {pct(d.crec_div_5a)} · "
                   f"Recortes: {int(d.recortes_5a)} · Payout: {pct(d.payout)} · Puntaje: {d.puntaje:.0f}/100"]
    lineas += ["", AVISO]
    telegram("\n".join(lineas))
    correo(f"Análisis de {t}", envolver_html(f"Análisis de {esc(t)}", "<br>".join(lineas[1:-1])))


if __name__ == "__main__":
    modo = (sys.argv[1] if len(sys.argv) > 1 else "diario").strip().lower()
    if modo == "intradia":
        modo_intradia()
    elif modo == "ticker":
        if len(sys.argv) < 3 or not sys.argv[2].strip():
            sys.exit("Indique el símbolo, por ejemplo: python main.py ticker AAPL")
        modo_ticker(sys.argv[2])
    elif modo == "dividendos":
        modo_dividendos()
    else:
        modo_diario()
