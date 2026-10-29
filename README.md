# Sistema de alertas de bolsa (EE. UU. y Colombia)

Corre gratis en GitHub Actions y envía notificaciones por **Telegram** y **correo**:

| Proceso | Cuándo | Qué hace |
|---|---|---|
| Reporte diario | 6:00 a. m. (hora Colombia), lun–vie | Top 10 de compras EE. UU. y Colombia, backtest de 3 años, estado de sus posiciones, CSV adjunto con el análisis completo |
| Alertas intradía | Cada 30 min durante la jornada | 🟢 COMPRAR cuando una acción del top entra en zona de entrada · 🔴 VENDER cuando una posición llega al +2 % neto · ⚠️ stop-loss |
| Dividendos (largo plazo) | Lunes (o a demanda) | Ranking de las 10 mejores pagadoras de dividendos por país |
| Análisis individual | A demanda | Análisis de 3 años de cualquier acción |

## Instalación (una sola vez, ~20 minutos)

### 1. Crear el repositorio
1. Cree una cuenta en https://github.com y un repositorio **privado** (p. ej. `bolsa-alertas`).
2. En el repositorio: **Add file → Upload files** y arrastre todo el contenido de esta carpeta.
   Si la carpeta `.github` no se sube (es oculta en algunos equipos), créela con **Add file → Create new file**
   escribiendo como nombre `.github/workflows/diario.yml` y pegando el contenido; repita con `intradia.yml`.

### 2. Bot de Telegram
1. En Telegram, abra **@BotFather**, envíe `/newbot` y siga los pasos. Copie el **token**.
2. Envíe cualquier mensaje a su nuevo bot.
3. Abra en el navegador `https://api.telegram.org/bot<TOKEN>/getUpdates` y copie el número de `"chat":{"id": ...}`.

### 3. Correo (Gmail)
1. Active la verificación en dos pasos en su cuenta de Google.
2. Cree una **contraseña de aplicación** en https://myaccount.google.com/apppasswords (16 caracteres).

### 4. Cargar las claves en GitHub
En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**:

| Nombre | Valor |
|---|---|
| `TELEGRAM_TOKEN` | Token de BotFather |
| `TELEGRAM_CHAT_ID` | Número de chat |
| `EMAIL_USUARIO` | Su correo Gmail |
| `EMAIL_CLAVE_APP` | Contraseña de aplicación |
| `EMAIL_DESTINO` | Correo donde recibirá los reportes (opcional) |

En la pestaña **Variables** (opcional) defina las comisiones de su comisionista como fracción:
`COMISION_CO` (por defecto `0.006` = 0,6 %) y `COMISION_US` (por defecto `0`).

### 5. Permisos
**Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**

### 6. Probar
**Actions → Reporte diario → Run workflow.** En 3–5 minutos llegará el primer reporte.

## Uso diario
- **Registrar una compra:** edite `posiciones.csv` en GitHub (ícono del lápiz) y agregue una fila:
  `ECOPETROL.CL,2450,100,2026-10-29`. Al vender, borre la fila. Así el sistema vigila su objetivo y stop-loss.
- **Analizar una acción:** **Actions → Reporte diario → Run workflow**, modo `ticker` y el símbolo
  (`AAPL`, `KO`, `PFBCOLOM.CL`…). Las acciones colombianas usan el sufijo `.CL`.
- **Ranking de dividendos a demanda:** mismo botón, modo `dividendos`.
- **Ajustar la estrategia:** todos los parámetros están comentados en `config.py`.

## Cómo decide
**Mediano plazo (compra/venta):** compra solo en tendencia alcista (precio > media 50 > media 200), en un
retroceso sin sobrecompra (RSI 35–58), con el MACD acelerando, volatilidad suficiente para alcanzar el 2 % y
liquidez mínima. Cada acción se somete a un backtest de 3 años con las mismas reglas; solo entran al top las que
históricamente acertaron al menos el 50 % de las veces, con resultado medio positivo y al menos 8 operaciones.
El precio de venta se calcula para dejar **2 % neto de comisiones**; el stop-loss es −1,5 %.

**Largo plazo (dividendos):** puntaje de 0 a 100 que pondera rendimiento por dividendo (penaliza rendimientos
> 10 %, posible trampa), crecimiento del dividendo en 5 años, ausencia de recortes, payout sostenible,
rentabilidad sobre patrimonio, endeudamiento y crecimiento del precio.

## Limitaciones importantes
- **Datos:** Yahoo Finance gratuito, con hasta ~15 min de retraso. Algunos símbolos de la BVC pueden no tener
  datos completos; el sistema los omite y lo informa en el registro de la ejecución. Verifíquelos en finance.yahoo.com.
- **Horarios:** GitHub puede retrasar las ejecuciones programadas varios minutos en horas de alta demanda.
- **Liquidez colombiana:** pocas acciones de la BVC cumplen los filtros; es normal que el top colombiano
  tenga menos de 10 acciones algunos días.
- **Rendimiento pasado no garantiza resultados futuros.** Es una herramienta de apoyo, no asesoría financiera.
