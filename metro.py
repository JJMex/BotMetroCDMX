import os
import time
import requests
from datetime import datetime, timedelta
from ntscraper import Nitter

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 1. AGREGAMOS LOS HASHTAGS A LAS PALABRAS CLAVE
# Ahora detecta si el tweet contiene estos hashtags oficiales de aviso
PALABRAS_CLAVE = [
    "retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", 
    "caos", "lento", "espera", "#MetroAlMomento", "#AvisoMetro"
]

IGNORAR = ["buenos días", "uso de cubrebocas", "tarjeta", "ingreso", "arte", "exposición"]

def obtener_hora_cdmx():
    # GitHub Actions usa UTC. CDMX es UTC-6 (aproximadamente, sin horario de verano)
    utc_now = datetime.utcnow()
    cdmx_now = utc_now - timedelta(hours=6)
    return cdmx_now

def enviar_telegram(mensaje):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {'chat_id': CHAT_ID, 'text': mensaje, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    requests.post(url, data=data)

def verificar_horario_servicio():
    """
    Verifica si estamos en horario de apertura o cierre para mandar aviso.
    """
    ahora = obtener_hora_cdmx()
    dia_semana = ahora.weekday() # 0=Lunes, 6=Domingo
    hora = ahora.hour
    minuto = ahora.minute

    # --- MENSAJE DE APERTURA ---
    # Lunes a Viernes (0-4) abre a las 5:00 AM
    if dia_semana <= 4 and hora == 5 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO</b>\n\nBuenos días. El Sistema de Transporte Colectivo Metro inicia operaciones. ¡Toma precauciones!"
    
    # Sábado (5) abre a las 6:00 AM
    elif dia_semana == 5 and hora == 6 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO (SÁBADO)</b>\n\nEl Metro inicia operaciones. ¡Excelente fin de semana!"
    
    # Domingo (6) abre a las 7:00 AM
    elif dia_semana == 6 and hora == 7 and minuto < 30:
        return "🟢 <b>INICIO DE SERVICIO (DOMINGO)</b>\n\nEl Metro inicia operaciones en horario festivo. ¡Buen viaje!"

    # --- MENSAJE DE CIERRE ---
    # Cierra a las 24:00 (Revisamos entre 23:30 y 23:59)
    elif hora == 23 and minuto >= 30:
        return "🔴 <b>CIERRE DE SERVICIO</b>\n\nEl servicio del Metro está por concluir (00:00 hrs). Si sigues en la red, anticipa tu salida."

    return None

def revisar_metro():
    scraper = Nitter(log_level=1, skip_instance_check=False)
    print("🔍 Revisando @MetroCDMX con hashtags...")
    
    try:
        # Buscamos tweets recientes
        tweets = scraper.get_tweets("MetroCDMX", mode='user', number=6)
        
        reportes_encontrados = False
        
        if 'tweets' in tweets and len(tweets['tweets']) > 0:
            for tweet in tweets['tweets']:
                texto = tweet['text'].lower()
                
                # Detectamos palabras clave O hashtags
                if any(p.lower() in texto for p in PALABRAS_CLAVE) and not any(i in texto for i in IGNORAR):
                    
                    # Formateamos el mensaje
                    mensaje = (
                        f"🚨 <b>ALERTA METRO</b> 🚨\n\n"
                        f"{tweet['text']}\n\n"
                        f"<a href='{tweet['link']}'>Ver Aviso Oficial</a>"
                    )
                    enviar_telegram(mensaje)
                    reportes_encontrados = True
        
        # Mensaje si todo está tranquilo
        if not reportes_encontrados:
            print("✅ Sin novedades.")
            enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes graves, #AvisoMetro o retrasos detectados en los últimos minutos. Flujo normal. 🚇")
            
    except Exception as e:
        print(f"Error Scraper: {e}")
        # Enviar un mensaje de error 'silencioso' a la consola, no al chat para no molestar

if __name__ == "__main__":
    # 1. Mensaje de Sistema Online
    mensaje_inicio = (
        "⚙️ <b>SISTEMA EN LÍNEA</b>\n\n"
        "Conexión establecida.\n"
        "<i>Analizando #MetroAlMomento y estado de la red...</i>"
    )
    enviar_telegram(mensaje_inicio)
    time.sleep(2)

    # 2. Verificar si hay que avisar de Apertura/Cierre
    mensaje_horario = verificar_horario_servicio()
    if mensaje_horario:
        enviar_telegram(mensaje_horario)
        time.sleep(2)

    # 3. Revisar Alertas de Tráfico/Fallas
    revisar_metro()
