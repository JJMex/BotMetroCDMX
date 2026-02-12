import os
import time
import requests
import feedparser
import pytz
from datetime import datetime, timedelta
from ntscraper import Nitter

# --- CONFIGURACIÓN DE IDENTIDAD JJMEX HUB ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')

# Configuración de Destinos (Dual Broadcast)
ID_GRUPO = os.environ.get('TELEGRAM_CHAT_ID') 
ID_CANAL = os.environ.get('TELEGRAM_CHANNEL_ID') 

# Creamos la lista de objetivos. Si falta alguno, el bot lo ignora y sigue con el otro.
DESTINATARIOS = [id_ for id_ in [ID_GRUPO, ID_CANAL] if id_]

# Filtros y Búsqueda
RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"
PALABRAS_CLAVE = ["retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", "caos", "lento", "espera", "sin servicio"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos"]

def enviar_telegram(mensaje):
    """
    Función de envío masivo: Recorre la lista de destinatarios (Grupo y Canal)
    y envía el mensaje a cada uno.
    """
    if not TOKEN:
        print("❌ Error: Falta el TELEGRAM_TOKEN")
        return

    if not DESTINATARIOS:
        print("⚠️ Advertencia: No hay destinos configurados (ni Grupo ni Canal).")
        return

    print(f"📡 Iniciando transmisión a {len(DESTINATARIOS)} destinos...")

    for chat_id in DESTINATARIOS:
        enviado = False
        for i in range(1, 4): # 3 intentos por destino
            try:
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                data = {
                    'chat_id': chat_id, 
                    'text': mensaje, 
                    'parse_mode': 'HTML', 
                    'disable_web_page_preview': True
                }
                r = requests.post(url, data=data, timeout=10)
                
                if r.status_code == 200:
                    tipo_destino = "CANAL" if "@" in str(chat_id) else "GRUPO"
                    print(f"✅ Mensaje enviado a {tipo_destino}: {chat_id}")
                    enviado = True
                    break
                else:
                    print(f"⚠️ Error {r.status_code} enviando a {chat_id}: {r.text}")
                    time.sleep(2)
            except Exception as e:
                print(f"❌ Error de conexión con {chat_id}: {e}")
                time.sleep(2)
        
        if not enviado:
            print(f"💀 Falló envío definitivo a {chat_id}")

def verificar_horario_servicio(ahora):
    dia = ahora.weekday() 
    hora = ahora.hour
    
    # Lógica de apertura y cierre
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
        print("🔎 Escaneando Google News...")
        feed = feedparser.parse(RSS_URL)
        limite = ahora - timedelta(minutes=65)
        for e in feed.entries:
            if hasattr(e, 'published_parsed'):
                # Convertir fecha de la noticia a zona horaria local
                f = datetime(*e.published_parsed[:6], tzinfo=pytz.utc).astimezone(ahora.tzinfo)
                if f > limite:
                    t = e.title.lower()
                    if any(p in t for p in PALABRAS_CLAVE):
                        incidentes.append(f"📰 <b>NOTICIA:</b> {e.title}\n🔗 <a href='{e.link}'>Ver Nota</a>")
    except Exception as e: 
        print(f"⚠️ Error en Google News: {e}")

    # 2. TWITTER (Nitter)
    try:
        print("🔎 Escaneando Twitter (MetroCDMX)...")
        scraper = Nitter(log_level=1, skip_instance_check=False)
        data = scraper.get_tweets("MetroCDMX", mode='user', number=10)
        if data and 'tweets' in data:
            for t in data['tweets']:
                txt = t['text'].lower()
                if any(p in txt for p in PALABRAS_CLAVE) and not any(i in txt for i in IGNORAR):
                    # Filtro simple de tiempo (revisamos si dice 'm' de minutos o 'h' de horas recientes)
                    if "m" in t['date'] or "1h" in t['date']:
                        incidentes.append(f"🚨 <b>AVISO OFICIAL:</b> {t['text']}\n🔗 <a href='{t['link']}'>Ver Tweet</a>")
    except Exception as e: 
        print(f"⚠️ Error en Nitter: {e}")

    return incidentes

def main():
    tz_mx = pytz.timezone('America/Mexico_City')
    ahora = datetime.now(tz_mx)
    
    print(f"🏁 Iniciando escaneo JJMex a las {ahora.strftime('%H:%M:%S')}")

    # --- 1. MENSAJE DE CONEXIÓN (Siempre se envía al iniciar) ---
    # Comentado: Para no saturar el canal cada hora con "Conectando...".
    # Descomenta la siguiente línea solo si quieres ese mensaje de "ping".
    enviar_telegram("📡 <i>Conectando con la red de movilidad y analizando reportes ciudadanos...</i>")
    
    time.sleep(2) # Pausa técnica

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
        # Eliminar duplicados exactos
        reportes_unicos = list(dict.fromkeys(reportes))
        enviar_telegram(header + "\n\n".join(reportes_unicos))
    else:
        # --- 4. MENSAJE DE NORMALIDAD (Si no hay fallas) ---
        print("✅ Sin incidentes detectados.")
        enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes de fallas o retrasos detectados en la última hora.\n<i>Sistema trabajando con normalidad.</i>")

if __name__ == "__main__":
    main()
