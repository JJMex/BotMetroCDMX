import os
import time
import requests
from datetime import datetime, timedelta
import pytz
from ntscraper import Nitter
import random

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

PALABRAS_CLAVE = [
    "retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", 
    "caos", "lento", "espera", "sin servicio", "#MetroAlMomento", "#AvisoMetro"
]

IGNORAR = ["buenos días", "uso de cubrebocas", "tarjeta", "ingreso", "arte", "exposición", "domingos y días festivos"]

def obtener_hora_cdmx():
    utc_now = datetime.utcnow()
    return utc_now - timedelta(hours=6)

def parsear_fecha_nitter(fecha_str):
    try:
        fecha_str = fecha_str.replace("·", "").replace("UTC", "").strip()
        return datetime.strptime(fecha_str, "%b %d, %Y %I:%M %p").replace(tzinfo=pytz.utc)
    except:
        return None

def enviar_telegram(mensaje):
    if not TOKEN or not CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {'chat_id': CHAT_ID, 'text': mensaje, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error Telegram: {e}")

def verificar_horario_servicio():
    ahora = obtener_hora_cdmx()
    dia_semana = ahora.weekday()
    hora = ahora.hour
    minuto = ahora.minute

    if dia_semana <= 4 and hora == 5 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO</b>\n\nBuenos días. El Metro inicia operaciones."
    elif dia_semana == 5 and hora == 6 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO (SÁBADO)</b>\n\nEl Metro inicia operaciones."
    elif dia_semana == 6 and hora == 7 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO (DOMINGO)</b>\n\nEl Metro inicia operaciones."
    elif hora == 23 and minuto >= 30:
        return "🔴 <b>CIERRE DE SERVICIO</b>\n\nEl servicio está por concluir (00:00 hrs)."
    return None

def revisar_metro():
    print("🔍 Iniciando escaneo robusto de @MetroCDMX...")
    
    # --- SISTEMA DE REINTENTOS ---
    # Intentaremos hasta 3 veces obtener los datos antes de rendirnos
    max_intentos = 3
    exito = False
    error_final = ""

    for intento in range(1, max_intentos + 1):
        try:
            print(f"🔄 Intento {intento} de {max_intentos}...")
            
            # Instanciamos el scraper en cada intento para buscar un servidor nuevo si falla
            scraper = Nitter(log_level=1, skip_instance_check=False)
            
            # Bajamos a 20 tweets para reducir probabilidad de bloqueo, sigue siendo suficiente
            tweets = scraper.get_tweets("MetroCDMX", mode='user', number=20)
            
            if tweets and 'tweets' in tweets and len(tweets['tweets']) > 0:
                # ¡CONEXIÓN EXITOSA! Procesamos y salimos del bucle
                procesar_tweets(tweets['tweets'])
                exito = True
                break # Romper el ciclo for
            else:
                raise Exception("Lista vacía recibida.")
                
        except Exception as e:
            print(f"⚠️ Fallo intento {intento}: {e}")
            error_final = str(e)
            time.sleep(5) # Esperar 5 segundos antes de reintentar
    
    if not exito:
        enviar_telegram(f"⚠️ <b>Error de Monitoreo Persistente</b>\n\nTwitter rechazó {max_intentos} intentos de conexión.\n<i>Error: {error_final[:50]}...</i>")

def procesar_tweets(lista_tweets):
    reportes_encontrados = False
    
    for tweet in lista_tweets:
        try:
            texto = tweet['text'].lower()
            fecha_tweet = parsear_fecha_nitter(tweet['date'])
            
            # Filtro de antigüedad (60 mins)
            es_reciente = False
            if fecha_tweet:
                if (datetime.now(pytz.utc) - fecha_tweet) < timedelta(minutes=60):
                    es_reciente = True
            else:
                es_reciente = True # Si falla fecha, asumir reciente por seguridad

            if es_reciente:
                if any(p.lower() in texto for p in PALABRAS_CLAVE) and not any(i in texto for i in IGNORAR):
                    hora_msg = ""
                    if fecha_tweet:
                        tz_mx = pytz.timezone('America/Mexico_City')
                        hora_msg = f" <i>({fecha_tweet.astimezone(tz_mx).strftime('%I:%M %p')})</i>"

                    mensaje = (
                        f"🚨 <b>ALERTA METRO{hora_msg}</b> 🚨\n\n"
                        f"{tweet['text']}\n\n"
                        f"<a href='{tweet['link']}'>Ver Aviso Oficial</a>"
                    )
                    enviar_telegram(mensaje)
                    reportes_encontrados = True
        except: continue

    if not reportes_encontrados:
        print("✅ Sin novedades.")
        enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes graves en los últimos 20 tweets analizados. Flujo normal. 🚇")

if __name__ == "__main__":
    mensaje_inicio = (
        "🚇 <b>SISTEMA METRO</b>\n"
        "<i>Intentando conexión segura con Nitter...</i>"
    )
    enviar_telegram(mensaje_inicio)
    time.sleep(2)

    aviso_hora = verificar_horario_servicio()
    if aviso_hora:
        enviar_telegram(aviso_hora)
        time.sleep(2)

    revisar_metro()
