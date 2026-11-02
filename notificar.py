"""Envío de notificaciones por Telegram y correo electrónico."""
import os
import smtplib
from email.message import EmailMessage

import requests


def telegram(texto):
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[aviso] Telegram no configurado.\n" + texto)
        return
    bloques, actual = [], ""
    for linea in texto.split("\n"):
        if len(actual) + len(linea) > 3800:
            bloques.append(actual)
            actual = ""
        actual += linea + "\n"
    bloques.append(actual)
    for b in bloques:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": b, "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=30)
        if not r.ok:
            print(f"[error] Telegram: {r.text}")


def correo(asunto, html, adjuntos=None):
    usuario, clave = os.getenv("EMAIL_USUARIO"), os.getenv("EMAIL_CLAVE_APP")
    if not usuario or not clave:
        print("[aviso] Correo no configurado.")
        return
    msg = EmailMessage()
    msg["Subject"], msg["From"] = asunto, usuario
    msg["To"] = os.getenv("EMAIL_DESTINO") or usuario
    msg.set_content("Este mensaje requiere un cliente de correo compatible con HTML.")
    msg.add_alternative(html, subtype="html")
    for ruta in adjuntos or []:
        with open(ruta, "rb") as f:
            msg.add_attachment(f.read(), maintype="text", subtype="csv",
                               filename=os.path.basename(ruta))
    with smtplib.SMTP_SSL(os.getenv("EMAIL_SMTP") or "smtp.gmail.com", 465) as s:
        s.login(usuario, clave)
        s.send_message(msg)


def telegram_documento(ruta, texto=""):
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    with open(ruta, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                          data={"chat_id": chat, "caption": texto[:1000], "parse_mode": "HTML"},
                          files={"document": (os.path.basename(ruta), f, "text/html")}, timeout=60)
    if not r.ok:
        print(f"[error] Telegram documento: {r.text}")
