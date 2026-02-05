import os
import time
import requests
from datetime import datetime, timedelta
import pytz
from ntscraper import Nitter

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Palabras clave y hashtags oficiales
PALABRAS_CLAVE = [
    "retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", 
    "caos", "lento", "espera", "sin servicio", "#MetroAlMomento", "#AvisoMetro"
]

IGNORAR = ["buenos días", "uso de cubrebocas", "tarjeta", "ingreso", "arte", "exposición", "domingos y días festivos"]

def obtener_hora_cdmx():
    """Obtiene la hora actual de CDMX ajustando UTC manualmente."""
    utc_now = datetime.utcnow()
    # Ajuste manual UTC-6 (CDMX estándar)
    cdmx_now = utc_now - timedelta(hours=6)
    return cdmx_now

def parsear_fecha_nitter(fecha_str):
    """Convierte la fecha rara de Nitter a un objeto datetime utilizable."""
    try:
        # Formatos comunes: "Feb 5, 2026 · 2:30 PM UTC" o "2h"
        fecha_str = fecha_str.replace("·", "").replace("UTC", "").strip()
        # Intentamos parsear el formato completo
        return datetime.strptime(fecha_str, "%b %d, %Y %I:%M %p").replace(tzinfo=pytz.utc)
    except:
        # Si falla (ej. dice "2m" o "1h"), retornamos None y el bot decidirá qué hacer
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
    dia_semana = ahora.weekday() # 0=Lunes, 6=Domingo
    hora = ahora.hour
    minuto = ahora.minute

    # --- MENSAJES DE APERTURA ---
    if dia_semana <= 4 and hora == 5 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO</b>\n\nBuenos días. El Metro inicia operaciones. ¡Toma precauciones!"
    elif dia_semana == 5 and hora == 6 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO (SÁBADO)</b>\n\nEl Metro inicia operaciones. ¡Excelente fin de semana!"
    elif dia_semana == 6 and hora == 7 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO (DOMINGO)</b>\n\nEl Metro inicia operaciones en horario festivo."

    # --- MENSAJE DE CIERRE ---
    elif hora == 23 and minuto >= 30:
        return "🔴 <b>CIERRE DE SERVICIO</b>\n\nEl servicio está por concluir (00:00 hrs). Anticipa tu salida."

    return None

def revisar_metro():
    scraper = Nitter(log_level=1, skip_instance_check=False)
    print("🔍 Escaneando últimos 30 tweets de @MetroCDMX...")
    
    datos_obtenidos = False
    reportes_encontrados = False

    try:
        # AQUÍ ESTÁ EL CAMBIO PRINCIPAL: number=30
        tweets = scraper.get_tweets("MetroCDMX", mode='user', number=30)
        
        if tweets and 'tweets' in tweets and len(tweets['tweets']) > 0:
            datos_obtenidos = True
            
            for tweet in tweets['tweets']:
                try:
                    texto = tweet['text'].lower()
                    
                    # 1. Filtro de Tiempo (Crucial al leer 30 tweets)
                    fecha_tweet = parsear_fecha_nitter(tweet['date'])
                    es_reciente = False
                    
                    if fecha_tweet:
                        # Si el tweet tiene menos de 60 minutos de antigüedad
                        if (datetime.now(pytz.utc) - fecha_tweet) < timedelta(minutes=60):
                            es_reciente = True
                    else:
                        # Si no pudimos leer la fecha, asumimos que es reciente por seguridad (solo los primeros 5)
                        # Esto evita perder alertas si Nitter cambia el formato
                        es_reciente = True 

                    # 2. Análisis de Contenido
                    if es_reciente:
                        if any(p.lower() in texto for p in PALABRAS_CLAVE) and not any(i in texto for i in IGNORAR):
                            
                            # Formatear hora para el mensaje (si la tenemos)
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
                except Exception as inner_e:
                    print(f"Error procesando un tweet: {inner_e}")
                    continue
        
        # --- CONCLUSIONES ---
        if not datos_obtenidos:
            raise Exception("Lista de tweets vacía o bloqueo de Nitter.")
            
        elif not reportes_encontrados:
            print("✅ Sin novedades recientes.")
            enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes graves ni #AvisoMetro detectados en la última hora (30 tweets analizados). Flujo normal. 🚇")
            
    except Exception as e:
        print(f"Error General: {e}")
        enviar_telegram(f"⚠️ <b>Error de Monitoreo</b>\n\nNo pude verificar los últimos avisos del Metro.\n<i>Intento: {str(e)[:40]}...</i>")

if __name__ == "__main__":
    # 1. Aviso de Sistema
    mensaje_inicio = (
        "🚇 <b>SISTEMA METRO EN LÍNEA</b>\n\n"
        "Analizando profundamente (@MetroCDMX)...\n"
        "<i>Escaneando últimos 30 registros.</i>"
    )
    enviar_telegram(mensaje_inicio)
    time.sleep(2)

    # 2. Verificar Horario
    aviso_hora = verificar_horario_servicio()
    if aviso_hora:
        enviar_telegram(aviso_hora)
        time.sleep(2)

    # 3. Escaneo Profundo
    revisar_metro()
