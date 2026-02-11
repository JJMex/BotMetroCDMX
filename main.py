import os
import time
import requests
import feedparser
import pytz
from datetime import datetime, timedelta
from ntscraper import Nitter

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Filtros y Búsqueda
RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"
PALABRAS_CLAVE = ["retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", "caos", "lento", "espera", "sin servicio"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos"]

def enviar_telegram(mensaje):
    if not TOKEN or not CHAT_ID: return
    for i in range(1, 4):
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            data = {'chat_id': CHAT_ID, 'text': mensaje, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
            r = requests.post(url, data=data, timeout=10)
            if r.status_code == 200: break
            time.sleep(5)
        except: time.sleep(5)

def verificar_horario_servicio(ahora):
    dia = ahora.weekday() 
    hora = ahora.hour
    
    if dia <= 4 and hora == 5:
        return "🚇 <b>INICIO DE SERVICIO</b>\n──────────────────\nLa red del Metro inicia operaciones. ¡Buen viaje!"
    elif dia == 5 and hora == 6:
        return "🚇 <b>INICIO DE SERVICIO (SÁBADO)</b>\n──────────────────\nInicia la operación de fin de semana."
    elif dia == 6 and hora == 7:
        return "🚇 <b>INICIO DE SERVICIO (DOMINGO)</b>\n──────────────────\nEl servicio dominical ha comenzado."
    elif hora == 0:
        return "💤 <b>CIERRE DE SERVICIO</b>\n──────────────────\nLa red ha concluido sus operaciones por hoy. ¡Buenas noches!"
    
    return None

def revisar_incidentes(ahora):
    incidentes = []
    
    # 1. GOOGLE NEWS
    try:
        feed = feedparser.parse(RSS_URL)
        limite = ahora - timedelta(minutes=65)
        for e in feed.entries:
            if hasattr(e, 'published_parsed'):
                f = datetime(*e.published_parsed[:6], tzinfo=pytz.utc).astimezone(ahora.tzinfo)
                if f > limite:
                    t = e.title.lower()
                    if any(p in t for p in PALABRAS_CLAVE):
                        incidentes.append(f"📰 <b>NOTICIA:</b> {e.title}\n🔗 <a href='{e.link}'>Ver Nota</a>")
    except: pass

    # 2. TWITTER (Nitter)
    try:
        scraper = Nitter(log_level=1, skip_instance_check=False)
        data = scraper.get_tweets("MetroCDMX", mode='user', number=10)
        if data and 'tweets' in data:
            for t in data['tweets']:
                txt = t['text'].lower()
                if any(p in txt for p in PALABRAS_CLAVE) and not any(i in txt for i in IGNORAR):
                    if "m" in t['date'] or "h" in t['date']:
                        incidentes.append(f"🚨 <b>AVISO OFICIAL:</b> {t['text']}\n🔗 <a href='{t['link']}'>Ver Tweet</a>")
    except: pass

    return incidentes

def main():
    tz_mx = pytz.timezone('America/Mexico_City')
    ahora = datetime.now(tz_mx)
    
    # --- 1. MENSAJE DE CONEXIÓN (Siempre se envía al iniciar) ---
    enviar_telegram("📡 <i>Conectando con la red de movilidad y analizando reportes ciudadanos...</i>")
    time.sleep(2) # Pausa para simular el escaneo

    # --- 2. REVISAR TURNO (Apertura/Cierre) ---
    mensaje_turno = verificar_horario_servicio(ahora)
    if mensaje_turno:
        enviar_telegram(mensaje_turno)
        return

    # --- 3. REVISAR INCIDENTES ---
    reportes = revisar_incidentes(ahora)
    
    if reportes:
        hora_str = ahora.strftime('%I:%M %p')
        header = f"🚨 <b>INCIDENCIAS DETECTADAS ({hora_str})</b>\n──────────────────\n"
        reportes_unicos = list(dict.fromkeys(reportes))
        enviar_telegram(header + "\n\n".join(reportes_unicos))
    else:
        # --- 4. MENSAJE DE NORMALIDAD (Si no hay fallas) ---
        enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes de fallas o retrasos detectados en la última hora.\n<i>Sistema trabajando con normalidad.</i>")

if __name__ == "__main__":
    main()
