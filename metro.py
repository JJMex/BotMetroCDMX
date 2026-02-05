import os
import time
import requests
from ntscraper import Nitter

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Palabras que indican problemas reales
PALABRAS_CLAVE = ["retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", "caos", "lento", "espera"]
# Palabras para ignorar (avisos institucionales aburridos)
IGNORAR = ["buenos días", "horario de servicio", "domingos y días festivos", "uso de cubrebocas", "tarjeta", "ingreso"]

def enviar_telegram(mensaje):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    # CAMBIO IMPORTANTE: Usamos 'HTML' para que las negritas <b> funcionen
    data = {'chat_id': CHAT_ID, 'text': mensaje, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    requests.post(url, data=data)

def revisar_metro():
    scraper = Nitter(log_level=1, skip_instance_check=False)
    print("🔍 Revisando @MetroCDMX...")
    
    try:
        # Buscamos los últimos 5 tweets de la cuenta oficial
        tweets = scraper.get_tweets("MetroCDMX", mode='user', number=5)
        
        reportes_encontrados = False
        
        if 'tweets' in tweets and len(tweets['tweets']) > 0:
            for tweet in tweets['tweets']:
                texto = tweet['text'].lower()
                
                # Detectar Problemas
                if any(p in texto for p in PALABRAS_CLAVE) and not any(i in texto for i in IGNORAR):
                    # Formato HTML para la alerta
                    mensaje = f"🚨 <b>ALERTA METRO</b> 🚨\n\n{tweet['text']}\n\n<a href='{tweet['link']}'>Ver Tweet Original</a>"
                    enviar_telegram(mensaje)
                    reportes_encontrados = True
        
        # --- LÓGICA DE "TODO BIEN" ---
        # Si después de revisar los 5 tweets no se activó ninguna alerta:
        if not reportes_encontrados:
            print("✅ Sin novedades.")
            enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes graves detectados en los últimos minutos. Todo fluye con normalidad. 🚇")
            
    except Exception as e:
        print(f"Error: {e}")
        # Opcional: Avisar si falló el scrapper
        # enviar_telegram(f"⚠️ Error al consultar el Metro: {e}")

if __name__ == "__main__":
    # 1. Mensaje de arranque (Con formato HTML corregido)
    mensaje_inicio = (
        "⚙️ <b>SISTEMA EN LÍNEA</b>\n\n"
        "La conexión se ha establecido correctamente.\n"
        "<i>El bot está analizando el estado del servicio en tiempo real...</i>"
    )
    enviar_telegram(mensaje_inicio)

    # Pequeña pausa dramática de 2 segundos para que no lleguen los mensajes pegados
    time.sleep(2)

    # 2. Ejecutar análisis (Mandará Alerta o Mensaje de "Todo Bien")
    revisar_metro()
