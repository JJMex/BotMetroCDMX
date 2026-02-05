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
    data = {'chat_id': CHAT_ID, 'text': mensaje, 'parse_mode': 'Markdown'}
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
                
                # 1. Filtro de antigüedad (Solo tweets de hace menos de 40 min aprox)
                # (Nota: Nitter a veces no da fecha exacta fácil, así que confiamos en que son los más recientes)
                
                # 2. Detectar Problemas
                if any(p in texto for p in PALABRAS_CLAVE) and not any(i in texto for i in IGNORAR):
                    mensaje = f"🚨 **ALERTA METRO** 🚨\n\n{tweet['text']}\n\n[Ver Tweet]({tweet['link']})"
                    enviar_telegram(mensaje)
                    reportes_encontrados = True
        
        # --- NUEVA FUNCIONALIDAD: AVISO DE CALMA ---
        if not reportes_encontrados:
            print("✅ Sin novedades.")
            enviar_telegram("✅ **Estado del Metro:** Sin reportes graves detectados en los últimos minutos. Buen viaje. 🚇")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    revisar_metro()
