import os
import time
import requests
import feedparser
import pytz
import random
from datetime import datetime, timedelta
from ntscraper import Nitter

# --- CONFIGURACIÓN DE IDENTIDAD JJMEX HUB ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ID_GRUPO = os.environ.get('TELEGRAM_CHAT_ID') 
ID_CANAL = os.environ.get('TELEGRAM_CHANNEL_ID') 

# Lista de destinos activa
DESTINATARIOS = [id_ for id_ in [ID_GRUPO, ID_CANAL] if id_]

# --- CONFIGURACIÓN DE BÚSQUEDA ---
RSS_URL = "https://news.google.com/rss/search?q=Metro+CDMX+retraso+OR+falla+OR+caos+when:1h&hl=es-419&gl=MX&ceid=MX:es-419"
PALABRAS_CLAVE = ["retraso", "marcha lenta", "falla", "desalojo", "humo", "detenido", "caos", "lento", "espera", "sin servicio", "colapso"]
IGNORAR = ["buenos días", "cubrebocas", "tarjeta", "arte", "exposición", "domingos y días festivos", "cultura"]

# --- DICCIONARIO DE LÍNEAS (MOTOR DE ETIQUETADO) ---
MAPA_LINEAS = {
    "1": "🩷 Línea 1 (Rosa)", 
    "2": "💙 Línea 2 (Azul)", 
    "3": "💚 Línea 3 (Verde)", 
    "4": "🩵 Línea 4 (Cian)", 
    "5": "💛 Línea 5 (Amarilla)", 
    "6": "❤️ Línea 6 (Roja)", 
    "7": "🧡 Línea 7 (Naranja)", 
    "8": "💚 Línea 8 (Verde)", 
    "9": "🤎 Línea 9 (Café)", 
    "a": "💜 Línea A (Férrea)",
    "b": "🩶 Línea B (Gris)",
    "12": "💛 Línea 12 (Dorada)"
}

def enviar_telegram(mensaje):
    """Envío masivo a Canal y Grupo con reintentos."""
    if not TOKEN or not DESTINATARIOS: return

    for chat_id in DESTINATARIOS:
        for _ in range(3): # 3 Intentos
            try:
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                data = {'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
                r = requests.post(url, data=data, timeout=10)
                if r.status_code == 200: break
                time.sleep(2)
            except: time.sleep(2)

def detectar_lineas(texto):
    """
    Analiza el texto buscando patrones como 'Línea 3', 'L3', 'Linea B'.
    Devuelve un string formateado con las líneas afectadas.
    """
    texto = texto.lower()
    detectadas = set()
    
    for clave, nombre in MAPA_LINEAS.items():
        # Buscamos patrones específicos para evitar falsos positivos (ej: no confundir "1 min" con "Linea 1")
        patrones = [
            f"línea {clave}", f"linea {clave}", 
            f"l{clave} ", f"l-{clave}", f"l {clave} "
        ]
        # Caso especial para letras A y B para evitar coincidir con palabras normales
        if clave in ['a', 'b']:
            patrones = [f"línea {clave}", f"linea {clave}", f"l-{clave}"]

        if any(p in texto for p in patrones):
            detectadas.add(nombre)
            
    if detectadas:
        return "\n⚠️ <b>AFECTACIÓN:</b> " + ", ".join(detectadas)
    return ""

def obtener_tweets_robusto():
    """
    Intenta obtener tweets rotando estrategias de Nitter para evitar bloqueos.
    """
    tweets_encontrados = []
    
    # Lista de instancias de respaldo por si la automática falla
    instancias_backup = [
        None, # Primero intentar automático
        "nitter.net",
        "nitter.cz",
        "nitter.privacydev.net"
    ]

    for instancia in instancias_backup:
        try:
            print(f"🦅 Intentando conectar a Nitter ({instancia or 'Auto'})...")
            # skip_instance_check=False obliga a buscar una instancia viva
            scraper = Nitter(log_level=1, skip_instance_check=False, instance=instancia)
            data = scraper.get_tweets("MetroCDMX", mode='user', number=8)
            
            if data and 'tweets' in data and len(data['tweets']) > 0:
                return data['tweets'] # Éxito, retornamos los tweets
            
        except Exception as e:
            print(f"⚠️ Falló instancia {instancia}: {e}")
            time.sleep(2) # Esperar antes de probar la siguiente
            
    return [] # Si todo falla, retornamos lista vacía

def revisar_incidentes(ahora):
    incidentes = []
    
    # --- 1. GOOGLE NEWS ---
    try:
        feed = feedparser.parse(RSS_URL)
        limite = ahora - timedelta(minutes=65)
        for e in feed.entries:
            if hasattr(e, 'published_parsed'):
                f = datetime(*e.published_parsed[:6], tzinfo=pytz.utc).astimezone(ahora.tzinfo)
                if f > limite:
                    t = e.title.lower()
                    if any(p in t for p in PALABRAS_CLAVE):
                        tag_linea = detectar_lineas(t)
                        incidentes.append(f"📰 <b>NOTICIA:</b> {e.title}{tag_linea}\n🔗 <a href='{e.link}'>Ver Nota</a>")
    except Exception as e: print(f"Error RSS: {e}")

    # --- 2. TWITTER (Nitter Rotativo) ---
    tweets = obtener_tweets_robusto()
    for t in tweets:
        try:
            txt = t['text'].lower()
            if any(p in txt for p in PALABRAS_CLAVE) and not any(i in txt for i in IGNORAR):
                # Filtro de tiempo: "m" (minutos) o "1h" (hace una hora)
                if "m" in t['date'] or "1h" in t['date']:
                    tag_linea = detectar_lineas(txt)
                    incidentes.append(f"🚨 <b>AVISO OFICIAL:</b> {t['text']}{tag_linea}\n🔗 <a href='{t['link']}'>Ver Tweet</a>")
        except: continue

    return incidentes

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
        return "💤 <b>CIERRE DE SERVICIO</b>\n──────────────────\nLa red ha concluido sus operaciones por hoy."
    return None

def main():
    tz_mx = pytz.timezone('America/Mexico_City')
    ahora = datetime.now(tz_mx)
    print(f"🏁 JJMex Scan iniciado: {ahora}")

    # 1. Turno
    msg_turno = verificar_horario_servicio(ahora)
    if msg_turno:
        enviar_telegram(msg_turno)
        return

    # 2. Incidentes
    reportes = revisar_incidentes(ahora)
    
    if reportes:
        # Eliminar duplicados exactos
        reportes_unicos = list(dict.fromkeys(reportes))
        hora_str = ahora.strftime('%I:%M %p')
        header = f"🚨 <b>INCIDENCIAS DETECTADAS ({hora_str})</b>\n──────────────────\n"
        enviar_telegram(header + "\n\n".join(reportes_unicos))
    else:
        print("✅ Todo normal.")
        # Opcional: Descomentar si quieres mensaje de "Todo Bien" cada hora
        # enviar_telegram("✅ <b>Estado del Metro:</b> Sin reportes graves en la última hora.")

if __name__ == "__main__":
    main()
