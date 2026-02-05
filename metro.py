import os
import requests
import time
from datetime import datetime, timedelta
import pytz
from ntscraper import Nitter

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TWITTER_USER = "MetroCDMX"

# Palabras clave para detectar problemas o avisos reales
PALABRAS_CLAVE = [
    "avance", "trenes", "marcha", "lenta", "seguridad", # Velocidad
    "retraso", "corte", "corriente", "interrupción", # Fallas
    "persona", "ajuste", "revisión", "vías", "desalojo", # Incidentes graves
    "servicio", "estación", "cerrada", "apoya", "rtp", # Cierres
    "lluvia", "tláloc", "contingencia", # Clima
    "aviso", "importante", "informamos" # General
]

def enviar_telegram(mensaje):
    if not TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML", "disable_web_page_preview": False}
        requests.post(url, data=payload)
    except Exception as e: print(f"Error TG: {e}")

def parsear_fecha_nitter(fecha_str):
    try:
        # Limpieza de formato de fecha que entrega Nitter
        fecha_str = fecha_str.replace("·", "").replace("UTC", "").strip()
        return datetime.strptime(fecha_str, "%b %d, %Y %I:%M %p").replace(tzinfo=pytz.utc)
    except: return None

def revisar_metro():
    print(f"--- Revisando @{TWITTER_USER} ---")
    try:
        scraper = Nitter(log_level=1, skip_instance_check=False)
        tweets = scraper.get_tweets(TWITTER_USER, mode='user', number=5)

        if not tweets or 'tweets' not in tweets: 
            print("No se pudieron leer tweets.")
            return

        tz_mx = pytz.timezone('America/Mexico_City')
        ahora_utc = datetime.now(pytz.utc)

        for tweet in tweets['tweets']:
            # 1. Filtro de Tiempo: Solo tweets de los últimos 40 mins
            fecha_utc = parsear_fecha_nitter(tweet['date'])
            if not fecha_utc: continue

            diferencia = ahora_utc - fecha_utc
            if diferencia > timedelta(minutes=40):
                continue 

            texto = tweet['text'].lower()

            # 2. Filtro Anti-Spam: Ignorar respuestas a usuarios
            if tweet['text'].startswith("@"):
                continue

            # 3. Filtro de Relevancia: Buscar palabras clave
            if any(palabra in texto for palabra in PALABRAS_CLAVE):

                hora_mx = fecha_utc.astimezone(tz_mx).strftime("%I:%M %p")

                # Emojis según el problema
                emoji = "🚇"
                if "lenta" in texto or "retraso" in texto or "lluvia" in texto: emoji = "🐢"
                if "corte" in texto or "persona" in texto or "cerrada" in texto: emoji = "🚨"
                if "avance" in texto: emoji = "🚦"

                msg = (f"{emoji} <b>ESTADO DEL METRO</b>\n"
                       f"🕒 <i>{hora_mx}</i>\n\n"
                       f"{tweet['text']}\n\n"
                       f"🔗 <a href='{tweet['link']}'>Ver tweet original</a>")

                enviar_telegram(msg)
                print(f"Alerta enviada: {tweet['text'][:30]}...")
                time.sleep(2)
            else:
                print(f"Ignorado (Irrelevante): {tweet['text'][:30]}...")

    except Exception as e: print(f"Error General: {e}")

if __name__ == "__main__":
    # --- MENSAJE DE ARRANQUE (PRUEBA) ---
    mensaje_inicio = (
        "✅ <b>SISTEMA EN LÍNEA</b>\n\n"
        "La conexión se ha establecido correctamente.\n"
        "<i>El bot realizará el análisis del sistema en breve.</i>"
    )
    enviar_telegram(mensaje_inicio)

    # --- EJECUCIÓN DEL ANÁLISIS ---
    revisar_metro()
