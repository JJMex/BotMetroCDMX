import os
import time
import requests
import random
from datetime import datetime, timedelta
import pytz
from ntscraper import Nitter

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_USER = "MetroCDMX"  # Usuario oficial asegurado

# Palabras de alerta y hashtags oficiales
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
    print(f"🔍 Iniciando escaneo de @{TARGET_USER}...")
    
    # --- SISTEMA DE REINTENTOS HÍBRIDO ---
    max_intentos = 5
    exito = False
    error_log = ""
    scraper = Nitter(log_level=1, skip_instance_check=False)

    for intento in range(1, max_intentos + 1):
        try:
            print(f"🔄 Intento {intento} de {max_intentos}...")
            tweets_data = None
            
            # ESTRATEGIA A: Intentar ver el perfil directo (Intentos 1 y 2)
            if intento <= 2:
                print("   👉 Estrategia: Perfil Directo")
                tweets_data = scraper.get_tweets(TARGET_USER, mode='user', number=15)
            
            # ESTRATEGIA B: Usar el buscador si el perfil falla (Intentos 3, 4, 5)
            else:
                print(f"   👉 Estrategia: Búsqueda (from:{TARGET_USER})")
                tweets_data = scraper.get_tweets(f"from:{TARGET_USER}", mode='term', number=15)
            
            # --- VERIFICACIÓN ANTI-ERROR "INDEX OUT OF RANGE" ---
            # Solo procesamos si REALMENTE llegaron tweets
            if tweets_data and 'tweets' in tweets_data and len(tweets_data['tweets']) > 0:
                print("   ✅ ¡Datos recibidos!")
                procesar_tweets(tweets_data['tweets'])
                exito = True
                break # Éxito rotundo, salimos del ciclo
            else:
                # Si llega vacío, lanzamos error controlado para forzar el siguiente intento
                raise Exception("Lista de tweets vacía (Bloqueo de instancia)")
                
        except Exception as e:
            print(f"⚠️ Fallo intento {intento}: {e}")
            error_log = str(e)
            # Espera progresiva: 5s, 10s, 15s...
            time.sleep(intento * 5)
    
    if not exito:
        enviar_telegram(f"⚠️ <b>Alerta de Conexión</b>\n\nNo pude conectar con @{TARGET_USER} tras {max_intentos} intentos.\n<i>Twitter está bloqueando las consultas temporales.</i>")

def procesar_tweets(lista_tweets):
    reportes_encontrados = False
    
    for tweet in lista_tweets:
        try:
            texto = tweet['text'].lower()
            fecha_tweet = parsear_fecha_nitter(tweet['date'])
            
            # Filtro de antigüedad (60 mins) para evitar spam de noticias viejas
            es_reciente = False
            if fecha_tweet:
                if (datetime.now(pytz.utc) - fecha_tweet) < timedelta(minutes=60):
                    es_reciente = True
            else:
                es_reciente = True # Si falla la fecha, asumimos reciente por seguridad

            if es_reciente:
                # Verificamos palabras clave en el texto
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
        enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes graves en la última hora. Todo parece fluir. 🚇")

if __name__ == "__main__":
    mensaje_inicio = (
        "🚇 <b>SISTEMA METRO EN LÍNEA</b>\n\n"
        "Conectando con la red de movilidad...\n"
        "<i>Buscando alertas recientes...</i>"
    )
    enviar_telegram(mensaje_inicio)
    
    time.sleep(3)

    aviso_hora = verificar_horario_servicio()
    if aviso_hora:
        enviar_telegram(aviso_hora)
        time.sleep(3)

    revisar_metro()
