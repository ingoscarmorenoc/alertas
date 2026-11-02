"""Genera el panel web (HTML autocontenido con gráficos)."""
import json
import math

import pandas as pd

from estrategia import _hora_local


def _limpio(x):
    if isinstance(x, dict):
        return {k: _limpio(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_limpio(v) for v in x]
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    if hasattr(x, "item"):
        try:
            return _limpio(x.item())
        except Exception:
            return str(x)
    return x


def _series(a):
    df = a["df"].tail(140)
    idx = _hora_local(df.index)
    fmt = "%d/%m %H:%M" if a["fila"]["base"] == "horario" else "%d/%m/%y"
    h = {"t": [i.strftime(fmt) for i in idx], "c": df["Close"].round(4).tolist(),
         "e9": df["EMA9"].round(4).tolist(), "e21": df["EMA21"].round(4).tolist()}
    d = {"t": [], "c": []}
    if a.get("diario") is not None:
        dd = a["diario"]["Close"].dropna().iloc[::3]
        d = {"t": [i.strftime("%d/%m/%y") for i in dd.index], "c": dd.round(4).tolist()}
    return h, d


def generar(ruta, analisis, compras, ventas, abiertas, cerradas, resumen, dividendos, actualizado, proxima):
    acciones = []
    for a in analisis.values():
        h, d = _series(a)
        acciones.append({**{k: v for k, v in a["fila"].items()}, "h": h, "d": d})
    datos = _limpio({"actualizado": actualizado, "proxima": proxima, "acciones": acciones,
                     "compras": compras, "ventas": ventas, "abiertas": abiertas,
                     "cerradas": list(reversed(cerradas[-30:])), "resumen": resumen,
                     "dividendos": dividendos})
    js = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(PLANTILLA.replace("__DATOS__", js))


PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="refresh" content="900">
<title>Panel de trading</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--fondo:#EEF2F5;--sup:#FFFFFF;--tinta:#14283C;--suave:#5A6B7C;--linea:#D5DDE5;
--compra:#17834F;--venta:#BE3B32;--alcista:#1F6FA8;--neutral:#8A96A3;--marca:#0E6E78;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--fondo:#0F1B27;--sup:#162534;--tinta:#E6EDF3;--suave:#94A6B8;
--linea:#26384A;--compra:#3CC07F;--venta:#F0675C;--alcista:#5AA9E6;--neutral:#7C8B99;--marca:#4FC1C9;color-scheme:dark}}
*{box-sizing:border-box}
html,body{margin:0;background:var(--fondo);color:var(--tinta);font-family:"Public Sans",system-ui,-apple-system,"Segoe UI",Arial,sans-serif;font-size:15px;line-height:1.5}
body{padding:env(safe-area-inset-top,0) 0 env(safe-area-inset-bottom,0)}
.num{font-variant-numeric:tabular-nums}
main{max-width:1120px;margin:0 auto;padding:28px 20px 48px}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 24px;margin-bottom:28px}
h1{font-size:1.9rem;font-weight:800;letter-spacing:-.02em;margin:0}
.meta{color:var(--suave);font-size:.9rem}
h2{font-size:1.15rem;font-weight:800;margin:40px 0 12px}
.ahora{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.accion{background:var(--sup);border-left:6px solid var(--compra);padding:14px 16px;border-radius:4px}
.accion.venta{border-left-color:var(--venta)}
.accion .tk{font-size:1.7rem;font-weight:800;letter-spacing:-.02em;line-height:1.1}
.accion .que{font-weight:600;color:var(--compra)}.accion.venta .que{color:var(--venta)}
.accion p{margin:6px 0 0;color:var(--suave);font-size:.9rem}
.vacio{grid-column:1/-1;max-width:60ch;background:var(--sup);padding:16px;border-radius:4px;color:var(--suave)}
.pestanas{display:flex;gap:4px;border-bottom:2px solid var(--linea);margin-bottom:0}
.pestanas button{font:inherit;font-weight:600;background:none;border:0;padding:10px 16px;color:var(--suave);cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px}
.pestanas button[aria-selected=true]{color:var(--tinta);border-bottom-color:var(--marca)}
button:focus-visible,tr:focus-visible{outline:2px solid var(--marca);outline-offset:2px}
.tabla{overflow-x:auto;background:var(--sup);border-radius:0 0 4px 4px}
table{width:100%;border-collapse:collapse;min-width:640px}
th{text-align:left;font-weight:600;color:var(--suave);font-size:.82rem;padding:10px 12px;border-bottom:1px solid var(--linea)}
td{padding:10px 12px;border-bottom:1px solid var(--linea);white-space:nowrap}
tbody tr.fila{cursor:pointer}tbody tr.fila:hover{background:color-mix(in srgb,var(--marca) 7%,transparent)}
.der{text-align:right}
.nom{display:block;color:var(--suave);font-size:.8rem}
.sube{color:var(--compra)}.baja{color:var(--venta)}
.estado{display:inline-block;font-weight:600;font-size:.82rem;padding:2px 8px;border-radius:999px;color:#fff}
.e-Comprar{background:var(--compra)}.e-Bajista{background:var(--venta)}.e-Alcista{background:var(--alcista)}.e-Neutral{background:var(--neutral)}
.detalle td{background:var(--fondo);white-space:normal;padding:16px}
.grafico{position:relative;height:280px}
.modo{display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap}
.modo button{font:inherit;font-size:.85rem;border:1px solid var(--linea);background:var(--sup);color:var(--tinta);padding:4px 12px;border-radius:999px;cursor:pointer}
.modo button[aria-pressed=true]{background:var(--marca);border-color:var(--marca);color:#fff}
.datos{display:flex;flex-wrap:wrap;gap:6px 24px;margin-top:10px;color:var(--suave);font-size:.88rem}
.datos b{color:var(--tinta);font-weight:600}
.cifras{display:flex;flex-wrap:wrap;gap:12px 40px;background:var(--sup);padding:16px;border-radius:4px 4px 0 0;border-bottom:1px solid var(--linea)}
.cifras div{font-size:.85rem;color:var(--suave)}.cifras b{display:block;font-size:1.4rem;color:var(--tinta);font-weight:800}
footer{margin-top:40px;color:var(--suave);font-size:.82rem;max-width:72ch}
svg.mini{display:block}
</style>
</head>
<body>
<main>
<header>
  <h1>Panel de trading</h1>
  <div class="meta" id="meta"></div>
</header>

<section aria-labelledby="t-ahora">
  <h2 id="t-ahora">Qué hacer ahora</h2>
  <div class="ahora" id="ahora"></div>
</section>

<section aria-labelledby="t-acc">
  <h2 id="t-acc">Estado de las acciones</h2>
  <div class="pestanas" role="tablist">
    <button role="tab" aria-selected="true" data-g="Colombia">Colombia</button>
    <button role="tab" aria-selected="false" data-g="EE. UU.">Tecnología EE. UU.</button>
  </div>
  <div class="tabla"><table>
    <thead><tr><th>Acción</th><th>Últimos días</th><th class="der">Precio</th><th class="der">Hoy</th><th class="der">RSI</th><th>Estado</th><th class="der">Llega a +2% (2 años)</th><th>Confianza</th></tr></thead>
    <tbody id="filas"></tbody>
  </table></div>
</section>

<section aria-labelledby="t-car">
  <h2 id="t-car">Operaciones</h2>
  <div class="cifras" id="cifras"></div>
  <div class="tabla"><table>
    <thead><tr><th>Acción</th><th>Origen</th><th class="der">Entrada</th><th class="der">Actual / salida</th><th class="der">Resultado neto</th><th>Estado</th></tr></thead>
    <tbody id="ops"></tbody>
  </table></div>
</section>

<section aria-labelledby="t-div" id="sec-div">
  <h2 id="t-div">Dividendos para largo plazo</h2>
  <div class="tabla"><table>
    <thead><tr><th>Acción</th><th>País</th><th class="der">Rendimiento</th><th class="der">Crec. dividendo 5 años</th><th class="der">Recortes</th><th class="der">Payout</th><th class="der">Puntaje</th></tr></thead>
    <tbody id="divs"></tbody>
  </table></div>
</section>

<footer>Datos de Yahoo Finance con hasta 15 minutos de retraso. Herramienta de apoyo basada en estadística histórica; no constituye asesoría financiera ni garantiza resultados. Verifique antes de operar.</footer>
</main>

<script>
const D = __DATOS__;
const $ = s => document.querySelector(s);
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const n = (x, d=2) => x == null ? "—" : Number(x).toLocaleString("es-CO", {minimumFractionDigits:d, maximumFractionDigits:d});
const p = (x, d=1) => x == null ? "—" : (x*100).toLocaleString("es-CO", {minimumFractionDigits:d, maximumFractionDigits:d}) + "%";
const signo = x => x == null ? "" : (x >= 0 ? "sube" : "baja");
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const corto = t => t.replace(".CL","");

$("#meta").textContent = `Actualizado ${D.actualizado} (hora Colombia). Próximo análisis: ${D.proxima}.`;

// Qué hacer ahora
const tarjetas = [
  ...D.compras.map(c => `<article class="accion"><div class="tk">${esc(corto(c.ticker))}</div>
     <div class="que">Comprar cerca de ${n(c.precio)}</div>
     <p>Vender en ${n(c.objetivo)} (+2% neto). Stop-loss en ${n(c.stop)}. Confianza ${esc(c.confianza)}: llegó al objetivo en ${p(c.acierto,0)} de ${c.operaciones} operaciones.</p></article>`),
  ...D.ventas.map(v => `<article class="accion venta"><div class="tk">${esc(corto(v.ticker))}</div>
     <div class="que">Vender: ${esc(v.motivo)}</div>
     <p>Entrada ${n(v.entrada)}, precio ${n(v.salida ?? v.actual)}. Resultado ${p(v.retorno)} neto.</p></article>`)
];
$("#ahora").innerHTML = tarjetas.length ? tarjetas.join("") :
  `<div class="vacio">No hay señales nuevas de compra ni de venta en esta hora. Próximo análisis: ${esc(D.proxima)}.</div>`;

// Mini gráfico
function mini(c){
  const v = c.slice(-35).filter(x => x != null); if (v.length < 2) return "";
  const lo = Math.min(...v), hi = Math.max(...v), w = 110, h = 30;
  const pts = v.map((x,i) => `${(i/(v.length-1)*w).toFixed(1)},${(h - (x-lo)/((hi-lo)||1)*h).toFixed(1)}`).join(" ");
  const col = v[v.length-1] >= v[0] ? css("--compra") : css("--venta");
  return `<svg class="mini" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline fill="none" stroke="${col}" stroke-width="1.6" points="${pts}"/></svg>`;
}

let grupo = "Colombia", graf = null, abierto = null;
function pintarTabla(){
  const filas = D.acciones.filter(a => a.grupo === grupo);
  $("#filas").innerHTML = filas.length ? filas.map(a => `
   <tr class="fila" tabindex="0" data-t="${esc(a.ticker)}">
     <td><b>${esc(corto(a.ticker))}</b><span class="nom">${esc(a.nombre)}</span></td>
     <td>${mini(a.h.c)}</td>
     <td class="der num">${n(a.precio)}</td>
     <td class="der num ${signo(a.var_dia)}">${a.var_dia==null?"—":(a.var_dia>=0?"+":"")+p(a.var_dia)}</td>
     <td class="der num">${n(a.rsi,0)}</td>
     <td><span class="estado e-${esc(a.estado)}">${esc(a.estado)}</span></td>
     <td class="der num">${p(a.acierto,0)} <span class="nom">${a.operaciones} operaciones</span></td>
     <td>${esc(a.confianza)}</td>
   </tr>`).join("") : `<tr><td colspan="8">No hay datos para este grupo en la fuente gratuita. Revise los símbolos en config.py.</td></tr>`;
  document.querySelectorAll("tr.fila").forEach(tr => {
    const ir = () => detalle(tr);
    tr.addEventListener("click", ir);
    tr.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ir(); }});
  });
}

function detalle(tr){
  const t = tr.dataset.t;
  document.querySelectorAll("tr.detalle").forEach(x => x.remove());
  if (graf) { graf.destroy(); graf = null; }
  if (abierto === t) { abierto = null; return; }
  abierto = t;
  const a = D.acciones.find(x => x.ticker === t);
  const fila = document.createElement("tr"); fila.className = "detalle";
  fila.innerHTML = `<td colspan="8">
    <div class="modo" role="group" aria-label="Periodo del gráfico">
      <button aria-pressed="true" data-m="h">${a.base === "horario" ? "Últimas 140 horas" : "Últimos 140 días"}</button>
      <button aria-pressed="false" data-m="d">3 años</button>
    </div>
    <div class="grafico"><canvas aria-label="Gráfico de precio de ${esc(t)}"></canvas></div>
    <div class="datos">
      <span>Si compra ahora: vender en <b>${n(a.objetivo)}</b>, stop en <b>${n(a.stop)}</b></span>
      <span>Variación 3 años <b>${p(a.ret_3a)}</b></span>
      <span>Volatilidad anual <b>${p(a.vol_anual)}</b></span>
      <span>Mayor caída 3 años <b>${p(a.max_caida_3a)}</b></span>
      <span>Operaciones ganadoras <b>${p(a.ganadoras,0)}</b></span>
      <span>Resultado medio <b>${p(a.ret_medio,2)}</b></span>
      <span>Datos <b>${a.base === "horario" ? "velas de 1 hora" : "velas diarias"}</b></span>
    </div></td>`;
  tr.after(fila);
  const dibujar = m => {
    if (graf) graf.destroy();
    const s = m === "h" ? a.h : a.d;
    const sets = [{label:"Precio", data:s.c, borderColor:css("--tinta"), borderWidth:1.8, pointRadius:0, tension:.15}];
    if (m === "h") {
      sets.push({label:"EMA 9", data:a.h.e9, borderColor:css("--compra"), borderWidth:1.2, pointRadius:0});
      sets.push({label:"EMA 21", data:a.h.e21, borderColor:css("--venta"), borderWidth:1.2, pointRadius:0});
      sets.push({label:"Objetivo", data:s.c.map(()=>a.objetivo), borderColor:css("--compra"), borderDash:[5,4], borderWidth:1, pointRadius:0});
      sets.push({label:"Stop", data:s.c.map(()=>a.stop), borderColor:css("--venta"), borderDash:[5,4], borderWidth:1, pointRadius:0});
    }
    graf = new Chart(fila.querySelector("canvas"), {type:"line", data:{labels:s.t, datasets:sets},
      options:{responsive:true, maintainAspectRatio:false, animation:false, interaction:{mode:"index", intersect:false},
        plugins:{legend:{labels:{color:css("--suave"), boxWidth:14}}},
        scales:{x:{ticks:{color:css("--suave"), maxTicksLimit:8}, grid:{display:false}},
                y:{ticks:{color:css("--suave")}, grid:{color:css("--linea")}}}}});
  };
  fila.querySelectorAll(".modo button").forEach(b => b.addEventListener("click", () => {
    fila.querySelectorAll(".modo button").forEach(x => x.setAttribute("aria-pressed", x === b));
    dibujar(b.dataset.m);
  }));
  if (window.Chart) dibujar("h"); else fila.querySelector(".grafico").textContent = "No se pudo cargar la librería de gráficos. Revise su conexión.";
}

document.querySelectorAll(".pestanas button").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".pestanas button").forEach(x => x.setAttribute("aria-selected", x === b));
  grupo = b.dataset.g; abierto = null; if (graf) { graf.destroy(); graf = null; } pintarTabla();
}));
pintarTabla();

// Operaciones
const r = D.resumen;
$("#cifras").innerHTML = `
  <div><b class="num">${D.abiertas.length}</b>abiertas</div>
  <div><b class="num">${r.operaciones}</b>cerradas por el sistema</div>
  <div><b class="num">${p(r.ganadoras,0)}</b>con ganancia</div>
  <div><b class="num ${signo(r.ret_total)}">${p(r.ret_total)}</b>resultado acumulado</div>`;
const filasOps = [
  ...D.abiertas.map(o => `<tr><td><b>${esc(corto(o.ticker))}</b></td><td>${o.tipo === "Real" ? "Mi compra" : "Señal del sistema"}</td>
    <td class="der num">${n(o.entrada)}</td><td class="der num">${n(o.actual)}</td>
    <td class="der num ${signo(o.retorno)}">${p(o.retorno)}</td><td>${esc(o.estado)}</td></tr>`),
  ...D.cerradas.map(o => `<tr><td><b>${esc(corto(o.ticker))}</b></td><td>Señal del sistema</td>
    <td class="der num">${n(o.entrada)}</td><td class="der num">${n(o.salida)}</td>
    <td class="der num ${signo(o.retorno)}">${p(o.retorno)}</td><td>Cerrada: ${esc(o.motivo)} (${esc(o.fecha_salida)})</td></tr>`)
];
$("#ops").innerHTML = filasOps.length ? filasOps.join("") :
  `<tr><td colspan="6">Aún no hay operaciones. Aparecerán aquí cuando el sistema emita su primera señal de compra.</td></tr>`;

// Dividendos
if (D.dividendos && (D.dividendos.us?.length || D.dividendos.co?.length)) {
  const fd = (lista, pais) => (lista||[]).slice(0,10).map(d => `<tr><td><b>${esc(corto(d.ticker))}</b><span class="nom">${esc(d.nombre)}</span></td>
    <td>${pais}</td><td class="der num">${p(d.rendimiento)}</td><td class="der num">${p(d.crec_div_5a)}</td>
    <td class="der num">${d.recortes_5a}</td><td class="der num">${p(d.payout,0)}</td><td class="der num">${n(d.puntaje,0)}</td></tr>`).join("");
  $("#divs").innerHTML = fd(D.dividendos.us, "EE. UU.") + fd(D.dividendos.co, "Colombia");
  $("#t-div").textContent = `Dividendos para largo plazo (análisis del ${D.dividendos.fecha})`;
} else {
  $("#divs").innerHTML = `<tr><td colspan="7">El ranking se calcula los lunes a las 10:00. También puede generarlo desde GitHub con el modo «dividendos».</td></tr>`;
}
</script>
</body>
</html>
"""
