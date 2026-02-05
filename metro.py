import os
import time
import requests
import random
import feedparser
from datetime import datetime, timedelta
import pytz
from ntscraper import Nitter

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 1. Configuración Google News
# Buscamos: Metro CDMX + (retraso O falla O caos) en la última hora
RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"

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
    print("🔍 Iniciando escaneo HÍBRIDO (Noticias + Twitter)...")
    
    reportes_encontrados = False
    twitter_exito = False # Para saber si logramos conectar con Twitter o no

    # ---------------------------------------------------------
    # PARTE 1: GOOGLE NEWS (Respaldo Seguro)
    # ---------------------------------------------------------
    try:
        print("📰 Revisando Google News...")
        feed = feedparser.parse(RSS_URL)
        tz_mx = pytz.timezone('America/Mexico_City')
        # Límite: Noticias de hace 60 minutos
        limite = datetime.now(tz_mx) - timedelta(minutes=60)

        for entrada in feed.entries:
            try:
                if hasattr(entrada, 'published_parsed'):
                    fecha = datetime(*entrada.published_parsed[:6], tzinfo=pytz.utc).astimezone(tz_mx)
                    
                    if fecha > limite:
                        titulo = entrada.title
                        # Doble verificación de palabras clave en el título
                        if any(p in titulo.lower() for p in ["retraso", "caos", "falla", "humo", "detenido", "sin servicio"]):
                            msg = f"📰 <b>NOTICIA METRO ({fecha.strftime('%H:%M')})</b>\n\n{titulo}\n\n<a href='{entrada.link}'>Leer Nota</a>"
                            enviar_telegram(msg)
                            reportes_encontrados = True
            except: continue
    except Exception as e:
        print(f"Error RSS: {e}")

    # ---------------------------------------------------------
    # PARTE 2: TWITTER (Con Reintentos)
    # ---------------------------------------------------------
    max_intentos = 5
    error_final = ""
    tweets_data = None
    scraper = Nitter(log_level=1, skip_instance_check=False)

    for intento in range(1, max_intentos + 1):
        try:
            print(f"🔄 Twitter: Intento {intento} de {max_intentos}...")
            
            if intento <= 2:
                tweets_data = scraper.get_tweets("MetroCDMX", mode='user', number=15)
            else:
                tweets_data = scraper.get_tweets("from:MetroCDMX", mode='term', number=15)
            
            if tweets_data and 'tweets' in tweets_data and len(tweets_data['tweets']) > 0:
                print("   ✅ ¡Datos de Twitter recibidos!")
                twitter_exito = True
                
                # Procesar Tweets
                for tweet in tweets_data['tweets']:
                    try:
                        texto = tweet['text'].lower()
                        fecha_tweet = parsear_fecha_nitter(tweet['date'])
                        
                        # Filtro de antigüedad (60 mins)
                        es_reciente = False
                        if fecha_tweet:
                            if (datetime.now(pytz.utc) - fecha_tweet) < timedelta(minutes=60):
                                es_reciente = True
                        else:
                            es_reciente = True # Si falla fecha, asumir reciente

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
                
                break # Éxito en Twitter, salir del bucle
            else:
                raise Exception("Lista vacía o bloqueo.")
                
        except Exception as e:
            print(f"⚠️ Fallo intento {intento}: {e}")
            error_final = str(e)
            time.sleep(random.randint(5, 15))
    
    # Si Twitter falló los 5 intentos, avisamos (pero NO nos quedamos callados si News funcionó)
    if not twitter_exito:
        enviar_telegram(f"⚠️ <b>Aviso Técnico</b>\n\nTwitter bloqueó la conexión tras {max_intentos} intentos. Se verificó el estado vía Google News.")

    # ---------------------------------------------------------
    # CONCLUSIÓN FINAL
    # ---------------------------------------------------------
    if not reportes_encontrados:
        print("✅ Sin novedades.")
        fuente = "Twitter y Noticias" if twitter_exito else "Noticias (Twitter Off)"
        enviar_telegram(f"✅ <b>Estado del Metro:</b> Sin reportes graves detectados en la última hora.\n<i>Fuente: {fuente}</i> 🚇")

if __name__ == "__main__":
    mensaje_inicio = (
        "🚇 <b>SISTEMA METRO EN LÍNEA</b>\n\n"
        "Conectando con la red de movilidad...\n"
        "<i>Escaneando Twitter y Noticias...</i>"
    )
    enviar_telegram(mensaje_inicio)
    
    time.sleep(3)

    aviso_hora = verificar_horario_servicio()
    if aviso_hora:
        enviar_telegram(aviso_hora)
        time.sleep(3)

    revisar_metro()
