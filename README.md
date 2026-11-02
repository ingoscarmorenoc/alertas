# Alertas de bolsa – versión 2.0

| Qué recibe en Telegram | Cuándo (hora Colombia) |
|---|---|
| Reporte completo: estado de todas las acciones, top 10, desempeño y panel | 10:00 a. m., lunes a viernes |
| Actualización horaria: compras, ventas, stop-loss y estado de cada acción | 11:00, 12:00, 13:00, 14:00, 15:00 y 16:00 |
| Ranking de dividendos | Lunes en el reporte de las 10:00 |

Panel gráfico: `https://<su-usuario>.github.io/<repositorio>/` (se actualiza cada hora).

## Cómo decide (velas de 1 hora)
Compra cuando la media rápida (EMA 9) cruza o rebota sobre la media de 21 horas, el precio está por
encima de las medias de 50 y 200 horas, el RSI está entre 45 y 70 y el MACD acelera. Solo alerta si esa
misma regla ha sido rentable en esa acción durante los últimos 2 años de velas horarias.
Vende al alcanzar +2 % neto de comisiones, al tocar el stop-loss (−1 %), si se pierde el impulso
(EMA 9 cae bajo EMA 21) o tras ~3 días de mercado. Todo es ajustable en `config.py`.

Cada señal se registra como operación simulada en `datos/operaciones.json`, así el panel mide el
desempeño real del sistema. Sus compras reales van en `posiciones.csv`.

## Limitaciones
- Datos gratuitos de Yahoo con hasta 15 min de retraso. Para precios en tiempo real de EE. UU. agregue
  el secreto opcional `FINNHUB_KEY` (clave gratuita en finnhub.io).
- Yahoo no siempre publica velas horarias de la BVC; en ese caso esas acciones se analizan con velas diarias.
- GitHub puede retrasar unos minutos las ejecuciones programadas.
- No es asesoría financiera ni garantiza resultados.
