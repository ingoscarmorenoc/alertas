"""Punto de entrada.
   python main.py hora          -> análisis horario (a las 10:00 envía además el reporte completo)
   python main.py reporte       -> fuerza el reporte completo + panel
   python main.py ticker AAPL   -> análisis individual
   python main.py dividendos    -> ranking de dividendos
"""
import datetime as dt
import html
import json
import os
import sys
from pathlib import Path

import config as cfg
import cartera
import panel
from dividendos import analizar_dividendos
from estrategia import analizar, mercado_de
from notificar import correo, telegram, telegram_documento

BASE = Path(__file__).parent
DATOS = BASE / "datos"
ARCH_ENVIADAS, ARCH_DIV, ARCH_PANEL = DATOS / "alertas_enviadas.json", DATOS / "dividendos.json", DATOS / "panel.html"
AVISO = "<i>Apoyo basado en estadística histórica; no es asesoría financiera ni garantiza resultados.</i>"
EMOJI = {"Comprar": "🟢", "Alcista": "🔵", "Neutral": "⚪", "Bajista": "🔴"}


def ahora():
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)   # Colombia, sin horario de verano


def esc(x):
    return html.escape(str(x))


def fmt(x):
    return "—" if x is None else f"{x:,.2f}"


def pct(x, d=1):
    return "—" if x is None else f"{x * 100:.{d}f}%"


def leer(ruta, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar(ruta, d):
    DATOS.mkdir(exist_ok=True)
    ruta.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def url_panel():
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if os.getenv("PANEL_URL"):
        return os.getenv("PANEL_URL")
    if "/" in repo:
        dueno, nombre = repo.split("/", 1)
        return f"https://{dueno.lower()}.github.io/{nombre}/"
    return None


def proxima_hora(t):
    dia, h = t.weekday(), t.hour + 1
    if dia < 5 and h < 10:
        return "hoy 10:00"
    if dia < 5 and h <= 16:
        return f"{h}:00"
    return "lunes 10:00" if dia >= 4 else "mañana 10:00"


def estado_lineas(analisis, grupo):
    filas = [a["fila"] for a in analisis.values() if a["fila"]["grupo"] == grupo]
    if not filas:
        return ["Sin datos disponibles en la fuente gratuita."]
    out = []
    for f in filas:
        var = "" if f["var_dia"] is None else f" ({'+' if f['var_dia'] >= 0 else ''}{pct(f['var_dia'])})"
        out.append(f"{EMOJI.get(f['estado'], '⚪')} <b>{esc(f['ticker'].replace('.CL', ''))}</b> "
                   f"{fmt(f['precio'])}{var} · {f['estado']}")
    return out


def ejecutar(modo):
    t = ahora()
    fecha, hora_txt = t.strftime("%Y-%m-%d"), t.strftime("%Y-%m-%d %H:%M")
    analisis = analizar(cfg.LISTA_CO + cfg.LISTA_US)
    ops = cartera.cargar_ops()
    enviadas = leer(ARCH_ENVIADAS, {})
    if enviadas.get("fecha") != fecha:
        enviadas = {"fecha": fecha, "claves": []}

    # 1) Ventas de operaciones del sistema
    cierres = cartera.actualizar_simuladas(ops, analisis, hora_txt)
    # 2) Posiciones reales del usuario
    reales = cartera.revisar_reales(analisis)
    ventas_reales = []
    for r in reales:
        clave = f"V:{r['ticker']}:{r['estado']}"
        if r["estado"].startswith("Vender") and clave not in enviadas["claves"]:
            ventas_reales.append(r)
            enviadas["claves"].append(clave)
    # 3) Compras nuevas
    abiertas_t = {o["ticker"] for o in ops["abiertas"]}
    compras = []
    for a in analisis.values():
        f = a["fila"]
        clave = f"C:{f['ticker']}:{f['senal_ts']}"
        if (f["estado"] == "Comprar" and f["confianza"] != "baja" and f["ticker"] not in abiertas_t
                and clave not in enviadas["claves"]):
            compras.append(f)
            enviadas["claves"].append(clave)
            cartera.abrir(ops, f, str(a["df"].index[-1]), hora_txt)
    cartera.guardar_ops(ops)
    guardar(ARCH_ENVIADAS, enviadas)

    completo = modo == "reporte" or t.hour == cfg.HORA_REPORTE
    dividendos = leer(ARCH_DIV, None)
    if completo and (t.weekday() == cfg.DIA_DIVIDENDOS or not dividendos):
        dividendos = calcular_dividendos(fecha)

    # ---- Mensaje de Telegram ----
    titulo = "📊 <b>Reporte diario</b>" if completo else "⏰ <b>Actualización horaria</b>"
    m = [f"{titulo} – {hora_txt} (hora Colombia)", ""]
    if compras:
        m.append("<b>Comprar ahora</b>")
        for f in compras:
            m.append(f"🟢 <b>{esc(f['ticker'])}</b> ~{fmt(f['precio'])} · vender {fmt(f['objetivo'])} (+2% neto) · "
                     f"stop {fmt(f['stop'])} · confianza {f['confianza']} ({pct(f['acierto'], 0)} de {f['operaciones']} op.)")
        m.append("")
    ventas_txt = [f"🔴 <b>{esc(c['ticker'])}</b> – {c['motivo']} a {fmt(c['salida'])} ({pct(c['retorno'])} neto) · señal del sistema"
                  for c in cierres]
    ventas_txt += [f"🔴 <b>{esc(r['ticker'])}</b> – {r['estado']} a {fmt(r['actual'])} ({pct(r['retorno'])} neto) · su posición"
                   for r in ventas_reales]
    if ventas_txt:
        m += ["<b>Vender ahora</b>"] + ventas_txt + [""]
    if not compras and not ventas_txt:
        m += ["Sin señales nuevas de compra o venta en esta hora.", ""]
    if ops["abiertas"]:
        m.append("<b>Operaciones abiertas del sistema</b>")
        for o in ops["abiertas"]:
            a = analisis.get(o["ticker"])
            actual = a["fila"]["precio"] if a else None
            ret = cartera.retorno_neto(o["entrada"], actual, mercado_de(o["ticker"])) if actual else None
            m.append(f"• {esc(o['ticker'])}: entrada {fmt(o['entrada'])}, actual {fmt(actual)} ({pct(ret)}) · "
                     f"objetivo {fmt(o['objetivo'])} · stop {fmt(o['stop'])}")
        m.append("")
    m += ["🇨🇴 <b>Colombia</b>"] + estado_lineas(analisis, "Colombia") + [""]
    m += ["🇺🇸 <b>Tecnología EE. UU.</b>"] + estado_lineas(analisis, "EE. UU.") + [""]

    if completo:
        top = sorted((a["fila"] for a in analisis.values() if a["fila"]["confianza"] != "baja"),
                     key=lambda f: ({"Comprar": 0, "Alcista": 1, "Neutral": 2, "Bajista": 3}[f["estado"]], -f["puntaje"]))[:10]
        if top:
            m.append("🏆 <b>Top 10 para vigilar hoy</b>")
            for k, f in enumerate(top, 1):
                m.append(f"{k}. {esc(f['ticker'])} · {f['estado']} · llega a +2% en {pct(f['acierto'], 0)} "
                         f"({f['operaciones']} op.) · confianza {f['confianza']}")
            m.append("")
        res = cartera.resumen(ops)
        if res["operaciones"]:
            m += [f"📈 <b>Desempeño del sistema</b>: {res['operaciones']} operaciones cerradas · "
                  f"{pct(res['ganadoras'], 0)} con ganancia · acumulado {pct(res['ret_total'])}", ""]
        if dividendos and t.weekday() == cfg.DIA_DIVIDENDOS:
            m.append("💰 <b>Dividendos (largo plazo)</b>")
            for pais, clave in (("EE. UU.", "us"), ("Colombia", "co")):
                lst = dividendos.get(clave, [])[:5]
                if lst:
                    m.append(f"{pais}: " + ", ".join(f"{d['ticker']} ({pct(d['rendimiento'])})" for d in lst))
            m.append("")
    enlace = url_panel()
    leyenda = "🟢 comprar · 🔵 alcista · ⚪ neutral · 🔴 bajista"
    m += [leyenda]
    if enlace:
        m.append(f'📉 <a href="{enlace}">Abrir panel gráfico</a>')
    m.append(AVISO)
    telegram("\n".join(m))

    # ---- Panel web ----
    abiertas_panel = []
    for o in ops["abiertas"]:
        a = analisis.get(o["ticker"])
        actual = a["fila"]["precio"] if a else None
        abiertas_panel.append({**o, "actual": actual, "tipo": "Señal",
                               "retorno": cartera.retorno_neto(o["entrada"], actual, mercado_de(o["ticker"])) if actual else None,
                               "estado": f"Objetivo {fmt(o['objetivo'])} · stop {fmt(o['stop'])}"})
    abiertas_panel += reales
    ventas_panel = [{"ticker": c["ticker"], "motivo": c["motivo"], "entrada": c["entrada"], "salida": c["salida"],
                     "retorno": c["retorno"]} for c in cierres]
    ventas_panel += [{"ticker": r["ticker"], "motivo": r["estado"].replace("Vender: ", ""), "entrada": r["entrada"],
                      "actual": r["actual"], "retorno": r["retorno"]} for r in ventas_reales]
    panel.generar(ARCH_PANEL, analisis, compras, ventas_panel, abiertas_panel, ops["cerradas"],
                  cartera.resumen(ops), dividendos, hora_txt, proxima_hora(t))
    if completo:
        telegram_documento(ARCH_PANEL, "Panel del día (ábralo con su navegador si el enlace no está activo).")
        correo(f"Reporte de bolsa – {fecha}", ARCH_PANEL.read_text(encoding="utf-8"))


def calcular_dividendos(fecha):
    us, co = analizar_dividendos(cfg.DIVIDENDOS_US), analizar_dividendos(cfg.DIVIDENDOS_CO)
    d = {"fecha": fecha, "us": json.loads(us.to_json(orient="records")) if not us.empty else [],
         "co": json.loads(co.to_json(orient="records")) if not co.empty else []}
    guardar(ARCH_DIV, d)
    return d


def modo_ticker(tk):
    tk = tk.strip().upper()
    a = analizar([tk]).get(tk)
    if not a:
        telegram(f"No hay datos suficientes para <b>{esc(tk)}</b>. Verifique el símbolo en finance.yahoo.com.")
        return
    f = a["fila"]
    lineas = [f"🔎 <b>{esc(tk)}</b> – {ahora():%Y-%m-%d %H:%M}", "",
              f"Precio {fmt(f['precio'])} · hoy {pct(f['var_dia'])} · RSI {f['rsi']:.0f}",
              f"Estado: {EMOJI.get(f['estado'], '')} {f['estado']} (velas {'de 1 hora' if f['base'] == 'horario' else 'diarias'})",
              f"Variación 3 años {pct(f['ret_3a'])} · volatilidad {pct(f['vol_anual'])} · mayor caída {pct(f['max_caida_3a'])}", "",
              "<b>Backtest de la estrategia</b>",
              f"{f['operaciones']} operaciones · llegó a +2% en {pct(f['acierto'], 0)} · ganadoras {pct(f['ganadoras'], 0)}",
              f"Resultado medio {pct(f['ret_medio'], 2)} · acumulado {pct(f['ret_total'])} · confianza {f['confianza']}", "",
              f"Si compra a {fmt(f['precio'])}: vender en {fmt(f['objetivo'])} · stop {fmt(f['stop'])}", "", AVISO]
    telegram("\n".join(lineas))


if __name__ == "__main__":
    modo = (sys.argv[1] if len(sys.argv) > 1 else "hora").strip().lower()
    if modo == "ticker":
        if len(sys.argv) < 3 or not sys.argv[2].strip():
            sys.exit("Indique el símbolo, por ejemplo: python main.py ticker AAPL")
        modo_ticker(sys.argv[2])
    elif modo == "dividendos":
        d = calcular_dividendos(ahora().strftime("%Y-%m-%d"))
        lineas = ["💰 <b>Ranking de dividendos</b>", ""]
        for pais, clave in (("🇺🇸 EE. UU.", "us"), ("🇨🇴 Colombia", "co")):
            lineas.append(f"<b>{pais}</b>")
            for k, x in enumerate(d[clave][:10], 1):
                lineas.append(f"{k}. {esc(x['ticker'])} · rend. {pct(x['rendimiento'])} · crec. div 5a "
                              f"{pct(x['crec_div_5a'])} · payout {pct(x['payout'])} · puntaje {x['puntaje']:.0f}")
            lineas.append("")
        telegram("\n".join(lineas + [AVISO]))
    else:
        ejecutar(modo)
