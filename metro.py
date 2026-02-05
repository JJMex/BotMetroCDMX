import os
import time
import requests
import feedparser
import random
from datetime import datetime, timedelta
import pytz
from ntscraper import Nitter

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_USER = "MetroCDMX"

# RSS Google News para Metro CDMX (Buscamos: Metro CDMX retraso/falla)
RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"

# Palabras clave
PALABRAS_CLAVE = [
    "retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", 
    "caos", "lento", "espera", "sin servicio", "línea", "estación", 
    "#MetroAlMomento", "#AvisoMetro"
]

IGNORAR = ["buenos días", "uso de cubrebocas", "tarjeta", "ingreso", "arte", "exposición", "domingos y días festivos"]

def obtener_hora_cdmx():
    utc_now = datetime.utcnow()
    return utc_now - timedelta(hours=6)

def parsear_fecha_nitter(fecha_str):
    try:
        fecha_str = fecha_str.replace("·", "").replace("UTC", "").strip()
        return datetime.strptime(fecha_str, "%b %d, %Y %I:%M %p").replace(tzinfo=pytz.utc)
    except: return None

def enviar_telegram(mensaje):
    if not TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': CHAT_ID, 'text': mensaje, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        requests.post(url, data=data)
    except Exception as e: print(f"Error TG: {e}")

def verificar_horario_servicio():
    ahora = obtener_hora_cdmx()
    dia_semana = ahora.weekday()
    hora = ahora.hour
    minuto = ahora.minute
    
    if dia_semana <= 4 and hora == 5 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO</b>\n\nEl Metro inicia operaciones. ¡Toma precauciones!"
    elif hora == 23 and minuto >= 30:
        return "🔴 <b>CIERRE DE SERVICIO</b>\n\nEl servicio está por concluir."
    return None

def revisar_metro():
    print("🚇 Iniciando Vigilancia Híbrida (Twitter + Noticias)...")
    reportes_encontrados = False
    twitter_funciono = False

    # ------------------------------------------------------
    # 1. INTENTO DE TWITTER (Puede fallar por bloqueo IP)
    # ------------------------------------------------------
    try:
        scraper = Nitter(log_level=1, skip_instance_check=False)
        # Solo 2 intentos para no perder tiempo si está bloqueado
        for i in range(2):
            try:
                tweets_data = scraper.get_tweets(TARGET_USER, mode='user', number=10)
                if tweets_data and 'tweets' in tweets_data and len(tweets_data['tweets']) > 0:
                    twitter_funciono = True
                    for tweet in tweets_data['tweets']:
                        texto = tweet['text'].lower()
                        # Lógica simplificada de fecha
                        es_reciente = True # Asumimos reciente si está en el top 10 para asegurar
                        
                        if any(p in texto for p in PALABRAS_CLAVE) and not any(ign in texto for ign in IGNORAR):
                            msg = f"🚨 <b>ALERTA TWITTER</b> 🚨\n\n{tweet['text']}\n\n<a href='{tweet['link']}'>Ver Fuente</a>"
                            enviar_telegram(msg)
                            reportes_encontrados = True
                    break # Salir del loop si funcionó
            except:
                time.sleep(2)
    except Exception as e:
        print(f"Twitter Error: {e}")

    # ------------------------------------------------------
    # 2. INTENTO DE GOOGLE NEWS (Respaldo Seguro)
    # ------------------------------------------------------
    try:
        print("📰 Revisando Noticias...")
        feed = feedparser.parse(RSS_URL)
        tz_mx = pytz.timezone('America/Mexico_City')
        limite = datetime.now(tz_mx) - timedelta(minutes=60)

        for entrada in feed.entries:
            try:
                # Filtrar por fecha (última hora)
                if hasattr(entrada, 'published_parsed'):
                    fecha = datetime(*entrada.published_parsed[:6], tzinfo=pytz.utc).astimezone(tz_mx)
                    if fecha > limite:
                        titulo = entrada.title
                        # Solo enviar si menciona palabras clave graves
                        if any(p in titulo.lower() for p in ["retraso", "caos", "falla", "humo", "detenido"]):
                            msg = f"📰 <b>NOTICIA METRO ({fecha.strftime('%H:%M')})</b>\n\n{titulo}\n\n<a href='{entrada.link}'>Leer Nota</a>"
                            enviar_telegram(msg)
                            reportes_encontrados = True
            except: continue
    except Exception as e:
        print(f"RSS Error: {e}")

    # ------------------------------------------------------
    # 3. CONCLUSIÓN
    # ------------------------------------------------------
    if not reportes_encontrados:
        origen = "Twitter y Noticias" if twitter_funciono else "Noticias (Twitter Bloqueado)"
        print("✅ Sin novedades.")
        enviar_telegram(f"✅ <b>Estado del Metro:</b> Sin reportes graves en la última hora.\nFuente: {origen} 🚇")

if __name__ == "__main__":
    enviar_telegram("🚇 <b>SISTEMA METRO EN LÍNEA</b>\n\n"
        "Conectando con la red de movilidad...\n"
        "<i>Buscando alertas recientes...</i>")
    time.sleep(2)
    
    horario = verificar_horario_servicio()
    if horario: enviar_telegram(horario)
    
    revisar_metro()
